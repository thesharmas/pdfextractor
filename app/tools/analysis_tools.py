import logging
from typing import List, Dict, Tuple
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from app.services.llm_factory import LLMFactory
import json
from langchain_core.pydantic_v1 import BaseModel, Field

logger = logging.getLogger(__name__)

# Store single LLM instance at module level
_llm = None

def set_llm(llm):
    """Set single LLM instance to be used by all tools"""
    global _llm
    _llm = llm

# Pydantic models for structured output
class NSFFee(BaseModel):
    """Structure for a single NSF fee"""
    date: str = Field(description="Date the NSF fee was charged")
    amount: float = Field(description="Amount of the NSF fee")
    description: str = Field(description="Description of the fee")

class NSFAnalysis(BaseModel):
    """Structure for NSF fee analysis"""
    total_fees: float = Field(description="Total amount of NSF fees")
    incident_count: int = Field(description="Number of NSF incidents")
    fees: List[NSFFee] = Field(description="List of individual NSF fees")

class BalanceAnalysis(BaseModel):
    """Structure for balance analysis"""
    average_daily_balance: float = Field(description="Average daily balance")
    details: str = Field(description="Explanation of the calculation")

@tool
def calculate_average_daily_balance() -> BalanceAnalysis:
    """Calculate the average daily balance from bank statements"""
    logger.info("🔧 Tool calculate_average_daily_balance called")
    try:
        prompt = """You are a JSON-only response bot. Analyze the bank statements and calculate the average daily balance.
        
        You must ONLY return a valid JSON object in this exact format, with no additional text or explanation:
        {
            "average_daily_balance": <number>,
            "details": "<explanation string>"
        }
        """
        
        response = _llm.get_response(prompt=prompt)
        logger.debug(f"Raw LLM Response: {response}")
        
        # Clean the response - remove any markdown formatting
        cleaned_response = response.strip()
        if cleaned_response.startswith('```json'):
            cleaned_response = cleaned_response.replace('```json', '', 1)
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()
        
        logger.debug(f"Cleaned Response: {cleaned_response}")
        
        try:
            json_data = json.loads(cleaned_response)
            logger.debug(f"Parsed JSON: {json_data}")
            return BalanceAnalysis(**json_data)
        except json.JSONDecodeError as je:
            logger.error(f"JSON parsing failed: {je}")
            logger.error(f"Failed response: {cleaned_response}")
            raise
        
    except Exception as e:
        logger.error("Tool error: %s", str(e))
        logger.error("Full traceback:", exc_info=True)
        return BalanceAnalysis(average_daily_balance=0.0, details=str(e))

@tool
def check_nsf() -> NSFAnalysis:
    """Check for NSF fees in bank statements."""
    logger.info("🔧 Tool check_nsf called")
    try:
        prompt = """You are a JSON-only response bot. Analyze these bank statements for NSF (Non-Sufficient Funds) fees.
        
        You must ONLY return a valid JSON object in this exact format, with no additional text or explanation:
        {
            "total_fees": <number>,
            "incident_count": <number>,
            "fees": [
                {
                    "date": "YYYY-MM-DD",
                    "amount": <number>,
                    "description": "<string>"
                }
            ]
        }
        """
        
        response = _llm.get_response(prompt=prompt)
        logger.debug(f"Raw LLM Response: {response}")
        
        # Clean the response - remove any markdown formatting
        cleaned_response = response.strip()
        if cleaned_response.startswith('```json'):
            cleaned_response = cleaned_response.replace('```json', '', 1)
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()
        
        logger.debug(f"Cleaned Response: {cleaned_response}")
        
        try:
            json_data = json.loads(cleaned_response)
            logger.debug(f"Parsed JSON: {json_data}")
            return NSFAnalysis(**json_data)
        except json.JSONDecodeError as je:
            logger.error(f"JSON parsing failed: {je}")
            logger.error(f"Failed response: {cleaned_response}")
            raise
        
    except Exception as e:
        logger.error("Tool error: %s", str(e))
        logger.error("Full traceback:", exc_info=True)
        return NSFAnalysis(total_fees=0.0, incident_count=0, fees=[]) 