"""
Integration tests for end-to-end parsing pipeline.

This test module validates the complete parsing pipeline with real-world
scenarios, including grading pipeline integration and performance validation.
"""

import pytest
import time
import json
from typing import Dict, Any, List
from unittest.mock import Mock, patch, MagicMock

# Import core modules
from core.enhanced_response_parser import EnhancedResponseParser
from core.grading_pipeline import GradingPipeline
from core.parsing_models import ParsingConfig, SuccessLevel
from core.dynamic_models import DynamicModelFactory
from models.llm_manager import LLMManager


class TestEndToEndParsingPipeline:
    """Integration tests for complete parsing pipeline."""
    
    def setup_method(self):
        """Setup test environment with mocked dependencies."""
        # Create test rubric
        self.test_rubric = [
            {
                'main_criterion': '지리적 정확성',
                'sub_criteria': [
                    {'score': 30, 'content': '위치 정확성'},
                    {'score': 20, 'content': '명칭 정확성'}
                ]
            },
            {
                'main_criterion': '표현 완성도',
                'sub_criteria': [
                    {'score': 25, 'content': '표기 명확성'},
                    {'score': 25, 'content': '전체 완성도'}
                ]
            }
        ]
        
        # Create parser from rubric
        self.parser = DynamicModelFactory.create_parser(self.test_rubric)
        
        # Mock LLM manager
        self.mock_llm_manager = Mock(spec=LLMManager)
        self.mock_llm = Mock()
        self.mock_llm_manager.get_llm.return_value = self.mock_llm
        
        # Mock retriever
        self.mock_retriever = Mock()
        
        # Create grading pipeline
        self.grading_pipeline = GradingPipeline(
            llm_manager=self.mock_llm_manager,
            retriever=self.mock_retriever,
            parsing_config=ParsingConfig(
                max_attempts=4,
                enable_fallback_recovery=True,
                enable_partial_recovery=True,
                log_all_attempts=True
            )
        )
    
    @patch('utils.retrieval.retrieve_documents')
    @patch('utils.retrieval.rerank_documents')
    @patch('prompts.prompt_templates.get_grading_prompt')
    def test_successful_end_to_end_parsing(self, mock_get_prompt, mock_rerank, mock_retrieve):
        """Test successful end-to-end parsing with perfect LLM response."""
        # Setup mocks
        mock_doc = Mock()
        mock_doc.page_content = "Sample document content"
        mock_doc.metadata = {"source": "test.pdf", "page": 1}
        
        mock_retrieve.return_value = [mock_doc]
        mock_rerank.return_value = [mock_doc]
        mock_get_prompt.return_value = "Test grading prompt"
        
        # Perfect LLM response
        perfect_response = """{
            "채점결과": {
                "주요_채점_요소_1_점수": 45,
                "세부_채점_요소_1_1_점수": 25,
                "세부_채점_요소_1_2_점수": 20,
                "주요_채점_요소_2_점수": 50,
                "세부_채점_요소_2_1_점수": 25,
                "세부_채점_요소_2_2_점수": 25,
                "합산_점수": 95,
                "점수_판단_근거": {
                    "주요_채점_요소_1": "위치와 명칭이 모두 정확함",
                    "주요_채점_요소_2": "표기가 명확하고 완성도가 높음"
                }
            },
            "피드백": {
                "교과_내용_피드백": "지도 표기가 매우 정확하고 완성도가 높습니다. 모든 요구사항을 충족하였습니다.",
                "의사_응답_여부": false,
                "의사_응답_설명": ""
            }
        }"""
        
        self.mock_llm_manager.call_llm_with_retry.return_value = perfect_response
        
        # Process student answer
        result = self.grading_pipeline.process_student_answer(
            student_name="김철수",
            student_answer="한국의 주요 도시들을 표기한 지도입니다.",
            rubric=self.test_rubric,
            question_type="지도 표기",
            parser=self.parser
        )
        
        # Verify successful processing
        assert "오류" not in result
        assert result["이름"] == "김철수"
        assert result["채점결과"]["합산_점수"] == 95
        assert "지도 표기가 매우 정확하고" in result["피드백"]["교과_내용_피드백"]
        assert "test.pdf" in result["참고문서"]
        assert "채점_소요_시간" in result
    
    @patch('utils.retrieval.retrieve_documents')
    @patch('utils.retrieval.rerank_documents')
    @patch('prompts.prompt_templates.get_grading_prompt')
    def test_end_to_end_with_malformed_response(self, mock_get_prompt, mock_rerank, mock_retrieve):
        """Test end-to-end processing with malformed LLM response that requires fixing."""
        # Setup mocks
        mock_doc = Mock()
        mock_doc.page_content = "Reference content"
        mock_doc.metadata = {"source": "reference.pdf", "page": 2}
        
        mock_retrieve.return_value = [mock_doc]
        mock_rerank.return_value = [mock_doc]
        mock_get_prompt.return_value = "Grading prompt"
        
        # Malformed response that should be recoverable
        malformed_response = """Here is the grading result:
        
        ```json
        {
            "채점결과": {
                "주요_채점_요소_1_점수": "35",  // String instead of int
                "합산_점수": 75,
                "점수_판단_근거": {
                    "주요_채점_요소_1": "기본 요구사항 충족"
                },
            },  // Trailing comma
            "피드백": {
                "교과_내용_피드백": "기본적인 내용은 포함되어 있으나 세부사항 보완 필요",
                "의사_응답_여부": "false"  // String instead of boolean
                // Missing 의사_응답_설명
            }
        }
        ```
        
        End of grading."""
        
        self.mock_llm_manager.call_llm_with_retry.return_value = malformed_response
        
        # Process student answer
        result = self.grading_pipeline.process_student_answer(
            student_name="박영희",
            student_answer="지도에 주요 도시를 표기했습니다.",
            rubric=self.test_rubric,
            question_type="지도 표기",
            parser=self.parser
        )
        
        # Should succeed with corrections
        assert result["이름"] == "박영희"
        assert result["채점결과"]["합산_점수"] == 75
        assert result["채점결과"]["주요_채점_요소_1_점수"] == 35  # Should be converted to int
        assert result["피드백"]["의사_응답_여부"] == False  # Should be converted to boolean
        
        # Should have parsing warnings
        if "파싱_경고" in result:
            assert len(result["파싱_경고"]) > 0
    
    @patch('utils.retrieval.retrieve_documents')
    @patch('utils.retrieval.rerank_documents')
    @patch('prompts.prompt_templates.get_grading_prompt')
    def test_end_to_end_with_complete_parsing_failure(self, mock_get_prompt, mock_rerank, mock_retrieve):
        """Test end-to-end processing when all parsing strategies fail."""
        # Setup mocks
        mock_doc = Mock()
        mock_doc.page_content = "Reference content"
        mock_doc.metadata = {"source": "doc.pdf", "page": 1}
        
        mock_retrieve.return_value = [mock_doc]
        mock_rerank.return_value = [mock_doc]
        mock_get_prompt.return_value = "Grading prompt"
        
        # Response that will trigger emergency fallback
        unparseable_response = "I cannot provide a proper grading result. The student's work is difficult to evaluate. Score might be around 60 points."
        
        self.mock_llm_manager.call_llm_with_retry.return_value = unparseable_response
        
        # Process student answer
        result = self.grading_pipeline.process_student_answer(
            student_name="이민수",
            student_answer="간단한 지도를 그렸습니다.",
            rubric=self.test_rubric,
            question_type="지도 표기",
            parser=self.parser
        )
        
        # Should use emergency fallback
        assert result["이름"] == "이민수"
        assert "오류" in result and "부분적 파싱 성공" in result["오류"]
        assert result["채점결과"]["합산_점수"] == 60  # Should extract score from text
        assert "시스템 오류로 인해" in result["피드백"]["교과_내용_피드백"]
        assert "원본_응답_샘플" in result
    
    @patch('utils.retrieval.retrieve_documents')
    @patch('utils.retrieval.rerank_documents')
    @patch('prompts.prompt_templates.get_grading_prompt')
    def test_end_to_end_with_llm_failure(self, mock_get_prompt, mock_rerank, mock_retrieve):
        """Test end-to-end processing when LLM call fails."""
        # Setup mocks
        mock_retrieve.return_value = []
        mock_rerank.return_value = []
        mock_get_prompt.return_value = "Grading prompt"
        
        # LLM returns None (failure)
        self.mock_llm_manager.call_llm_with_retry.return_value = None
        
        # Process student answer
        result = self.grading_pipeline.process_student_answer(
            student_name="최지은",
            student_answer="지도 작성했습니다.",
            rubric=self.test_rubric,
            question_type="지도 표기",
            parser=self.parser
        )
        
        # Should handle LLM failure gracefully
        assert result["이름"] == "최지은"
        assert "오류" in result
        assert "LLM 응답을 받지 못했습니다" in result["오류"]


