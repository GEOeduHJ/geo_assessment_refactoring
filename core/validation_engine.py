"""
Validation engine for parsed content with schema validation and error recovery.

This module provides comprehensive validation and error correction capabilities
for parsed JSON content from LLM responses.
"""

import json
import re
from typing import Dict, List, Optional, Any, Set, Union
import logging
from difflib import SequenceMatcher
from langchain_core.output_parsers import PydanticOutputParser

from .parsing_models import (
    ValidationResult, RecoveryResult, ParsingConfig,
    SuccessLevel
)

logger = logging.getLogger(__name__)


class ValidationEngine:
    """Engine for validating and correcting parsed content."""
    
    def __init__(self, config: ParsingConfig):
        self.config = config
    
    def validate_structure(self, json_data: Dict[str, Any], parser: PydanticOutputParser) -> ValidationResult:
        """
        Validate JSON data against Pydantic schema.
        
        Args:
            json_data: Parsed JSON data to validate
            parser: Pydantic output parser with schema
            
        Returns:
            ValidationResult with validation outcome
        """
        try:
            # Try direct validation first
            validated_obj = parser.parse(json.dumps(json_data, ensure_ascii=False))
            
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                corrected_data=validated_obj.model_dump() if hasattr(validated_obj, 'model_dump') else json_data
            )
            
        except Exception as e:
            logger.debug(f"Direct validation failed: {e}")
            
            # Attempt error correction if enabled
            if self.config.allow_field_mapping or self.config.allow_type_coercion:
                recovery_result = self.attempt_error_correction(json_data, parser, str(e))
                
                if recovery_result.success and recovery_result.recovered_data:
                    try:
                        # Validate corrected data
                        validated_obj = parser.parse(json.dumps(recovery_result.recovered_data, ensure_ascii=False))
                        
                        return ValidationResult(
                            is_valid=True,
                            errors=[],
                            warnings=[f"Data corrected: {note}" for note in recovery_result.recovery_notes],
                            corrected_data=validated_obj.model_dump() if hasattr(validated_obj, 'model_dump') else recovery_result.recovered_data
                        )
                    except Exception as correction_error:
                        logger.debug(f"Corrected data validation failed: {correction_error}")
            
            return ValidationResult(
                is_valid=False,
                errors=[str(e)],
                warnings=[],
                corrected_data=None
            )
    
    def attempt_error_correction(self, json_data: Dict[str, Any], 
                               parser: PydanticOutputParser, 
                               original_error: str) -> RecoveryResult:
        """
        Attempt to correct errors in JSON data.
        
        Args:
            json_data: Original JSON data with errors
            parser: Pydantic parser for schema reference
            original_error: Original validation error message
            
        Returns:
            RecoveryResult with correction outcome
        """
        try:
            corrected_data = json_data.copy()
            recovery_notes = []
            corrections_made = 0
            
            # Get expected schema information
            expected_fields = self._extract_expected_fields(parser)
            
            # Apply correction strategies
            if self.config.allow_field_mapping:
                field_corrections = self._correct_field_names(corrected_data, expected_fields)
                corrections_made += len(field_corrections)
                recovery_notes.extend([f"Mapped field: {old} -> {new}" for old, new in field_corrections])
            
            if self.config.allow_type_coercion:
                type_corrections = self._correct_field_types(corrected_data, expected_fields)
                corrections_made += len(type_corrections)
                recovery_notes.extend([f"Corrected type: {field} ({correction})" for field, correction in type_corrections])
            
            # Fill missing required fields with defaults
            if self.config.require_all_required_fields:
                missing_corrections = self._fill_missing_fields(corrected_data, expected_fields)
                corrections_made += len(missing_corrections)
                recovery_notes.extend([f"Added missing field: {field} = {value}" for field, value in missing_corrections])
            
            # Calculate confidence score
            confidence = min(1.0, max(0.1, 1.0 - (corrections_made * 0.2)))
            
            return RecoveryResult(
                success=corrections_made > 0,
                recovered_data=corrected_data if corrections_made > 0 else None,
                confidence_score=confidence,
                recovery_notes=recovery_notes
            )
            
        except Exception as e:
            logger.error(f"Error correction failed: {e}")
            return RecoveryResult(
                success=False,
                recovered_data=None,
                confidence_score=0.0,
                recovery_notes=[f"Correction failed: {str(e)}"]
            )
    
    def _extract_expected_fields(self, parser: PydanticOutputParser) -> Dict[str, Dict[str, Any]]:
        """Extract expected field information from parser schema."""
        try:
            # Get the pydantic model from parser
            model = parser.pydantic_object
            
            if hasattr(model, 'model_fields'):
                # Pydantic v2
                fields_info = {}
                for field_name, field_info in model.model_fields.items():
                    fields_info[field_name] = {
                        'type': field_info.annotation if hasattr(field_info, 'annotation') else str,
                        'required': field_info.is_required() if hasattr(field_info, 'is_required') else True,
                        'default': field_info.default if hasattr(field_info, 'default') else None
                    }
                return fields_info
            elif hasattr(model, '__fields__'):
                # Pydantic v1
                fields_info = {}
                for field_name, field_info in model.__fields__.items():
                    fields_info[field_name] = {
                        'type': field_info.type_,
                        'required': field_info.required,
                        'default': field_info.default
                    }
                return fields_info
            else:
                # Fallback - try to infer from model
                return self._infer_fields_from_model(model)
                
        except Exception as e:
            logger.warning(f"Could not extract schema fields: {e}")
            return {}
    
    def _infer_fields_from_model(self, model) -> Dict[str, Dict[str, Any]]:
        """Infer field information from model annotations."""
        try:
            fields_info = {}
            
            if hasattr(model, '__annotations__'):
                for field_name, field_type in model.__annotations__.items():
                    fields_info[field_name] = {
                        'type': field_type,
                        'required': True,  # Conservative assumption
                        'default': None
                    }
            
            return fields_info
            
        except Exception as e:
            logger.warning(f"Could not infer fields from model: {e}")
            return {}
    
    def _correct_field_names(self, data: Dict[str, Any], expected_fields: Dict[str, Dict[str, Any]]) -> List[tuple]:
        """Correct field names using fuzzy matching."""
        corrections = []
        expected_names = set(expected_fields.keys())
        current_names = set(data.keys())
        
        # Find fields that need correction
        for current_name in list(current_names):
            if current_name not in expected_names:
                # Find best match
                best_match = self._find_best_field_match(current_name, expected_names)
                if best_match and best_match not in current_names:
                    # Perform the correction
                    data[best_match] = data.pop(current_name)
                    corrections.append((current_name, best_match))
        
        return corrections
    
    def _find_best_field_match(self, field_name: str, candidates: Set[str], threshold: float = 0.6) -> Optional[str]:
        """Find the best matching field name using similarity."""
        best_match = None
        best_score = threshold
        
        for candidate in candidates:
            # Calculate similarity
            similarity = SequenceMatcher(None, field_name.lower(), candidate.lower()).ratio()
            
            if similarity > best_score:
                best_score = similarity
                best_match = candidate
        
        return best_match
    
    def _correct_field_types(self, data: Dict[str, Any], expected_fields: Dict[str, Dict[str, Any]]) -> List[tuple]:
        """Correct field types through coercion."""
        corrections = []
        
        for field_name, field_info in expected_fields.items():
            if field_name in data:
                current_value = data[field_name]
                expected_type = field_info.get('type', str)
                
                correction = self._coerce_type(current_value, expected_type)
                if correction is not None and correction != current_value:
                    data[field_name] = correction
                    corrections.append((field_name, f"{type(current_value).__name__} -> {type(correction).__name__}"))
        
        return corrections
    
    def _coerce_type(self, value: Any, expected_type: type) -> Any:
        """Attempt to coerce value to expected type."""
        try:
            # Handle Union types (e.g., Optional[str])
            if hasattr(expected_type, '__origin__'):
                if expected_type.__origin__ is Union:
                    # Try each type in the union
                    for arg_type in expected_type.__args__:
                        if arg_type is type(None):
                            continue
                        try:
                            return self._coerce_simple_type(value, arg_type)
                        except:
                            continue
                    return value
            
            return self._coerce_simple_type(value, expected_type)
            
        except Exception:
            return value
    
    def _coerce_simple_type(self, value: Any, expected_type: type) -> Any:
        """Coerce value to a simple type."""
        if isinstance(value, expected_type):
            return value
        
        # String to number
        if expected_type in (int, float) and isinstance(value, str):
            # Extract numbers from string
            numbers = re.findall(r'-?\d+\.?\d*', value)
            if numbers:
                return expected_type(numbers[0])
        
        # Number to string
        if expected_type is str and isinstance(value, (int, float)):
            return str(value)
        
        # String to boolean
        if expected_type is bool and isinstance(value, str):
            value_lower = value.lower().strip()
            if value_lower in ('true', 'yes', '1', 'on', 'enabled'):
                return True
            elif value_lower in ('false', 'no', '0', 'off', 'disabled'):
                return False
        
        # List conversion
        if expected_type is list and not isinstance(value, list):
            if isinstance(value, str):
                # Try to split string into list
                return [item.strip() for item in value.split(',') if item.strip()]
            else:
                return [value]
        
        # Dictionary conversion
        if expected_type is dict and isinstance(value, str):
            try:
                return json.loads(value)
            except:
                return {"content": value}
        
        # Default conversion attempt
        try:
            return expected_type(value)
        except:
            return value
    
    def _fill_missing_fields(self, data: Dict[str, Any], expected_fields: Dict[str, Dict[str, Any]]) -> List[tuple]:
        """Fill missing required fields with default values."""
        additions = []
        
        for field_name, field_info in expected_fields.items():
            if field_name not in data and field_info.get('required', True):
                default_value = self._get_default_value(field_name, field_info)
                if default_value is not None:
                    data[field_name] = default_value
                    additions.append((field_name, default_value))
        
        return additions
    
    def _get_default_value(self, field_name: str, field_info: Dict[str, Any]) -> Any:
        """Get appropriate default value for a field."""
        # Use explicit default if available
        if 'default' in field_info and field_info['default'] is not None:
            return field_info['default']
        
        # Infer default based on field name and type
        field_type = field_info.get('type', str)
        field_name_lower = field_name.lower()
        
        # Common field patterns
        if '점수' in field_name_lower or 'score' in field_name_lower:
            return 0
        elif '피드백' in field_name_lower or 'feedback' in field_name_lower:
            return "피드백을 생성할 수 없습니다."
        elif '판단' in field_name_lower or '근거' in field_name_lower:
            return "판단 근거를 생성할 수 없습니다."
        elif '결과' in field_name_lower or 'result' in field_name_lower:
            return {}
        
        # Default by type
        if field_type in (int, float):
            return 0
        elif field_type is str:
            return ""
        elif field_type is list:
            return []
        elif field_type is dict:
            return {}
        elif field_type is bool:
            return False
        
        return None
    
    def _create_adaptive_schema(self, rubric_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create flexible schema based on actual rubric structure.
        
        This method creates a JSON schema that adapts to the specific rubric
        structure, making validation more flexible and successful.
        
        Args:
            rubric_items: List of rubric items with main_criterion and sub_criteria
            
        Returns:
            JSON schema dictionary for validation
        """
        logger.debug(f"Creating adaptive schema for {len(rubric_items)} rubric items")
        
        # Create schema for scoring results
        scoring_properties = {}
        
        # Add score fields for each rubric item
        for i, item in enumerate(rubric_items):
            # Main criterion score field
            main_field = f"주요_채점_요소_{i+1}_점수"
            scoring_properties[main_field] = {
                "type": "integer",
                "description": f"주요 채점 요소 {i+1}에 대한 점수",
                "minimum": 0
            }
            
            # Sub-criteria score fields
            for j, sub_item in enumerate(item.get('sub_criteria', [])):
                sub_field = f"세부_채점_요소_{i+1}_{j+1}_점수"
                scoring_properties[sub_field] = {
                    "type": "integer",
                    "description": f"세부 채점 요소 {i+1}-{j+1}에 대한 점수",
                    "minimum": 0
                }
        
        # Add required total score and reasoning fields
        scoring_properties["합산_점수"] = {
            "type": "integer",
            "description": "모든 주요 채점 요소 점수의 합산",
            "minimum": 0
        }
        
        scoring_properties["점수_판단_근거"] = {
            "type": "object",
            "description": "각 주요 채점 요소별 점수 판단 근거",
            "additionalProperties": True  # Allow flexible structure
        }
        
        # Create schema for feedback
        feedback_properties = {
            "교과_내용_피드백": {
                "type": "string",
                "description": "교과 내용에 대한 구체적인 피드백",
                "minLength": 1
            },
            "의사_응답_여부": {
                "type": "boolean",
                "description": "학생 답안이 의사 응답(bluffing)인지 여부"
            },
            "의사_응답_설명": {
                "type": "string",
                "description": "의사 응답인 경우 설명, 아니면 빈 문자열",
                "default": ""
            }
        }
        
        # Combine into full schema
        adaptive_schema = {
            "type": "object",
            "properties": {
                "채점결과": {
                    "type": "object",
                    "properties": scoring_properties,
                    "required": ["합산_점수"],  # Only require essential fields
                    "additionalProperties": False
                },
                "피드백": {
                    "type": "object",
                    "properties": feedback_properties,
                    "required": ["교과_내용_피드백", "의사_응답_여부"],
                    "additionalProperties": False
                }
            },
            "required": ["채점결과", "피드백"],
            "additionalProperties": False
        }
        
        logger.debug(f"Created adaptive schema with {len(scoring_properties)} scoring fields")
        return adaptive_schema
    
    def validate_with_adaptive_schema(self, json_data: Dict[str, Any], 
                                    rubric_items: List[Dict[str, Any]]) -> ValidationResult:
        """Validate JSON data using adaptive schema.
        
        Args:
            json_data: Parsed JSON data to validate
            rubric_items: Rubric items for schema creation
            
        Returns:
            ValidationResult with validation outcome
        """
        try:
            adaptive_schema = self._create_adaptive_schema(rubric_items)
            
            # Perform basic structure validation
            validation_errors = []
            validation_warnings = []
            corrected_data = json_data.copy()
            
            # Check required top-level fields
            if "채점결과" not in corrected_data:
                validation_errors.append("Missing required field: 채점결과")
            if "피드백" not in corrected_data:
                validation_errors.append("Missing required field: 피드백")
            
            if validation_errors:
                # Try to add missing top-level structures
                if "채점결과" not in corrected_data:
                    corrected_data["채점결과"] = {"합산_점수": 0}
                    validation_warnings.append("Added missing 채점결과 structure")
                
                if "피드백" not in corrected_data:
                    corrected_data["피드백"] = {
                        "교과_내용_피드백": "구조적 오류로 인해 피드백을 생성할 수 없습니다.",
                        "의사_응답_여부": False,
                        "의사_응답_설명": ""
                    }
                    validation_warnings.append("Added missing 피드백 structure")
            
            # Validate and correct scoring fields
            scoring_section = corrected_data.get("채점결과", {})
            if "합산_점수" not in scoring_section:
                scoring_section["합산_점수"] = 0
                validation_warnings.append("Added missing 합산_점수 field")
            
            # Validate and correct feedback fields
            feedback_section = corrected_data.get("피드백", {})
            required_feedback_fields = ["교과_내용_피드백", "의사_응답_여부"]
            for field in required_feedback_fields:
                if field not in feedback_section:
                    if field == "교과_내용_피드백":
                        feedback_section[field] = "필수 피드백 필드가 누락되었습니다."
                    elif field == "의사_응답_여부":
                        feedback_section[field] = False
                    validation_warnings.append(f"Added missing {field} field")
            
            # If we had errors but managed corrections, it's a partial success
            if validation_errors and validation_warnings:
                return ValidationResult(
                    is_valid=True,
                    errors=[],
                    warnings=validation_warnings,
                    corrected_data=corrected_data
                )
            
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=validation_warnings,
                corrected_data=corrected_data
            )
            
        except Exception as e:
            logger.error(f"Adaptive validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                errors=[f"Adaptive validation error: {str(e)}"],
                warnings=[],
                corrected_data=None
            )