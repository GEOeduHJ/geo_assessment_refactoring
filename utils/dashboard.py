import streamlit as st
import pandas as pd
import plotly.express as px
import io

def display_dashboard(graded_results: list):
    """
    채점 결과를 바탕으로 대시보드를 시각화합니다.
    학생 개별 데이터 및 반 전체 평균 데이터를 표시합니다.
    """
    if not graded_results:
        st.info("시각화할 채점 결과가 없습니다.")
        return

    results_df = pd.DataFrame(graded_results)

    # '채점결과' 딕셔너리에서 '합산_점수'를 추출하여 새로운 컬럼으로 추가
    # '채점결과'가 딕셔너리가 아닌 문자열일 경우를 대비하여 안전하게 처리
    results_df['합산_점수'] = results_df['채점결과'].apply(lambda x: x.get('합산_점수', 0) if isinstance(x, dict) else 0)

    st.subheader("📊 채점 결과 대시보드")

    # 탭 생성 (기존 4개 -> 3개로 축소)
    tab1, tab2, tab3 = st.tabs(["종합 요약 및 인사이트", "루브릭 항목별 분석", "개별 학생 분석"])

    with tab1:
        st.write("### 종합 요약 및 인사이트")

        # 1. 핵심 성취도 요약
        avg_score = results_df['합산_점수'].mean()
        max_score = results_df['합산_점수'].max()
        min_score = results_df['합산_점수'].min()
        # 만점자 수 계산 (최고점과 같은 점수를 받은 학생)
        perfect_scorers_count = results_df[results_df['합산_점수'] == max_score].shape[0]
        below_average_count = results_df[results_df['합산_점수'] < avg_score].shape[0]

        cols = st.columns(5)
        cols[0].metric(label="반 평균 점수", value=f"{avg_score:.2f}점")
        cols[1].metric(label="최고점", value=f"{max_score}점")
        cols[2].metric(label="최저점", value=f"{min_score}점")
        cols[3].metric(label="만점자 수", value=f"{perfect_scorers_count}명")
        cols[4].metric(label="평균 이하", value=f"{below_average_count}명")

        # 2. 자동 생성 교육 인사이트
        rubric_scores_list = [res['채점결과'] for res in graded_results if isinstance(res.get('채점결과'), dict)]
        if rubric_scores_list:
            rubric_scores = pd.DataFrame(rubric_scores_list)
            # 점수 관련 컬럼만 선택 (숫자형이고 '합산'이 아닌 것)
            score_columns = [col for col in rubric_scores.columns if '점수' in col and '합산' not in col and pd.api.types.is_numeric_dtype(rubric_scores[col])]
            
            if score_columns:
                avg_rubric_scores = rubric_scores[score_columns].mean()
                weakest_item = avg_rubric_scores.idxmin()
                weakest_item_name = weakest_item.replace('_', ' ').replace(' 점수', '')
                st.info(f"💡 **교육 인사이트**: 가장 많은 학생들이 어려움을 겪은 항목은 **'{weakest_item_name}'** 입니다. 해당 부분에 대한 보충 설명이 필요해 보입니다.")

        # 3. 학생 합산 점수 분포 (산포도)
        st.write("#### 학생별 점수 분포")
        fig_dist = px.scatter(results_df,
                              x='이름',
                              y='합산_점수',
                              text='합산_점수',
                              title='학생별 점수 분포',
                              labels={'이름': '학생', '합산_점수': '점수'})
        fig_dist.update_traces(textposition='top center')
        fig_dist.update_layout(xaxis={'categoryorder':'total descending'})
        st.plotly_chart(fig_dist, use_container_width=True)

    with tab2:
        st.write("### 루브릭 항목별 분석 (계층 구조)")
        st.info("점수 구조를 파악하기 위한 세 가지 시각화 방법입니다. 각 차트를 비교해보고 가장 유용하다고 생각하는 최종안을 선택해주세요.")

        # Check for necessary data
        rubric_scores_list = [res['채점결과'] for res in graded_results if isinstance(res.get('채점결과'), dict)]
        rubric = st.session_state.get('final_rubric')

        if rubric_scores_list and rubric:
            rubric_scores_df = pd.DataFrame(rubric_scores_list)
            avg_scores = rubric_scores_df.mean() # Calculate all averages once

            # Prepare hierarchical data
            hierarchical_data = []
            total_score_avg = avg_scores.get('합산_점수', 0)
            hierarchical_data.append({'ids': '총점', 'parents': '', 'labels': '총점', 'values': total_score_avg})

            for i, main_item in enumerate(rubric):
                main_id = f"주요_{i+1}"
                main_label = main_item.get('main_criterion', f'주요 채점 요소 {i+1}')
                main_score_avg = 0

                # Temp list to calculate main score sum
                sub_scores_for_main = []

                for j, sub_item in enumerate(main_item.get('sub_criteria', [])):
                    sub_id = f"세부_{i+1}_{j+1}"
                    sub_col_name = f"세부_채점_요소_{i+1}_{j+1}_점수"
                    sub_label = sub_item.get('content', f'세부 {i+1}-{j+1}')
                    sub_score_avg = avg_scores.get(sub_col_name, 0)
                    sub_scores_for_main.append(sub_score_avg)
                    hierarchical_data.append({'ids': sub_id, 'parents': main_id, 'labels': sub_label, 'values': sub_score_avg})
                
                # Main score is the sum of its sub-scores
                main_score_avg = sum(sub_scores_for_main)
                hierarchical_data.append({'ids': main_id, 'parents': '총점', 'labels': main_label, 'values': main_score_avg})

            hierarchical_df = pd.DataFrame(hierarchical_data)
            
            # Filter out zero-value rows which can cause issues in some charts
            hierarchical_df = hierarchical_df[hierarchical_df['values'] > 0]

            # --- Chart 1: Sunburst ---
            st.subheader("대안 1: 선버스트 차트 (Sunburst Chart)")
            st.write("원의 중심으로 갈수록 상위 항목을 나타냅니다. 각 조각의 크기와 색상은 평균 점수를 의미하며, 전체 점수 구성과 비중을 파악하는 데 유용합니다.")
            fig_sunburst = px.sunburst(
                hierarchical_df,
                ids='ids',
                parents='parents',
                names='labels',
                values='values',
                color='values',
                color_continuous_scale='Blues',
                hover_data={'values':':.2f'}
            )
            fig_sunburst.update_layout(margin=dict(t=0, l=0, r=0, b=0))
            st.plotly_chart(fig_sunburst, use_container_width=True)

            # --- Chart 2: Treemap ---
            st.subheader("대안 2: 트리맵 (Treemap)")
            st.write("전체 영역을 항목별 점수 비중에 따라 사각형으로 나눕니다. 각 항목의 상대적인 크기를 비교하고, 색상을 통해 점수 수준을 파악하기 좋습니다.")
            fig_treemap = px.treemap(
                hierarchical_df,
                ids='ids',
                parents='parents',
                names='labels',
                values='values',
                color='values',
                color_continuous_scale='Blues',
                hover_data={'values':':.2f'}
            )
            fig_treemap.update_layout(margin=dict(t=0, l=0, r=0, b=0))
            st.plotly_chart(fig_treemap, use_container_width=True)

            # --- Chart 3: Icicle Chart ---
            st.subheader("대안 3: 아이시클 차트 (Icicle Chart)")
            st.write("계층 구조를 위에서 아래로 선형적으로 보여줍니다. 상위 항목(총점)에서 하위 항목으로 어떻게 점수가 나뉘는지 그 경로를 추적하는 데 유용합니다.")
            fig_icicle = px.icicle(
                hierarchical_df,
                ids='ids',
                parents='parents',
                names='labels',
                values='values',
                color='values',
                color_continuous_scale='Blues',
                hover_data={'values':':.2f'}
            )
            fig_icicle.update_layout(margin=dict(t=25, l=0, r=0, b=0))
            st.plotly_chart(fig_icicle, use_container_width=True)

        else:
            st.info("루브릭 항목별 점수 데이터가 없거나 루브릭이 설정되지 않아 계층 구조 시각화를 생성할 수 없습니다.")

    with tab3:
        st.write("### 개별 학생 분석")

        student_names = results_df['이름'].unique()
        selected_student = st.selectbox("학생 선택", student_names)

        if selected_student:
            student_data = results_df[results_df['이름'] == selected_student].iloc[0]

            # 1. 개인별 성취도 프로파일 (레이더 차트)
            st.write(f"#### {selected_student} 학생의 성취도 프로파일")
            
            student_scores_dict = student_data.get('채점결과', {})
            rubric_scores_list = [res['채점결과'] for res in graded_results if isinstance(res.get('채점결과'), dict)]

            if rubric_scores_list:
                rubric_scores_df = pd.DataFrame(rubric_scores_list)
                score_columns = [col for col in rubric_scores_df.columns if '점수' in col and '합산' not in col and pd.api.types.is_numeric_dtype(rubric_scores_df[col])]
                
                if score_columns:
                    avg_scores = rubric_scores_df[score_columns].mean()
                    student_scores = {k: v for k, v in student_scores_dict.items() if k in score_columns}

                    plot_df = pd.DataFrame({
                        '채점 항목': list(student_scores.keys()) * 2,
                        '점수': list(student_scores.values()) + list(avg_scores[student_scores.keys()].values),
                        '유형': ['학생 점수'] * len(student_scores) + ['반 평균'] * len(student_scores)
                    })

                    fig_radar = px.line_polar(plot_df, r='점수', theta='채점 항목', color='유형', line_close=True,
                                              title=f'{selected_student} 학생 성취도와 반 평균 비교',
                                              markers=True)
                    st.plotly_chart(fig_radar, use_container_width=True)

            # 2. 상세 정보 (기존 내용 + 피드백 노트 생성)
            st.write(f"#### {selected_student} 학생의 상세 분석")
            st.write(f"**합산 점수:** {student_data['합산_점수']}점")
            st.write("**학생 답안:**")
            st.info(student_data['답안'])

            with st.expander("상세 채점 결과 및 피드백 보기"):
                st.write("**채점 결과:**")
                if isinstance(student_data.get('채점결과'), dict):
                    for criterion, score in student_data['채점결과'].items():
                        if criterion != '합산_점수':
                            st.write(f"- {criterion}: {score}점")
                
                st.write("**점수 판단 근거:**")
                if isinstance(student_data.get('점수_판단_근거'), dict):
                    for criterion, reason in student_data['점수_판단_근거'].items():
                        st.write(f"- {criterion}: {reason}")
                else:
                    st.info("점수 판단 근거 데이터가 없습니다.")

                st.write("**피드백:**")
                if isinstance(student_data.get('피드백'), dict):
                    st.write(f"- 교과 내용 피드백: {student_data['피드백'].get('교과_내용_피드백', 'N/A')}")
                    st.write(f"- 의사 응답 여부: {student_data['피드백'].get('의사_응답_여부', 'N/A')}")
                    if student_data['피드백'].get('의사_응답_여부', False):
                        st.write(f"  - 설명: {student_data['피드백'].get('의사_응답_설명', 'N/A')}")
                else:
                    st.info("피드백 데이터가 없습니다.")
                
                st.write("**참고 문서:**")
                st.info(student_data['참고문서'])

            # 3. 개인화된 학습 자료 자동 생성
            st.write("#### 📝 개인화된 학습 자료 생성")
            if 'final_rubric' in st.session_state:
                rubric = st.session_state['final_rubric']
                
                # --- TXT 파일 내용 생성 ---
                feedback_note_content = f"# {selected_student} 학생을 위한 피드백 노트\n\n"
                feedback_note_content += "이 노트는 채점 결과를 바탕으로 부족한 부분을 보충하고, 더 깊이 학습할 수 있도록 돕기 위해 만들어졌습니다.\n\n---\n\n"
                
                has_improvement_points = False
                excel_rows = []

                for i, item in enumerate(rubric):
                    for j, sub_item in enumerate(item.get('sub_criteria', [])):
                        sub_key = f"세부_채점_요소_{i+1}_{j+1}_점수"
                        student_score = student_scores_dict.get(sub_key, 0)
                        max_score = sub_item.get('score', 0)
                        
                        if student_score < max_score:
                            has_improvement_points = True
                            main_feedback_key = f"주요_채점_요소_{i+1}"
                            feedback_reason = student_data.get('점수_판단_근거', {}).get(main_feedback_key, "관련 피드백이 없습니다.")
                            
                            # TXT 내용 추가
                            feedback_note_content += f"## 📌 보충이 필요한 항목: {item['main_criterion']} - {sub_item['content']}\n"
                            feedback_note_content += f"- 내 점수: {student_score} / {max_score}점\n"
                            feedback_note_content += f"- 관련 피드백: {feedback_reason}\n\n"

                            # Excel 데이터 추가
                            excel_rows.append({
                                '구분': '보충 필요 항목',
                                '주요 채점 요소': item['main_criterion'],
                                '세부 채점 요소': sub_item['content'],
                                '내 점수': student_score,
                                '만점': max_score,
                                '피드백': feedback_reason
                            })

                if not has_improvement_points:
                    feedback_note_content += "🎉 모든 항목에서 좋은 점수를 받았습니다! 대단해요!\n"
                    excel_rows.append({'구분': '총평', '내용': '모든 항목에서 좋은 점수를 받았습니다!'})
                    
                feedback_note_content += "\n---\n\n"
                feedback_note_content += "### 💡 참고하면 좋은 자료\n"
                feedback_note_content += "다음 자료들을 다시 한번 읽어보며 개념을 복습해보세요.\n"
                feedback_note_content += f"- {student_data.get('참고문서', '참고 문서가 없습니다.')}\n"
                excel_rows.append({})
                excel_rows.append({'구분': '참고 자료', '내용': student_data.get('참고문서', '참고 문서가 없습니다.')})

                # --- Excel 파일 생성 ---
                excel_df = pd.DataFrame(excel_rows)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    excel_df.to_excel(writer, index=False, sheet_name=f'{selected_student}_피드백')
                excel_data = output.getvalue()

                # --- 다운로드 버튼 표시 ---
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="피드백 노트 (.txt)",
                        data=feedback_note_content,
                        file_name=f"{selected_student}_feedback_note.txt",
                        mime="text/plain",
                    )
                with col2:
                    st.download_button(
                        label="피드백 노트 (.xlsx)",
                        data=excel_data,
                        file_name=f"{selected_student}_feedback_note.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
            else:
                st.warning("세션에 루브릭 정보가 없어 개인화된 학습 자료를 생성할 수 없습니다.")
