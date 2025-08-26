"""
Enhanced Response Parser for LLM outputs.

This module provides the main parser class that orchestrates multiple parsing
strategies, validation, and error recovery to robustly handle LLM responses.
"""

import time
import logging
from typing import Optional, List
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
            # Create extraction context
            context = self._create_extraction_context(response)
            
            # Initialize result
            result = ParsingResult(
                success_level=SuccessLevel.FAILED,
                raw_response=response,
                total_processing_time_ms=0.0
            )
            
            # Try each strategy in order
            for strategy in self.strategies:
                if self._should_try_strategy(strategy, context, result):
                    attempt = strategy.execute(response, context)
                    result.attempts.append(attempt)
                    
                    if attempt.success and attempt.parsed_data:
                        # Validate the parsed data
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
                
                recovery_result = self._attempt_final_recovery(response, parser)
                if recovery_result.success:
                    result.success_level = SuccessLevel.PARTIAL
                    result.partial_content = recovery_result.recovered_data
                    result.recovery_notes.extend(recovery_result.recovery_notes)
                    result.warnings.append(f"Partial recovery successful (confidence: {recovery_result.confidence_score:.2f})")
            
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
        """Log a summary of the parsing result."""
        if self.config.log_all_attempts:
            logger.info(f"Parsing completed: {result.success_level.value}")
            logger.info(f"Attempts: {len(result.attempts)}")
            logger.info(f"Processing time: {result.total_processing_time_ms:.2f}ms")
            
            if result.successful_strategy:
                logger.info(f"Successful strategy: {result.successful_strategy.value}")
            
            if result.errors:
                logger.warning(f"Errors: {result.errors}")
            
            if result.warnings:
                logger.info(f"Warnings: {result.warnings}")
    
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