class TestPerformanceAndReliability:
    """Test performance characteristics and reliability improvements."""
    
    def setup_method(self):
        """Setup performance testing environment."""
        self.config = ParsingConfig(
            max_attempts=4,
            enable_fallback_recovery=True,
            enable_partial_recovery=True,
            log_all_attempts=False  # Reduce logging for performance tests
        )
        self.parser_instance = EnhancedResponseParser(self.config)
        
        # Create test rubric and parser
        self.test_rubric = [
            {
                'main_criterion': '기본 요구사항',
                'sub_criteria': [
                    {'score': 50, 'content': '필수 내용 포함'}
                ]
            }
        ]
        self.pydantic_parser = DynamicModelFactory.create_parser(self.test_rubric)
    
    def test_parsing_performance_benchmark(self):
        """Test parsing performance with various response types."""
        test_cases = [
            # Perfect JSON
            '{"채점결과": {"합산_점수": 85}, "피드백": {"교과_내용_피드백": "좋음", "의사_응답_여부": false}}',
            
            # JSON with artifacts
            '''Here is the result:
            ```json
            {"채점결과": {"합산_점수": 75}, "피드백": {"교과_내용_피드백": "보통", "의사_응답_여부": false}}
            ```''',
            
            # Malformed JSON
            '{"채점결과": {"합산_점수": 65,}, "피드백": {"교과_내용_피드백": "수정필요", "의사_응답_여부": false,}}',
            
            # Text requiring emergency fallback
            'The score should be around 55 points. Good effort but needs improvement.'
        ]
        
        total_time = 0
        successful_parses = 0
        
        for i, response in enumerate(test_cases):
            start_time = time.time()
            
            result = self.parser_instance.parse_response_with_rubric(
                response, self.pydantic_parser, self.test_rubric
            )
            
            end_time = time.time()
            parse_time = (end_time - start_time) * 1000  # Convert to ms
            total_time += parse_time
            
            # Verify result is usable
            assert result.success_level in [SuccessLevel.FULL, SuccessLevel.PARTIAL]
            assert result.has_usable_data()
            
            if result.success_level == SuccessLevel.FULL:
                successful_parses += 1
            
            # Performance assertion - should complete within reasonable time
            assert parse_time < 1000, f"Parse {i} took too long: {parse_time}ms"
            
            print(f"Test case {i}: {parse_time:.2f}ms, Success level: {result.success_level.value}")
        
        avg_time = total_time / len(test_cases)
        success_rate = successful_parses / len(test_cases) * 100
        
        print(f"Average parsing time: {avg_time:.2f}ms")
        print(f"Full success rate: {success_rate:.1f}%")
        
        # Performance targets
        assert avg_time < 500, f"Average parsing time too high: {avg_time}ms"
        assert success_rate >= 50, f"Success rate too low: {success_rate}%"
    
    def test_fallback_reliability(self):
        """Test that fallback mechanisms always provide usable results."""
        problematic_responses = [
            "",  # Empty response
            "No JSON here at all",  # No structured content
            "{'invalid': json syntax}",  # Invalid JSON syntax
            "점수는 알 수 없습니다.",  # Korean text with no extractable score
            "Score: 점수를 매길 수 없음",  # Mixed language, no score
            "The student did well, maybe 80-90 points range",  # Ambiguous score
            "JSON: {broken syntax, no closing brace",  # Broken JSON
            "```\nNot JSON content\n```",  # Code block with non-JSON content
        ]
        
        for i, response in enumerate(problematic_responses):
            result = self.parser_instance.parse_response_with_rubric(
                response, self.pydantic_parser, self.test_rubric
            )
            
            # Even with problematic input, should always get usable data
            assert result.has_usable_data(), f"Response {i} failed to provide usable data"
            
            best_data = result.get_best_data()
            assert best_data is not None
            assert "채점결과" in best_data
            assert "피드백" in best_data
            assert "합산_점수" in best_data["채점결과"]
            assert "교과_내용_피드백" in best_data["피드백"]
            
            print(f"Problematic response {i}: {result.success_level.value}")
    
    def test_adaptive_validation_improvement(self):
        """Test that adaptive validation improves success rates."""
        # Response with non-standard field structure
        response_with_variations = """{
            "채점결과": {
                "주요점수_1": 40,  // Different field name pattern
                "total_score": 85,  // English field name
                "reasoning": {"note": "Good work"},  // Different structure
                "extra_field": "ignored"  // Extra field
            },
            "피드백": {
                "content_feedback": "학생이 잘 했습니다",  // English field name
                "is_bluffing": false,  // English field name
                "explanation": "Solid work"
            }
        }"""
        
        # Test with standard validation (should be more strict)
        result_standard = self.parser_instance.parse_response(response_with_variations, self.pydantic_parser)
        
        # Test with adaptive validation (should be more flexible)
        result_adaptive = self.parser_instance.parse_response_with_rubric(
            response_with_variations, self.pydantic_parser, self.test_rubric
        )
        
        # Adaptive validation should be more successful or equal
        assert result_adaptive.success_level.value >= result_standard.success_level.value
        
        # At minimum, adaptive validation should provide usable data
        assert result_adaptive.has_usable_data()
        
        print(f"Standard validation: {result_standard.success_level.value}")
        print(f"Adaptive validation: {result_adaptive.success_level.value}")


