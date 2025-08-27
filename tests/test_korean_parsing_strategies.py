"""
Unit tests for Korean content parsing strategies and enhanced error handling.

This test module validates all the implemented fixes for LLM response parsing failures,
specifically testing with Korean grading content and error recovery scenarios.
"""

import pytest
import json
from typing import Dict, Any, List
from unittest.mock import Mock, patch

# Import core modules
from core.enhanced_response_parser import EnhancedResponseParser
from core.parsing_models import ParsingConfig, SuccessLevel, ParsingStrategy
from core.validation_engine import ValidationEngine
from core.dynamic_models import DynamicModelFactory, get_default_parser


class TestKoreanContentParsing:
    """Test parsing strategies with Korean grading content."""
    
    def setup_method(self):
        """Setup test environment with Korean rubric."""
        self.config = ParsingConfig(
            max_attempts=4,
            enable_fallback_recovery=True,
            enable_partial_recovery=True,
            allow_field_mapping=True,
            allow_type_coercion=True,
            log_all_attempts=True
        )
        self.parser_instance = EnhancedResponseParser(self.config)
        
        # Create Korean rubric for testing
        self.korean_rubric = [
            {
                'main_criterion': '지리적 위치 표기',
                'sub_criteria': [
                    {'score': 20, 'content': '주요 도시 정확히 표기'},
                    {'score': 15, 'content': '지역 경계 표기'}
                ]
            },
            {
                'main_criterion': '교통 네트워크',
                'sub_criteria': [
                    {'score': 25, 'content': '주요 교통로 표기'},
                    {'score': 20, 'content': '교통 연결점 표기'}
                ]
            }
        ]
        
        self.pydantic_parser = DynamicModelFactory.create_parser(self.korean_rubric)
    
    def test_perfect_korean_json_parsing(self):
        """Test parsing perfect Korean JSON response."""
        response = """{
            "채점결과": {
                "주요_채점_요소_1_점수": 35,
                "세부_채점_요소_1_1_점수": 20,
                "세부_채점_요소_1_2_점수": 15,
                "주요_채점_요소_2_점수": 45,
                "세부_채점_요소_2_1_점수": 25,
                "세부_채점_요소_2_2_점수": 20,
                "합산_점수": 80,
                "점수_판단_근거": {
                    "주요_채점_요소_1": "지리적 위치가 정확하게 표기됨",
                    "주요_채점_요소_2": "교통 네트워크가 잘 표현됨"
                }
            },
            "피드백": {
                "교과_내용_피드백": "지도에 주요 요소들이 잘 표기되어 있습니다. 특히 도시 위치와 교통로가 정확합니다.",
                "의사_응답_여부": false,
                "의사_응답_설명": ""
            }
        }"""
        
        result = self.parser_instance.parse_response_with_rubric(response, self.pydantic_parser, self.korean_rubric)
        
        assert result.success_level == SuccessLevel.FULL
        assert result.data is not None
        assert result.data["채점결과"]["합산_점수"] == 80
        assert "지도에 주요 요소들이 잘 표기되어 있습니다" in result.data["피드백"]["교과_내용_피드백"]
        assert len(result.errors) == 0
    
    def test_korean_json_with_artifacts(self):
        """Test parsing Korean JSON wrapped in LLM artifacts."""
        response = """다음은 학생 답안에 대한 채점 결과입니다:

```json
{
    "채점결과": {
        "주요_채점_요소_1_점수": 30,
        "합산_점수": 70,
        "점수_판단_근거": {
            "주요_채점_요소_1": "기본적인 위치 표기는 되어있음"
        }
    },
    "피드백": {
        "교과_내용_피드백": "기본적인 내용은 잘 표기되었으나 세부사항이 부족합니다.",
        "의사_응답_여부": false,
        "의사_응답_설명": ""
    }
}
```

이상으로 채점을 마칩니다."""
        
        result = self.parser_instance.parse_response_with_rubric(response, self.pydantic_parser, self.korean_rubric)
        
        assert result.success_level == SuccessLevel.FULL
        assert result.data is not None
        assert result.data["채점결과"]["합산_점수"] == 70
        assert "기본적인 내용은 잘 표기되었으나" in result.data["피드백"]["교과_내용_피드백"]
    
    def test_malformed_korean_json_with_recovery(self):
        """Test recovery of malformed Korean JSON."""
        response = """{
            "채점결과": {
                "주요_채점_요소_1_점수": "25",  // String instead of int
                "합산_점수": 60,
                "점수_판단_근거": {
                    "주요_채점_요소_1": "양호한 수준"
                },
            },  // Trailing comma
            "피드백": {
                "교과_내용_피드백": "전반적으로 양호합니다",
                "의사_응답_여부": "false",  // String instead of boolean
                // Missing 의사_응답_설명
            }
        }"""
        
        result = self.parser_instance.parse_response_with_rubric(response, self.pydantic_parser, self.korean_rubric)
        
        # Should succeed with corrections or partial recovery
        assert result.success_level in [SuccessLevel.FULL, SuccessLevel.PARTIAL]
        if result.success_level == SuccessLevel.FULL:
            assert result.data["채점결과"]["주요_채점_요소_1_점수"] == 25  # Converted to int
            assert result.data["피드백"]["의사_응답_여부"] == False  # Converted to boolean
        assert len(result.warnings) > 0  # Should have conversion warnings
    
    def test_mixed_language_content(self):
        """Test parsing response with mixed Korean/English content."""
        response = """{
            "채점결과": {
                "main_score": 50,  // English field name
                "합산_점수": 50,
                "점수_판단_근거": {
                    "note": "Basic completion achieved"
                }
            },
            "피드백": {
                "교과_내용_피드백": "The map shows basic understanding of geographical concepts.",
                "의사_응답_여부": false,
                "의사_응답_설명": ""
            }
        }"""
        
        result = self.parser_instance.parse_response_with_rubric(response, self.pydantic_parser, self.korean_rubric)
        
        # Should handle field mapping or partial recovery
        assert result.success_level in [SuccessLevel.FULL, SuccessLevel.PARTIAL]
        assert result.data is not None or result.partial_content is not None


