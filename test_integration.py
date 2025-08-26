"""
Quick integration test for enhanced LLM response parsing system.

This script tests the enhanced parser with real-world LLM response patterns
to validate the improvements in error handling.
"""

import sys
import os
import json
from typing import Dict, Any, List

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.enhanced_response_parser import parse_llm_response
from core.parsing_models import ParsingConfig, SuccessLevel
from core.dynamic_models import DynamicModelFactory


def create_test_parser():
    """Create a test parser with typical rubric structure."""
    test_rubric = [
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
    
    return DynamicModelFactory.create_parser(test_rubric)


def test_case_1_perfect_json():
    """Test case 1: Perfect JSON response."""
    print("Test Case 1: Perfect JSON Response")
    print("-" * 50)
    
    response = """{
    "채점결과": {
        "지리적_위치_표기": {
            "주요_도시_정확히_표기": 20,
            "지역_경계_표기": 15
        },
        "교통_네트워크": {
            "주요_교통로_표기": 25,
            "교통_연결점_표기": 20
        },
        "총점": 80,
        "점수_판단_근거": {
            "지리적_위치_표기": "주요 도시와 지역 경계가 정확히 표기됨",
            "교통_네트워크": "교통 네트워크가 잘 표현됨"
        }
    },
    "피드백": {
        "종합평가": "전반적으로 우수한 답안입니다.",
        "잘한점": ["정확한 지리적 표기", "체계적인 구성"],
        "개선사항": ["세부 내용 보완"],
        "의사응답여부": false
    }
}"""
    
    parser = create_test_parser()
    config = ParsingConfig()
    
    result = parse_llm_response(response, parser, config)
    
    print(f"Success Level: {result.success_level.value}")
    print(f"Attempts: {len(result.attempts)}")
    print(f"Successful Strategy: {result.successful_strategy.value if result.successful_strategy else 'None'}")
    print(f"Processing Time: {result.total_processing_time_ms:.2f}ms")
    
    if result.success_level == SuccessLevel.FULL:
        print("✅ Perfect JSON parsing successful!")
        print(f"Total Score: {result.data['채점결과']['총점']}")
    else:
        print("❌ Perfect JSON parsing failed")
        print(f"Errors: {result.errors}")
    
    print()
    return result.success_level == SuccessLevel.FULL


def test_case_2_markdown_wrapped():
    """Test case 2: JSON wrapped in markdown."""
    print("Test Case 2: Markdown Wrapped JSON")
    print("-" * 50)
    
    response = """학생 답안을 분석한 결과는 다음과 같습니다:

채점 과정에서 다음 요소들을 확인했습니다:
- 지리적 위치 표기의 정확성
- 교통 네트워크 표현의 완성도

```json
{
    "채점결과": {
        "지리적_위치_표기": {
            "주요_도시_정확히_표기": 15,
            "지역_경계_표기": 10
        },
        "교통_네트워크": {
            "주요_교통로_표기": 20,
            "교통_연결점_표기": 15
        },
        "총점": 60,
        "점수_판단_근거": {
            "지리적_위치_표기": "일부 도시 위치가 부정확함",
            "교통_네트워크": "주요 교통로는 잘 표현되었으나 연결점이 부족함"
        }
    },
    "피드백": {
        "종합평가": "기본적인 요구사항은 충족하나 세밀함이 부족합니다.",
        "잘한점": ["기본 구조 이해", "주요 요소 파악"],
        "개선사항": ["정확성 향상", "세부 표기 추가"],
        "의사응답여부": false
    }
}
```

추가적으로, 학생은 지리적 개념에 대한 기본적인 이해를 보여주었습니다."""
    
    parser = create_test_parser()
    config = ParsingConfig()
    
    result = parse_llm_response(response, parser, config)
    
    print(f"Success Level: {result.success_level.value}")
    print(f"Attempts: {len(result.attempts)}")
    print(f"Successful Strategy: {result.successful_strategy.value if result.successful_strategy else 'None'}")
    print(f"Processing Time: {result.total_processing_time_ms:.2f}ms")
    
    if result.success_level == SuccessLevel.FULL:
        print("✅ Markdown wrapped JSON parsing successful!")
        print(f"Total Score: {result.data['채점결과']['총점']}")
    else:
        print("❌ Markdown wrapped JSON parsing failed")
        print(f"Errors: {result.errors}")
    
    print()
    return result.success_level == SuccessLevel.FULL


def test_case_3_malformed_json():
    """Test case 3: Malformed JSON that should trigger fallback."""
    print("Test Case 3: Malformed JSON")
    print("-" * 50)
    
    response = """{
    "채점결과": {
        "지리적_위치_표기": {
            "주요_도시_정확히_표기": 10,
            "지역_경계_표기": 5
        },
        "교통_네트워크": {
            "주요_교통로_표기": 15,
            "교통_연결점_표기": 10  // Missing comma and closing bracket
        "총점": 40,
        "점수_판단_근거": {
            "지리적_위치_표기": "도시 위치가 많이 부정확함",
            "교통_네트워크": "교통로 표기가 미흡함"
        }
    },
    "피드백": {
        "종합평가": "전반적으로 개선이 필요합니다.",
        "잘한점": ["기본적인 시도"],
        "개선사항": ["정확성 대폭 향상 필요", "체계적 접근"],
        "의사응답여부": false
    }
}"""
    
    parser = create_test_parser()
    config = ParsingConfig()
    
    result = parse_llm_response(response, parser, config)
    
    print(f"Success Level: {result.success_level.value}")
    print(f"Attempts: {len(result.attempts)}")
    print(f"Successful Strategy: {result.successful_strategy.value if result.successful_strategy else 'None'}")
    print(f"Processing Time: {result.total_processing_time_ms:.2f}ms")
    
    if result.success_level in [SuccessLevel.FULL, SuccessLevel.PARTIAL]:
        print("✅ Malformed JSON handling successful!")
        if result.data:
            print(f"Total Score: {result.data.get('채점결과', {}).get('총점', 'Unknown')}")
        elif result.partial_content:
            print(f"Partial recovery achieved")
    else:
        print("❌ Malformed JSON handling failed")
        print(f"Errors: {result.errors}")
    
    print()
    return result.success_level != SuccessLevel.FAILED


def test_case_4_no_json():
    """Test case 4: Response with no JSON - should trigger text recovery."""
    print("Test Case 4: Text-only Response (Fallback Recovery)")
    print("-" * 50)
    
    response = """채점 결과를 말씀드리겠습니다.

점수는 다음과 같습니다:
- 지리적 위치 표기: 25점 (주요 도시 15점, 지역 경계 10점)
- 교통 네트워크: 30점 (교통로 20점, 연결점 10점)
- 총점: 55점

피드백:
학생의 답안은 전반적으로 평균 수준입니다. 지리적 위치는 어느 정도 정확하게 표기되었으나, 교통 네트워크 부분에서 일부 누락이 있었습니다.

개선사항:
1. 세부 지명의 정확성 향상
2. 교통 연결점 추가 표기
3. 전체적인 구성의 체계성 강화

의사응답 여부: 아니오 (성실한 답안임)"""
    
    parser = create_test_parser()
    config = ParsingConfig()
    
    result = parse_llm_response(response, parser, config)
    
    print(f"Success Level: {result.success_level.value}")
    print(f"Attempts: {len(result.attempts)}")
    print(f"Successful Strategy: {result.successful_strategy.value if result.successful_strategy else 'None'}")
    print(f"Processing Time: {result.total_processing_time_ms:.2f}ms")
    
    if result.success_level == SuccessLevel.PARTIAL:
        print("✅ Text recovery successful!")
        if result.partial_content:
            print(f"Recovered data: {result.partial_content}")
    elif result.success_level == SuccessLevel.FULL:
        print("✅ Unexpected full success from text!")
        print(f"Total Score: {result.data.get('채점결과', {}).get('총점', 'Unknown')}")
    else:
        print("⚠️ Text recovery failed (expected for this case)")
        print(f"Errors: {result.errors}")
    
    print()
    return result.success_level != SuccessLevel.FAILED


def test_case_5_error_correction():
    """Test case 5: JSON with field name issues that need correction."""
    print("Test Case 5: Field Name Correction")
    print("-" * 50)
    
    response = """{
    "grading_results": {
        "location_marking": {
            "city_accuracy": 18,
            "boundary_marking": 12
        },
        "transportation": {
            "main_routes": 22,
            "connection_points": 18
        },
        "total_score": 70,
        "scoring_rationale": {
            "location_marking": "도시 위치가 대체로 정확함",
            "transportation": "교통 네트워크가 잘 표현됨"
        }
    },
    "feedback_section": {
        "overall_assessment": "좋은 수준의 답안입니다.",
        "strengths": ["정확한 표기", "체계적 구성"],
        "improvements_needed": ["세부 정보 추가"],
        "is_bluff": false
    }
}"""
    
    parser = create_test_parser()
    config = ParsingConfig(allow_field_mapping=True, allow_type_coercion=True)
    
    result = parse_llm_response(response, parser, config)
    
    print(f"Success Level: {result.success_level.value}")
    print(f"Attempts: {len(result.attempts)}")
    print(f"Successful Strategy: {result.successful_strategy.value if result.successful_strategy else 'None'}")
    print(f"Warnings: {result.warnings}")
    print(f"Processing Time: {result.total_processing_time_ms:.2f}ms")
    
    if result.success_level == SuccessLevel.FULL:
        print("✅ Field correction successful!")
        print(f"Total Score: {result.data['채점결과']['총점']}")
    elif result.success_level == SuccessLevel.PARTIAL:
        print("⚠️ Partial field correction")
        if result.partial_content:
            print(f"Partial data: {result.partial_content}")
    else:
        print("❌ Field correction failed")
        print(f"Errors: {result.errors}")
    
    print()
    return result.success_level != SuccessLevel.FAILED


def main():
    """Run all integration tests."""
    print("Enhanced LLM Response Parser Integration Tests")
    print("=" * 60)
    print()
    
    test_results = []
    
    # Run all test cases
    test_results.append(test_case_1_perfect_json())
    test_results.append(test_case_2_markdown_wrapped())
    test_results.append(test_case_3_malformed_json())
    test_results.append(test_case_4_no_json())
    test_results.append(test_case_5_error_correction())
    
    # Summary
    print("Integration Test Summary")
    print("=" * 60)
    print(f"Total tests: {len(test_results)}")
    print(f"Passed: {sum(test_results)}")
    print(f"Failed: {len(test_results) - sum(test_results)}")
    print(f"Success rate: {(sum(test_results) / len(test_results)) * 100:.1f}%")
    
    if sum(test_results) >= 4:  # At least 4/5 should pass
        print("\n✅ Integration tests PASSED! Enhanced parser is working correctly.")
        return True
    else:
        print("\n❌ Integration tests FAILED! Please review the implementation.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)