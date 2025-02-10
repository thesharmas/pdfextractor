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
        prompt = """
        Analyze the bank statements and calculate the average daily balance.
        Return the result in this exact JSON structure:
        {
            "average_daily_balance": <calculated average balance>,
            "details": "<explanation of how the calculation was performed>"
        }
        """
        
        response = _llm.get_response(prompt=prompt)
        return BalanceAnalysis.model_validate_json(response)
        
    except Exception as e:
        logger.error("Tool error: %s", str(e))
        logger.error("Full traceback:", exc_info=True)
        return BalanceAnalysis(average_daily_balance=0.0, details=str(e))

@tool
def check_nsf() -> NSFAnalysis:
    """Check for NSF fees in bank statements."""
    logger.info("🔧 Tool check_nsf called")
    try:
        prompt = """
        Analyze these bank statements for NSF (Non-Sufficient Funds) fees.
        Return the information in this exact JSON structure:
        {
            "total_fees": <total amount of all NSF fees>,
            "incident_count": <number of NSF incidents>,
            "fees": [
                {
                    "date": "YYYY-MM-DD",
                    "amount": <fee amount>,
                    "description": "<description of the fee>"
                }
                // ... additional fees if any
            ]
        }
        """
        
        response = _llm.get_response(prompt=prompt)
        return NSFAnalysis.model_validate_json(response)
        
    except Exception as e:
        logger.error("Tool error: %s", str(e))
        logger.error("Full traceback:", exc_info=True)
        return NSFAnalysis(total_fees=0.0, incident_count=0, fees=[]) 