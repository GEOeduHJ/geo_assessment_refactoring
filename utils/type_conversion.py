"""
Type conversion utilities for ensuring Streamlit Cloud and PyArrow compatibility.
Handles data type conversion issues that occur when displaying DataFrames in Streamlit Cloud.
"""
import pandas as pd
from typing import Union, Any


class GradingTimeFormatter:
    """Handles formatting of grading time values for Arrow table compatibility."""
    
    @staticmethod
    def format_grading_time(time_value: Union[float, None, str]) -> str:
        """
        Convert grading time to Arrow-compatible string format.
        
        Args:
            time_value: The time value to format (float, None, or str)
            
        Returns:
            str: Formatted time string that's Arrow-compatible
        """
        if time_value is None:
            return "N/A"
        if isinstance(time_value, str):
            # If already a string, check if it's a formatted time or raw number
            if "초" in time_value or time_value == "N/A":
                return time_value  # Already formatted
            else:
                # Try to parse as number and format
                try:
                    float_val = float(time_value)
                    return f"{float_val:.2f}초"
                except (ValueError, TypeError):
                    return "N/A"
        if isinstance(time_value, (int, float)):
            return f"{time_value:.2f}초"
        return "N/A"
    
    @staticmethod
    def validate_and_format(time_value: Any) -> str:
        """
        Robust validation and formatting with comprehensive error handling.
        
        Args:
            time_value: Any type of time value to validate and format
            
        Returns:
            str: Safely formatted time string
        """
        try:
            if pd.isna(time_value):
                return "N/A"
            float_val = float(time_value)
            return f"{float_val:.2f}초"
        except (ValueError, TypeError):
            return "N/A"


class DataFrameTypeEnforcer:
    """Ensures DataFrame columns are Arrow-compatible by enforcing proper types."""
    
    @staticmethod
    def enforce_string_types(df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure all columns are Arrow-compatible string types.
        
        Args:
            df: Input DataFrame with potentially mixed types
            
        Returns:
            pd.DataFrame: DataFrame with all columns converted to Arrow-compatible strings
        """
        df_copy = df.copy()
        
        # Target columns that need special handling
        time_columns = ['채점_소요_시간']
        complex_columns = ['채점결과', '피드백']
        
        # Handle time columns with specific formatting
        for col in time_columns:
            if col in df_copy.columns:
                df_copy[col] = df_copy[col].apply(
                    GradingTimeFormatter.validate_and_format
                )
        
        # Handle complex object columns
        for col in complex_columns:
            if col in df_copy.columns:
                df_copy[col] = df_copy[col].astype(str)
        
        # Ensure all remaining columns are strings
        for col in df_copy.columns:
            if df_copy[col].dtype == 'object':
                df_copy[col] = df_copy[col].fillna("").astype(str)
            elif df_copy[col].dtype in ['float64', 'int64']:
                df_copy[col] = df_copy[col].astype(str)
        
        return df_copy
    
    @staticmethod
    def validate_arrow_compatibility(df: pd.DataFrame) -> bool:
        """
        Check if DataFrame is compatible with Arrow table conversion.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            bool: True if compatible, False otherwise
        """
        try:
            import pyarrow as pa
            table = pa.Table.from_pandas(df)
            return True
        except Exception:
            return False
    
    @staticmethod
    def get_problematic_columns(df: pd.DataFrame) -> list:
        """
        Identify columns that may cause Arrow conversion issues.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            list: List of problematic column names and their types
        """
        problematic = []
        
        for col in df.columns:
            dtype = str(df[col].dtype)
            # Check for mixed types or problematic dtypes
            if 'object' in dtype:
                # Check if object column contains mixed types
                sample_types = set(type(val).__name__ for val in df[col].dropna().head(10))
                if len(sample_types) > 1:
                    problematic.append((col, f"Mixed types: {sample_types}"))
            elif 'float' in dtype or 'int' in dtype:
                # Numeric types that might cause issues
                problematic.append((col, dtype))
        
        return problematic


class DisplayErrorRecovery:
    """Provides graceful degradation for DataFrame display errors."""
    
    @staticmethod
    def safe_display_with_recovery(df: pd.DataFrame, title: str = "Results"):
        """
        Multi-level fallback for DataFrame display with comprehensive error handling.
        
        Args:
            df: DataFrame to display
            title: Title for error messages
            
        Returns:
            bool: True if display succeeded, False otherwise
        """
        import streamlit as st
        
        try:
            # Primary: Standard dataframe with type enforcement
            validated_df = DataFrameTypeEnforcer.enforce_string_types(df)
            st.dataframe(validated_df)
            return True
            
        except Exception as e1:
            st.warning(f"Standard display failed for {title}: {str(e1)[:100]}...")
            
            try:
                # Secondary: Force string conversion
                string_df = df.astype(str).fillna("")
                st.dataframe(string_df)
                return True
                
            except Exception as e2:
                st.warning(f"String conversion failed for {title}: {str(e2)[:100]}...")
                
                try:
                    # Tertiary: Static table display
                    st.table(df.head(10))  # Limit to first 10 rows
                    if len(df) > 10:
                        st.info(f"Showing first 10 of {len(df)} rows due to display limitations")
                    return True
                    
                except Exception as e3:
                    # Final fallback: Text representation
                    st.error(f"All display methods failed for {title}. Raw data:")
                    st.text(str(df.to_string()))
                    st.error(f"Errors: {str(e1)}, {str(e2)}, {str(e3)}")
                    return False


class StreamlitCompatibilityMiddleware:
    """Middleware to ensure Streamlit Cloud compatibility."""
    
    @staticmethod
    def validate_dataframe_for_arrow(df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate DataFrame for Arrow table compatibility.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            pd.DataFrame: Validated and potentially fixed DataFrame
        """
        # Check for problematic data types
        problematic_types = ['float64', 'int64', 'complex', 'datetime64']
        issues_found = []
        
        for col in df.columns:
            if str(df[col].dtype) in problematic_types:
                issues_found.append(f"Column '{col}' has type {df[col].dtype}")
        
        if issues_found:
            # Apply automatic fixes
            df_fixed = DataFrameTypeEnforcer.enforce_string_types(df)
            return df_fixed
        
        return df
    
    @staticmethod
    def safe_streamlit_display(df: pd.DataFrame, title: str = "Results"):
        """
        Safely display DataFrame in Streamlit with error handling.
        
        Args:
            df: DataFrame to display
            title: Title for error messages
        """
        import streamlit as st
        
        try:
            # Pre-validate for Arrow compatibility
            validated_df = StreamlitCompatibilityMiddleware.validate_dataframe_for_arrow(df)
            st.dataframe(validated_df)
        except Exception as e:
            st.error(f"Display error for {title}: {str(e)}")
            # Fallback to recovery mechanism
            DisplayErrorRecovery.safe_display_with_recovery(df, title)