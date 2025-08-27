"""
Enhanced Response Parser for LLM outputs.

This module provides the main parser class that orchestrates multiple parsing
strategies, validation, and error recovery to robustly handle LLM responses.
"""

import time
import logging
import re
from typing import Optional, List, Dict, Any
from langchain_core.output_parsers import PydanticOutputParser

from .parsing_models import (
    ParsingResult, SuccessLevel, ParsingConfig, ExtractionContext,
    ParsingStrategy, RecoveryResult
)
from .parsing_strategies import StrategyFactory, BaseExtractionStrategy
from .validation_engine import ValidationEngine

logger = logging.getLogger(__name__)


class EnhancedResponseParser:
    """
    Enhanced parser for LLM responses with multi-strategy parsing and error recovery.
    
    This parser attempts multiple strategies to extract and validate JSON content
    from LLM responses, providing robust error handling and partial recovery.
    """
    
    def __init__(self, config: Optional[ParsingConfig] = None):
        """
        Initialize the enhanced parser.
        
        Args:
            config: Configuration for parsing behavior
        """
        self.config = config or ParsingConfig()
        self.validation_engine = ValidationEngine(self.config)
        self.strategies = StrategyFactory.create_all_strategies(self.config)
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging for the parser."""
        if self.config.log_all_attempts:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
    
    def parse_response(self, response: str, parser: PydanticOutputParser) -> ParsingResult:
        """Parse LLM response using multiple strategies with validation and recovery."""
        return self._parse_response_internal(response, parser, None)
    
    def parse_response_with_rubric(self, response: str, parser: PydanticOutputParser, 
                                  rubric: List[Dict[str, Any]]) -> ParsingResult:
        """Parse LLM response with adaptive validation based on rubric structure.
        
        Args:
            response: Raw LLM response string
            parser: Pydantic output parser for validation
            rubric: Rubric items for adaptive schema creation
            
        Returns:
            ParsingResult with parsing outcome and details
        """
        return self._parse_response_internal(response, parser, rubric)
    
    def _parse_response_internal(self, response: str, parser: PydanticOutputParser, 
                               rubric: Optional[List[Dict[str, Any]]] = None) -> ParsingResult:
        """
        Parse LLM response using multiple strategies with validation and recovery.
        
        Args:
            response: Raw LLM response string
            parser: Pydantic output parser for validation
            
        Returns:
            ParsingResult with parsing outcome and details
        """
        start_time = time.time()
        
        try:
            # Pre-process the response to clean LLM artifacts
            cleaned_response = self._preprocess_response(response)
            logger.debug(f"Response preprocessing: {len(response)} -> {len(cleaned_response)} chars")
            
            # Create extraction context with cleaned response
            context = self._create_extraction_context(cleaned_response)
            
            # Initialize result
            result = ParsingResult(
                success_level=SuccessLevel.FAILED,
                raw_response=response,
                total_processing_time_ms=0.0
            )
            
            # Try each strategy in order
            for strategy in self.strategies:
                if self._should_try_strategy(strategy, context, result):
                    attempt = strategy.execute(cleaned_response, context)  # Use cleaned response
                    result.attempts.append(attempt)
                    
                    if attempt.success and attempt.parsed_data:
                        # Choose validation method based on rubric availability
                        if rubric:
                            # Use adaptive validation with rubric
                            validation_result = self.validation_engine.validate_with_adaptive_schema(
                                attempt.parsed_data, rubric
                            )
                        else:
                            # Use standard validation with parser
                            validation_result = self.validation_engine.validate_structure(
                                attempt.parsed_data, parser
                            )
                        result.validation_result = validation_result
                        
                        if validation_result.is_valid:
                            # Success!
                            result.success_level = SuccessLevel.FULL
                            result.data = validation_result.corrected_data
                            result.successful_strategy = strategy.get_strategy_type()
                            result.warnings.extend(validation_result.warnings)
                            break
                        else:
                            # Validation failed, but we have data
                            if self.config.enable_partial_recovery:
                                result.partial_content = attempt.parsed_data
                                result.success_level = SuccessLevel.PARTIAL
                                result.errors.extend(validation_result.errors)
                                result.warnings.append(f"Partial data recovered using {strategy.get_strategy_type().value}")
            
            # If no strategy succeeded and fallback recovery is enabled
            if (result.success_level == SuccessLevel.FAILED and 
                self.config.enable_fallback_recovery):
                
                recovery_result = self._attempt_final_recovery(cleaned_response, parser)
                if recovery_result.success:
                    result.success_level = SuccessLevel.PARTIAL
                    result.partial_content = recovery_result.recovered_data
                    result.recovery_notes.extend(recovery_result.recovery_notes)
                    result.warnings.append(f"Partial recovery successful (confidence: {recovery_result.confidence_score:.2f})")
                else:
                    # Final emergency recovery when everything else fails
                    logger.warning("All parsing and recovery strategies failed - activating emergency recovery")
                    emergency_data = self._attempt_emergency_recovery(response)
                    result.success_level = SuccessLevel.PARTIAL
                    result.partial_content = emergency_data
                    result.recovery_notes.append("Emergency fallback activated - manual review required")
                    result.warnings.append("Emergency recovery used - results need manual verification")
            
            # Calculate total processing time
            result.total_processing_time_ms = (time.time() - start_time) * 1000
            
            # Log result summary
            self._log_result_summary(result)
            
            return result
            
        except Exception as e:
            # Catastrophic failure
            total_time = (time.time() - start_time) * 1000
            logger.error(f"Enhanced parser failed catastrophically: {e}")
            
            return ParsingResult(
                success_level=SuccessLevel.FAILED,
                raw_response=response,
                errors=[f"Parser failure: {str(e)}"],
                total_processing_time_ms=total_time
            )
    
    def _create_extraction_context(self, response: str) -> ExtractionContext:
        """Create extraction context from response."""
        return ExtractionContext(
            original_response=response,
            response_length=len(response),
            detected_format=self._detect_response_format(response),
            has_code_blocks=self._has_code_blocks(response),
            has_json_markers=self._has_json_markers(response),
            language_hints=self._detect_language_hints(response)
        )
    
    def _detect_response_format(self, response: str) -> Optional[str]:
        """Detect the format of the response."""
        response_lower = response.lower()
        
        if '```' in response:
            return 'markdown'
        elif response.strip().startswith('{') and response.strip().endswith('}'):
            return 'json'
        elif 'json' in response_lower:
            return 'json_embedded'
        else:
            return 'text'
    
    def _has_code_blocks(self, response: str) -> bool:
        """Check if response contains code blocks."""
        return '```' in response or '~~~' in response
    
    def _has_json_markers(self, response: str) -> bool:
        """Check if response contains JSON markers."""
        return '{' in response and '}' in response
    
    def _detect_language_hints(self, response: str) -> List[str]:
        """Detect language hints in the response."""
        hints = []
        
        # Check for Korean content
        if any(ord(char) >= 0xAC00 and ord(char) <= 0xD7A3 for char in response):
            hints.append('korean')
        
        # Check for JSON-related terms
        if any(term in response.lower() for term in ['json', 'object', 'array']):
            hints.append('json')
        
        return hints
    
    def _should_try_strategy(self, strategy: BaseExtractionStrategy, 
                           context: ExtractionContext, 
                           current_result: ParsingResult) -> bool:
        """Determine if a strategy should be attempted."""
        strategy_type = strategy.get_strategy_type()
        
        # Always try if no previous success
        if current_result.success_level == SuccessLevel.FAILED:
            return True
        
        # Skip fallback if we already have partial success
        if (strategy_type == ParsingStrategy.FALLBACK_RECOVERY and 
            current_result.success_level != SuccessLevel.FAILED):
            return False
        
        # Strategy-specific logic
        if strategy_type == ParsingStrategy.MARKDOWN_BLOCK and not context.has_code_blocks:
            return False
        
        return True
    
    def _attempt_final_recovery(self, response: str, parser: PydanticOutputParser) -> RecoveryResult:
        """Attempt final recovery using fallback strategy."""
        try:
            fallback_strategy = StrategyFactory.create_strategy(
                ParsingStrategy.FALLBACK_RECOVERY, 
                self.config
            )
            
            context = self._create_extraction_context(response)
            attempt = fallback_strategy.execute(response, context)
            
            if attempt.success and attempt.parsed_data:
                return RecoveryResult(
                    success=True,
                    recovered_data=attempt.parsed_data,
                    confidence_score=0.5,  # Medium confidence for fallback
                    recovery_notes=["Final fallback recovery successful"]
                )
            
            return RecoveryResult(
                success=False,
                recovered_data=None,
                confidence_score=0.0,
                recovery_notes=["Final recovery failed"]
            )
            
        except Exception as e:
            logger.error(f"Final recovery failed: {e}")
            return RecoveryResult(
                success=False,
                recovered_data=None,
                confidence_score=0.0,
                recovery_notes=[f"Final recovery error: {str(e)}"]
            )
    
    def _log_result_summary(self, result: ParsingResult):
        """Log a summary of the parsing result with detailed error diagnostics."""
        if self.config.log_all_attempts:
            logger.info(f"Parsing completed: {result.success_level.value}")
            logger.info(f"Attempts: {len(result.attempts)}")
            logger.info(f"Processing time: {result.total_processing_time_ms:.2f}ms")
            
            if result.successful_strategy:
                logger.info(f"Successful strategy: {result.successful_strategy.value}")
            
            # Enhanced error logging for failures
            if result.success_level == SuccessLevel.FAILED:
                logger.error(f"All parsing strategies failed")
                
                # Log raw response sample for debugging
                if result.raw_response:
                    sample_length = min(500, len(result.raw_response))
                    sample = result.raw_response[:sample_length]
                    if len(result.raw_response) > sample_length:
                        sample += "... (truncated)"
                    logger.error(f"Raw response sample: {repr(sample)}")
                    logger.error(f"Response length: {len(result.raw_response)} characters")
                
                # Log strategy-specific failure analysis
                for i, attempt in enumerate(result.attempts):
                    strategy_name = attempt.strategy.value
                    logger.error(f"Strategy {i+1}/{len(result.attempts)} ({strategy_name}) failed: {attempt.error_message}")
                    if attempt.error_details:
                        logger.error(f"  - Error details: {attempt.error_details}")
                    if attempt.execution_time_ms > 0:
                        logger.error(f"  - Execution time: {attempt.execution_time_ms:.2f}ms")
                
                # Log response format analysis
                if hasattr(result, 'raw_response') and result.raw_response:
                    format_info = self._analyze_response_format(result.raw_response)
                    logger.error(f"Response format analysis: {format_info}")
            
            if result.errors:
                logger.warning(f"Errors: {result.errors}")
            
            if result.warnings:
                logger.info(f"Warnings: {result.warnings}")
                
    def _analyze_response_format(self, response: str) -> dict:
        """Analyze response format for debugging purposes."""
        analysis = {
            "starts_with": response[:50] if response else "<empty>",
            "ends_with": response[-50:] if len(response) > 50 else response,
            "contains_json_brackets": '{' in response and '}' in response,
            "contains_code_blocks": '```' in response,
            "contains_korean": any(ord(char) >= 0xAC00 and ord(char) <= 0xD7A3 for char in response),
            "line_count": response.count('\n') + 1 if response else 0,
            "char_count": len(response)
        }
        return analysis
    
    def _attempt_emergency_recovery(self, response: str) -> Dict[str, Any]:
        """Emergency recovery when all parsing strategies fail.
        
        Returns a basic response structure to prevent complete system failure.
        This ensures the grading pipeline can continue even when parsing fails.
        
        Args:
            response: Original LLM response that failed to parse
            
        Returns:
            Dict with basic Korean grading structure
        """
        logger.warning("Activating emergency recovery - returning basic response structure")
        
        # Basic Korean grading structure for emergency fallback
        emergency_response = {
            "채점결과": {
                "주요_채점_요소_1_점수": 0,
                "합산_점수": 0,
                "점수_판단_근거": {
                    "emergency_note": "파싱 실패로 인한 기본값 - 수동 검토 필요"
                }
            },
            "피드백": {
                "교과_내용_피드백": "시스템 오류로 인해 자동 채점을 완료할 수 없습니다. 수동 검토가 필요합니다.",
                "의사_응답_여부": False,
                "의사_응답_설명": "시스템 오류로 판단 불가"
            }
        }
        
        # Try to extract any score numbers from the response as a last resort
        import re
        score_matches = re.findall(r'\b(?:점수|score).*?([0-9]+)', response, re.IGNORECASE)
        if score_matches:
            try:
                # Use the first found score as the main score
                extracted_score = int(score_matches[0])
                emergency_response["채점결과"]["주요_채점_요소_1_점수"] = extracted_score
                emergency_response["채점결과"]["합산_점수"] = extracted_score
                emergency_response["채점결과"]["점수_판단_근거"]["extracted_score"] = f"응답에서 추출된 점수: {extracted_score}"
                logger.info(f"Emergency recovery extracted score: {extracted_score}")
            except ValueError:
                logger.warning("Could not convert extracted score to integer")
        
        # Try to extract any feedback text
        feedback_patterns = [
            r'피드백[:s]*([^\n]+)',
            r'feedback[:s]*([^\n]+)',
            r'평가[:s]*([^\n]+)',
        ]
        
        for pattern in feedback_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE | re.UNICODE)
            if matches:
                feedback_text = matches[0].strip()
                if len(feedback_text) > 10:  # Only use if substantial feedback
                    emergency_response["피드백"]["교과_내용_피드백"] = f"추출된 피드백: {feedback_text}"
                    logger.info(f"Emergency recovery extracted feedback: {feedback_text[:50]}...")
                    break
        
        return emergency_response
    
    def _preprocess_response(self, response: str) -> str:
        """Clean and normalize response before parsing.
        
        This method removes common LLM artifacts and normalizes the response
        to improve parsing success rates.
        
        Args:
            response: Raw LLM response string
            
        Returns:
            Cleaned and normalized response string
        """
        if not response or not response.strip():
            return response
        
        original_length = len(response)
        cleaned = response
        
        # Step 1: Remove leading/trailing LLM artifacts
        # Remove common leading phrases
        leading_patterns = [
            r'^.*?다음은.*?입니다[.:]*\s*',  # "다음은 ... 입니다"
            r'^.*?Here\s+is.*?:\s*',  # "Here is ..."
            r'^.*?결과는.*?입니다[.:]*\s*',  # "결과는 ... 입니다"
            r'^[^{]*?(?=\{)',  # Remove everything before first {
        ]
        
        for pattern in leading_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        
        # Step 2: Remove trailing artifacts after JSON
        # Remove everything after the last }
        if '}' in cleaned:
            last_brace = cleaned.rfind('}')
            if last_brace != -1:
                cleaned = cleaned[:last_brace + 1]
        
        # Step 3: Clean up code block markers
        cleaned = cleaned.replace('```json', '').replace('```JSON', '')
        cleaned = cleaned.replace('```', '')
        cleaned = cleaned.replace('~~~json', '').replace('~~~', '')
        
        # Step 4: Fix common JSON formatting issues
        # Remove trailing commas before closing braces/brackets
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        
        # Fix missing commas between objects (basic heuristic)
        cleaned = re.sub(r'}\s*{', '},{', cleaned)
        
        # Step 5: Normalize whitespace
        # Replace multiple whitespace with single space (but preserve newlines in strings)
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = re.sub(r'\n\s*\n', '\n', cleaned)
        
        # Step 6: Ensure proper JSON structure
        cleaned = cleaned.strip()
        
        # If content doesn't start with { but contains JSON-like content, try to extract it
        if not cleaned.startswith('{') and '{' in cleaned:
            first_brace = cleaned.find('{')
            if first_brace != -1:
                cleaned = cleaned[first_brace:]
        
        # Log preprocessing results if significant changes were made
        if len(cleaned) != original_length:
            logger.debug(f"Preprocessing: {original_length} -> {len(cleaned)} chars")
            logger.debug(f"Removed: {original_length - len(cleaned)} characters")
        
        return cleaned
    
    def get_parsing_statistics(self) -> dict:
        """Get statistics about parser performance."""
        return {
            "config": {
                "max_attempts": self.config.max_attempts,
                "timeout_seconds": self.config.timeout_seconds,
                "enable_fallback_recovery": self.config.enable_fallback_recovery,
                "enable_partial_recovery": self.config.enable_partial_recovery,
            },
            "available_strategies": [strategy.get_strategy_type().value for strategy in self.strategies],
            "validation_features": {
                "field_mapping": self.config.allow_field_mapping,
                "type_coercion": self.config.allow_type_coercion,
                "require_all_fields": self.config.require_all_required_fields,
            }
        }


# Convenience function for simple usage
def parse_llm_response(response: str, parser: PydanticOutputParser, 
                      config: Optional[ParsingConfig] = None) -> ParsingResult:
    """
    Convenience function to parse LLM response with enhanced parser.
    
    Args:
        response: Raw LLM response string
        parser: Pydantic output parser for validation
        config: Optional parsing configuration
        
    Returns:
        ParsingResult with parsing outcome
    """
    enhanced_parser = EnhancedResponseParser(config)
    return enhanced_parser.parse_response(response, parser)