#!/usr/bin/env python3
"""
Simple test script to verify the DataFrame boolean evaluation fix.
"""
import pandas as pd
import sys
import os
from unittest.mock import patch

# Add current directory to path
sys.path.append('.')

def test_dataframe_fix():
    """Test that the DataFrame boolean evaluation fix works."""
    # Mock streamlit session state
    mock_session_state = {}
    
    with patch('streamlit.session_state', mock_session_state):
        from ui.state_manager import StateManager
        
        # Create StateManager instance
        state_manager = StateManager()
        
        print("=== Testing DataFrame Boolean Evaluation Fix ===")
        
        # Test 1: Non-empty DataFrame
        print("\n1. Testing non-empty DataFrame:")
        test_df = pd.DataFrame({'answers': ['answer1', 'answer2', 'answer3']})
        result = state_manager._is_value_valid(test_df)
        print(f"   Non-empty DataFrame is valid: {result}")
        assert result is True
        
        # Test 2: Empty DataFrame
        print("\n2. Testing empty DataFrame:")
        empty_df = pd.DataFrame()
        result = state_manager._is_value_valid(empty_df)
        print(f"   Empty DataFrame is valid: {result}")
        assert result is False
        
        # Test 3: validate_grading_prerequisites with DataFrame (main test)
        print("\n3. Testing validate_grading_prerequisites with DataFrame:")
        print("   Setting up valid session state...")
        state_manager.set('student_answers_df', test_df)
        state_manager.set('vector_db', 'mock_vector_db')
        state_manager.set('final_rubric', ['rubric_item_1', 'rubric_item_2'])
        state_manager.set('selected_llm', 'mock_llm_model')
        
        print("   Calling validate_grading_prerequisites()...")
        try:
            is_valid, error_msg = state_manager.validate_grading_prerequisites()
            print(f"   Prerequisites validation result: {is_valid}")
            print(f"   Error message: '{error_msg}'")
            assert is_valid is True
            assert error_msg == ""
            print("   ✓ SUCCESS: No ValueError raised!")
        except ValueError as e:
            print(f"   ✗ FAILED: ValueError still occurs: {e}")
            raise
        
        # Test 4: validate_grading_prerequisites with empty DataFrame
        print("\n4. Testing validate_grading_prerequisites with empty DataFrame:")
        state_manager.set('student_answers_df', empty_df)
        is_valid, error_msg = state_manager.validate_grading_prerequisites()
        print(f"   Prerequisites validation result: {is_valid}")
        print(f"   Error message: '{error_msg}'")
        assert is_valid is False
        assert "학생 답안이 로드되지 않았습니다" in error_msg
        print("   ✓ Correctly identified empty DataFrame as invalid")
        
        # Test 5: Other data types
        print("\n5. Testing other data types:")
        test_cases = [
            (None, False, "None"),
            ([], False, "Empty list"),
            ([1, 2, 3], True, "Non-empty list"),
            ({}, False, "Empty dict"),
            ({'key': 'value'}, True, "Non-empty dict"),
            ("", False, "Empty string"),
            ("test", True, "Non-empty string"),
            (0, False, "Zero"),
            (42, True, "Positive number"),
            (False, False, "False boolean"),
            (True, True, "True boolean")
        ]
        
        for value, expected, description in test_cases:
            result = state_manager._is_value_valid(value)
            print(f"   {description}: {result} (expected {expected})")
            assert result == expected
        
        print("\n=== All tests passed! The DataFrame boolean evaluation fix works correctly ===")

if __name__ == "__main__":
    test_dataframe_fix()