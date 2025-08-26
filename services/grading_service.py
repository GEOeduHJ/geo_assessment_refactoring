"""
Grading service for handling the grading workflow and validation.
Coordinates the grading process and manages validation logic.
"""
import streamlit as st
import time
from typing import List, Dict, Any, Optional
from ui.state_manager import StateManager
from core.dynamic_models import DynamicModelFactory
from utils.retrieval import get_retriever
from utils.student_answer_loader import load_student_answers
from utils.map_item import grade_map_question


class GradingService:
    """Service for handling grading operations and workflow."""
    
    def __init__(self, state_manager: StateManager, llm_manager):
        """Initialize the grading service."""
        self.state_manager = state_manager
        self.llm_manager = llm_manager
    
    def load_student_answers(self, uploaded_file) -> bool:
        """
        Load student answers from uploaded Excel file.
        
        Args:
            uploaded_file: Streamlit uploaded file object
            
        Returns:
            bool: True if loading was successful, False otherwise
        """
        if uploaded_file is None:
            return False
        
        try:
            student_answers_df = load_student_answers(uploaded_file)
            if student_answers_df is not None:
                self.state_manager.set('student_answers_df', student_answers_df)
                st.success("학생 답안이 성공적으로 로드되었습니다.")
                return True
            else:
                st.error("학생 답안 로드에 실패했습니다.")
                return False
        except Exception as e:
            st.error(f"학생 답안 로드 중 오류 발생: {str(e)}")
            return False
    
    def load_map_images(self, uploaded_images) -> bool:
        """
        Load map images for map-type questions.
        
        Args:
            uploaded_images: List of uploaded image files
            
        Returns:
            bool: True if loading was successful, False otherwise
        """
        if not uploaded_images:
            return False
        
        try:
            self.state_manager.set('uploaded_map_images', uploaded_images)
            st.success(f"{len(uploaded_images)}개의 백지도 이미지가 로드되었습니다.")
            return True
        except Exception as e:
            st.error(f"백지도 이미지 로드 중 오류 발생: {str(e)}")
            return False
    
    def validate_grading_prerequisites(self, question_type: str) -> tuple[bool, str]:
        """
        Validate that all prerequisites for grading are met.
        
        Args:
            question_type: Type of question ("서술형" or "백지도")
            
        Returns:
            tuple: (is_valid, error_message)
        """
        is_valid, error_msg = self.state_manager.validate_grading_prerequisites()
        
        if not is_valid:
            return False, error_msg
        
        # Additional validation for map questions
        if question_type == "백지도":
            if not self.state_manager.get('uploaded_map_images'):
                return False, "백지도 이미지 파일이 로드되지 않았습니다."
        
        # Check if student answers DataFrame is empty
        student_answers_df = self.state_manager.get('student_answers_df')
        if student_answers_df is None or student_answers_df.empty:
            return False, "학생 답안이 로드되지 않았습니다."
        
        return True, ""
    
    def start_grading(self, question_type: str) -> bool:
        """
        Start the grading process for all students.
        
        Args:
            question_type: Type of question ("서술형" or "백지도")
            
        Returns:
            bool: True if grading was successful, False otherwise
        """
        # Validate prerequisites
        is_valid, error_msg = self.validate_grading_prerequisites(question_type)
        if not is_valid:
            st.error(error_msg)
            return False
        
        try:
            # Clear previous results
            self.state_manager.clear_grading_data()
            
            # Get required data from state
            student_answers_df = self.state_manager.get('student_answers_df')
            rubric = self.state_manager.get('final_rubric')
            llm = self.state_manager.get('selected_llm')
            vector_db = self.state_manager.get('vector_db')
            
            # Create dynamic parser based on rubric
            dynamic_parser = DynamicModelFactory.create_parser(rubric)
            
            # Set up progress tracking
            total_students = len(student_answers_df)
            progress_bar = st.progress(0)
            graded_results = []
            
            st.info(f"총 {total_students}명의 학생 답안을 채점합니다...")
            start_time = time.time()
            
            # Import grading pipeline here to avoid circular imports
            from core.grading_pipeline import GradingPipeline
            grading_pipeline = GradingPipeline(self.llm_manager, get_retriever(vector_db, k=10))
            
            # Process each student sequentially
            for i, (index, row) in enumerate(student_answers_df.iterrows()):
                student_name = row["이름"]
                
                if question_type == "백지도":
                    result = self._grade_map_question(student_name, rubric, dynamic_parser)
                else:
                    if "답안" not in row:
                        result = {"이름": student_name, "오류": f"{student_name} 학생의 답안 컬럼이 누락되었습니다."}
                    else:
                        student_answer = row["답안"]
                        result = grading_pipeline.process_student_answer(
                            student_name, student_answer, rubric, question_type, dynamic_parser
                        )
                
                graded_results.append(result)
                progress_bar.progress((i + 1) / total_students)
            
            # Save results to state
            self.state_manager.set('graded_results', graded_results)
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            st.success(f"모든 학생 답안 채점 완료! (총 소요 시간: {elapsed_time:.2f}초)")
            
            return True
            
        except Exception as e:
            st.error(f"채점 중 오류 발생: {str(e)}")
            return False
    
    def _grade_map_question(self, student_name: str, rubric: List[Dict], dynamic_parser) -> Dict[str, Any]:
        """
        Grade a map question for a specific student.
        
        Args:
            student_name: Name of the student
            rubric: Grading rubric
            dynamic_parser: Parser for grading results
            
        Returns:
            dict: Grading result for the student
        """
        uploaded_map_images = self.state_manager.get('uploaded_map_images', [])
        
        # Find the corresponding image for the student
        uploaded_image = None
        for img in uploaded_map_images:
            # Assuming image filename (without extension) matches student name
            if img.name.split('.')[0] == student_name:
                uploaded_image = img
                break
        
        if uploaded_image is None:
            return {"이름": student_name, "오류": f"{student_name} 학생의 백지도 이미지를 찾을 수 없습니다."}
        
        try:
            start_time_student = time.time()
            result = grade_map_question(
                student_name=student_name,
                uploaded_image=uploaded_image,
                rubric=rubric,
                parser=dynamic_parser
            )
            end_time_student = time.time()
            
            # Add timing information if grading was successful
            if "오류" not in result:
                result['채점_소요_시간'] = end_time_student - start_time_student
            
            return result
            
        except Exception as e:
            return {"이름": student_name, "오류": f"백지도 채점 중 오류 발생: {str(e)}"}
    
    def get_grading_results(self) -> Optional[List[Dict[str, Any]]]:
        """Get the current grading results."""
        return self.state_manager.get('graded_results')
    
    def has_grading_results(self) -> bool:
        """Check if grading results are available."""
        results = self.get_grading_results()
        return bool(results and len(results) > 0)
    
    def get_valid_results_count(self) -> int:
        """Get the number of valid (error-free) grading results."""
        results = self.get_grading_results()
        if not results:
            return 0
        
        valid_count = sum(1 for result in results if "오류" not in result or not result.get("오류"))
        return valid_count