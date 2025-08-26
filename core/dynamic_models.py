"""
Dynamic Pydantic model creation for grading results.
This module creates Pydantic models based on rubric structure.
"""
from pydantic import BaseModel, Field, create_model
from langchain_core.output_parsers import PydanticOutputParser
from typing import Dict, List, Any


class 피드백(BaseModel):
    """Fixed feedback model for all grading types."""
    교과_내용_피드백: str = Field(description="교과 내용에 대한 구체적인 피드백")
    의사_응답_여부: bool = Field(description="학생 답안이 의사 응답(bluffing)인지 여부 (True/False)")
    의사_응답_설명: str = Field(description="의사 응답인 경우 설명, 아니면 빈 문자열")


class DynamicModelFactory:
    """Factory class for creating dynamic Pydantic models based on rubric."""
    
    @staticmethod
    def create_grading_result_model(rubric_items: List[Dict[str, Any]]):
        """
        Create a dynamic grading result model based on rubric items.
        
        Args:
            rubric_items: List of rubric items with main_criterion and sub_criteria
            
        Returns:
            Dynamic Pydantic model class for grading results
        """
        fields = {}
        
        # Add score fields for each rubric item
        for i, item in enumerate(rubric_items):
            # Main criterion score field
            field_name = f"주요_채점_요소_{i+1}_점수"
            fields[field_name] = (int, Field(description=f"주요 채점 요소 {i+1}에 대한 점수"))
            
            # Sub-criteria score fields
            for j, sub_item in enumerate(item.get('sub_criteria', [])):
                sub_field_name = f"세부_채점_요소_{i+1}_{j+1}_점수"
                fields[sub_field_name] = (int, Field(description=f"세부 채점 요소 {i+1}-{j+1}에 대한 점수"))
        
        # Add total score and reasoning fields
        fields["합산_점수"] = (int, Field(description="모든 주요 채점 요소 점수의 합산"))
        fields["점수_판단_근거"] = (dict, Field(
            description='각 주요 채점 요소별 점수 판단 근거 (예: {"주요_채점_요소_1": "근거 내용"})'
        ))
        
        # Create the dynamic model
        Dynamic채점결과 = create_model("채점결과", **fields)
        return Dynamic채점결과
    
    @staticmethod
    def create_grading_output_model(rubric_items: List[Dict[str, Any]]):
        """
        Create a complete grading output model with both scoring and feedback.
        
        Args:
            rubric_items: List of rubric items with main_criterion and sub_criteria
            
        Returns:
            Dynamic Pydantic model class for complete grading output
        """
        Dynamic채점결과 = DynamicModelFactory.create_grading_result_model(rubric_items)
        
        DynamicGradingOutput = create_model(
            "GradingOutput", 
            채점결과=(Dynamic채점결과, ...), 
            피드백=(피드백, ...)
        )
        
        return DynamicGradingOutput
    
    @staticmethod
    def create_parser(rubric_items: List[Dict[str, Any]]) -> PydanticOutputParser:
        """
        Create a Pydantic output parser for the given rubric.
        
        Args:
            rubric_items: List of rubric items with main_criterion and sub_criteria
            
        Returns:
            PydanticOutputParser configured for the dynamic model
        """
        DynamicGradingOutput = DynamicModelFactory.create_grading_output_model(rubric_items)
        return PydanticOutputParser(pydantic_object=DynamicGradingOutput)


def get_default_parser() -> PydanticOutputParser:
    """
    Get a default parser for basic grading structure.
    Used when no specific rubric is available.
    """
    # Create a basic rubric structure for default parser
    default_rubric = [
        {
            'main_criterion': '기본 채점 요소',
            'sub_criteria': [
                {'score': 1, 'content': '기본 채점 내용'}
            ]
        }
    ]
    
    return DynamicModelFactory.create_parser(default_rubric)