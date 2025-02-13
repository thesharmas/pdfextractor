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
from datetime import datetime, timedelta
from app.config import LLMProvider


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
def check_nsf(input_text: str) -> str:
    """Check for NSF (Non-Sufficient Funds) fees and incidents. Returns JSON response."""
    prompt = """You are a JSON-only response bot. Analyze ALL bank statements for NSF (Non-Sufficient Funds) fees across the ENTIRE date range. Do not consider any fees that are not NSF fees (like overdraft fees).
    
You must ONLY return a valid JSON object in this exact format, with no additional text or explanation:

{
    "nsf_incidents": [
        {
            "date": "YYYY-MM-DD",
            "amount": fee_amount        
        }
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
            parts = cleaned_response.split("```")
            if len(parts) >= 3:
                cleaned_response = parts[1]
                if cleaned_response.startswith("json"):
                    cleaned_response = cleaned_response[4:].strip()
        
        logger.info("Cleaned response:")
        logger.info(cleaned_response)
        
        # Validate JSON
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
            
            return cleaned_response
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Attempted to parse: {cleaned_response}")
            raise ValueError(f"Invalid JSON response: {str(e)}")
            
    except Exception as e:
        logger.error(f"Tool error: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return json.dumps({
            "error": str(e),
            "nsf_incidents": [],
            "total_fees": 0,
            "incident_count": 0
        })

@tool
def calculate_average_daily_balance(pdf_text: str = "None") -> Tuple[float, str]:
    """
    Calculate average daily balance from bank statements.
    Returns tuple of (final_average, details_json_string)
    """
    prompt = """You are a JSON-only response bot. Extract ALL transactions from the bank statements provided.
        
    You must ONLY return a valid JSON object in this exact format, with no additional text or explanation:

    {
        "transactions": [
            {
                "date": "YYYY-MM-DD",
                "balance": amount,
                "is_business_day": boolean,
                "description": "transaction description if available"
            }
        ]
    }

    CRITICAL RULES:
    1. Return ONLY valid JSON - no extra text
    2. Include EVERY transaction and balance from the statements
    3. DO NOT interpolate or create transactions
    4. DO NOT skip any transactions
    5. Mark business days (Mon-Fri) as true, weekends as false
    6. Round all amounts to 2 decimal places
    7. Include the ending balance for each day that appears in statements
    8. Order transactions by date ascending"""

    # Get raw transactions from LLM
    llm_response = _llm.get_llm_response(prompt=prompt)
    transactions = llm_response.get("transactions", [])

    # Calculate daily balances and averages
    def is_business_day(date: datetime) -> bool:
        return date.weekday() < 5  # 0-4 are Monday to Friday

    # Sort transactions by date
    sorted_trans = sorted(transactions, key=lambda x: x['date'])
    
    # Group transactions by month
    monthly_data = {}
    
    current_period = {
        'start_date': None,
        'end_date': None,
        'last_balance': None,
        'business_days': 0
    }
    
    for trans in sorted_trans:
        date = datetime.strptime(trans['date'], '%Y-%m-%d')
        month_key = date.strftime('%Y-%m')
        
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                'daily_balances': {},
                'statement_periods': [],
                'sum': 0,
                'days': 0
            }
        
        # Handle statement periods
        if current_period['start_date'] is None:
            current_period['start_date'] = date
            current_period['business_days'] = 1
        elif (date - current_period['end_date']).days > 3:  # Gap detected
            if current_period['business_days'] >= 3:  # Valid period
                monthly_data[month_key]['statement_periods'].append({
                    'start_date': current_period['start_date'].strftime('%Y-%m-%d'),
                    'end_date': current_period['end_date'].strftime('%Y-%m-%d'),
                    'days_in_period': (current_period['end_date'] - current_period['start_date']).days + 1
                })
            # Start new period
            current_period = {
                'start_date': date,
                'end_date': date,
                'last_balance': trans['balance'],
                'business_days': 1
            }
        else:
            # Fill in any missing days between last transaction and current
            prev_date = current_period['end_date']
            while prev_date < date - timedelta(days=1):
                prev_date += timedelta(days=1)
                if prev_date.month == date.month:
                    monthly_data[month_key]['daily_balances'][prev_date.strftime('%Y-%m-%d')] = current_period['last_balance']
            
            current_period['end_date'] = date
            current_period['last_balance'] = trans['balance']
            if is_business_day(date):
                current_period['business_days'] += 1
        
        # Store the actual transaction balance
        monthly_data[month_key]['daily_balances'][trans['date']] = trans['balance']
    
    # Calculate monthly averages
    for month_data in monthly_data.values():
        total_sum = sum(month_data['daily_balances'].values())
        total_days = len(month_data['daily_balances'])
        month_data['sum'] = total_sum
        month_data['days'] = total_days
        month_data['average'] = total_sum / total_days if total_days > 0 else 0

    # Return in the expected format
    final_amount = sum(m['average'] for m in monthly_data.values()) / len(monthly_data) if monthly_data else 0
    
    details = {
        "daily_balances": {
            date: balance 
            for month in monthly_data.values() 
            for date, balance in month['daily_balances'].items()
        },
        "monthly_averages": monthly_data,
        "total_months": len(monthly_data),
        "FINAL_AMOUNT": final_amount
    }
    
    return final_amount, json.dumps(details)

@tool
def check_statement_continuity(input_text: str) -> str:
    """
    Check if bank statements are contiguous (sequential months with no gaps).
    Returns JSON string with analysis results.
    """
    prompt = """You are a JSON-only response bot. THOROUGHLY analyze ALL bank statements to identify date ranges covered.
    
    You must ONLY return a valid JSON object in this exact format, with no additional text or explanation:

    {
        "statement_periods": [
            {
                "start_date": "YYYY-MM-DD",
                "end_date": "YYYY-MM-DD"
            }
        ],
        "analysis": {
            "is_contiguous": boolean,
            "gap_details": ["Gap found between YYYY-MM-DD and YYYY-MM-DD"],
            "explanation": "Detailed explanation of why statements are not contiguous, or 'Statements are contiguous' if no gaps"
        }
    }

    CRITICAL RULES:
    1. Return ONLY valid JSON - no extra text
    2. IMPORTANT: You MUST check EVERY page of EVERY statement thoroughly
    3. DO NOT skip any pages or statements
    4. Search for ALL month headers, dates, and period indicators
    5. Common statement indicators to look for:
       - "Statement Period: MM/DD to MM/DD"
       - "Statement Dates: MM/DD/YYYY - MM/DD/YYYY"
       - Monthly headers showing statement month
       - Date ranges at top or bottom of statements
    6. After finding ALL periods:
       - Sort them by start_date
       - Check for gaps between sorted periods
       - Month transitions (like July 31 to August 1) are NOT gaps
    7. VERIFY before responding:
       - Have you checked every page?
       - Did you find all month headers?
       - Are all statement periods accounted for?
    8. If you find any mention of September, October, or any month:
       - You MUST include it in the periods list
       - Double-check start and end dates
    9. DO NOT assume months are missing without thorough verification
    10. If you're unsure about a period, include it and note in explanation"""

    try:
        logger.info("🔧 Tool check_statement_continuity called")
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
            parts = cleaned_response.split("```")
            if len(parts) >= 3:
                cleaned_response = parts[1]
                if cleaned_response.startswith("json"):
                    cleaned_response = cleaned_response[4:].strip()
        
        logger.info("Cleaned response:")
        logger.info(cleaned_response)
        
        # Validate JSON
        try:
            data = json.loads(cleaned_response)
            
            # Validate required fields
            if 'statement_periods' not in data or 'analysis' not in data:
                raise ValueError("Missing required fields: statement_periods or analysis")
                
            if 'is_contiguous' not in data['analysis']:
                raise ValueError("Missing is_contiguous in analysis")
            
            logger.info(f"Successfully parsed JSON with {len(data['statement_periods'])} periods")
            logger.info(f"Is contiguous: {data['analysis']['is_contiguous']}")
            
            # Add explanation validation
            if 'explanation' not in data['analysis']:
                raise ValueError("Missing required field: analysis.explanation")
            
            logger.info(f"Continuity explanation: {data['analysis']['explanation']}")
            
            return cleaned_response
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Attempted to parse: {cleaned_response}")
            raise ValueError(f"Invalid JSON response: {str(e)}")
            
    except Exception as e:
        logger.error(f"Tool error: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return json.dumps({
            "statement_periods": [],
            "analysis": {
                "is_contiguous": False,
                "gap_details": [f"Error analyzing continuity: {str(e)}"],
                "explanation": f"Error during analysis: {str(e)}"
            }
        })

