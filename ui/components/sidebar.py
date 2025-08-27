"""
Sidebar component for the RAG grading platform.
Handles LLM model selection, file uploads, and document processing.
"""
import streamlit as st
from typing import Literal, Optional
from ui.state_manager import StateManager
from services.file_service import FileService
from models.llm_manager import LLMManager


class SidebarComponent:
    """Component for rendering the application sidebar."""
    
    def __init__(self, state_manager: StateManager, file_service: FileService, llm_manager: LLMManager):
        """Initialize the sidebar component."""
        self.state_manager = state_manager
        self.file_service = file_service
        self.llm_manager = llm_manager
    
    def render(self):
        """Render the complete sidebar interface."""
        with st.sidebar:
            self._render_header()
            self._render_llm_selection()
            self._render_file_upload()
            self._render_chunking_section()
            self._render_vector_db_section()
    
    def _render_header(self):
        """Render the sidebar header."""
        st.header("⚙️ 설정")
        st.header("1. LLM 모델 선택 및 데이터 준비")
    
    def _render_llm_selection(self):
        """Render LLM model selection interface."""
        # LLM Provider Selection
        llm_provider = st.selectbox(
            "LLM 모델 제공사 선택", 
            ("GROQ", "OpenAI", "Google"), 
            index=0
        )
        
        # Model Selection based on Provider
        llm_model = ""
        if llm_provider == "GROQ":
            llm_model: Literal['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'openai/gpt-oss-120b', 'openai/gpt-oss-20b', 'qwen/qwen3-32b', 'meta-llama/llama-guard-4-12b'] = st.selectbox(
                "GROQ 모델 선택", 
                ("llama-3.3-70b-versatile", "llama-3.1-8b-instant", 
                 "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3-32b",
                 "meta-llama/llama-guard-4-12b")
            )
        elif llm_provider == "OpenAI":
            llm_model = st.selectbox("OpenAI 모델 선택", ("gpt-5",))
        elif llm_provider == "Google":
            llm_model = st.selectbox("Google Gemini 모델 선택", ("gemini-2.5-pro", "gemini-2.5-flash"))
        
        # Initialize selected LLM
        if llm_model:
            selected_llm = self.llm_manager.get_llm(llm_provider, llm_model)
            self.state_manager.set('selected_llm', selected_llm)
            
            if selected_llm:
                st.success(f"{llm_provider}의 {llm_model} 모델이 선택되었습니다.")
            else:
                st.error(f"{llm_provider}의 {llm_model} 모델 초기화에 실패했습니다. API 키를 확인해주세요.")
    
    def _render_file_upload(self):
        """Render file upload interface for source documents."""
        st.subheader("Source Data 업로드")
        
        uploaded_file = st.file_uploader(
            "문항 개발 시 사용된 원본 자료를 업로드하세요", 
            type=["pdf", "xlsx", "xls", "docx", "doc", "txt"], 
            key="file_uploader"
        )
        
        if uploaded_file is not None:
            success = self.file_service.process_uploaded_file(uploaded_file)
            if success and self.file_service.has_source_documents():
                document_count = self.file_service.get_documents_count()
                if document_count > 0:
                    st.info(f"현재 {document_count}개의 문서가 로드되어 있습니다.")
    
    def _render_chunking_section(self):
        """Render document chunking interface."""
        st.subheader("Chunking 및 Embedding")
        
        if self.file_service.has_source_documents():
            # Chunking parameters
            chunk_size = st.slider("청크 크기", 100, 2000, 1000, 50)
            chunk_overlap = st.slider("청크 오버랩", 0, 500, 200, 50)
            
            # Chunking button
            if st.button("청킹 실행"):
                success = self.file_service.create_chunks(chunk_size, chunk_overlap)
                if success:
                    st.rerun()
            
            # Display chunk count if available
            if self.file_service.has_chunks():
                chunk_count = self.file_service.get_chunks_count()
                st.success(f"총 {chunk_count}개의 청크가 생성되었습니다.")
        else:
            st.info("Source Data가 업로드되면 Chunking 설정이 활성화됩니다.")
    
    def _render_vector_db_section(self):
        """Render vector database creation interface."""
        st.header("2. 벡터 DB 구축")
        
        if self.file_service.has_vector_db():
            st.success("벡터 DB가 준비되었습니다.")
        elif self.file_service.has_chunks():
            if st.button("벡터 DB 구축 또는 로드"):
                success = self.file_service.build_vector_database()
                if success:
                    st.rerun()
        else:
            st.info("청크가 생성되면 벡터 DB를 구축할 수 있습니다.")
    
    def get_sidebar_state(self) -> dict:
        """
        Get current sidebar state for debugging.
        
        Returns:
            dict: Current state of sidebar components
        """
        return {
            "has_source_documents": self.file_service.has_source_documents(),
            "has_chunks": self.file_service.has_chunks(),
            "has_vector_db": self.file_service.has_vector_db(),
            "documents_count": self.file_service.get_documents_count(),
            "chunks_count": self.file_service.get_chunks_count(),
            "selected_llm": bool(self.state_manager.get('selected_llm'))
        }