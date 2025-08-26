"""
File service for handling document uploads and processing.
Manages document loading, chunking, and vector database creation.
"""
import streamlit as st
from typing import Optional, List, Any
from utils.data_loader import load_document
from utils.text_splitter import split_documents
from utils.embedding import get_embedding_model
from utils.vector_db import create_vector_db, load_vector_db
from ui.state_manager import StateManager


class FileService:
    """Service for handling file operations and document processing."""
    
    def __init__(self, state_manager: StateManager):
        """Initialize the file service with state manager."""
        self.state_manager = state_manager
        self.embedding_model = get_embedding_model()
    
    def process_uploaded_file(self, uploaded_file) -> bool:
        """
        Process an uploaded source document file.
        
        Args:
            uploaded_file: Streamlit uploaded file object
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        if uploaded_file is None:
            return False
        
        # Check if this is a new file
        if not self.state_manager.is_file_changed(uploaded_file.name):
            return True  # File already processed
        
        try:
            with st.spinner("파일 처리 중..."):
                documents = load_document(uploaded_file)
                
                if documents:
                    self.state_manager.update(
                        source_documents=documents,
                        uploaded_file_name=uploaded_file.name
                    )
                    # Clear dependent data when new file is uploaded
                    self.state_manager.clear_document_data()
                    
                    st.success(f"'{uploaded_file.name}'에서 {len(documents)}개의 문서를 로드했습니다.")
                    return True
                else:
                    st.error(f"'{uploaded_file.name}' 파일 처리 중 오류가 발생했습니다.")
                    return False
                    
        except Exception as e:
            st.error(f"파일 처리 중 오류 발생: {str(e)}")
            return False
    
    def create_chunks(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> bool:
        """
        Create document chunks from loaded documents.
        
        Args:
            chunk_size: Size of each chunk
            chunk_overlap: Overlap between chunks
            
        Returns:
            bool: True if chunking was successful, False otherwise
        """
        source_documents = self.state_manager.get('source_documents')
        
        if not source_documents:
            st.error("문서가 로드되지 않았습니다. 먼저 문서를 업로드해주세요.")
            return False
        
        try:
            with st.spinner("문서를 청크로 분할 중..."):
                chunks = split_documents(source_documents, chunk_size, chunk_overlap)
                self.state_manager.set('chunks', chunks)
                st.success(f"총 {len(chunks)}개의 청크가 생성되었습니다.")
                return True
                
        except Exception as e:
            st.error(f"청크 생성 중 오류 발생: {str(e)}")
            return False
    
    def build_vector_database(self) -> bool:
        """
        Build or load vector database from chunks.
        
        Returns:
            bool: True if vector DB creation/loading was successful, False otherwise
        """
        chunks = self.state_manager.get('chunks')
        
        if not chunks:
            st.error("청크가 생성되지 않았습니다. 먼저 청킹을 실행해주세요.")
            return False
        
        try:
            with st.spinner("벡터 DB 처리 중..."):
                # Try to load existing vector DB first
                vector_db = load_vector_db(self.embedding_model)
                
                if vector_db is None:
                    # Create new vector DB if none exists
                    vector_db = create_vector_db(chunks, self.embedding_model)
                
                if vector_db:
                    self.state_manager.set('vector_db', vector_db)
                    st.success("벡터 DB가 준비되었습니다.")
                    return True
                else:
                    st.error("벡터 DB 처리 중 오류가 발생했습니다.")
                    return False
                    
        except Exception as e:
            st.error(f"벡터 DB 구축 중 오류 발생: {str(e)}")
            return False
    
    def has_source_documents(self) -> bool:
        """Check if source documents are loaded."""
        return bool(self.state_manager.get('source_documents'))
    
    def has_chunks(self) -> bool:
        """Check if chunks are created."""
        return bool(self.state_manager.get('chunks'))
    
    def has_vector_db(self) -> bool:
        """Check if vector database is ready."""
        return bool(self.state_manager.get('vector_db'))
    
    def get_documents_count(self) -> int:
        """Get number of loaded documents."""
        documents = self.state_manager.get('source_documents', [])
        return len(documents) if documents else 0
    
    def get_chunks_count(self) -> int:
        """Get number of created chunks."""
        chunks = self.state_manager.get('chunks', [])
        return len(chunks) if chunks else 0