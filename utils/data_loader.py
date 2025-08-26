import streamlit as st
from langchain_community.document_loaders import PyPDFLoader, UnstructuredExcelLoader, UnstructuredWordDocumentLoader, TextLoader
from langchain.docstore.document import Document
import os

def load_document(uploaded_file):
    """
    업로드된 파일을 기반으로 문서를 로드합니다. UI 피드백 없이 데이터 처리만 수행합니다.
    지원 형식: PDF, Excel, Word, Text
    """
    if uploaded_file is not None:
        file_type = uploaded_file.type
        file_name = uploaded_file.name
        
        # 데이터 디렉토리 확인 및 생성
        data_dir = "./data"
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        file_path = os.path.join(data_dir, file_name)

        # 임시 파일로 저장
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        loader = None
        if file_type == "application/pdf":
            loader = PyPDFLoader(file_path)
        elif file_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel"]:
            loader = UnstructuredExcelLoader(file_path)
        elif file_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
            loader = UnstructuredWordDocumentLoader(file_path)
        elif file_type == "text/plain":
            loader = TextLoader(file_path)
        
        if loader is None:
            print(f"Unsupported file type: {file_type}")
            return []

        try:
            documents = loader.load()
            return documents
        except Exception as e:
            print(f"Error loading document '{file_name}': {e}")
            return []
    return []
