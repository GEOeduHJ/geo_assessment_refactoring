"""
Unit tests for the DataFrame boolean evaluation fix in StateManager.

Tests verify that the _is_value_valid() method handles different data types correctly
and that validate_grading_prerequisites() no longer raises ValueError with DataFrames.
"""
import unittest
import pandas as pd
import streamlit as st
from unittest.mock import patch, MagicMock

# Import the StateManager class
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'ui'))
from ui.state_manager import StateManager


class TestStateManagerFix(unittest.TestCase):
    """Test cases for the DataFrame boolean evaluation fix."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock streamlit session state
        self.mock_session_state = {}
        
        # Patch streamlit session state
        self.session_state_patcher = patch('streamlit.session_state', self.mock_session_state)
        self.session_state_patcher.start()
        
        # Create StateManager instance
        self.state_manager = StateManager()
    
    def tearDown(self):
        """Clean up after tests."""
        self.session_state_patcher.stop()
    
    def test_is_value_valid_with_none(self):
        """Test that None values are considered invalid."""
        result = self.state_manager._is_value_valid(None)
        self.assertFalse(result)
    
    def test_is_value_valid_with_empty_dataframe(self):
        """Test that empty DataFrames are considered invalid."""
        empty_df = pd.DataFrame()
        result = self.state_manager._is_value_valid(empty_df)
        self.assertFalse(result)
    
    def test_is_value_valid_with_non_empty_dataframe(self):
        """Test that non-empty DataFrames are considered valid."""
        data_df = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
        result = self.state_manager._is_value_valid(data_df)
        self.assertTrue(result)
    
    def test_is_value_valid_with_empty_list(self):
        """Test that empty lists are considered invalid."""
        result = self.state_manager._is_value_valid([])
        self.assertFalse(result)
    
    def test_is_value_valid_with_non_empty_list(self):
        """Test that non-empty lists are considered valid."""
        result = self.state_manager._is_value_valid([1, 2, 3])
        self.assertTrue(result)
    
    def test_is_value_valid_with_empty_dict(self):
        """Test that empty dictionaries are considered invalid."""
        result = self.state_manager._is_value_valid({})
        self.assertFalse(result)
    
    def test_is_value_valid_with_non_empty_dict(self):
        """Test that non-empty dictionaries are considered valid."""
        result = self.state_manager._is_value_valid({'key': 'value'})
        self.assertTrue(result)
    
    def test_is_value_valid_with_empty_string(self):
        """Test that empty strings are considered invalid."""
        result = self.state_manager._is_value_valid("")
        self.assertFalse(result)
    
    def test_is_value_valid_with_non_empty_string(self):
        """Test that non-empty strings are considered valid."""
        result = self.state_manager._is_value_valid("test")
        self.assertTrue(result)
    
    def test_is_value_valid_with_zero(self):
        """Test that zero is considered invalid (falsy)."""
        result = self.state_manager._is_value_valid(0)
        self.assertFalse(result)
    
    def test_is_value_valid_with_positive_number(self):
        """Test that positive numbers are considered valid."""
        result = self.state_manager._is_value_valid(42)
        self.assertTrue(result)
    
    def test_is_value_valid_with_false(self):
        """Test that False is considered invalid."""
        result = self.state_manager._is_value_valid(False)
        self.assertFalse(result)
    
    def test_is_value_valid_with_true(self):
        """Test that True is considered valid."""
        result = self.state_manager._is_value_valid(True)
        self.assertTrue(result)
    
    def test_is_value_valid_with_mock_object(self):
        """Test that mock objects are considered valid."""
        mock_obj = MagicMock()
        result = self.state_manager._is_value_valid(mock_obj)
        self.assertTrue(result)
    
    def test_validate_grading_prerequisites_with_dataframe_no_error(self):
        """Test that prerequisites validation with DataFrame doesn't raise ValueError."""
        # Setup state with valid DataFrame and other required objects
        valid_df = pd.DataFrame({'answers': ['answer1', 'answer2']})
        mock_vector_db = MagicMock()
        mock_llm = MagicMock()
        
        self.state_manager.set('student_answers_df', valid_df)
        self.state_manager.set('vector_db', mock_vector_db)
        self.state_manager.set('final_rubric', ['rubric_item'])
        self.state_manager.set('selected_llm', mock_llm)
        
        # This should not raise a ValueError
        try:
            is_valid, error_msg = self.state_manager.validate_grading_prerequisites()
            self.assertTrue(is_valid)
            self.assertEqual(error_msg, "")
        except ValueError as e:
            self.fail(f"validate_grading_prerequisites() raised ValueError: {e}")
    
    def test_validate_grading_prerequisites_with_empty_dataframe(self):
        """Test prerequisites validation fails with empty DataFrame."""
        empty_df = pd.DataFrame()
        mock_vector_db = MagicMock()
        mock_llm = MagicMock()
        
        self.state_manager.set('student_answers_df', empty_df)
        self.state_manager.set('vector_db', mock_vector_db)
        self.state_manager.set('final_rubric', ['rubric_item'])
        self.state_manager.set('selected_llm', mock_llm)
        
        is_valid, error_msg = self.state_manager.validate_grading_prerequisites()
        self.assertFalse(is_valid)
        self.assertIn("학생 답안이 로드되지 않았습니다", error_msg)
    
    def test_validate_grading_prerequisites_missing_vector_db(self):
        """Test prerequisites validation fails when vector_db is missing."""
        valid_df = pd.DataFrame({'answers': ['answer1', 'answer2']})
        mock_llm = MagicMock()
        
        self.state_manager.set('student_answers_df', valid_df)
        self.state_manager.set('vector_db', None)
        self.state_manager.set('final_rubric', ['rubric_item'])
        self.state_manager.set('selected_llm', mock_llm)
        
        is_valid, error_msg = self.state_manager.validate_grading_prerequisites()
        self.assertFalse(is_valid)
        self.assertIn("벡터 DB가 구축되지 않았습니다", error_msg)
    
    def test_validate_grading_prerequisites_missing_rubric(self):
        """Test prerequisites validation fails when rubric is empty."""
        valid_df = pd.DataFrame({'answers': ['answer1', 'answer2']})
        mock_vector_db = MagicMock()
        mock_llm = MagicMock()
        
        self.state_manager.set('student_answers_df', valid_df)
        self.state_manager.set('vector_db', mock_vector_db)
        self.state_manager.set('final_rubric', [])
        self.state_manager.set('selected_llm', mock_llm)
        
        is_valid, error_msg = self.state_manager.validate_grading_prerequisites()
        self.assertFalse(is_valid)
        self.assertIn("평가 루브릭이 입력되지 않았습니다", error_msg)
    
    def test_validate_grading_prerequisites_missing_llm(self):
        """Test prerequisites validation fails when LLM is not selected."""
        valid_df = pd.DataFrame({'answers': ['answer1', 'answer2']})
        mock_vector_db = MagicMock()
        
        self.state_manager.set('student_answers_df', valid_df)
        self.state_manager.set('vector_db', mock_vector_db)
        self.state_manager.set('final_rubric', ['rubric_item'])
        self.state_manager.set('selected_llm', None)
        
        is_valid, error_msg = self.state_manager.validate_grading_prerequisites()
        self.assertFalse(is_valid)
        self.assertIn("LLM 모델이 선택되지 않았습니다", error_msg)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)