class TestEmergencyFallbackScenarios:
    """Test emergency fallback mechanisms with various failure scenarios."""
    
    def setup_method(self):
        """Setup test environment for emergency scenarios."""
        self.config = ParsingConfig(
            max_attempts=4,
            enable_fallback_recovery=True,
            enable_partial_recovery=True,
            log_all_attempts=True
        )
        self.parser_instance = EnhancedResponseParser(self.config)
        self.pydantic_parser = get_default_parser()
    
    def test_complete_nonsense_response(self):
        """Test emergency fallback with complete nonsense response."""
        response = "This is completely unrelated text with no JSON or Korean content whatsoever."
        
        result = self.parser_instance.parse_response(response, self.pydantic_parser)
        
        # Should activate emergency fallback
        assert result.success_level == SuccessLevel.PARTIAL  # Emergency recovery provides partial data
        assert result.partial_content is not None
        assert "교과_내용_피드백" in result.partial_content["피드백"]
        assert "emergency" in str(result.recovery_notes).lower() or "manual" in str(result.warnings).lower()
    
    def test_response_with_extractable_score(self):
        """Test emergency fallback that can extract score from text."""
        response = "학생의 점수는 75점입니다. 전반적으로 잘 작성된 답안이라고 생각합니다."
        
        result = self.parser_instance.parse_response(response, self.pydantic_parser)
        
        assert result.success_level == SuccessLevel.PARTIAL
        assert result.partial_content is not None
        # Emergency recovery should extract the score
        assert result.partial_content["채점결과"]["주요_채점_요소_1_점수"] == 75
        assert result.partial_content["채점결과"]["합산_점수"] == 75
    
    def test_response_with_extractable_feedback(self):
        """Test emergency fallback that can extract feedback from text."""
        response = "피드백: 답안이 매우 우수하며 모든 요구사항을 충족합니다. 점수는 95점입니다."
        
        result = self.parser_instance.parse_response(response, self.pydantic_parser)
        
        assert result.success_level == SuccessLevel.PARTIAL
        assert result.partial_content is not None
        # Should extract both score and feedback
        assert result.partial_content["채점결과"]["합산_점수"] == 95
        assert "답안이 매우 우수하며" in result.partial_content["피드백"]["교과_내용_피드백"]
    
    def test_empty_response(self):
        """Test handling of empty response."""
        response = ""
        
        result = self.parser_instance.parse_response(response, self.pydantic_parser)
        
        assert result.success_level == SuccessLevel.PARTIAL  # Emergency fallback
        assert result.partial_content is not None
        assert result.partial_content["채점결과"]["합산_점수"] == 0


class TestAdaptiveValidation:
    """Test adaptive validation with rubric-based schema creation."""
    
    def setup_method(self):
        """Setup test environment for adaptive validation."""
        self.config = ParsingConfig(log_all_attempts=True)
        self.validation_engine = ValidationEngine(self.config)
        
        self.complex_rubric = [
            {
                'main_criterion': '내용 정확성',
                'sub_criteria': [
                    {'score': 30, 'content': '사실 정확성'},
                    {'score': 20, 'content': '논리적 구성'}
                ]
            },
            {
                'main_criterion': '표현 능력',
                'sub_criteria': [
                    {'score': 25, 'content': '문법 정확성'},
                    {'score': 25, 'content': '어휘 사용'}
                ]
            }
        ]
    
    def test_adaptive_schema_creation(self):
        """Test creation of adaptive schema from rubric."""
        schema = self.validation_engine._create_adaptive_schema(self.complex_rubric)
        
        assert schema["type"] == "object"
        assert "채점결과" in schema["properties"]
        assert "피드백" in schema["properties"]
        
        # Check scoring fields are created properly
        scoring_props = schema["properties"]["채점결과"]["properties"]
        assert "주요_채점_요소_1_점수" in scoring_props
        assert "주요_채점_요소_2_점수" in scoring_props
        assert "세부_채점_요소_1_1_점수" in scoring_props
        assert "세부_채점_요소_2_2_점수" in scoring_props
        assert "합산_점수" in scoring_props
        assert "점수_판단_근거" in scoring_props
    
    def test_adaptive_validation_success(self):
        """Test successful adaptive validation."""
        json_data = {
            "채점결과": {
                "주요_채점_요소_1_점수": 45,
                "세부_채점_요소_1_1_점수": 25,
                "합산_점수": 90,
                "점수_판단_근거": {"주요_채점_요소_1": "우수함"}
            },
            "피드백": {
                "교과_내용_피드백": "매우 좋은 답안입니다",
                "의사_응답_여부": False,
                "의사_응답_설명": ""
            }
        }
        
        result = self.validation_engine.validate_with_adaptive_schema(json_data, self.complex_rubric)
        
        assert result.is_valid == True
        assert len(result.errors) == 0
        assert result.corrected_data == json_data
    
    def test_adaptive_validation_with_missing_fields(self):
        """Test adaptive validation with missing required fields."""
        json_data = {
            "채점결과": {
                "주요_채점_요소_1_점수": 40
                # Missing 합산_점수 and other fields
            }
            # Missing 피드백 entirely
        }
        
        result = self.validation_engine.validate_with_adaptive_schema(json_data, self.complex_rubric)
        
        assert result.is_valid == True  # Should be corrected
        assert len(result.warnings) > 0  # Should have warnings about additions
        assert "피드백" in result.corrected_data
        assert "합산_점수" in result.corrected_data["채점결과"]


