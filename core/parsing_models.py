"""
Data models for enhanced LLM response parsing system.

This module defines the core data structures used for parsing results,
success levels, and validation outcomes in the enhanced response parser.
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from dataclasses import dataclass


class SuccessLevel(Enum):
    """Enumeration for parsing success levels."""
    FULL = "full"          # Complete successful parsing
    PARTIAL = "partial"    # Some content recovered
    FAILED = "failed"      # No usable content


class ParsingStrategy(Enum):
    """Enumeration for parsing strategy types."""
    DIRECT_JSON = "direct_json"
    MARKDOWN_BLOCK = "markdown_block"
    REGEX_PATTERN = "regex_pattern"
    FALLBACK_RECOVERY = "fallback_recovery"


class ValidationResult(BaseModel):
    """Result of schema validation."""
    is_valid: bool = Field(description="Whether validation was successful")
    errors: List[str] = Field(default_factory=list, description="Validation error messages")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    corrected_data: Optional[Dict[str, Any]] = Field(default=None, description="Data after error correction")


class ParsingAttempt(BaseModel):
    """Details of a single parsing attempt."""
    strategy: ParsingStrategy = Field(description="Strategy used for parsing")
    success: bool = Field(description="Whether this attempt was successful")
    extracted_content: Optional[str] = Field(default=None, description="Extracted JSON content")
    parsed_data: Optional[Dict[str, Any]] = Field(default=None, description="Successfully parsed data")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    execution_time_ms: float = Field(description="Time taken for this attempt in milliseconds")


class ParsingResult(BaseModel):
    """
    Comprehensive result of LLM response parsing.
    
    This class contains all information about the parsing process,
    including success level, data, errors, and diagnostic information.
    """
    success_level: SuccessLevel = Field(description="Overall success level of parsing")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Successfully parsed and validated data")
    errors: List[str] = Field(default_factory=list, description="List of error messages")
    warnings: List[str] = Field(default_factory=list, description="List of warning messages")
    raw_response: str = Field(description="Original LLM response")
    
    # Diagnostic information
    attempts: List[ParsingAttempt] = Field(default_factory=list, description="All parsing attempts made")
    successful_strategy: Optional[ParsingStrategy] = Field(default=None, description="Strategy that succeeded")
    total_processing_time_ms: float = Field(description="Total time for all parsing attempts")
    validation_result: Optional[ValidationResult] = Field(default=None, description="Final validation result")
    
    # Recovery information
    partial_content: Optional[Dict[str, Any]] = Field(default=None, description="Partially recovered content")
    recovery_notes: List[str] = Field(default_factory=list, description="Notes about recovery attempts")

    def is_successful(self) -> bool:
        """Check if parsing was successful (FULL or PARTIAL)."""
        return self.success_level in [SuccessLevel.FULL, SuccessLevel.PARTIAL]
    
    def has_usable_data(self) -> bool:
        """Check if there is usable data available."""
        return self.data is not None or self.partial_content is not None
    
    def get_best_data(self) -> Optional[Dict[str, Any]]:
        """Get the best available data (primary data or partial content)."""
        return self.data if self.data is not None else self.partial_content


class RecoveryResult(BaseModel):
    """Result of error recovery attempt."""
    success: bool = Field(description="Whether recovery was successful")
    recovered_data: Optional[Dict[str, Any]] = Field(default=None, description="Recovered data")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence in recovery quality")
    recovery_notes: List[str] = Field(default_factory=list, description="Notes about recovery process")


@dataclass
class ParsingConfig:
    """Configuration for the enhanced parser."""
    max_attempts: int = 4
    timeout_seconds: float = 30.0
    enable_fallback_recovery: bool = True
    enable_partial_recovery: bool = True
    require_all_required_fields: bool = True
    allow_field_mapping: bool = True
    allow_type_coercion: bool = True
    log_all_attempts: bool = True


class ExtractionContext(BaseModel):
    """Context information for content extraction."""
    original_response: str = Field(description="Original LLM response")
    response_length: int = Field(description="Length of original response")
    detected_format: Optional[str] = Field(default=None, description="Detected response format")
    has_code_blocks: bool = Field(default=False, description="Whether response contains code blocks")
    has_json_markers: bool = Field(default=False, description="Whether response contains JSON markers")
    language_hints: List[str] = Field(default_factory=list, description="Detected language hints")