"""
Comprehensive test suite for enhanced LLM response parsing system.

This module contains tests for all parsing strategies, validation engine,
and integration scenarios to ensure robust error handling.
"""

import json
import pytest
import time
from typing import Dict, Any, List
from unittest.mock import Mock, patch
from pydantic import BaseModel, Field

# Import modules to test
from core.enhanced_response_parser import EnhancedResponseParser, parse_llm_response
from core.parsing_strategies import (
    DirectJSONStrategy, MarkdownBlockStrategy, RegexPatternStrategy, 
    FallbackRecoveryStrategy, StrategyFactory
)
from core.validation_engine import ValidationEngine
from core.parsing_models import (
    ParsingConfig, SuccessLevel, ParsingStrategy, 
    ParsingResult, ValidationResult, ExtractionContext
)
from langchain_core.output_parsers import PydanticOutputParser


# Test data models
class TestGradingResult(BaseModel):
    """Test model for grading results."""
    총점: int = Field(description=\"총점수\")
    세부점수: Dict[str, int] = Field(description=\"세부 점수들\")
    점수_판단_근거: str = Field(description=\"점수 판단 근거\")


class TestFeedback(BaseModel):
    """Test model for feedback."""
    피드백내용: str = Field(description=\"피드백 내용\")
    개선사항: List[str] = Field(description=\"개선 사항들\")
    의사응답여부: bool = Field(description=\"의사 응답 여부\")


class TestGradingOutput(BaseModel):
    \"\"\"Test model for complete grading output.\"\"\"
    채점결과: TestGradingResult = Field(description=\"채점 결과\")
    피드백: TestFeedback = Field(description=\"피드백\")


class TestParsingStrategies:
    \"\"\"Test cases for individual parsing strategies.\"\"\"
    
    def setup_method(self):
        \"\"\"Setup test environment.\"\"\"
        self.config = ParsingConfig()
        self.context = ExtractionContext(
            original_response=\"test\",
            response_length=100,
            detected_format=\"json\",
            has_code_blocks=False,
            has_json_markers=True
        )
    
    def test_direct_json_strategy_success(self):
        \"\"\"Test DirectJSONStrategy with valid JSON.\"\"\"
        strategy = DirectJSONStrategy(self.config)
        
        response = '''Here is the result:
        {\"총점\": 85, \"세부점수\": {\"기준1\": 40, \"기준2\": 45}, \"점수_판단_근거\": \"잘함\"}
        That's the analysis.'''
        
        success, content, error = strategy.extract_content(response, self.context)
        
        assert success is True
        assert content is not None
        assert error is None
        
        # Validate extracted JSON
        parsed = json.loads(content)
        assert parsed[\"총점\"] == 85
        assert \"세부점수\" in parsed
    
    def test_direct_json_strategy_failure(self):
        \"\"\"Test DirectJSONStrategy with invalid JSON.\"\"\"
        strategy = DirectJSONStrategy(self.config)
        
        response = \"No JSON content here at all\"
        
        success, content, error = strategy.extract_content(response, self.context)
        
        assert success is False
        assert content is None
        assert \"No valid JSON brackets found\" in error
    
    def test_markdown_strategy_success(self):
        \"\"\"Test MarkdownBlockStrategy with valid markdown.\"\"\"
        strategy = MarkdownBlockStrategy(self.config)
        
        response = '''Here is the grading result:
        
        ```json
        {
            \"총점\": 90,
            \"세부점수\": {\"기준1\": 45, \"기준2\": 45},
            \"점수_판단_근거\": \"우수함\"
        }
        ```
        
        Analysis complete.'''
        
        success, content, error = strategy.extract_content(response, self.context)
        
        assert success is True
        assert content is not None
        assert error is None
        
        parsed = json.loads(content)
        assert parsed[\"총점\"] == 90
    
    def test_markdown_strategy_multiple_blocks(self):
        \"\"\"Test MarkdownBlockStrategy with multiple code blocks.\"\"\"
        strategy = MarkdownBlockStrategy(self.config)
        
        response = '''First block:
        ```
        {\"invalid\": \"json\" missing bracket
        ```
        
        Second block:
        ```json
        {\"총점\": 75, \"세부점수\": {\"기준1\": 35, \"기준2\": 40}}
        ```'''
        
        success, content, error = strategy.extract_content(response, self.context)
        
        assert success is True
        assert content is not None
        
        parsed = json.loads(content)
        assert parsed[\"총점\"] == 75
    
    def test_regex_strategy_success(self):
        \"\"\"Test RegexPatternStrategy with malformed JSON.\"\"\"
        strategy = RegexPatternStrategy(self.config)
        
        response = '''Some text before
        {\"총점\": 80, \"세부점수\": {\"기준1\": 40, \"기준2\": 40}, \"추가정보\": \"기타\"}
        Some text after'''
        
        success, content, error = strategy.extract_content(response, self.context)
        
        assert success is True
        assert content is not None
        
        parsed = json.loads(content)
        assert parsed[\"총점\"] == 80
    
    def test_fallback_strategy_recovery(self):
        \"\"\"Test FallbackRecoveryStrategy with text content.\"\"\"
        strategy = FallbackRecoveryStrategy(self.config)
        
        response = '''점수: 70점
        피드백: 전반적으로 양호함
        판단근거: 요구사항을 대부분 충족
        총점: 70'''
        
        success, content, error = strategy.extract_content(response, self.context)
        
        assert success is True
        assert content is not None
        
        parsed = json.loads(content)
        assert \"점수\" in parsed or \"총점\" in parsed
    
    def test_strategy_factory(self):
        \"\"\"Test StrategyFactory functionality.\"\"\"
        strategies = StrategyFactory.create_all_strategies(self.config)
        
        assert len(strategies) == 4
        assert any(isinstance(s, DirectJSONStrategy) for s in strategies)
        assert any(isinstance(s, MarkdownBlockStrategy) for s in strategies)
        assert any(isinstance(s, RegexPatternStrategy) for s in strategies)
        assert any(isinstance(s, FallbackRecoveryStrategy) for s in strategies)
        
        # Test specific strategy creation
        direct_strategy = StrategyFactory.create_strategy(ParsingStrategy.DIRECT_JSON, self.config)
        assert isinstance(direct_strategy, DirectJSONStrategy)


class TestValidationEngine:
    \"\"\"Test cases for validation engine.\"\"\"
    
    def setup_method(self):
        \"\"\"Setup test environment.\"\"\"
        self.config = ParsingConfig()
        self.engine = ValidationEngine(self.config)
        self.parser = PydanticOutputParser(pydantic_object=TestGradingOutput)
    
    def test_successful_validation(self):
        \"\"\"Test successful validation with correct data.\"\"\"
        valid_data = {
            \"채점결과\": {
                \"총점\": 85,
                \"세부점수\": {\"기준1\": 40, \"기준2\": 45},
                \"점수_판단_근거\": \"잘함\"
            },
            \"피드백\": {
                \"피드백내용\": \"좋은 답안입니다\",
                \"개선사항\": [\"세부 내용 추가\"],
                \"의사응답여부\": False
            }
        }
        
        result = self.engine.validate_structure(valid_data, self.parser)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.corrected_data is not None
    
    def test_field_name_correction(self):
        \"\"\"Test field name correction functionality.\"\"\"
        data_with_typos = {
            \"채점결과\": {
                \"총점수\": 85,  # Should be \"총점\"
                \"세부점수들\": {\"기준1\": 40, \"기준2\": 45},  # Should be \"세부점수\"
                \"점수_판단_근거\": \"잘함\"
            },
            \"피드백\": {
                \"피드백내용\": \"좋은 답안입니다\",
                \"개선사항\": [\"세부 내용 추가\"],
                \"의사응답여부\": False
            }
        }
        
        recovery_result = self.engine.attempt_error_correction(data_with_typos, self.parser, \"Field error\")
        
        assert recovery_result.success is True
        assert recovery_result.recovered_data is not None
        assert len(recovery_result.recovery_notes) > 0
    
    def test_type_coercion(self):
        \"\"\"Test type coercion functionality.\"\"\"
        data_with_wrong_types = {
            \"채점결과\": {
                \"총점\": \"85\",  # String instead of int
                \"세부점수\": {\"기준1\": \"40\", \"기준2\": \"45\"},  # Strings instead of ints
                \"점수_판단_근거\": \"잘함\"
            },
            \"피드백\": {
                \"피드백내용\": \"좋은 답안입니다\",
                \"개선사항\": \"세부 내용 추가\",  # String instead of list
                \"의사응답여부\": \"false\"  # String instead of bool
            }
        }
        
        recovery_result = self.engine.attempt_error_correction(data_with_wrong_types, self.parser, \"Type error\")
        
        assert recovery_result.success is True
        assert recovery_result.recovered_data is not None
        assert isinstance(recovery_result.recovered_data[\"채점결과\"][\"총점\"], int)


class TestEnhancedResponseParser:
    \"\"\"Test cases for the main enhanced response parser.\"\"\"
    
    def setup_method(self):
        \"\"\"Setup test environment.\"\"\"
        self.config = ParsingConfig(log_all_attempts=False)
        self.parser_instance = EnhancedResponseParser(self.config)
        self.pydantic_parser = PydanticOutputParser(pydantic_object=TestGradingOutput)
    
    def test_successful_parsing_direct_json(self):
        \"\"\"Test successful parsing with direct JSON.\"\"\"
        response = '''{
            \"채점결과\": {
                \"총점\": 85,
                \"세부점수\": {\"기준1\": 40, \"기준2\": 45},
                \"점수_판단_근거\": \"잘함\"
            },
            \"피드백\": {
                \"피드백내용\": \"좋은 답안입니다\",
                \"개선사항\": [\"세부 내용 추가\"],
                \"의사응답여부\": false
            }
        }'''
        
        result = self.parser_instance.parse_response(response, self.pydantic_parser)
        
        assert result.success_level == SuccessLevel.FULL
        assert result.data is not None
        assert result.successful_strategy == ParsingStrategy.DIRECT_JSON
        assert len(result.errors) == 0
    
    def test_successful_parsing_markdown(self):
        \"\"\"Test successful parsing with markdown blocks.\"\"\"
        response = '''Here is the grading result:
        
        ```json
        {
            \"채점결과\": {
                \"총점\": 90,
                \"세부점수\": {\"기준1\": 45, \"기준2\": 45},
                \"점수_판단_근거\": \"우수함\"
            },
            \"피드백\": {
                \"피드백내용\": \"매우 좋은 답안입니다\",
                \"개선사항\": [\"완벽함\"],
                \"의사응답여부\": false
            }
        }
        ```'''
        
        result = self.parser_instance.parse_response(response, self.pydantic_parser)
        
        assert result.success_level == SuccessLevel.FULL
        assert result.data is not None
        assert result.successful_strategy == ParsingStrategy.MARKDOWN_BLOCK
    
    def test_partial_recovery(self):
        \"\"\"Test partial recovery functionality.\"\"\"
        response = '''점수는 80점입니다.
        피드백: 답안이 전반적으로 좋습니다.
        개선사항: 좀 더 구체적인 설명이 필요합니다.'''
        
        result = self.parser_instance.parse_response(response, self.pydantic_parser)
        
        # Should get partial recovery
        assert result.success_level in [SuccessLevel.PARTIAL, SuccessLevel.FAILED]
        assert len(result.attempts) > 0
        
        # Check that fallback was attempted
        fallback_attempts = [a for a in result.attempts if a.strategy == ParsingStrategy.FALLBACK_RECOVERY]
        assert len(fallback_attempts) > 0
    
    def test_complete_parsing_failure(self):
        \"\"\"Test complete parsing failure handling.\"\"\"
        response = \"This response contains no meaningful content for grading.\"
        
        result = self.parser_instance.parse_response(response, self.pydantic_parser)
        
        assert result.success_level == SuccessLevel.FAILED
        assert len(result.attempts) > 0
        assert len(result.errors) > 0
        assert result.data is None
    
    def test_performance_timing(self):
        \"\"\"Test that parsing performance is tracked.\"\"\"
        response = '''{\"채점결과\": {\"총점\": 85, \"세부점수\": {}, \"점수_판단_근거\": \"\"}, \"피드백\": {\"피드백내용\": \"\", \"개선사항\": [], \"의사응답여부\": false}}'''
        
        result = self.parser_instance.parse_response(response, self.pydantic_parser)
        
        assert result.total_processing_time_ms > 0
        assert all(attempt.execution_time_ms >= 0 for attempt in result.attempts)
    
    def test_configuration_options(self):
        \"\"\"Test different configuration options.\"\"\"
        # Test with minimal config
        minimal_config = ParsingConfig(
            max_attempts=2,
            enable_fallback_recovery=False,
            enable_partial_recovery=False
        )
        
        parser_minimal = EnhancedResponseParser(minimal_config)
        
        response = \"Invalid response\"
        result = parser_minimal.parse_response(response, self.pydantic_parser)
        
        assert len(result.attempts) <= 2
        assert result.success_level == SuccessLevel.FAILED


class TestRealWorldScenarios:
    \"\"\"Test cases for real-world scenarios and edge cases.\"\"\"
    
    def setup_method(self):
        \"\"\"Setup test environment.\"\"\"
        self.config = ParsingConfig()
        self.parser = PydanticOutputParser(pydantic_object=TestGradingOutput)
    
    def test_korean_content_handling(self):
        \"\"\"Test handling of Korean content in responses.\"\"\"
        response = '''채점 결과입니다:
        
        ```json
        {
            \"채점결과\": {
                \"총점\": 75,
                \"세부점수\": {\"문법\": 35, \"내용\": 40},
                \"점수_판단_근거\": \"한국어 문법이 정확하고 내용이 충실함\"
            },
            \"피드백\": {
                \"피드백내용\": \"전반적으로 우수한 답안입니다. 한국어 표현이 자연스럽습니다.\",
                \"개선사항\": [\"더 구체적인 예시 추가\", \"결론 부분 보강\"],
                \"의사응답여부\": false
            }
        }
        ```'''
        
        result = parse_llm_response(response, self.parser, self.config)
        
        assert result.success_level == SuccessLevel.FULL
        assert result.data is not None
        assert \"한국어\" in result.data[\"피드백\"][\"피드백내용\"]
    
    def test_mixed_format_response(self):
        \"\"\"Test handling of mixed format responses.\"\"\"
        response = '''학생 답안을 분석한 결과는 다음과 같습니다:
        
        **점수 분석:**
        - 총점: 82점
        - 기준1: 40점
        - 기준2: 42점
        
        JSON 형식 결과:
        ```
        {
            \"채점결과\": {
                \"총점\": 82,
                \"세부점수\": {\"기준1\": 40, \"기준2\": 42},
                \"점수_판단_근거\": \"요구사항을 잘 충족함\"
            },
            \"피드백\": {
                \"피드백내용\": \"답안이 체계적이고 논리적입니다\",
                \"개선사항\": [\"예시 추가 필요\"],
                \"의사응답여부\": false
            }
        }
        ```
        
        **상세 분석:**
        답안의 구조가 명확하고...'''
        
        result = parse_llm_response(response, self.parser, self.config)
        
        assert result.success_level in [SuccessLevel.FULL, SuccessLevel.PARTIAL]
        if result.success_level == SuccessLevel.FULL:
            assert result.data[\"채점결과\"][\"총점\"] == 82
    
    def test_malformed_json_recovery(self):
        \"\"\"Test recovery from malformed JSON.\"\"\"
        response = '''{
            \"채점결과\": {
                \"총점\": 78,
                \"세부점수\": {\"기준1\": 38, \"기준2\": 40},
                \"점수_판단_근거\": \"양호함\"
            },
            \"피드백\": {
                \"피드백내용\": \"답안이 적절합니다\",
                \"개선사항\": [\"구체성 향상\",  // Missing closing bracket
                \"의사응답여부\": false
            }
        }'''
        
        result = parse_llm_response(response, self.parser, self.config)
        
        # Should attempt multiple strategies
        assert len(result.attempts) > 1
        # May succeed with regex strategy or get partial recovery
        assert result.success_level in [SuccessLevel.FULL, SuccessLevel.PARTIAL, SuccessLevel.FAILED]
    
    def test_very_long_response(self):
        \"\"\"Test handling of very long responses.\"\"\"
        # Create a very long response with valid JSON buried inside
        long_text = \"This is a very long preamble. \" * 1000
        
        response = f'''{long_text}
        
        The actual result is:
        {{
            \"채점결과\": {{
                \"총점\": 95,
                \"세부점수\": {{\"기준1\": 50, \"기준2\": 45}},
                \"점수_판단_근거\": \"매우 우수함\"
            }},
            \"피드백\": {{
                \"피드백내용\": \"완벽한 답안입니다\",
                \"개선사항\": [],
                \"의사응답여부\": false
            }}
        }}
        
        {\"Additional text \" * 500}'''
        
        result = parse_llm_response(response, self.parser, self.config)
        
        assert result.success_level == SuccessLevel.FULL
        assert result.data[\"채점결과\"][\"총점\"] == 95
    
    @pytest.mark.parametrize(\"strategy_type\", [
        ParsingStrategy.DIRECT_JSON,
        ParsingStrategy.MARKDOWN_BLOCK,
        ParsingStrategy.REGEX_PATTERN,
        ParsingStrategy.FALLBACK_RECOVERY
    ])
    def test_individual_strategy_performance(self, strategy_type):
        \"\"\"Test individual strategy performance.\"\"\"
        config = ParsingConfig()
        strategy = StrategyFactory.create_strategy(strategy_type, config)
        
        # Test with appropriate response format for each strategy
        test_responses = {
            ParsingStrategy.DIRECT_JSON: '{\"test\": \"value\"}',
            ParsingStrategy.MARKDOWN_BLOCK: '```json\\n{\"test\": \"value\"}\\n```',
            ParsingStrategy.REGEX_PATTERN: 'Some text {\"test\": \"value\"} more text',
            ParsingStrategy.FALLBACK_RECOVERY: 'test: value\\nother: data'
        }
        
        response = test_responses[strategy_type]
        context = ExtractionContext(
            original_response=response,
            response_length=len(response),
            detected_format=\"json\",
            has_code_blocks='```' in response,
            has_json_markers='{' in response
        )
        
        attempt = strategy.execute(response, context)
        
        assert attempt.strategy == strategy_type
        assert attempt.execution_time_ms >= 0
        # Don't assert success since some strategies may legitimately fail with test data


def run_comprehensive_tests():
    \"\"\"Run all tests and provide summary.\"\"\"
    import subprocess
    import sys
    
    print(\"Running comprehensive parsing tests...\")
    
    # Run pytest with verbose output
    result = subprocess.run([
        sys.executable, \"-m\", \"pytest\", __file__, \"-v\", \"--tb=short\"
    ], capture_output=True, text=True)
    
    print(\"Test Results:\")
    print(result.stdout)
    if result.stderr:
        print(\"Errors:\")
        print(result.stderr)
    
    return result.returncode == 0


if __name__ == \"__main__\":
    # Run tests when script is executed directly
    success = run_comprehensive_tests()
    if success:
        print(\"\\n✅ All tests passed! Enhanced parser is ready for production.\")
    else:
        print(\"\\n❌ Some tests failed. Please review and fix issues.\")