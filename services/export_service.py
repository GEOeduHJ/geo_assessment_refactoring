"""
Export service for handling results formatting and Excel export.
Formats grading results for display and export to Excel.
Now includes Arrow-compatible type conversion for Streamlit Cloud deployment.
"""
import pandas as pd
import io
from typing import List, Dict, Any
from utils.type_conversion import DataFrameTypeEnforcer, GradingTimeFormatter


class ExportService:
    """Service for handling export operations and result formatting."""
    
    @staticmethod
    def format_results_for_display(graded_results: List[Dict[str, Any]], question_type: str) -> pd.DataFrame:
        """
        Format grading results for display in Streamlit with Arrow-compatible types.
        
        Args:
            graded_results: List of grading result dictionaries
            question_type: Type of question ("서술형" or "백지도")
            
        Returns:
            pandas.DataFrame: Formatted results for display with Arrow-compatible types
        """
        if not graded_results:
            return pd.DataFrame()
        
        # Define columns based on question type
        if question_type == "백지도":
            display_columns = ["이름", "인식된_텍스트", "채점결과", "피드백", "참고문서", "채점_소요_시간", "오류"]
        else:
            display_columns = ["이름", "답안", "채점결과", "피드백", "참고문서", "채점_소요_시간", "오류"]
        
        # Create DataFrame and filter existing columns
        results_df = pd.DataFrame(graded_results)
        existing_columns = [col for col in display_columns if col in results_df.columns]
        
        # Create display DataFrame with robust type handling
        display_df = results_df[existing_columns].copy()
        
        # Apply comprehensive type enforcement for Arrow compatibility
        display_df = DataFrameTypeEnforcer.enforce_string_types(display_df)
        
        return display_df.fillna("")
    
    @staticmethod
    def format_results_for_export(graded_results: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Format grading results for Excel export with explicit type conversion.
        
        Args:
            graded_results: List of grading result dictionaries
            
        Returns:
            pandas.DataFrame: Formatted results for Excel export with proper types
        """
        if not graded_results:
            return pd.DataFrame()
        
        final_excel_rows = []
        
        for result in graded_results:
            new_row = {
                "이름": str(result.get("이름", "")),
                "답안": str(result.get("답안") if "답안" in result else result.get("인식된_텍스트", "")),
                "참고문서": str(result.get("참고문서", "")),
                "채점_소요_시간": GradingTimeFormatter.format_grading_time(
                    result.get("채점_소요_시간")
                ),
                "오류": str(result.get("오류", ""))
            }
            
            # Flatten 채점결과 (grading results) into separate columns with string conversion
            if isinstance(result.get("채점결과"), dict):
                for key, value in result["채점결과"].items():
                    new_row[f"채점결과_{key}"] = str(value) if value is not None else ""
            else:
                new_row["채점결과"] = str(result.get("채점결과", ""))
            
            # Flatten 피드백 (feedback) into separate columns with string conversion
            if isinstance(result.get("피드백"), dict):
                for key, value in result["피드백"].items():
                    new_row[f"피드백_{key}"] = str(value) if value is not None else ""
            else:
                new_row["피드백"] = str(result.get("피드백", ""))
            
            # Add 점수_판단_근거 (scoring rationale) with string conversion
            if "점수_판단_근거" in result:
                if isinstance(result["점수_판단_근거"], dict):
                    for key, value in result["점수_판단_근거"].items():
                        new_row[f"점수_판단_근거_{key}"] = str(value) if value is not None else ""
                else:
                    new_row["점수_판단_근거"] = str(result["점수_판단_근거"])
            
            final_excel_rows.append(new_row)
        
        return pd.DataFrame(final_excel_rows)
    
    @staticmethod
    def create_excel_download(graded_results: List[Dict[str, Any]]) -> bytes:
        """
        Create Excel file data for download.
        
        Args:
            graded_results: List of grading result dictionaries
            
        Returns:
            bytes: Excel file data
        """
        excel_df = ExportService.format_results_for_export(graded_results)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            excel_df.to_excel(writer, index=False, sheet_name='채점결과')
        
        return output.getvalue()
    
    @staticmethod
    def get_results_summary(graded_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get a summary of grading results.
        
        Args:
            graded_results: List of grading result dictionaries
            
        Returns:
            dict: Summary statistics
        """
        if not graded_results:
            return {
                "total_students": 0,
                "successful_grades": 0,
                "failed_grades": 0,
                "average_score": 0,
                "total_time": 0
            }
        
        total_students = len(graded_results)
        failed_grades = sum(1 for result in graded_results if "오류" in result and result.get("오류"))
        successful_grades = total_students - failed_grades
        
        # Calculate average score from successful grades
        valid_scores = []
        total_time = 0
        
        for result in graded_results:
            if "오류" not in result or not result.get("오류"):
                # Extract total score if available
                if isinstance(result.get("채점결과"), dict):
                    total_score = result["채점결과"].get("합산_점수")
                    if total_score is not None:
                        valid_scores.append(total_score)
                
                # Add up grading time
                grading_time = result.get("채점_소요_시간", 0)
                if grading_time:
                    total_time += grading_time
        
        average_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
        
        return {
            "total_students": total_students,
            "successful_grades": successful_grades,
            "failed_grades": failed_grades,
            "average_score": round(average_score, 2),
            "total_time": round(total_time, 2)
        }
    
    @staticmethod
    def filter_valid_results(graded_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out results with errors for dashboard visualization.
        
        Args:
            graded_results: List of grading result dictionaries
            
        Returns:
            list: Filtered results without errors
        """
        return [
            result for result in graded_results 
            if "오류" not in result or pd.isna(result.get("오류")) or not result.get("오류")
        ]