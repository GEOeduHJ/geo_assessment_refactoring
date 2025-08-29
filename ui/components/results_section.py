"""
Results section component for the RAG grading platform.
Handles display of grading results, detailed views, and Excel export.
Now includes Arrow-compatible display methods for Streamlit Cloud deployment.
"""
import streamlit as st
import pandas as pd
from typing import List, Dict, Any, Optional
from ui.state_manager import StateManager
from services.grading_service import GradingService
from services.export_service import ExportService
from utils.type_conversion import StreamlitCompatibilityMiddleware


class ResultsSectionComponent:
    """Component for rendering the grading results section."""
    
    def __init__(self, state_manager: StateManager, grading_service: GradingService):
        """Initialize the results section component."""
        self.state_manager = state_manager
        self.grading_service = grading_service
        self.export_service = ExportService()
    
    def render(self, question_type: str):
        """
        Render the complete results section interface.
        
        Args:
            question_type: Type of question for proper result formatting
        """
        if not self.grading_service.has_grading_results():
            st.info("채점 결과가 없습니다. 채점을 시작해주세요.")
            return
        
        st.header("5. 최종 결과")
        
        graded_results = self.grading_service.get_grading_results()
        
        # Results summary
        self._render_results_summary(graded_results, question_type)
        
        # Detailed individual results
        self._render_detailed_results(graded_results)
        
        # Dashboard visualization
        self._render_dashboard(graded_results)
        
        # Excel export
        self._render_excel_export(graded_results)
    
    def _render_results_summary(self, graded_results: List[Dict[str, Any]], question_type: str):
        """
        Render the results summary table.
        
        Args:
            graded_results: List of grading result dictionaries
            question_type: Type of question for proper formatting
        """
        st.subheader("채점 결과 요약")
        
        # Get summary statistics
        summary = self.export_service.get_results_summary(graded_results)
        
        # Display summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("총 학생 수", summary["total_students"])
        with col2:
            st.metric("성공한 채점", summary["successful_grades"])
        with col3:
            st.metric("실패한 채점", summary["failed_grades"])
        with col4:
            st.metric("평균 점수", f"{summary['average_score']:.1f}점")
        
        # Format and display results table with Arrow-compatible safe display
        display_df = self.export_service.format_results_for_display(graded_results, question_type)
        
        if not display_df.empty:
            # Use safe display method to handle Arrow conversion issues
            StreamlitCompatibilityMiddleware.safe_streamlit_display(
                display_df, "채점 결과 요약"
            )
        else:
            st.warning("표시할 결과가 없습니다.")
    
    def _render_detailed_results(self, graded_results: List[Dict[str, Any]]):
        """
        Render detailed individual student results.
        
        Args:
            graded_results: List of grading result dictionaries
        """
        st.subheader("개별 학생 채점 결과 상세")
        
        results_df = pd.DataFrame(graded_results)
        
        for index, row in results_df.iterrows():
            with st.expander(f"{row['이름']} 학생의 채점 결과"):
                self._render_individual_result(row)
    
    def _render_individual_result(self, result_row: pd.Series):
        """
        Render an individual student's result.
        
        Args:
            result_row: Single row from results DataFrame
        """
        # Check for errors first
        if "오류" in result_row and pd.notna(result_row["오류"]):
            st.error(f"오류: {result_row['오류']}")
            return
        
        # Display student answer or recognized text
        if "답안" in result_row:
            st.write(f"**학생 답안:** {result_row['답안']}")
        elif "인식된_텍스트" in result_row:
            if isinstance(result_row["인식된_텍스트"], list):
                st.write(f"**인식된 텍스트:** {', '.join(result_row['인식된_텍스트'])}")
            else:
                st.write(f"**인식된 텍스트:** {result_row['인식된_텍스트']}")
        
        # Display grading results
        if "채점결과" in result_row and isinstance(result_row['채점결과'], dict):
            st.write("**채점 결과:**")
            
            # Separate main and sub criteria for better display
            for criterion, score in result_row['채점결과'].items():
                if "세부_채점_요소" in criterion:
                    st.write(f"  - {criterion}: {score}")
                else:
                    st.write(f"- {criterion}: {score}")
            
            # Display scoring rationale if available
            if "점수_판단_근거" in result_row and isinstance(result_row['점수_판단_근거'], dict):
                st.write("**점수 판단 근거:**")
                for criterion, reason in result_row['점수_판단_근거'].items():
                    st.write(f"- {criterion}: {reason}")
            
            # Highlight total score
            total_score = result_row['채점결과'].get('합산_점수', 'N/A')
            st.write(f"**합산 점수:** {total_score}")
        
        # Display feedback
        if "피드백" in result_row and isinstance(result_row['피드백'], dict):
            st.write("**피드백:**")
            st.write(f"- 교과 내용 피드백: {result_row['피드백'].get('교과_내용_피드백', 'N/A')}")
            st.write(f"- 의사 응답 여부: {result_row['피드백'].get('의사_응답_여부', 'N/A')}")
            
            if result_row['피드백'].get('의사_응답_여부', False):
                st.write(f"  - 설명: {result_row['피드백'].get('의사_응답_설명', 'N/A')}")
        
        # Display reference documents
        if "참고문서" in result_row:
            st.write(f"**참고 문서:** {result_row['참고문서']}")
        
        # Display processing time
        if "채점_소요_시간" in result_row:
            st.write(f"**채점 소요 시간:** {result_row['채점_소요_시간']:.2f}초")
    
    def _render_dashboard(self, graded_results: List[Dict[str, Any]]):
        """
        Render dashboard visualization.
        
        Args:
            graded_results: List of grading result dictionaries
        """
        # Filter out results with errors
        valid_results = self.export_service.filter_valid_results(graded_results)
        
        if valid_results:
            st.subheader("대시보드 시각화")
            try:
                from utils.dashboard import display_dashboard
                display_dashboard(valid_results)
            except ImportError:
                st.warning("대시보드 모듈을 찾을 수 없습니다.")
            except Exception as e:
                st.error(f"대시보드 생성 중 오류 발생: {str(e)}")
        else:
            st.info("시각화할 유효한 결과가 없습니다.")
    
    def _render_excel_export(self, graded_results: List[Dict[str, Any]]):
        """
        Render Excel export section.
        
        Args:
            graded_results: List of grading result dictionaries
        """
        st.subheader("Excel 다운로드")
        
        try:
            excel_data = self.export_service.create_excel_download(graded_results)
            
            st.download_button(
                label="채점 결과 Excel 다운로드",
                data=excel_data,
                file_name="graded_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"Excel 파일 생성 중 오류 발생: {str(e)}")
    
    def get_results_section_state(self) -> dict:
        """
        Get current results section state for debugging.
        
        Returns:
            dict: Current state of results section
        """
        graded_results = self.grading_service.get_grading_results()
        summary = self.export_service.get_results_summary(graded_results) if graded_results else {}
        
        return {
            "has_results": self.grading_service.has_grading_results(),
            "results_count": len(graded_results) if graded_results else 0,
            "valid_results_count": self.grading_service.get_valid_results_count(),
            "summary_stats": summary
        }