class TestRealWorldScenarios:
    """Test with realistic, complex scenarios that might occur in production."""
    
    def setup_method(self):
        """Setup realistic testing environment."""
        # Complex rubric similar to real geography grading
        self.geography_rubric = [
            {
                'main_criterion': '지리적 위치 정확성',
                'sub_criteria': [
                    {'score': 15, 'content': '주요 도시 위치'},
                    {'score': 15, 'content': '행정구역 경계'},
                    {'score': 10, 'content': '지형적 특징'}
                ]
            },
            {
                'main_criterion': '교통 및 인프라',
                'sub_criteria': [
                    {'score': 20, 'content': '주요 교통로'},
                    {'score': 10, 'content': '공항 및 항만'},
                    {'score': 10, 'content': '철도 네트워크'}
                ]
            },
            {
                'main_criterion': '표기 완성도',
                'sub_criteria': [
                    {'score': 10, 'content': '명칭 정확성'},
                    {'score': 10, 'content': '전체적 완성도'}
                ]
            }
        ]
        
        self.parser = DynamicModelFactory.create_parser(self.geography_rubric)
        self.config = ParsingConfig(
            max_attempts=4,
            enable_fallback_recovery=True,
            enable_partial_recovery=True,
            log_all_attempts=True
        )
        self.enhanced_parser = EnhancedResponseParser(self.config)
    
    def test_realistic_llm_response_variations(self):
        """Test with realistic variations of LLM responses."""
        realistic_responses = [
            # Verbose response with explanation
            """학생의 지도를 평가한 결과는 다음과 같습니다:

```json
{
    "채점결과": {
        "주요_채점_요소_1_점수": 35,
        "세부_채점_요소_1_1_점수": 12,
        "세부_채점_요소_1_2_점수": 13,
        "세부_채점_요소_1_3_점수": 10,
        "주요_채점_요소_2_점수": 45,
        "세부_채점_요소_2_1_점수": 20,
        "세부_채점_요소_2_2_점수": 15,
        "세부_채점_요소_2_3_점수": 10,
        "주요_채점_요소_3_점수": 18,
        "세부_채점_요소_3_1_점수": 8,
        "세부_채점_요소_3_2_점수": 10,
        "합산_점수": 98,
        "점수_판단_근거": {
            "주요_채점_요소_1": "지리적 위치가 대체로 정확하나 일부 수정 필요",
            "주요_채점_요소_2": "교통 인프라가 잘 표현되어 있음",
            "주요_채점_요소_3": "표기가 명확하고 완성도가 높음"
        }
    },
    "피드백": {
        "교과_내용_피드백": "전반적으로 우수한 지도입니다. 주요 도시와 교통망이 정확하게 표기되어 있고, 행정구역도 적절히 구분되어 있습니다. 다만 일부 지형적 특징의 표기가 미흡한 부분이 있어 보완이 필요합니다.",
        "의사_응답_여부": false,
        "의사_응답_설명": ""
    }
}
```

이상으로 채점을 완료합니다.""",
            
            # Response with mixed formatting
            """채점 결과:
            
{
"채점결과": {
"주요_채점_요소_1_점수": 25,
"합산_점수": 75,
"점수_판단_근거": {
"overall": "기본 요구사항은 충족하였으나 세부사항 보완 필요"
}
},
"피드백": {
"교과_내용_피드백": "지도의 기본 구조는 잘 잡혀있습니다. 추가적인 상세 정보가 필요합니다.",
"의사_응답_여부": false
}
}""",
            
            # Response with errors but extractable content
            """{
    "채점결과": {
        "주요_채점_요소_1_점수": "30",  # String instead of int
        "합산_점수": 65,
        "점수_판단_근거": {"note": "Acceptable performance"},
    },  # Trailing comma
    "피드백": {
        "교과_내용_피드백": "학생이 기본적인 이해를 보여주었습니다.",
        "의사_응답_여부": "false",  # String instead of boolean
        # Missing 의사_응답_설명
    }
}"""
        ]
        
        for i, response in enumerate(realistic_responses):
            result = self.enhanced_parser.parse_response_with_rubric(
                response, self.parser, self.geography_rubric
            )
            
            # Should successfully parse or provide fallback
            assert result.has_usable_data(), f"Failed to parse realistic response {i}"
            
            best_data = result.get_best_data()
            assert "채점결과" in best_data
            assert "피드백" in best_data
            assert "합산_점수" in best_data["채점결과"]
            
            print(f"Realistic response {i}: {result.success_level.value}")
            if result.warnings:
                print(f"  Warnings: {len(result.warnings)}")
    
    def test_edge_case_scenarios(self):
        """Test edge cases that might occur in production."""
        edge_cases = [
            # Very long response
            '{"채점결과": {"합산_점수": 80}, "피드백": {"교과_내용_피드백": "' + "매우 " * 1000 + '좋습니다", "의사_응답_여부": false}}',
            
            # Response with special characters
            '{"채점결과": {"합산_점수": 70}, "피드백": {"교과_내용_피드백": "学生作品不错！Good work~ 🌟", "의사_응답_여부": false}}',
            
            # Response with nested Korean content
            '{"채점결과": {"합산_점수": 90, "상세내용": {"평가": "우수함", "개선점": "없음"}}, "피드백": {"교과_내용_피드백": "완벽합니다", "의사_응답_여부": false}}',
            
            # Response with encoding issues simulation
            '{"채점결과": {"합산_점수": 60}, "피드백": {"교과_내용_피드백": "기본적인 내용 포함", "의사_응답_여부": false}}',
        ]
        
        for i, response in enumerate(edge_cases):
            try:
                result = self.enhanced_parser.parse_response_with_rubric(
                    response, self.parser, self.geography_rubric
                )
                
                # Should handle edge cases gracefully
                assert result.has_usable_data(), f"Failed to handle edge case {i}"
                print(f"Edge case {i}: {result.success_level.value}")
                
            except Exception as e:
                pytest.fail(f"Edge case {i} caused exception: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])