@tool
def extract_daily_balances(input_text: str) -> str:
    """Extract or calculate daily balances from bank statements. Returns JSON response."""
    
    try:
        # Parse input_text as JSON to get continuity data
        input_data = json.loads(input_text) if input_text != "None" else {}
        continuity_data = input_data.get("continuity_data", {})
        
        if not continuity_data:
            logger.error("No continuity data provided")
            return json.dumps({"daily_balances": []})
        
        periods = continuity_data.get("statement_periods", [])
        if not periods:
            logger.error("No statement periods found in continuity data")
            return json.dumps({"daily_balances": []})
        
        # Sort periods to ensure chronological order
        periods.sort(key=lambda x: x['start_date'])
        
        # Process statements in chunks of 2 months
        all_balances = []
        
        for i in range(0, len(periods), 2):
            chunk_periods = periods[i:i+2]
            chunk_start = chunk_periods[0]['start_date']
            chunk_end = chunk_periods[-1]['end_date']
            
            logger.info(f"Processing chunk from {chunk_start} to {chunk_end}")
            
            chunk_prompt = f"""You are a JSON-only response bot. Extract daily balances for the period from {chunk_start} to {chunk_end}.

            CRITICAL RULES FOR BALANCE TYPES:
            1. "direct" balances:
               - Use ONLY when the exact balance is directly stated in the statement
               - Typically found at statement start/end dates
               - Found in "Ending Balance", "Beginning Balance", or "Balance Forward" entries
               - These are the ACTUAL balances from the bank statement
            
            2. "calculated" balances:
               - Use ONLY when a direct balance is NOT available
               - Must be calculated from transactions
               - Should be less common than direct balances
               - Only use when you need to fill gaps between direct balances

            Return ONLY a valid JSON object in this exact format:
            {{
                "daily_balances": [
                    {{
                        "date": "YYYY-MM-DD",
                        "balance": amount,
                        "is_business_day": boolean,
                        "balance_type": "direct" or "calculated"
                    }}
                ]
            }}

            IMPORTANT: 
            - Prefer "direct" balances whenever possible
            - Only use "calculated" when you must fill gaps
            - Extract ALL daily balances between {chunk_start} and {chunk_end}
            """

            try:
                chunk_response = _llm.get_response(prompt=chunk_prompt)
                
                # Log raw response for debugging
                logger.info("Raw chunk response:")
                logger.info("-" * 50)
                logger.info(chunk_response)
                logger.info("-" * 50)
                
                # Clean the response
                cleaned_response = chunk_response.strip()
                if "```json" in cleaned_response:
                    cleaned_response = cleaned_response.split("```json")[1]
                if "```" in cleaned_response:
                    cleaned_response = cleaned_response.split("```")[0]
                cleaned_response = cleaned_response.strip()
                
                logger.info("Cleaned chunk response:")
                logger.info(cleaned_response)
                
                chunk_data = json.loads(cleaned_response)
                all_balances.extend(chunk_data.get("daily_balances", []))
                
            except Exception as e:
                logger.error(f"Error processing chunk {chunk_start} to {chunk_end}: {str(e)}")
                logger.error(f"Raw response was: {chunk_response}")
                logger.error(f"Full traceback:\n{traceback.format_exc()}")
        
        # Sort all balances by date
        all_balances.sort(key=lambda x: x['date'])
        
        # Remove any duplicates
        seen_dates = set()
        unique_balances = []
        for balance in all_balances:
            if balance['date'] not in seen_dates:
                seen_dates.add(balance['date'])
                unique_balances.append(balance)
        
        return json.dumps({"daily_balances": unique_balances})
        
    except Exception as e:
        logger.error(f"Error in extract_daily_balances: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return json.dumps({"daily_balances": []}) 