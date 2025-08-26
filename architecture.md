# 프로젝트 아키텍처: RAG 기반 지리과 서답형 자동 채점 플랫폼

## 1. 시스템 개요
본 플랫폼은 RAG(검색 증강 생성) 기술과 LLM(대규모 언어 모델)을 결합하여, 지리 교과의 서답형 문항을 자동으로 채점하고 학생들에게 맞춤형 피드백을 제공합니다. 사용자는 Streamlit으로 구현된 웹 인터페이스를 통해 학습 자료, 채점 기준, 학생 답안을 입력하고, 시스템의 모든 채점 과정을 직관적으로 제어하며 결과를 분석할 수 있습니다.

## 2. 사용자 워크플로우 (Streamlit UI 기준)
사용자는 `main.py`가 실행하는 Streamlit 웹 앱에서 다음의 순서로 작업을 수행합니다. 각 단계는 특정 모듈과 유기적으로 상호작용합니다.

### **1단계: 환경 설정**
- **위치**: 사이드바 (`st.sidebar`)
- **사용자 작업**:
    1.  사용할 LLM 모델(예: `gpt-4o`, `claude-3-opus-20240229`)을 드롭다운 메뉴에서 선택합니다.
    2.  선택한 모델에 필요한 API 키를 입력합니다.
- **백엔드 모듈**:
    -   `models/llm_manager.py`: 사용자가 선택한 모델 이름과 API 키를 받아 해당 LLM과 통신할 수 있는 객체를 생성하고, 이를 세션 상태(`st.session_state`)에 저장하여 앱 전반에서 사용 가능하게 합니다.

### **2단계: 지식 기반 구축 (Vector DB 생성)**
- **위치**: 메인 화면
- **사용자 작업**:
    1.  `st.file_uploader`를 통해 채점의 근거가 될 원본 학습 자료(PDF, DOCX, TXT 등)를 업로드합니다.
    2.  '벡터 DB 생성' 버튼을 클릭합니다.
- **백엔드 모듈**:
    -   `utils/data_loader.py`: 업로드된 파일을 읽어 텍스트 콘텐츠를 추출합니다.
    -   `utils/text_splitter.py`: 추출된 텍스트를 의미 있는 단위의 청크(chunk)로 분할합니다.
    -   `utils/embedding.py`: **HuggingFace의 `sentence-transformers` 모델**을 사용하여 텍스트 청크를 고차원 벡터로 변환(임베딩)합니다.
    -   `utils/vector_db.py`: 임베딩된 벡터들을 FAISS 인덱스에 저장하여 검색 가능한 벡터 데이터베이스를 구축합니다. 생성된 인덱스는 `vector_db/` 디렉토리에 저장되어 재사용됩니다.

### **3단계: 채점 기준 설정 (루브릭 관리)**
- **위치**: 메인 화면
- **사용자 작업**:
    1.  `st.data_editor`를 사용하여 채점 기준(루브릭)을 직접 입력, 수정, 삭제합니다. 각 기준은 '채점 요소', '만점', '상세 설명'으로 구성됩니다.
- **백엔드 모듈**:
    -   `utils/rubric_manager.py`: 사용자가 편집하는 루브릭 데이터를 `st.session_state`에 실시간으로 저장하고 관리합니다.

### **4단계: 학생 답안 업로드**
- **위치**: 메인 화면
- **사용자 작업**:
    1.  채점할 문항 유형('서술형', '백지도형')을 선택합니다.
    2.  유형에 맞는 학생 답안 파일을 `st.file_uploader`로 업로드합니다. (서술형: Excel, 백지도형: 이미지 파일)
- **백엔드 모듈**:
    -   `utils/student_answer_loader.py`: Excel 파일을 읽어 학생들의 텍스트 답안을 데이터프레임으로 변환합니다.
    -   `utils/map_item.py`: 백지도 이미지 파일을 처리할 준비를 합니다.

### **5단계: 자동 채점 실행**
- **위치**: 메인 화면
- **사용자 작업**: '채점 시작' 버튼을 클릭하여 전체 채점 프로세스를 시작합니다.
- **백엔드 모듈 (RAG 파이프라인)**:
    1.  **검색 및 순위 재조정 (Retrieval & Reranking)**: `utils/retrieval.py`가 학생 답안을 쿼리로 사용하여 **Vector DB**에서 관련 문서 청크를 1차적으로 검색한 후, **`Dongjin-kr/ko-reranker` 모델**을 통해 관련성 높은 순으로 문서 순위를 재조정(Re-ranking)합니다.
    2.  **증강 (Augmentation)**: `prompts/prompt_templates.py`가 재조정된 문서, 3단계의 루브릭, 학생 답안을 조합하여 LLM에게 전달할 상세한 프롬프트를 동적으로 생성합니다.
        -   **백지도 채점**: `utils/map_item.py`이 **Google Gemini (gemini-2.5-flash) 모델**을 직접 호출하여 이미지와 텍스트를 함께 분석하고, 이를 기반으로 프롬프트를 구성합니다.
    3.  **생성 (Generation)**: `models/llm_manager.py`가 최종 프롬프트를 1단계에서 설정한 **LLM**에 전달하고, 채점 결과(점수, 피드백, 근거)가 포함된 구조화된 JSON 응답을 받습니다.

### **6단계: 결과 확인 및 분석**
- **위치**: 메인 화면
- **사용자 작업**:
    1.  채점이 완료된 결과를 실시간으로 테이블에서 확인합니다.
    2.  '상세 결과 보기'를 통해 개별 학생의 상세 피드백, 점수 근거, 참고 문서를 조회합니다.
    3.  '대시보드' 탭으로 이동하여 전체 학생의 점수 분포, 문항별 평균 등 시각화된 통계 자료를 분석합니다.
    4.  '결과 다운로드' 버튼을 클릭하여 모든 채점 결과를 Excel 파일로 저장합니다.
- **백엔드 모듈**:
    -   `main.py`: LLM으로부터 받은 채점 결과를 데이터프레임에 누적하고 `st.dataframe`으로 표시합니다.
    -   `utils/dashboard.py`: 저장된 채점 결과를 바탕으로 Plotly 차트를 생성하여 `st.plotly_chart`로 시각화합니다.

## 3. 핵심 구성 요소 역할 요약
- **`main.py`**: Streamlit UI 렌더링, 사용자 입력 처리, 세션 상태 관리, 전체 워크플로우 오케스트레이션.
- **`models/llm_manager.py`**: 여러 LLM(OpenAI, Gemini 등) API와의 연동을 표준화하고 관리.
- **`prompts/prompt_templates.py`**: LLM의 출력을 안정적이고 일관된 JSON 형식으로 유도하기 위한 프롬프트 템플릿 관리.
- **`utils/`**:
    -   `data_loader.py`, `text_splitter.py`, `embedding.py`, `vector_db.py`: RAG의 **Indexing** 파이프라인 구성. (`embedding.py`는 HuggingFace 모델 사용)
    -   `retrieval.py`: RAG의 **Retrieval** 및 **Reranking** 단계 담당. (`Dongjin-kr/ko-reranker` 모델 사용)
    -   `rubric_manager.py`, `student_answer_loader.py`: 사용자 입력(루브릭, 답안) 처리.
    -   `map_item.py`: Gemini 멀티모달 모델을 이용한 이미지 기반 채점 특수 처리.
    -   `dashboard.py`: 결과 데이터 시각화.
- **`vector_db/`**: FAISS 인덱스 파일(`index.faiss`, `index.pkl`) 영구 저장.