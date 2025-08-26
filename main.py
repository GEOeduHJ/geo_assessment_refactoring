import streamlit as st
from utils.data_loader import load_document
from utils.text_splitter import split_documents
from utils.embedding import get_embedding_model
from utils.vector_db import create_vector_db, load_vector_db
from models.llm_manager import LLMManager
from utils.rubric_manager import display_rubric_editor
from utils.student_answer_loader import load_student_answers
from utils.retrieval import get_retriever, retrieve_documents, rerank_documents
from prompts.prompt_templates import get_grading_prompt
from utils.map_item import grade_map_question # 백지도 채점 모듈 임포트
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import io
import time

"""
Simplified main.py entry point for the RAG grading platform.
This file has been refactored from 387 lines to under 50 lines.

The original complex logic has been extracted into modular components:
- UI components (sidebar, grading section, results section)
- Service layer (file service, grading service, export service)
- Core logic (grading pipeline, dynamic models)
- State management (centralized session state)
"""
import streamlit as st
from ui.app import GradingApp, set_app_instance


def main():
    """
    Main entry point for the Streamlit application.
    
    This function initializes the page configuration and runs the main application.
    All complex logic has been moved to the GradingApp class and its components.
    """
    # Set page configuration
    st.set_page_config(
        layout="wide", 
        page_title="RAG 기반 지리과 서답형 자동채점 플랫폼"
    )
    
    # Initialize and run the application
    app = GradingApp()
    set_app_instance(app)  # For debugging purposes
    
    # Run the application
    app.run()


if __name__ == "__main__":
    main()


# Refactoring Summary:
# ===================
# Original main.py: 387 lines with mixed responsibilities
# New main.py: ~40 lines with single responsibility (entry point)
# 
# Code has been modularized into:
# 1. ui/app.py - Main application orchestrator
# 2. ui/state_manager.py - Centralized session state management
# 3. ui/components/ - Modular UI components
# 4. services/ - Business logic layer
# 5. core/ - Core grading algorithms and models
#
# Benefits:
# - Improved maintainability and readability
# - Better separation of concerns
# - Easier testing and debugging
# - Enhanced modularity and reusability
