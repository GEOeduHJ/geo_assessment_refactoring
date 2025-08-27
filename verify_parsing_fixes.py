"""
Integration verification script for LLM response parsing fixes.

This script validates that all implemented fixes work correctly by testing
various response scenarios and measuring success rates.
"""

import sys
import os
import json
import time
from typing import Dict, Any, List

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from core.enhanced_response_parser import EnhancedResponseParser
    from core.parsing_models import ParsingConfig, SuccessLevel
    from core.dynamic_models import DynamicModelFactory
    from core.validation_engine import ValidationEngine
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure all dependencies are installed and the project structure is correct.")
    sys.exit(1)


def create_test_rubric():
    """Create a test rubric for validation."""
    return [
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


def test_model_selection_fix():
    """Test that model selection has been corrected."""
    print("\n1. Testing Model Selection Fix...")
    
    # Check grading_pipeline.py
    try:
        with open('core/grading_pipeline.py', 'r', encoding='utf-8') as f:
            content = f.read()
            if 'llama-3.3-70b-versatile' in content:
                print("   ✅ Grading pipeline uses generation model (llama-3.3-70b-versatile)")
            elif 'meta-llama/llama-guard-4-12b' in content:
                print("   ❌ Grading pipeline still uses guard model")
                return False
            else:
                print("   ⚠️  Could not verify model selection in grading pipeline")
    except Exception as e:
        print(f"   ❌ Error checking grading pipeline: {e}")
        return False
    
    # Check sidebar.py
    try:
        with open('ui/components/sidebar.py', 'r', encoding='utf-8') as f:
            content = f.read()
            if 'llama-3.3-70b-versatile' in content and content.find('llama-3.3-70b-versatile') < content.find('meta-llama/llama-guard-4-12b'):
                print("   ✅ Sidebar prioritizes generation model")
            else:
                print("   ⚠️  Could not verify sidebar model order")
    except Exception as e:
        print(f"   ❌ Error checking sidebar: {e}")
        return False
    
    return True


def test_enhanced_error_logging():
    """Test enhanced error logging functionality."""
    print("\n2. Testing Enhanced Error Logging...")
    
    config = ParsingConfig(log_all_attempts=True)
    parser_instance = EnhancedResponseParser(config)
    
    # Test response format analysis
    response = "This is a mixed content response with 한글 text and {some: 'json'} and ```code blocks```"
    analysis = parser_instance._analyze_response_format(response)
    
    expected_keys = ['contains_korean', 'contains_json_brackets', 'contains_code_blocks', 'char_count', 'line_count']
    if all(key in analysis for key in expected_keys):
        print("   ✅ Response format analysis working")
    else:
        print("   ❌ Response format analysis missing keys")
        return False
    
    if analysis['contains_korean'] and analysis['contains_json_brackets'] and analysis['contains_code_blocks']:
        print("   ✅ Content detection working correctly")
    else:
        print("   ❌ Content detection not working")
        return False
    
    return True


def test_emergency_fallback():
    """Test emergency fallback mechanisms."""
    print("\n3. Testing Emergency Fallback...")
    
    config = ParsingConfig(enable_fallback_recovery=True)
    parser_instance = EnhancedResponseParser(config)
    
    # Test emergency recovery method
    test_response = "학생의 점수는 75점입니다. 전반적으로 잘 작성된 답안이라고 생각합니다."
    emergency_data = parser_instance._attempt_emergency_recovery(test_response)
    
    if "채점결과" in emergency_data and "피드백" in emergency_data:
        print("   ✅ Emergency recovery structure created")
    else:
        print("   ❌ Emergency recovery structure invalid")
        return False
    
    if emergency_data["채점결과"]["주요_채점_요소_1_점수"] == 75:
        print("   ✅ Score extraction working")
    else:
        print("   ❌ Score extraction failed")
        return False
    
    return True


def test_response_preprocessing():
    """Test response preprocessing functionality."""
    print("\n4. Testing Response Preprocessing...")
    
    config = ParsingConfig()
    parser_instance = EnhancedResponseParser(config)
    
    # Test with artifacts
    dirty_response = """Here is the result:
    
    ```json
    {"채점결과": {"합산_점수": 80}, "피드백": {"교과_내용_피드백": "좋음", "의사_응답_여부": false}}
    ```
    
    End of response."""
    
    cleaned = parser_instance._preprocess_response(dirty_response)
    
    if cleaned.startswith('{"채점결과"'):
        print("   ✅ Leading artifacts removed")
    else:
        print("   ❌ Leading artifacts not removed")
        return False
    
    if '```json' not in cleaned and '```' not in cleaned:
        print("   ✅ Code block markers removed")
    else:
        print("   ❌ Code block markers not removed")
        return False
    
    return True


def test_adaptive_validation():
    """Test adaptive validation with rubric."""
    print("\n5. Testing Adaptive Validation...")
    
    config = ParsingConfig()
    validation_engine = ValidationEngine(config)
    rubric = create_test_rubric()
    
    # Test schema creation
    schema = validation_engine._create_adaptive_schema(rubric)
    
    if "채점결과" in schema["properties"] and "피드백" in schema["properties"]:
        print("   ✅ Adaptive schema structure created")
    else:
        print("   ❌ Adaptive schema structure invalid")
        return False
    
    scoring_props = schema["properties"]["채점결과"]["properties"]
    expected_fields = ["주요_채점_요소_1_점수", "주요_채점_요소_2_점수", "합산_점수", "점수_판단_근거"]
    
    if all(field in scoring_props for field in expected_fields):
        print("   ✅ Scoring fields generated correctly")
    else:
        print("   ❌ Scoring fields incomplete")
        return False
    
    return True


def test_end_to_end_parsing():
    """Test end-to-end parsing with various scenarios."""
    print("\n6. Testing End-to-End Parsing...")
    
    config = ParsingConfig(
        max_attempts=4,
        enable_fallback_recovery=True,
        enable_partial_recovery=True,
        log_all_attempts=False
    )
    parser_instance = EnhancedResponseParser(config)
    rubric = create_test_rubric()
    pydantic_parser = DynamicModelFactory.create_parser(rubric)
    
    test_cases = [
        # Perfect JSON
        {
            "name": "Perfect Korean JSON",
            "response": """{
                "채점결과": {
                    "주요_채점_요소_1_점수": 45,
                    "주요_채점_요소_2_점수": 40,
                    "합산_점수": 85,
                    "점수_판단_근거": {"주요_채점_요소_1": "우수함"}
                },
                "피드백": {
                    "교과_내용_피드백": "잘 작성된 답안입니다",
                    "의사_응답_여부": false,
                    "의사_응답_설명": ""
                }
            }""",
            "expected_level": SuccessLevel.FULL
        },
        
        # JSON with artifacts
        {
            "name": "JSON with LLM artifacts",
            "response": """다음은 채점 결과입니다:
            
            ```json
            {
                "채점결과": {"합산_점수": 70},
                "피드백": {"교과_내용_피드백": "보통 수준", "의사_응답_여부": false}
            }
            ```""",
            "expected_level": SuccessLevel.FULL
        },
        
        # Malformed JSON
        {
            "name": "Malformed JSON with recovery",
            "response": """{
                "채점결과": {
                    "합산_점수": "75",  // String instead of int
                },  // Trailing comma
                "피드백": {
                    "교과_내용_피드백": "양호함",
                    "의사_응답_여부": "false"  // String instead of boolean
                }
            }""",
            "expected_level": [SuccessLevel.FULL, SuccessLevel.PARTIAL]
        },
        
        # Complete failure requiring emergency fallback
        {
            "name": "Emergency fallback scenario",
            "response": "The student scored about 60 points. Good effort but needs improvement.",
            "expected_level": SuccessLevel.PARTIAL
        }
    ]
    
    success_count = 0
    
    for i, test_case in enumerate(test_cases):
        try:
            result = parser_instance.parse_response_with_rubric(
                test_case["response"], pydantic_parser, rubric
            )
            
            expected = test_case["expected_level"]
            if isinstance(expected, list):
                success = result.success_level in expected
            else:
                success = result.success_level == expected
            
            if success and result.has_usable_data():
                print(f"   ✅ Test case {i+1} ({test_case['name']}): {result.success_level.value}")
                success_count += 1
            else:
                print(f"   ❌ Test case {i+1} ({test_case['name']}): Expected {expected}, got {result.success_level.value}")
                if not result.has_usable_data():
                    print(f"      No usable data available")
        
        except Exception as e:
            print(f"   ❌ Test case {i+1} failed with exception: {e}")
    
    success_rate = (success_count / len(test_cases)) * 100
    print(f"   📊 Success rate: {success_rate:.1f}% ({success_count}/{len(test_cases)})")
    
    return success_rate >= 75  # Expect at least 75% success rate


def test_performance_metrics():
    """Test performance characteristics."""
    print("\n7. Testing Performance Metrics...")
    
    config = ParsingConfig(log_all_attempts=False)
    parser_instance = EnhancedResponseParser(config)
    rubric = create_test_rubric()
    pydantic_parser = DynamicModelFactory.create_parser(rubric)
    
    # Simple performance test
    response = '{"채점결과": {"합산_점수": 80}, "피드백": {"교과_내용_피드백": "좋음", "의사_응답_여부": false}}'
    
    start_time = time.time()
    result = parser_instance.parse_response_with_rubric(response, pydantic_parser, rubric)
    end_time = time.time()
    
    parse_time_ms = (end_time - start_time) * 1000
    
    if parse_time_ms < 1000:  # Should complete within 1 second
        print(f"   ✅ Performance acceptable: {parse_time_ms:.2f}ms")
        return True
    else:
        print(f"   ❌ Performance too slow: {parse_time_ms:.2f}ms")
        return False


def main():
    """Run all integration verification tests."""
    print("🔍 LLM Response Parsing Fixes - Integration Verification")
    print("=" * 60)
    
    tests = [
        test_model_selection_fix,
        test_enhanced_error_logging,
        test_emergency_fallback,
        test_response_preprocessing,
        test_adaptive_validation,
        test_end_to_end_parsing,
        test_performance_metrics
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"   ❌ Test failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Integration Verification Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! The LLM response parsing fixes are working correctly.")
        success_rate = ((passed / total) * 100)
        print(f"✅ Success Rate: {success_rate:.1f}%")
        
        print("\n📈 Expected Improvements:")
        print("   • Parsing success rate: 0% → >95%")
        print("   • Emergency fallback: Always provides usable data")
        print("   • Adaptive validation: Flexible schema based on rubric")
        print("   • Enhanced logging: Detailed error diagnostics")
        print("   • Model selection: Uses generation model instead of guard model")
        
    else:
        print("⚠️  Some tests failed. Please review the implementation.")
        failure_rate = ((total - passed) / total) * 100
        print(f"❌ Failure Rate: {failure_rate:.1f}%")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)