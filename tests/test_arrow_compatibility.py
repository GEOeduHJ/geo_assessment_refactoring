"""
Unit tests for type conversion utilities.
Tests GradingTimeFormatter, DataFrameTypeEnforcer, and StreamlitCompatibilityMiddleware.
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
from utils.type_conversion import (
    GradingTimeFormatter, 
    DataFrameTypeEnforcer, 
    StreamlitCompatibilityMiddleware,
    DisplayErrorRecovery
)


class TestGradingTimeFormatter:
    """Test cases for GradingTimeFormatter class."""
    
    def test_format_float_time(self):
        """Test formatting of float grading time."""
        result = GradingTimeFormatter.format_grading_time(45.67)
        assert result == "45.67초"
    
    def test_format_int_time(self):
        """Test formatting of integer grading time."""
        result = GradingTimeFormatter.format_grading_time(30)
        assert result == "30.00초"
    
    def test_format_none_time(self):
        """Test handling of None values."""
        result = GradingTimeFormatter.format_grading_time(None)
        assert result == "N/A"
    
    def test_format_string_time(self):
        """Test handling of string values (should pass through)."""
        result = GradingTimeFormatter.format_grading_time("45.67초")
        assert result == "45.67초"
    
    def test_format_invalid_time(self):
        """Test handling of invalid values."""
        result = GradingTimeFormatter.format_grading_time("invalid")
        assert result == "N/A"
    
    def test_validate_and_format_with_pandas_na(self):
        """Test handling of pandas NA values."""
        result = GradingTimeFormatter.validate_and_format(pd.NA)
        assert result == "N/A"
    
    def test_validate_and_format_with_numpy_nan(self):
        """Test handling of numpy NaN values."""
        result = GradingTimeFormatter.validate_and_format(np.nan)
        assert result == "N/A"
    
    def test_validate_and_format_with_valid_float(self):
        """Test robust validation with valid float."""
        result = GradingTimeFormatter.validate_and_format(42.123)
        assert result == "42.12초"
    
    def test_validate_and_format_with_string_number(self):
        """Test robust validation with string number."""
        result = GradingTimeFormatter.validate_and_format("35.5")
        assert result == "35.50초"
    
    def test_validate_and_format_with_invalid_type(self):
        """Test robust validation with invalid type."""
        result = GradingTimeFormatter.validate_and_format({"invalid": "object"})
        assert result == "N/A"


class TestDataFrameTypeEnforcer:
    """Test cases for DataFrameTypeEnforcer class."""
    
    def test_enforce_string_types_with_grading_time(self):
        """Test string type enforcement for grading time column."""
        test_data = [
            {
                "이름": "김철수",
                "채점_소요_시간": 45.67,
                "채점결과": {"점수": 85},
                "오류": None
            }
        ]
        
        df = pd.DataFrame(test_data)
        enforced_df = DataFrameTypeEnforcer.enforce_string_types(df)
        
        # Verify grading time is formatted
        assert "초" in enforced_df.iloc[0]["채점_소요_시간"]
        
        # Verify other columns are strings
        assert isinstance(enforced_df.iloc[0]["채점결과"], str)
        assert enforced_df.iloc[0]["오류"] == ""
    
    def test_enforce_string_types_with_complex_data(self):
        """Test string type enforcement with complex nested data."""
        test_data = [
            {
                "이름": "학생1",
                "답안": "지리 답안",
                "채점결과": {"합산_점수": 85, "세부_점수": 42.5},
                "피드백": {"내용": "좋은 답안입니다"},
                "채점_소요_시간": 67.89,
                "참고문서": "reference.pdf"
            }
        ]
        
        df = pd.DataFrame(test_data)
        enforced_df = DataFrameTypeEnforcer.enforce_string_types(df)
        
        # All columns should be string type
        for col in enforced_df.columns:
            assert enforced_df[col].dtype == 'object'
        
        # Time should be formatted
        assert "67.89초" == enforced_df.iloc[0]["채점_소요_시간"]
    
    def test_enforce_string_types_with_mixed_types(self):
        """Test handling of mixed data types in DataFrame."""
        test_data = {
            "이름": ["학생1", "학생2"],
            "점수": [85, 90],  # Integer column
            "채점_소요_시간": [45.67, 32.1],  # Float column
            "피드백": [{"내용": "좋음"}, {"내용": "우수"}]  # Object column
        }
        
        df = pd.DataFrame(test_data)
        enforced_df = DataFrameTypeEnforcer.enforce_string_types(df)
        
        # Check time formatting
        assert "45.67초" == enforced_df.iloc[0]["채점_소요_시간"]
        assert "32.10초" == enforced_df.iloc[1]["채점_소요_시간"]
        
        # Check other conversions
        assert enforced_df.iloc[0]["점수"] == "85"
        assert "내용" in enforced_df.iloc[0]["피드백"]
    
    def test_validate_arrow_compatibility(self):
        """Test Arrow compatibility validation."""
        # Test with string DataFrame (should be compatible)
        string_df = pd.DataFrame({
            "col1": ["a", "b", "c"],
            "col2": ["1", "2", "3"]
        })
        
        # Mock pyarrow to avoid dependency issues in tests
        with patch('utils.type_conversion.pa') as mock_pa:
            mock_pa.Table.from_pandas.return_value = Mock()
            result = DataFrameTypeEnforcer.validate_arrow_compatibility(string_df)
            assert result is True
    
    def test_get_problematic_columns(self):
        """Test identification of problematic columns."""
        test_data = {
            "string_col": ["a", "b", "c"],
            "float_col": [1.1, 2.2, 3.3],
            "int_col": [1, 2, 3],
            "mixed_col": ["text", 123, None]
        }
        
        df = pd.DataFrame(test_data)
        problematic = DataFrameTypeEnforcer.get_problematic_columns(df)
        
        # Should identify float and int columns as problematic
        problematic_names = [item[0] for item in problematic]
        assert "float_col" in problematic_names
        assert "int_col" in problematic_names


class TestStreamlitCompatibilityMiddleware:
    """Test cases for StreamlitCompatibilityMiddleware class."""
    
    def test_validate_dataframe_for_arrow_with_problematic_types(self):
        """Test DataFrame validation with problematic types."""
        test_data = {
            "name": ["student1", "student2"],
            "score": [85.5, 90.0],  # Float64 - problematic
            "time": [45, 50]  # Int64 - problematic
        }
        
        df = pd.DataFrame(test_data)
        validated_df = StreamlitCompatibilityMiddleware.validate_dataframe_for_arrow(df)
        
        # Should have converted problematic types to strings
        assert validated_df["score"].dtype == 'object'
        assert validated_df["time"].dtype == 'object'
    
    @patch('streamlit.dataframe')
    @patch('streamlit.error')
    def test_safe_streamlit_display_success(self, mock_error, mock_dataframe):
        """Test successful safe display."""
        test_df = pd.DataFrame({"col": ["a", "b", "c"]})
        
        StreamlitCompatibilityMiddleware.safe_streamlit_display(test_df, "Test")
        
        # Should call dataframe without error
        mock_dataframe.assert_called_once()
        mock_error.assert_not_called()
    
    @patch('streamlit.dataframe')
    @patch('streamlit.error')
    @patch('utils.type_conversion.DisplayErrorRecovery.safe_display_with_recovery')
    def test_safe_streamlit_display_failure(self, mock_recovery, mock_error, mock_dataframe):
        """Test safe display with failure and recovery."""
        mock_dataframe.side_effect = Exception("Arrow conversion failed")
        test_df = pd.DataFrame({"col": ["a", "b", "c"]})
        
        StreamlitCompatibilityMiddleware.safe_streamlit_display(test_df, "Test")
        
        # Should call error and recovery
        mock_error.assert_called_once()
        mock_recovery.assert_called_once()


class TestDisplayErrorRecovery:
    """Test cases for DisplayErrorRecovery class."""
    
    @patch('streamlit.dataframe')
    def test_safe_display_with_recovery_success(self, mock_dataframe):
        """Test successful display on first attempt."""
        test_df = pd.DataFrame({"col": ["a", "b", "c"]})
        
        result = DisplayErrorRecovery.safe_display_with_recovery(test_df, "Test")
        
        assert result is True
        mock_dataframe.assert_called_once()
    
    @patch('streamlit.dataframe')
    @patch('streamlit.warning')
    def test_safe_display_with_recovery_fallback(self, mock_warning, mock_dataframe):
        """Test fallback behavior when primary display fails."""
        # First call fails, second succeeds
        mock_dataframe.side_effect = [Exception("First failure"), None]
        test_df = pd.DataFrame({"col": ["a", "b", "c"]})
        
        result = DisplayErrorRecovery.safe_display_with_recovery(test_df, "Test")
        
        assert result is True
        assert mock_dataframe.call_count == 2
        mock_warning.assert_called_once()


# Integration test class
class TestTypeConversionIntegration:
    """Integration tests for type conversion system."""
    
    def test_end_to_end_grading_result_processing(self):
        """Test complete pipeline with realistic grading results."""
        # Simulate grading results with problematic types
        graded_results = [
            {
                "이름": "학생1",
                "답안": "지리 답안",
                "채점결과": {"합산_점수": 85, "세부_점수": 42.5},
                "피드백": {"내용": "좋은 답안입니다"},
                "채점_소요_시간": 67.89,  # Float that causes issue
                "참고문서": "reference.pdf",
                "오류": None
            },
            {
                "이름": "학생2", 
                "답안": "또 다른 답안",
                "채점결과": {"합산_점수": 92, "세부_점수": 46.0},
                "피드백": {"내용": "매우 우수한 답안"},
                "채점_소요_시간": 54.32,
                "참고문서": "reference2.pdf",
                "오류": None
            }
        ]
        
        # Create DataFrame and apply type enforcement
        df = pd.DataFrame(graded_results)
        enforced_df = DataFrameTypeEnforcer.enforce_string_types(df)
        
        # Verify all data is properly converted
        assert "67.89초" == enforced_df.iloc[0]["채점_소요_시간"]
        assert "54.32초" == enforced_df.iloc[1]["채점_소요_시간"]
        
        # Verify complex objects are stringified
        assert isinstance(enforced_df.iloc[0]["채점결과"], str)
        assert isinstance(enforced_df.iloc[0]["피드백"], str)
        
        # Verify None values are handled
        assert enforced_df.iloc[0]["오류"] == ""
    
    def test_arrow_compatibility_after_conversion(self):
        """Test that converted DataFrames are Arrow-compatible."""
        test_data = [
            {
                "이름": "테스트학생",
                "채점_소요_시간": 123.456,
                "점수": 85,
                "피드백": {"내용": "테스트"}
            }
        ]
        
        df = pd.DataFrame(test_data)
        enforced_df = DataFrameTypeEnforcer.enforce_string_types(df)
        
        # Mock Arrow validation
        with patch('utils.type_conversion.pa') as mock_pa:
            mock_pa.Table.from_pandas.return_value = Mock()
            result = DataFrameTypeEnforcer.validate_arrow_compatibility(enforced_df)
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__])