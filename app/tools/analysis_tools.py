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

@tool
def analyze_monthly_financials(input_str: str = "None") -> str:
    """Analyzes monthly expenses and revenues from bank statements, providing statistical analysis."""
    try:
        prompt = """You are a JSON-only response bot. Based on the bank statements, please provide:
        1. Monthly breakdown of expenses, revenues, and cashflow
        2. Statistical analysis including standard deviation and averages
        
        Format your response as a JSON with this structure:
        {
            "monthly_data": {
                "YYYY-MM": {
                    "expenses": total_expenses,
                    "revenue": total_revenue,
                    "cashflow": revenue_minus_expenses
                }
            },
            "statistics": {
                "revenue": {
                    "average": avg_monthly_revenue,
                    "std_deviation": revenue_std_dev
                },
                "expenses": {
                    "average": avg_monthly_expenses,
                    "std_deviation": expenses_std_dev
                },
                "cashflow": {
                    "average": avg_monthly_cashflow,
                    "std_deviation": cashflow_std_dev
                }
            }
        }
        
        IMPORTANT:
        - Calculate cashflow as (revenue - expenses) for each month
        - All amounts should be numbers (not strings)
        - Round all amounts to 2 decimal places
        - Include ALL months found in statements
        - Ensure the JSON is valid and properly formatted
        
        Include only the JSON in your response, no additional text."""

        logger.info("🔄 Calling LLM for monthly financials analysis")
        response = _llm.get_response(prompt)
        
        logger.info("Raw response from LLM:")
        logger.info("-" * 50)
        logger.info(response)
        logger.info("-" * 50)
        
        # Clean the response
        cleaned_response = response.strip()
        if "```json" in cleaned_response:
            cleaned_response = cleaned_response.split("```json")[1]
        if "```" in cleaned_response:
            cleaned_response = cleaned_response.split("```")[0]
        cleaned_response = cleaned_response.strip()
        
        logger.info("Cleaned response:")
        logger.info("-" * 50)
        logger.info(cleaned_response)
        logger.info("-" * 50)
        
        # Validate JSON format
        try:
            json_response = json.loads(cleaned_response)
            
            # Validate required fields and structure
            if "monthly_data" not in json_response or "statistics" not in json_response:
                raise ValueError("Missing required top-level fields")
                
            for month, data in json_response["monthly_data"].items():
                if not all(k in data for k in ["expenses", "revenue", "cashflow"]):
                    raise ValueError(f"Missing required fields in monthly data for {month}")
                    
            for metric in ["revenue", "expenses", "cashflow"]:
                if not all(k in json_response["statistics"][metric] for k in ["average", "std_deviation"]):
                    raise ValueError(f"Missing required fields in statistics for {metric}")
            
            logger.info("✅ Successfully parsed and validated JSON response")
            return json.dumps(json_response, indent=2)
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing error: {str(e)}")
            logger.error(f"Failed to parse response: {cleaned_response}")
            return json.dumps({
                "error": "Failed to parse financial analysis",
                "details": f"Invalid JSON format in response: {str(e)}"
            })
        except ValueError as e:
            logger.error(f"❌ Validation error: {str(e)}")
            return json.dumps({
                "error": "Failed to validate financial analysis",
                "details": str(e)
            })

    except Exception as e:
        logger.error(f"❌ Error in analyze_monthly_financials: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return json.dumps({
            "error": "Failed to analyze financials",
            "details": str(e)
        })

