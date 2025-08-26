from langchain_huggingface import HuggingFaceEmbeddings
from langchain.docstore.document import Document
import streamlit as st

@st.cache_resource
def get_embedding_model():
    """
    Hugging Face 임베딩 모델을 로드합니다.
    """
    model_name = "sentence-transformers/static-similarity-mrl-multilingual-v1"
    model_kwargs = {'device': 'cpu'}
    encode_kwargs = {'normalize_embeddings': True}
    hf_embeddings = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs
    )
    return hf_embeddings

def embed_documents(documents: list[Document], embeddings_model) -> list[list[float]]:
    """
    문서 리스트를 임베딩합니다.
    """
    texts = [doc.page_content for doc in documents]
    embedded_docs = embeddings_model.embed_documents(texts)
    return embedded_docs