class TestResponsePreprocessing:
    """Test response preprocessing and cleaning functionality."""
    
    def setup_method(self):
        """Setup test environment for preprocessing tests."""
        self.config = ParsingConfig(log_all_attempts=True)
        self.parser_instance = EnhancedResponseParser(self.config)
    
    def test_remove_leading_artifacts(self):
        """Test removal of leading LLM artifacts."""
        response = """다음은 채점 결과입니다:

{"채점결과": {"합산_점수": 80}, "피드백": {"교과_내용_피드백": "좋음", "의사_응답_여부": false}}"""
        
        cleaned = self.parser_instance._preprocess_response(response)
        
        assert cleaned.startswith('{"채점결과"')
        assert "다음은 채점 결과입니다" not in cleaned
    
    def test_remove_code_block_markers(self):
        """Test removal of code block markers."""
        response = """```json
{"채점결과": {"합산_점수": 85}, "피드백": {"교과_내용_피드백": "우수", "의사_응답_여부": false}}
```"""
        
        cleaned = self.parser_instance._preprocess_response(response)
        
        assert "```json" not in cleaned
        assert "```" not in cleaned
        assert cleaned.startswith('{"채점결과"')
    
    def test_fix_trailing_commas(self):
        """Test fixing of trailing commas in JSON."""
        response = """{
            "채점결과": {
                "합산_점수": 75,
            },
            "피드백": {
                "교과_내용_피드백": "양호",
                "의사_응답_여부": false,
            },
        }"""
        
        cleaned = self.parser_instance._preprocess_response(response)
        
        # Should not have trailing commas
        assert ",}" not in cleaned
        assert ",]" not in cleaned
    
    def test_normalize_whitespace(self):
        """Test normalization of excessive whitespace."""
        response = """{
            "채점결과":    {
                "합산_점수":     90
            },


            "피드백": {
                "교과_내용_피드백":   "우수함"   ,
                "의사_응답_여부":false
            }
        }"""
        
        cleaned = self.parser_instance._preprocess_response(response)
        
        # Should have normalized whitespace
        assert "    " not in cleaned  # No excessive spaces
        assert "\n\n\n" not in cleaned  # No excessive newlines


class TestErrorLoggingEnhancements:
    """Test enhanced error logging functionality."""
    
    def setup_method(self):
        """Setup test environment for logging tests."""
        self.config = ParsingConfig(log_all_attempts=True)
        self.parser_instance = EnhancedResponseParser(self.config)
        self.pydantic_parser = get_default_parser()
    
    def test_response_format_analysis(self):
        """Test response format analysis for debugging."""
        response = "This is a mixed content response with 한글 text and {some: 'json'} and ```code blocks```"
        
        analysis = self.parser_instance._analyze_response_format(response)
        
        assert analysis["contains_korean"] == True
        assert analysis["contains_json_brackets"] == True
        assert analysis["contains_code_blocks"] == True
        assert analysis["char_count"] == len(response)
        assert analysis["line_count"] >= 1
    
    @patch('core.enhanced_response_parser.logger')
    def test_detailed_failure_logging(self, mock_logger):
        """Test that detailed failure information is logged."""
        response = "This will definitely fail to parse as JSON"
        
        result = self.parser_instance.parse_response(response, self.pydantic_parser)
        
        assert result.success_level == SuccessLevel.PARTIAL  # Emergency fallback
        
        # Verify that detailed logging was called
        mock_logger.error.assert_called()
        
        # Check that strategy-specific errors were logged
        error_calls = [call.args[0] for call in mock_logger.error.call_args_list]
        assert any("Strategy" in call and "failed" in call for call in error_calls)
        assert any("Raw response sample" in call for call in error_calls)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])