@tool
def extract_monthly_closing_balances(input_str: str = "None") -> str:
    """Extract closing balances for each month from bank statements."""
    try:
        prompt = """You are a JSON-only response bot. Extract the closing balance for each month from the bank statements.

        CRITICAL RULES FOR BALANCE TYPES:
        1. "direct" balances:
           - Use ONLY when the closing balance is explicitly stated in the statement
           - Look for terms like "Ending Balance", "Closing Balance", "Statement End Balance"
           - Must be the ACTUAL balance stated for the last day of the month
           - These are directly from the bank statement
           - Often found at the bottom of monthly statements
        
        2. "calculated" balances:
           - Use ONLY when a direct closing balance is NOT available
           - Calculation steps:
             a. Start with the previous month's ending balance
             b. Add all deposits/credits in chronological order by transaction date
             c. Subtract all withdrawals/debits in chronological order by transaction date
             d. Continue until the last transaction of the month
             e. The final number is your calculated closing balance
           - Must account for ALL transactions in chronological order
           - Pay attention to transaction dates, not posting dates
           - Double-check your math - amounts should match statement totals
        
        VERIFICATION STEPS:
        1. For each month:
           - First look for an explicit ending balance statement
           - If not found, use the calculation method
           - Cross-reference with next month's opening balance
           - Verify all transactions are included
        
        2. Common places to find direct balances:
           - Bottom of statement summary
           - End of transaction list
           - Next month's opening balance
           - Daily balance summary sections
        
        Format your response as a JSON with this structure:
        {
            "monthly_closing_balances": [
                {
                    "month": "YYYY-MM",
                    "closing_date": "YYYY-MM-DD",
                    "balance": amount,
                    "balance_type": "direct" or "calculated",
                    "source": "Ending Balance statement" or "Calculated from transactions",
                    "verification": "Matches next month opening balance" or "Calculated from all transactions"
                }
            ],
            "analysis": {
                "months_covered": number_of_months,
                "direct_balances": number_of_direct,
                "calculated_balances": number_of_calculated,
                "verification_notes": ["Any discrepancies or important notes about the calculations"]
            }
        }
        
        IMPORTANT:
        - List balances for ALL months in the statements
        - Balance must be from the LAST DAY of each month
        - All amounts must be numbers (not strings)
        - Round all amounts to 2 decimal places
        - Sort entries by month chronologically
        - Clearly indicate if balance was direct or calculated
        - Include detailed source information for audit purposes
        - Add verification notes if calculated balance differs from next month's opening
        
        Include only the JSON in your response, no additional text."""

        logger.info("🔄 Calling LLM for monthly closing balances")
        response = _llm.get_response(prompt)
        
        logger.info("Raw response from LLM:")
        logger.info("-" * 50)
        logger.info(response)
        logger.info("-" * 50)
        
        # Clean the response
        cleaned_response = response.strip()
        if "```json" in cleaned_response:
            cleaned_response = cleaned_response.split("```json")[1]
        if "```" in cleaned_response:
            cleaned_response = cleaned_response.split("```")[0]
        cleaned_response = cleaned_response.strip()
        
        logger.info("Cleaned response:")
        logger.info("-" * 50)
        logger.info(cleaned_response)
        logger.info("-" * 50)
        
        # Validate JSON format
        try:
            json_response = json.loads(cleaned_response)
            
            # Validate required fields and structure
            if "monthly_closing_balances" not in json_response or "analysis" not in json_response:
                raise ValueError("Missing required top-level fields")
            
            # Validate each monthly balance entry
            for entry in json_response["monthly_closing_balances"]:
                required_fields = ["month", "closing_date", "balance", "balance_type", "source", "verification"]
                if not all(k in entry for k in required_fields):
                    raise ValueError(f"Missing required fields in entry for {entry.get('month', 'unknown month')}")
                if entry["balance_type"] not in ["direct", "calculated"]:
                    raise ValueError(f"Invalid balance_type for {entry['month']}")
            
            # Validate analysis section
            required_analysis = ["months_covered", "direct_balances", "calculated_balances", "verification_notes"]
            if not all(k in json_response["analysis"] for k in required_analysis):
                raise ValueError("Missing required analysis fields")
            
            logger.info("✅ Successfully parsed and validated JSON response")
            return json.dumps(json_response, indent=2)
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parsing error: {str(e)}")
            logger.error(f"Failed to parse response: {cleaned_response}")
            return json.dumps({
                "error": "Failed to parse closing balances",
                "details": f"Invalid JSON format in response: {str(e)}"
            })
        except ValueError as e:
            logger.error(f"❌ Validation error: {str(e)}")
            return json.dumps({
                "error": "Failed to validate closing balances",
                "details": str(e)
            })

    except Exception as e:
        logger.error(f"❌ Error in extract_monthly_closing_balances: {str(e)}")
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return json.dumps({
            "error": "Failed to extract closing balances",
            "details": str(e)
        }) 