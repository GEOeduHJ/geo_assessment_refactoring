from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
from langchain_core.embeddings import Embeddings
import streamlit as st

def get_retriever(vector_db: FAISS, k: int = 3):
    """
    FAISS 벡터 DB로부터 Retriever를 생성합니다.
    """
    return vector_db.as_retriever(search_kwargs={"k": k})

def retrieve_documents(retriever, query: str, student_name: str) -> list[Document]:
    """
    주어진 쿼리에 대해 관련 문서를 검색합니다.
    """
    if not retriever:
        st.error("Retriever가 초기화되지 않았습니다.")
        return []
    
    with st.spinner(f"{student_name} 학생의 답안과 관련된 문서를 검색 중..."):
        try:
            docs = retriever.invoke(query)
            st.success(f"{student_name} 학생의 답안과 관련된 {len(docs)}개의 관련 문서를 찾았습니다.")
            return docs
        except Exception as e:
            st.error(f"문서 검색 중 오류 발생: {e}")
            return []

from sentence_transformers import CrossEncoder
import torch


@st.cache_resource
def get_reranker_model():
    """
    Reranker 모델을 로드합니다. GPU가 사용 가능하면 GPU를 사용합니다.
    """
    model_name = "Dongjin-kr/ko-reranker"
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    return CrossEncoder(model_name, device=device)

def rerank_documents(documents: list[Document], query: str) -> list[Document]:
    """
    검색된 문서를 쿼리와의 관련성 기준으로 재정렬합니다. 배치 처리를 사용합니다.
    """
    if not documents:
        return []

    reranker = get_reranker_model()
    
    # 쿼리와 각 문서의 텍스트 쌍을 생성
    pairs = [[query, doc.page_content] for doc in documents]
    
    # CrossEncoder를 사용하여 점수 계산 (배치 처리 적용)
    scores = reranker.predict(pairs, batch_size=32) # 배치 크기 조정 가능
    
    # 문서와 점수를 묶어서 정렬
    scored_documents = sorted(zip(scores, documents), key=lambda x: x[0], reverse=True)
    
    # 점수가 높은 순서대로 문서만 반환
    reranked_docs = [doc for score, doc in scored_documents]
    
    st.info(f"Rerank를 통해 {len(reranked_docs)}개의 문서가 재정렬되었고, 상위 5개가 선택되었습니다.")
    return reranked_docs[:5]
