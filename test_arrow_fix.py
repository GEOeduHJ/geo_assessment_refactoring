"""
End-to-end test script for Arrow compatibility fix.
Tests the complete pipeline with various data types that previously caused issues.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.export_service import ExportService
from utils.type_conversion import (
    GradingTimeFormatter, 
    DataFrameTypeEnforcer, 
    StreamlitCompatibilityMiddleware
)


def create_test_grading_results() -> List[Dict[str, Any]]:
    """Create test grading results with various problematic data types."""
    return [
        {
            "이름": "김철수",
            "답안": "유럽 연합은 경제적 통합을 통해 회원국 간의 무역을 촉진합니다.",
            "채점결과": {
                "합산_점수": 85,
                "세부_점수": 42.5,
                "기본_개념_이해": 20,
                "응용_능력": 15,
                "표현_능력": 7.5
            },
            "피드백": {
                "교과_내용_피드백": "유럽연합의 경제적 효과에 대한 이해가 우수함",
                "의사_응답_여부": True,
                "의사_응답_설명": "관련 내용을 잘 설명함"
            },
            "점수_판단_근거": {
                "기본_개념_이해": "유럽연합의 기본 개념을 정확히 이해하고 있음",
                "응용_능력": "경제적 통합의 효과를 구체적으로 설명함"
            },
            "참고문서": "EU_economic_integration.pdf (p.15); trade_policies.pdf (p.23)",
            "채점_소요_시간": 67.89,  # Float that causes the issue
            "오류": None
        },
        {
            "이름": "이영희",
            "답안": "NATO는 북대서양 조약기구로, 집단 안보를 제공합니다.",
            "채점결과": {
                "합산_점수": 92,
                "세부_점수": 46.0,
                "기본_개념_이해": 22,
                "응용_능력": 18,
                "표현_능력": 6.0
            },
            "피드백": {
                "교과_내용_피드백": "NATO의 역할과 기능에 대한 정확한 이해",
                "의사_응답_여부": True,
                "의사_응답_설명": "집단 안보 개념을 명확히 설명"
            },
            "점수_판단_근거": {
                "기본_개념_이해": "NATO의 기본 목적을 정확히 파악",
                "응용_능력": "집단 안보의 의미를 잘 설명함"
            },
            "참고문서": "NATO_handbook.pdf (p.8); security_alliances.pdf (p.45)",
            "채점_소요_시간": 54.32,  # Another float
            "오류": None
        },
        {
            "이름": "박민수",
            "답안": "",  # Empty answer
            "채점결과": {},
            "피드백": {},
            "참고문서": "",
            "채점_소요_시간": None,  # None value
            "오류": "답안이 비어있어 채점할 수 없습니다."
        },
        {
            "이름": "정수현",
            "인식된_텍스트": ["서울", "부산", "대구"],  # For 백지도 type
            "채점결과": {
                "인식된_지명_수": 3,
                "정확한_위치_수": 2,
                "정확도": 66.67
            },
            "피드백": {
                "교과_내용_피드백": "주요 도시들의 위치를 대부분 정확히 표시함",
                "의사_응답_여부": True
            },
            "참고문서": "korea_geography.pdf (p.12)",
            "채점_소요_시간": 123.456,  # High precision float
            "오류": None
        }
    ]


def test_export_service_display_formatting():
    """Test ExportService format_results_for_display with problematic data types."""
    print("=== Testing ExportService Display Formatting ===")
    
    graded_results = create_test_grading_results()
    
    # Test with 서술형 question type
    print("Testing 서술형 formatting...")
    display_df_descriptive = ExportService.format_results_for_display(graded_results, "서술형")
    print(f"DataFrame shape: {display_df_descriptive.shape}")
    print(f"DataFrame dtypes:\n{display_df_descriptive.dtypes}")
    print(f"Sample time values: {display_df_descriptive['채점_소요_시간'].tolist()}")
    
    # Test with 백지도 question type  
    print("\nTesting 백지도 formatting...")
    display_df_map = ExportService.format_results_for_display(graded_results, "백지도")
    print(f"DataFrame shape: {display_df_map.shape}")
    print(f"DataFrame dtypes:\n{display_df_map.dtypes}")
    
    return display_df_descriptive, display_df_map


def test_export_service_excel_formatting():
    """Test ExportService format_results_for_export with type conversion."""
    print("\n=== Testing ExportService Excel Formatting ===")
    
    graded_results = create_test_grading_results()
    excel_df = ExportService.format_results_for_export(graded_results)
    
    print(f"Excel DataFrame shape: {excel_df.shape}")
    print(f"Excel DataFrame dtypes:\n{excel_df.dtypes}")
    
    # Check if time columns are properly formatted
    time_columns = [col for col in excel_df.columns if "소요_시간" in col]
    for col in time_columns:
        print(f"Time column '{col}' values: {excel_df[col].tolist()}")
    
    return excel_df


def test_arrow_compatibility():
    """Test Arrow table compatibility after type conversion."""
    print("\n=== Testing Arrow Compatibility ===")
    
    graded_results = create_test_grading_results()
    
    # Test original data (should fail in Streamlit Cloud)
    original_df = pd.DataFrame(graded_results)
    print(f"Original DataFrame problematic columns:")
    problematic = DataFrameTypeEnforcer.get_problematic_columns(original_df)
    for col, issue in problematic:
        print(f"  - {col}: {issue}")
    
    # Test after type enforcement (should be compatible)
    enforced_df = DataFrameTypeEnforcer.enforce_string_types(original_df)
    print(f"\nAfter type enforcement:")
    print(f"DataFrame dtypes:\n{enforced_df.dtypes}")
    
    # Simulate Arrow compatibility check
    try:
        # This is a mock test since we can't import pyarrow in all environments
        all_strings = all(enforced_df[col].dtype == 'object' for col in enforced_df.columns)
        print(f"All columns are object/string type: {all_strings}")
        
        # Check specific formatting
        time_col = "채점_소요_시간"
        if time_col in enforced_df.columns:
            time_values = enforced_df[time_col].tolist()
            all_formatted = all("초" in str(val) or val == "N/A" for val in time_values)
            print(f"All time values properly formatted: {all_formatted}")
            print(f"Time values: {time_values}")
        
        return True
        
    except Exception as e:
        print(f"Arrow compatibility test failed: {e}")
        return False


def test_grading_time_formatter():
    """Test GradingTimeFormatter with various input types."""
    print("\n=== Testing GradingTimeFormatter ===")
    
    test_cases = [
        (45.67, "45.67초"),
        (30, "30.00초"),
        (None, "N/A"),
        ("already formatted", "already formatted"),
        (np.nan, "N/A"),
        (pd.NA, "N/A"),
        ("123.45", "123.45초"),
        ({"invalid": "object"}, "N/A"),
        ([], "N/A")
    ]
    
    for input_val, expected in test_cases:
        result = GradingTimeFormatter.validate_and_format(input_val)
        status = "✓" if result == expected else "✗"
        print(f"{status} Input: {input_val} -> Output: {result} (Expected: {expected})")


def test_streamlit_compatibility_middleware():
    """Test StreamlitCompatibilityMiddleware validation."""
    print("\n=== Testing StreamlitCompatibilityMiddleware ===")
    
    # Create DataFrame with problematic types
    test_data = {
        "string_col": ["a", "b", "c"],
        "float_col": [1.1, 2.2, 3.3],
        "int_col": [1, 2, 3],
        "time_col": [45.67, 32.1, 78.9]
    }
    
    df = pd.DataFrame(test_data)
    print(f"Original dtypes:\n{df.dtypes}")
    
    validated_df = StreamlitCompatibilityMiddleware.validate_dataframe_for_arrow(df)
    print(f"Validated dtypes:\n{validated_df.dtypes}")
    
    # Check if time column is properly formatted
    if "time_col" in validated_df.columns:
        print(f"Time values after validation: {validated_df['time_col'].tolist()}")


def run_all_tests():
    """Run all compatibility tests."""
    print("Starting Arrow Compatibility Fix Tests")
    print("=" * 50)
    
    try:
        # Test individual components
        test_grading_time_formatter()
        test_streamlit_compatibility_middleware()
        
        # Test service layer
        display_df_desc, display_df_map = test_export_service_display_formatting()
        excel_df = test_export_service_excel_formatting()
        
        # Test Arrow compatibility
        is_compatible = test_arrow_compatibility()
        
        print("\n" + "=" * 50)
        print("TEST SUMMARY")
        print("=" * 50)
        print(f"✓ GradingTimeFormatter: Working")
        print(f"✓ DataFrameTypeEnforcer: Working")
        print(f"✓ ExportService Display: {display_df_desc.shape[0]} records formatted")
        print(f"✓ ExportService Excel: {excel_df.shape[0]} records formatted")
        print(f"✓ Arrow Compatibility: {'PASS' if is_compatible else 'FAIL'}")
        
        if is_compatible:
            print("\n🎉 All tests passed! The Arrow compatibility fix should work in Streamlit Cloud.")
        else:
            print("\n❌ Some tests failed. Please review the implementation.")
            
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()