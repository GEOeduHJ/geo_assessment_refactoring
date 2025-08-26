"""
Parsing strategies for extracting JSON content from LLM responses.

This module implements various strategies to extract and parse JSON content
from LLM responses, handling different formats and edge cases.
"""

import json
import re
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
import logging

from .parsing_models import (
    ParsingStrategy, ParsingAttempt, ExtractionContext, 
    ParsingConfig, RecoveryResult
)

logger = logging.getLogger(__name__)


class BaseExtractionStrategy(ABC):
    """Base class for all parsing strategies."""
    
    def __init__(self, config: ParsingConfig):
        self.config = config
    
    @abstractmethod
    def extract_content(self, response: str, context: ExtractionContext) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Extract JSON content from response.
        
        Returns:
            Tuple of (success, extracted_content, error_message)
        """
        pass
    
    @abstractmethod
    def get_strategy_type(self) -> ParsingStrategy:
        """Get the strategy type."""
        pass
    
    def execute(self, response: str, context: ExtractionContext) -> ParsingAttempt:
        """Execute the parsing strategy and return attempt details."""
        start_time = time.time()
        
        try:
            success, extracted_content, error_message = self.extract_content(response, context)
            
            parsed_data = None
            if success and extracted_content:
                try:
                    parsed_data = json.loads(extracted_content)
                except json.JSONDecodeError as e:
                    success = False
                    error_message = f"JSON decode error: {str(e)}"
            
            execution_time = (time.time() - start_time) * 1000
            
            return ParsingAttempt(
                strategy=self.get_strategy_type(),
                success=success,
                extracted_content=extracted_content,
                parsed_data=parsed_data,
                error_message=error_message,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return ParsingAttempt(
                strategy=self.get_strategy_type(),
                success=False,
                extracted_content=None,
                parsed_data=None,
                error_message=f"Strategy execution failed: {str(e)}",
                execution_time_ms=execution_time
            )


class DirectJSONStrategy(BaseExtractionStrategy):
    """Strategy for extracting JSON from clean responses."""
    
    def get_strategy_type(self) -> ParsingStrategy:
        return ParsingStrategy.DIRECT_JSON
    
    def extract_content(self, response: str, context: ExtractionContext) -> Tuple[bool, Optional[str], Optional[str]]:
        """Extract JSON using simple bracket matching."""
        try:
            # Find first and last curly braces
            first_brace = response.find('{')
            last_brace = response.rfind('}')
            
            if first_brace == -1 or last_brace == -1 or first_brace >= last_brace:
                return False, None, "No valid JSON brackets found"
            
            json_content = response[first_brace:last_brace + 1]
            
            # Quick validation - try to parse
            json.loads(json_content)
            
            return True, json_content, None
            
        except json.JSONDecodeError as e:
            return False, None, f"JSON validation failed: {str(e)}"
        except Exception as e:
            return False, None, f"Extraction failed: {str(e)}"


class MarkdownBlockStrategy(BaseExtractionStrategy):
    """Strategy for extracting JSON from markdown code blocks."""
    
    def get_strategy_type(self) -> ParsingStrategy:
        return ParsingStrategy.MARKDOWN_BLOCK
    
    def extract_content(self, response: str, context: ExtractionContext) -> Tuple[bool, Optional[str], Optional[str]]:
        """Extract JSON from markdown code blocks."""
        try:
            # Pattern for markdown code blocks with optional language specification
            patterns = [
                r'```(?:json)?\s*\n(.*?)\n```',  # Standard code blocks
                r'```(?:json)?\s*(.*?)```',       # Inline code blocks
                r'`{3,}(?:json)?\s*\n(.*?)\n`{3,}',  # Flexible backtick count
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
                
                for match in matches:
                    json_content = match.strip()
                    
                    # Skip empty matches
                    if not json_content:
                        continue
                    
                    try:
                        # Validate JSON
                        json.loads(json_content)
                        return True, json_content, None
                    except json.JSONDecodeError:
                        continue
            
            return False, None, "No valid JSON found in markdown blocks"
            
        except Exception as e:
            return False, None, f"Markdown extraction failed: {str(e)}"


class RegexPatternStrategy(BaseExtractionStrategy):
    """Strategy for extracting JSON using regex patterns."""
    
    def get_strategy_type(self) -> ParsingStrategy:
        return ParsingStrategy.REGEX_PATTERN
    
    def extract_content(self, response: str, context: ExtractionContext) -> Tuple[bool, Optional[str], Optional[str]]:
        """Extract JSON using sophisticated regex patterns."""
        try:
            # Multiple regex patterns for different scenarios
            patterns = [
                # JSON objects with proper structure
                r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
                # More flexible pattern for nested objects
                r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}',
                # Pattern for objects that might have unmatched braces
                r'\{.*?(?:"채점결과"|"피드백").*?\}',
                # Last resort - capture everything between first { and last }
                r'\{.*\}',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response, re.DOTALL)
                
                for match in matches:
                    json_content = match.strip()
                    
                    # Skip very short matches
                    if len(json_content) < 10:
                        continue
                    
                    try:
                        # Validate JSON
                        parsed = json.loads(json_content)
                        
                        # Check if it contains expected structure
                        if isinstance(parsed, dict) and (
                            "채점결과" in parsed or "피드백" in parsed or 
                            len(parsed) > 2  # At least some content
                        ):
                            return True, json_content, None
                    except json.JSONDecodeError:
                        continue
            
            return False, None, "No valid JSON found using regex patterns"
            
        except Exception as e:
            return False, None, f"Regex extraction failed: {str(e)}"


class FallbackRecoveryStrategy(BaseExtractionStrategy):
    """Fallback strategy for recovering partial content."""
    
    def get_strategy_type(self) -> ParsingStrategy:
        return ParsingStrategy.FALLBACK_RECOVERY
    
    def extract_content(self, response: str, context: ExtractionContext) -> Tuple[bool, Optional[str], Optional[str]]:
        """Attempt to recover partial JSON content."""
        try:
            # Try to construct JSON from text content
            recovered_data = self._extract_key_value_pairs(response)
            
            if recovered_data:
                json_content = json.dumps(recovered_data, ensure_ascii=False, indent=2)
                return True, json_content, "Recovered from text analysis"
            
            return False, None, "Could not recover any structured content"
            
        except Exception as e:
            return False, None, f"Fallback recovery failed: {str(e)}"
    
    def _extract_key_value_pairs(self, response: str) -> Dict[str, Any]:
        """Extract key-value pairs from text."""
        recovered = {}
        
        try:
            # Look for common Korean patterns
            patterns = {
                "점수": r"점수[:\s]*(\d+)",
                "총점": r"총점[:\s]*(\d+)",
                "채점결과": r"채점결과[:\s]*(.+?)(?=\n|$)",
                "피드백": r"피드백[:\s]*(.+?)(?=\n|$)",
                "점수_판단_근거": r"판단[근거]*[:\s]*(.+?)(?=\n|$)",
            }
            
            for key, pattern in patterns.items():
                matches = re.findall(pattern, response, re.IGNORECASE | re.MULTILINE)
                if matches:
                    value = matches[0].strip()
                    
                    # Try to convert to appropriate type
                    if key in ["점수", "총점"]:
                        try:
                            recovered[key] = int(value)
                        except ValueError:
                            recovered[key] = value
                    else:
                        recovered[key] = value
            
            # Try to extract structured sections
            if "채점결과" not in recovered:
                grading_section = self._extract_grading_section(response)
                if grading_section:
                    recovered["채점결과"] = grading_section
            
            if "피드백" not in recovered:
                feedback_section = self._extract_feedback_section(response)
                if feedback_section:
                    recovered["피드백"] = feedback_section
            
            return recovered
            
        except Exception as e:
            logger.error(f"Error in key-value extraction: {e}")
            return {}
    
    def _extract_grading_section(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract grading information from text."""
        try:
            grading_info = {}
            
            # Look for score patterns
            score_patterns = [
                r"(\d+)점",
                r"점수[:\s]*(\d+)",
                r"총점[:\s]*(\d+)",
            ]
            
            for pattern in score_patterns:
                matches = re.findall(pattern, response)
                if matches:
                    try:
                        grading_info["총점"] = int(matches[0])
                        break
                    except ValueError:
                        continue
            
            return grading_info if grading_info else None
            
        except Exception:
            return None
    
    def _extract_feedback_section(self, response: str) -> Optional[str]:
        """Extract feedback information from text."""
        try:
            # Look for feedback indicators
            feedback_patterns = [
                r"피드백[:\s]*(.+?)(?=\n\n|\n[A-Z]|$)",
                r"개선[사항]*[:\s]*(.+?)(?=\n\n|\n[A-Z]|$)",
                r"코멘트[:\s]*(.+?)(?=\n\n|\n[A-Z]|$)",
            ]
            
            for pattern in feedback_patterns:
                matches = re.findall(pattern, response, re.IGNORECASE | re.DOTALL)
                if matches:
                    feedback = matches[0].strip()
                    if len(feedback) > 10:  # Reasonable length
                        return feedback
            
            return None
            
        except Exception:
            return None


class StrategyFactory:
    """Factory for creating parsing strategies."""
    
    @staticmethod
    def create_all_strategies(config: ParsingConfig) -> List[BaseExtractionStrategy]:
        """Create all available parsing strategies."""
        return [
            DirectJSONStrategy(config),
            MarkdownBlockStrategy(config),
            RegexPatternStrategy(config),
            FallbackRecoveryStrategy(config),
        ]
    
    @staticmethod
    def create_strategy(strategy_type: ParsingStrategy, config: ParsingConfig) -> BaseExtractionStrategy:
        """Create a specific strategy."""
        strategy_map = {
            ParsingStrategy.DIRECT_JSON: DirectJSONStrategy,
            ParsingStrategy.MARKDOWN_BLOCK: MarkdownBlockStrategy,
            ParsingStrategy.REGEX_PATTERN: RegexPatternStrategy,
            ParsingStrategy.FALLBACK_RECOVERY: FallbackRecoveryStrategy,
        }
        
        strategy_class = strategy_map.get(strategy_type)
        if not strategy_class:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
        
        return strategy_class(config)