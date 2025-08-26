from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
import streamlit as st
import os

def create_vector_db(chunks: list[Document], embeddings_model, db_path: str = "./vector_db/faiss_index"):
    """
    청크와 임베딩 모델을 사용하여 FAISS 벡터 데이터베이스를 생성하고 저장합니다.
    """
    if not chunks:
        st.warning("임베딩할 청크가 없습니다.")
        return None

    st.info("FAISS 벡터 데이터베이스를 구축 중입니다...")
    try:
        vector_db = FAISS.from_documents(chunks, embeddings_model)
        vector_db.save_local(db_path)
        st.success(f"FAISS 벡터 데이터베이스가 '{db_path}'에 성공적으로 구축 및 저장되었습니다.")
        return vector_db
    except Exception as e:
        st.error(f"FAISS 벡터 데이터베이스 구축 중 오류 발생: {e}")
        return None

def load_vector_db(embeddings_model, db_path: str = "./vector_db/faiss_index"):
    """
    저장된 FAISS 벡터 데이터베이스를 로드합니다.
    """
    if not os.path.exists(db_path):
        st.warning(f"'{db_path}' 경로에 저장된 벡터 데이터베이스가 없습니다.")
        return None

    st.info(f"'{db_path}'에서 FAISS 벡터 데이터베이스를 로드 중입니다...")
    try:
        vector_db = FAISS.load_local(db_path, embeddings_model, allow_dangerous_deserialization=True)
        st.success("FAISS 벡터 데이터베이스가 성공적으로 로드되었습니다.")
        return vector_db
    except Exception as e:
        st.error(f"FAISS 벡터 데이터베이스 로드 중 오류 발생: {e}")
        return None
