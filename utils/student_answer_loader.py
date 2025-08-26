import streamlit as st
import pandas as pd

def load_student_answers(uploaded_file):
    """
    업로드된 Excel 파일에서 학생 답안을 로드하고 파싱합니다.
    """
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            required_columns = ["이름", "학년", "반", "번호"]
            if not all(col in df.columns for col in required_columns):
                st.error(f"필수 컬럼이 누락되었습니다. 다음 컬럼이 필요합니다: {', '.join(required_columns)}")
                return None
            st.success(f"{len(df)}명의 학생 답안이 성공적으로 로드되었습니다.")
            return df
        except Exception as e:
            st.error(f"학생 답안 Excel 파일 로드 중 오류 발생: {e}")
            return None
    return None
