"""
Core grading pipeline for processing student answers.
Contains the main grading logic extracted from the original main.py.
Now includes enhanced response parsing for robust LLM output handling.
"""
import time
from typing import Dict, Any, List
from utils.retrieval import retrieve_documents, rerank_documents
from prompts.prompt_templates import get_grading_prompt
from .enhanced_response_parser import EnhancedResponseParser, parse_llm_response
from .parsing_models import ParsingConfig, SuccessLevel


class GradingPipeline:
    """Pipeline for processing individual student answers through the grading system."""
    
    def __init__(self, llm_manager, retriever, parsing_config=None):
        """
        Initialize the grading pipeline.
        
        Args:
            llm_manager: LLM manager instance for making API calls
            retriever: Document retriever for RAG functionality
            parsing_config: Configuration for enhanced response parsing
        """
        self.llm_manager = llm_manager
        self.retriever = retriever
        
        # Initialize enhanced parser
        self.parsing_config = parsing_config or ParsingConfig(
            max_attempts=4,
            enable_fallback_recovery=True,
            enable_partial_recovery=True,
            allow_field_mapping=True,
            allow_type_coercion=True,
            log_all_attempts=True
        )
        self.enhanced_parser = EnhancedResponseParser(self.parsing_config)
    
    def process_student_answer(self, student_name: str, student_answer: str, 
                             rubric: List[Dict], question_type: str, parser) -> Dict[str, Any]:
        """
        Process a single student answer through the complete grading pipeline.
        
        This function replicates the original process_student_answer logic from main.py
        but with better error handling and structure.
        
        Args:
            student_name: Name of the student
            student_answer: The student's answer text
            rubric: Grading rubric for evaluation
            question_type: Type of question being graded
            parser: Pydantic parser for structured output
            
        Returns:
            dict: Complete grading result including scores, feedback, and metadata
        """
        start_time = time.time()
        
        try:
            # Step 1: Retrieve relevant documents using RAG
            retrieved_docs = retrieve_documents(self.retriever, student_answer, student_name)
            
            # Step 2: Rerank documents for better relevance
            reranked_docs = rerank_documents(retrieved_docs, student_answer)
            
            # Step 3: Prepare context from retrieved documents
            retrieved_docs_content = "\n\n".join([doc.page_content for doc in reranked_docs])
            
            # Step 4: Get format instructions from parser
            format_instructions = parser.get_format_instructions()
            
            # Step 5: Generate grading prompt
            grading_prompt = get_grading_prompt(
                question_type, rubric, student_answer, 
                retrieved_docs_content, format_instructions
            )
            
            # Step 6: Call LLM for grading
            llm = self.llm_manager.get_llm("GROQ", "llama-3.3-70b-versatile")  # Use generation model (not guard model)
            llm_response_str = self.llm_manager.call_llm_with_retry(llm, grading_prompt)
            
            if not llm_response_str:
                return {"이름": student_name, "오류": "LLM 응답을 받지 못했습니다."}
            
            # Step 7: Parse LLM response using enhanced parser with adaptive validation
            parsing_result = self.enhanced_parser.parse_response_with_rubric(llm_response_str, parser, rubric)
            
            # Step 8: Handle parsing results based on success level
            if parsing_result.success_level == SuccessLevel.FULL:
                # Full parsing success
                try:
                    # Create parsed object from the corrected data
                    parsed_output = parser.pydantic_object(**parsing_result.data)
                    
                    # Extract and format results
                    score_results = parsed_output.채점결과.model_dump()
                    feedback_results = parsed_output.피드백.model_dump()
                    
                    # Extract scoring rationale
                    점수_판단_근거 = score_results.pop("점수_판단_근거", {})
                    
                    # Step 9: Prepare referenced documents information
                    referenced_docs_info = [
                        f"{doc.metadata.get('source', 'Unknown')} (p.{doc.metadata.get('page', 'N/A')})" 
                        for doc in reranked_docs
                    ]
                    
                    # Step 10: Calculate processing time
                    end_time = time.time()
                    processing_time = end_time - start_time
                    
                    # Step 11: Return complete result
                    result = {
                        "이름": student_name,
                        "답안": student_answer,
                        "채점결과": score_results,
                        "피드백": feedback_results,
                        "점수_판단_근거": 점수_판단_근거,
                        "참고문서": "; ".join(referenced_docs_info),
                        "채점_소요_시간": processing_time
                    }
                    
                    # Add parsing warnings if any
                    if parsing_result.warnings:
                        result["파싱_경고"] = "; ".join(parsing_result.warnings)
                    
                    return result
                    
                except Exception as formatting_error:
                    # Even with successful parsing, object creation failed
                    return {
                        "이름": student_name,
                        "오류": f"파싱된 데이터 처리 오류: {formatting_error}",
                        "파싱_데이터": parsing_result.data,
                        "파싱_경고": "; ".join(parsing_result.warnings) if parsing_result.warnings else None
                    }
                    
            elif parsing_result.success_level == SuccessLevel.PARTIAL:
                # Partial parsing success - return what we can
                best_data = parsing_result.get_best_data()
                
                return {
                    "이름": student_name,
                    "답안": student_answer,
                    "오류": "부분적 파싱 성공",
                    "채점결과": best_data.get("채점결과", {}) if best_data else {},
                    "피드백": best_data.get("피드백", {}) if best_data else {},
                    "점수_판단_근거": best_data.get("점수_판단_근거", {}) if best_data else {},
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
            return {"이름": student_name, "오류": f"채점 중 오류 발생: {e}"}
    
    def process_batch(self, student_answers_df, rubric: List[Dict], 
                     question_type: str, parser) -> List[Dict[str, Any]]:
        """
        Process multiple student answers in batch.
        
        Args:
            student_answers_df: DataFrame containing student answers
            rubric: Grading rubric for evaluation
            question_type: Type of question being graded
            parser: Pydantic parser for structured output
            
        Returns:
            list: List of grading results for all students
        """
        results = []
        
        for index, row in student_answers_df.iterrows():
            student_name = row["이름"]
            
            if "답안" not in row:
                result = {"이름": student_name, "오류": f"{student_name} 학생의 답안 컬럼이 누락되었습니다."}
            else:
                student_answer = row["답안"]
                result = self.process_student_answer(
                    student_name, student_answer, rubric, question_type, parser
                )
            
            results.append(result)
        
        return results
    
    def get_pipeline_info(self) -> Dict[str, Any]:
        """
        Get information about the current pipeline configuration.
        
        Returns:
            dict: Pipeline configuration information
        """
        return {
            "llm_manager": type(self.llm_manager).__name__,
            "retriever": type(self.retriever).__name__ if self.retriever else None,
            "pipeline_version": "2.0",
            "enhanced_parsing": True,
            "parsing_config": {
                "max_attempts": self.parsing_config.max_attempts,
                "fallback_recovery": self.parsing_config.enable_fallback_recovery,
                "partial_recovery": self.parsing_config.enable_partial_recovery,
                "field_mapping": self.parsing_config.allow_field_mapping,
                "type_coercion": self.parsing_config.allow_type_coercion
            },
            "parsing_statistics": self.enhanced_parser.get_parsing_statistics()
        }