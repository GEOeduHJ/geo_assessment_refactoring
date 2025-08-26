"""
Centralized session state management for the RAG grading platform.
Handles all Streamlit session state operations in one place.
"""
import streamlit as st
from typing import Any, Dict, Optional


class StateManager:
    """Centralized state management for the Streamlit application."""
    
    def __init__(self):
        """Initialize the state manager and set up default session state."""
        self._initialize_state()
    
    def _initialize_state(self):
        """Initialize session state with default values if not already set."""
        defaults = {
            'initialized': True,
            'selected_llm': None,
            'source_documents': None,
            'uploaded_file_name': None,
            'chunks': None,
            'vector_db': None,
            'final_rubric': [],
            'rubric_items': [],
            'last_question_type': None,
            'student_answers_df': None,
            'uploaded_map_images': None,
            'graded_results': []
        }
        
        for key, default_value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from session state."""
        return st.session_state.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in session state."""
        st.session_state[key] = value
    
    def update(self, **kwargs) -> None:
        """Update multiple session state values at once."""
        st.session_state.update(kwargs)
    
    def has(self, key: str) -> bool:
        """Check if a key exists in session state."""
        return key in st.session_state
    
    def remove(self, key: str) -> None:
        """Remove a key from session state if it exists."""
        if key in st.session_state:
            del st.session_state[key]
    
    def clear_document_data(self) -> None:
        """Clear document-related data when new file is uploaded."""
        keys_to_clear = ['chunks', 'vector_db']
        for key in keys_to_clear:
            self.remove(key)
    
    def clear_grading_data(self) -> None:
        """Clear grading results when starting new grading."""
        self.set('graded_results', [])
    
    def is_file_changed(self, new_filename: str) -> bool:
        """Check if uploaded file is different from current file."""
        current_filename = self.get('uploaded_file_name')
        return current_filename != new_filename
    
    def _is_value_valid(self, value: Any) -> bool:
        """
        Type-safe value validation that handles DataFrames properly.
        
        Args:
            value: The value to validate
            
        Returns:
            bool: True if value is valid (non-empty/non-None), False otherwise
        """
        if value is None:
            return False
        
        # Handle pandas DataFrame specifically to avoid ambiguous truth value error
        if hasattr(value, 'empty'):
            return not value.empty
        
        # Handle collections (list, dict, etc.) but exclude strings
        if hasattr(value, '__len__') and not isinstance(value, str):
            return len(value) > 0
        
        # Handle other types with standard truthiness
        return bool(value)
    
    def validate_grading_prerequisites(self) -> tuple[bool, str]:
        """
        Validate that all prerequisites for grading are met.
        Uses type-safe validation to avoid DataFrame boolean evaluation errors.
        
        Returns:
            tuple: (is_valid, error_message)
        """
        checks = [
            ('vector_db', "벡터 DB가 구축되지 않았습니다."),
            ('student_answers_df', "학생 답안이 로드되지 않았습니다."),
            ('final_rubric', "평가 루브릭이 입력되지 않았습니다."),
            ('selected_llm', "LLM 모델이 선택되지 않았습니다.")
        ]
        
        for key, error_msg in checks:
            value = self.get(key)
            if not self._is_value_valid(value):
                return False, error_msg
        
        return True, ""
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of current state for debugging."""
        summary = {}
        for key in st.session_state:
            value = st.session_state[key]
            if hasattr(value, '__len__') and not isinstance(value, str):
                summary[key] = f"{type(value).__name__} with {len(value)} items"
            else:
                summary[key] = f"{type(value).__name__}: {str(value)[:50]}..."
        return summary