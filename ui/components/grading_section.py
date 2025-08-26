"""
Grading section component for the RAG grading platform.
Handles rubric editing, student answer uploads, and grading initiation.
"""
import streamlit as st
from typing import Optional
from ui.state_manager import StateManager
from services.grading_service import GradingService
from utils.rubric_manager import display_rubric_editor


class GradingSectionComponent:
    """Component for rendering the grading section interface."""
    
    def __init__(self, state_manager: StateManager, grading_service: GradingService):
        """Initialize the grading section component."""
        self.state_manager = state_manager
        self.grading_service = grading_service
    
    def render(self):
        """Render the complete grading section interface."""
        st.header("3. 평가 기준 및 학생 답안 입력")
        
        # Question type selection
        question_type = self._render_question_type_selection()
        
        # Rubric editor
        self._render_rubric_editor(question_type)
        
        # Student answers upload
        self._render_student_answers_upload()
        
        # Map images upload (for map questions)
        if question_type == "백지도":
            self._render_map_images_upload()
        
        # Grading start section
        self._render_grading_section(question_type)
    
    def _render_question_type_selection(self) -> str:
        """
        Render question type selection interface.
        
        Returns:
            str: Selected question type
        """
        question_type = st.radio("문항 유형 선택", ("서술형", "백지도"))
        st.info(f"선택된 문항 유형: {question_type}")
        return question_type
    
    def _render_rubric_editor(self, question_type: str):
        """
        Render the rubric editor interface.
        
        Args:
            question_type: Type of question for rubric initialization
        """
        # Use the existing rubric manager for rubric editing
        display_rubric_editor(question_type)
    
    def _render_student_answers_upload(self):
        """Render student answers upload interface."""
        st.subheader("학생 답안 업로드")
        
        uploaded_student_answers = st.file_uploader(
            "학생 답안 Excel 파일을 업로드하세요", 
            type=["xlsx", "xls"], 
            key="student_answers_uploader"
        )
        
        if uploaded_student_answers:
            success = self.grading_service.load_student_answers(uploaded_student_answers)
            if success:
                # Display the loaded student answers
                student_answers_df = self.state_manager.get('student_answers_df')
                if student_answers_df is not None:
                    st.dataframe(student_answers_df)
    
    def _render_map_images_upload(self):
        """Render map images upload interface for map-type questions."""
        uploaded_map_images = st.file_uploader(
            "학생 백지도 이미지 파일을 업로드하세요 (PNG, JPG)", 
            type=["png", "jpg", "jpeg"], 
            accept_multiple_files=True, 
            key="map_image_uploader"
        )
        
        if uploaded_map_images:
            self.grading_service.load_map_images(uploaded_map_images)
    
    def _render_grading_section(self, question_type: str):
        """
        Render the grading initiation section.
        
        Args:
            question_type: Type of question being graded
        """
        st.header("4. RAG 기반 유사 문서 검색 및 채점")
        
        if st.button("채점 시작"):
            self._handle_grading_start(question_type)
    
    def _handle_grading_start(self, question_type: str):
        """
        Handle the grading start process.
        
        Args:
            question_type: Type of question being graded
        """
        # Validate prerequisites before starting grading
        is_valid, error_msg = self.grading_service.validate_grading_prerequisites(question_type)
        
        if not is_valid:
            st.error(error_msg)
            return
        
        # Show student count information
        student_answers_df = self.state_manager.get('student_answers_df')
        if student_answers_df is not None and not student_answers_df.empty:
            total_students = len(student_answers_df)
            st.info(f"총 {total_students}명의 학생 답안을 처리합니다.")
            
            # Start the grading process
            success = self.grading_service.start_grading(question_type)
            
            if success:
                st.success("채점이 완료되었습니다!")
                # Trigger rerun to show results
                st.rerun()
            else:
                st.error("채점 중 오류가 발생했습니다.")
        else:
            st.error("학생 답안이 로드되지 않았습니다.")
    
    def has_rubric(self) -> bool:
        """Check if rubric is configured."""
        rubric = self.state_manager.get('final_rubric', [])
        return bool(rubric and len(rubric) > 0)
    
    def has_student_answers(self) -> bool:
        """Check if student answers are loaded."""
        student_answers_df = self.state_manager.get('student_answers_df')
        return student_answers_df is not None and not student_answers_df.empty
    
    def get_student_count(self) -> int:
        """Get the number of loaded students."""
        student_answers_df = self.state_manager.get('student_answers_df')
        if student_answers_df is not None:
            return len(student_answers_df)
        return 0
    
    def get_grading_section_state(self) -> dict:
        """
        Get current grading section state for debugging.
        
        Returns:
            dict: Current state of grading section components
        """
        return {
            "has_rubric": self.has_rubric(),
            "has_student_answers": self.has_student_answers(),
            "student_count": self.get_student_count(),
            "has_map_images": bool(self.state_manager.get('uploaded_map_images')),
            "has_grading_results": self.grading_service.has_grading_results()
        }