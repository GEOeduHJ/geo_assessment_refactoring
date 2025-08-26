import json
from typing import List, Dict, Any
import os
import mimetypes

from google import genai
from google.genai import types

from langchain_core.output_parsers import PydanticOutputParser
from core.enhanced_response_parser import parse_llm_response
from core.parsing_models import ParsingConfig, SuccessLevel


def grade_map_question(
    student_name: str,
    uploaded_image: Any,  # Streamlit UploadedFile object
    rubric: List[Dict],
    parser: PydanticOutputParser,
    parsing_config: ParsingConfig = None
) -> Dict:
    """
    Scores a student's blank map submission using the Gemini 2.5 Flash model.
    Now includes enhanced response parsing for better reliability.
    """
    # Configure enhanced parsing
    if parsing_config is None:
        parsing_config = ParsingConfig(
            max_attempts=4,
            enable_fallback_recovery=True,
            enable_partial_recovery=True,
            allow_field_mapping=True,
            allow_type_coercion=True,
            log_all_attempts=False  # Less verbose for image processing
        )
    try:
        # 1. Configure Google Gemini API
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"이름": student_name, "오류": "GEMINI_API_KEY 환경 변수가 설정되지 않았습니다."}
        
        # The new SDK uses genai.Client(api_key=...) or environment variables.
        client = genai.Client(api_key=api_key)

        # 2. Prepare prompt and image
        rubric_str = ""
        for i, item in enumerate(rubric):
            rubric_str += f"- 주요 채점 요소 {i+1}: {item['main_criterion']}\n"
            for j, sub_item in enumerate(item['sub_criteria']):
                rubric_str += f"  - 세부 내용 {j+1} (점수: {sub_item['score']}점): {sub_item['content']}\n"

        format_instructions = parser.get_format_instructions()

        image_bytes = uploaded_image.read()
        
        mime_type = mimetypes.guess_type(uploaded_image.name)[0] if uploaded_image.name else 'image/png'

        # Create the image part for the prompt, as in the example
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=mime_type
        )

        prompt_text = f"""
당신은 지리 과목의 백지도 문항을 채점하는 전문 채점관입니다. 학생이 제출한 백지도 이미지를 바탕으로 다음 지시사항에 따라 채점하고 피드백을 제공해주세요.

--- 평가 루브릭 ---
{rubric_str}

--- 지시사항 ---
1. 먼저, 학생이 제출한 백지도 이미지에서 평가 루브릭에 명시된 지리적 요소(예: 인구 이동 방향 화살표, 주요 공항 사각형 표시, 제주도 시내 원 표시 등)가 어떻게 표현되었는지 **자세히 설명**해주세요. 만약 해당 요소가 보이지 않는다면, 보이지 않는다고 명확히 언급해주세요.
2. 위에서 설명한 내용을 바탕으로, 평가 루브릭의 각 항목에 따라 학생 답안을 면밀히 분석하고 채점해주세요.
3. 평가 루브릭의 각 '주요 채점 요소'별로 점수를 부여하고, 최종 합산 점수를 계산해주세요. 이때, 점수는 반드시 루브릭에 명시된 점수로 부여하고, 부분 점수는 부여하지 않습니다.
4. 학생 답안에 대한 교과 내용적인 피드백을 제공해주세요. 특히, 이미지에서 식별된 요소들을 바탕으로 표기된 지리적 요소의 정확성과 누락 여부에 집중해주세요.
5. 학생 답안이 '의사 응답(bluffing)'인지 여부를 판단하고, 그렇다면 그 이유를 간략하게 설명해주세요. 의사 응답은 내용 없이 길게 늘어뜨리거나, 관련 없는 내용을 포함하는 경우를 의미합니다.
6. 각 주요 채점 요소별로 점수를 부여한 근거를 이미지에서 식별된 구체적인 내용을 바탕으로 상세하게 작성해주세요.
7. **반드시 아래 `format_instructions`에 명시된 JSON 형식에 맞춰 `채점결과`와 `피드백` 두 가지 최상위 키를 모두 포함하여 응답을 생성해주세요.****
{format_instructions}
"""

        # 3. Call the Gemini API using the specified model, as per the example
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt_text, image_part],
        )
        llm_response_str = response.text

        if not llm_response_str:
            return {"이름": student_name, "오류": "LLM 응답을 받지 못했습니다."}

        # 4. Parse the response using enhanced parser
        parsing_result = parse_llm_response(llm_response_str, parser, parsing_config)
        
        # Handle parsing results based on success level
        if parsing_result.success_level == SuccessLevel.FULL:
            try:
                # Create parsed object from the corrected data
                parsed_output = parser.pydantic_object(**parsing_result.data)
                
                score_results = parsed_output.채점결과.model_dump()
                feedback_results = parsed_output.피드백.model_dump()
                
                점수_판단_근거 = score_results.pop("점수_판단_근거", {})
                
                referenced_docs_info = []
                
                result = {
                    "이름": student_name,
                    "답안": "백지도 이미지",
                    "채점결과": score_results,
                    "피드백": feedback_results,
                    "점수_판단_근거": 점수_판단_근거,
                    "참고문서": "; ".join(referenced_docs_info)
                }
                
                # Add parsing warnings if any
                if parsing_result.warnings:
                    result["파싱_경고"] = "; ".join(parsing_result.warnings)
                
                return result
                
            except Exception as formatting_error:
                return {
                    "이름": student_name,
                    "오류": f"파싱된 데이터 처리 오류: {formatting_error}",
                    "파싱_데이터": parsing_result.data,
                    "파싱_경고": "; ".join(parsing_result.warnings) if parsing_result.warnings else None
                }
                
        elif parsing_result.success_level == SuccessLevel.PARTIAL:
            # Partial parsing success
            best_data = parsing_result.get_best_data()
            
            return {
                "이름": student_name,
                "답안": "백지도 이미지",
                "오류": "부분적 파싱 성공",
                "채점결과": best_data.get("채점결과", {}) if best_data else {},
                "피드백": best_data.get("피드백", {}) if best_data else {},
                "점수_판단_근거": best_data.get("점수_판단_근거", {}) if best_data else {},
                "참고문서": "",
                "파싱_경고": "; ".join(parsing_result.warnings) if parsing_result.warnings else "부분 데이터 복구됨",
                "파싱_오류": "; ".join(parsing_result.errors) if parsing_result.errors else None,
                "원본_응답_샘플": llm_response_str[:200] + "..." if len(llm_response_str) > 200 else llm_response_str
            }
            
        else:
            # Complete parsing failure
            return {
                "이름": student_name,
                "오류": f"LLM 응답 파싱 실패: {'; '.join(parsing_result.errors)}",
                "파싱_시도_횟수": len(parsing_result.attempts),
                "파싱_전략들": [attempt.strategy.value for attempt in parsing_result.attempts],
                "처리_시간_ms": f"{parsing_result.total_processing_time_ms:.2f}",
                "원본_응답_샘플": llm_response_str[:500] + "..." if len(llm_response_str) > 500 else llm_response_str
            }

    except Exception as e:
        return {"이름": student_name, "오류": f"백지도 채점 중 오류 발생: {e}"}