import logging
from typing import List, Dict, Tuple, Any
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from app.services.llm_factory import LLMFactory
import json
from langchain_core.pydantic_v1 import BaseModel, Field
import time
import traceback
import re

logger = logging.getLogger(__name__)

# Store single LLM instance at module level
_llm = None

def set_llm(llm: Any) -> None:
    """Set the LLM instance to be used by the tools.
    
    Args:
        llm (Any): The LLM wrapper instance to use
    """
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
def calculate_average_daily_balance(input_text: str) -> Tuple[float, str]:
    """Calculate the average daily balance from bank statements."""
    prompt = """You are a JSON-only response bot. Analyze ALL bank statements provided, covering the ENTIRE date range.
        
You must ONLY return a valid JSON object in this exact format, with no additional text or explanation:

{
    "daily_balances": {
        "YYYY-MM-DD": amount,
        // Include EVERY day from the FIRST to LAST date in statements
    },
    "total_days": number_of_days,
    "sum_of_balances": total_sum,
    "FINAL_AMOUNT": final_average
}

CRITICAL RULES:
1. Return ONLY valid JSON - no extra text
2. Analyze ALL months in the statements
3. Include EVERY day from first to last date
4. Use ending balance for each day
5. Round all amounts to 2 decimal places
6. Do not add ANY text before or after the JSON
7. Ensure ALL quotes and brackets are properly closed"""

    try:
        logger.info("🔧 Tool calculate_average_daily_balance called")
        response = _llm.get_response(prompt=prompt)
        
        logger.info("Raw response received:")
        logger.info("-" * 50)
        logger.info(response)
        logger.info("-" * 50)

        # Clean and validate JSON
        try:
            # Remove any non-JSON text
            cleaned_response = response.strip()
            
            # Find JSON boundaries
            start = cleaned_response.find('{')
            end = cleaned_response.rfind('}') + 1
            
            if start == -1 or end == 0:
                raise ValueError("No JSON object found in response")
                
            cleaned_response = cleaned_response[start:end]
            
            # Fix common JSON issues
            cleaned_response = cleaned_response.replace('\n', ' ')
            cleaned_response = cleaned_response.replace('\\', '\\\\')
            cleaned_response = re.sub(r'(?<!\\)"(?![:,}\]])', '\\"', cleaned_response)
            
            # Fix unquoted property names
            cleaned_response = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', cleaned_response)
            
            # Remove comments
            cleaned_response = re.sub(r'//.*?\n', '', cleaned_response)
            cleaned_response = re.sub(r'/\*.*?\*/', '', cleaned_response, flags=re.DOTALL)
            
            logger.info("Cleaned response:")
            logger.info(cleaned_response)
            
            # Parse JSON
            try:
                data = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                # If still failing, try a more aggressive cleaning
                cleaned_response = re.sub(r'[^{}[\]:",.0-9a-zA-Z_-]', ' ', cleaned_response)
                cleaned_response = re.sub(r'\s+', ' ', cleaned_response)
                data = json.loads(cleaned_response)
            
            # Validate required fields
            required_fields = ['daily_balances', 'total_days', 'sum_of_balances', 'FINAL_AMOUNT']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            logger.info(f"Successfully parsed JSON with {len(data['daily_balances'])} days")
            
            return data['FINAL_AMOUNT'], json.dumps(data, indent=2)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Attempted to parse: {cleaned_response}")
            raise ValueError(f"Invalid JSON response: {str(e)}")
            
    except Exception as e:
        logger.error(f"Tool error: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return 0.0, json.dumps({
            "error": str(e),
            "daily_balances": {},
            "total_days": 0,
            "sum_of_balances": 0,
            "FINAL_AMOUNT": 0
        })

@tool
def check_nsf(input_text: str) -> Tuple[float, int, str]:
    """Check for NSF (Non-Sufficient Funds) fees and incidents."""
    prompt = """You are a JSON-only response bot. Analyze ALL bank statements for NSF (Non-Sufficient Funds) fees across the ENTIRE date range. Do not consider any fees that are not NSF fees (like overdraft fees).
    
You must ONLY return a valid JSON object in this exact format, with no additional text or explanation:

{
    "nsf_incidents": [
        {
            "date": "YYYY-MM-DD",
            "amount": fee_amount        }
    ],
    "total_fees": total_amount,
    "incident_count": number_of_incidents
}

IMPORTANT:
1. Check ALL months in the statements, not just the first month
2. Look for NSF fees across the entire date range
3. Include ALL incidents found in ANY month
4. All dates must be in YYYY-MM-DD format
5. All amounts must be numbers (not strings)
6. Round all amounts to 2 decimal places
7. Verify you've checked all statements before responding
8. Ensure the JSON is valid and properly formatted"""

    try:
        logger.info("🔧 Tool check_nsf called")
        response = _llm.get_response(prompt=prompt)
        
        logger.info("Raw response received:")
        logger.info("-" * 50)
        logger.info(response)
        logger.info("-" * 50)
        
        if not response:
            logger.error("Received empty response from LLM")
            raise ValueError("Empty response from LLM")
            
        # Clean the response
        cleaned_response = response.strip()
        
        # Remove markdown and language indicators
        if "```" in cleaned_response:
            # Extract content between first and last ```
            parts = cleaned_response.split("```")
            if len(parts) >= 3:
                cleaned_response = parts[1]  # Get content between first set of ```
                # Remove language indicator if present
                if cleaned_response.startswith("json"):
                    cleaned_response = cleaned_response[4:].strip()
        
        logger.info("Cleaned response:")
        logger.info(cleaned_response)
        
        try:
            data = json.loads(cleaned_response)
            
            # Validate required fields
            required_fields = ['nsf_incidents', 'total_fees', 'incident_count']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate incident data
            for incident in data['nsf_incidents']:
                required_incident_fields = ['date', 'amount']
                for field in required_incident_fields:
                    if field not in incident:
                        raise ValueError(f"Missing field {field} in NSF incident")
            
            logger.info(f"Successfully parsed JSON with {len(data['nsf_incidents'])} incidents")
            logger.info(f"Total fees: ${data['total_fees']:,.2f}")
            logger.info(f"Incident count: {data['incident_count']}")
            
            return data['total_fees'], data['incident_count'], json.dumps(data, indent=2)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Attempted to parse: {cleaned_response}")
            raise ValueError(f"Invalid JSON response: {str(e)}")
            
    except Exception as e:
        logger.error(f"Tool error: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return 0.0, 0, json.dumps({
            "error": str(e),
            "nsf_incidents": [],
            "total_fees": 0,
            "incident_count": 0
        }) 