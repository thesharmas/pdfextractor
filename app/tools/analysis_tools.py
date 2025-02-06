import logging
from typing import List, Dict, Tuple
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from app.services.llm_factory import LLMFactory

logger = logging.getLogger(__name__)

# Store single LLM instance at module level
_llm = None

def set_llm(llm):
    """Set single LLM instance to be used by all tools"""
    global _llm
    _llm = llm

@tool
def calculate_average_daily_balance() -> Tuple[float, str]:
    """Calculate the average daily balance from bank statements."""
    logger.info("🔧 Tool calculate_average_daily_balance called")
    try:
        prompt = """
        Analyze these bank statements and calculate the average daily balance.
        
        Instructions:
        1. Extract all daily balances from the statements
        2. Calculate their average
        3. Show your work clearly
        4. Your response MUST end with a line in exactly this format:
        FINAL_AMOUNT:1234.56
        """
        
        response_text = _llm.get_response(prompt=prompt)

        logger.debug("Raw response: %s", response_text)        
        
        lines = response_text.split('\n')
        for line in lines:
            line = line.strip()
            logger.debug("Processing line: %s", line)
            
            if line.startswith('FINAL_AMOUNT:'):
                try:
                    amount_str = line.replace('FINAL_AMOUNT:', '').strip()
                    amount = float(amount_str)
                    logger.info(f"Found amount: {amount}")
                    return amount, response_text
                except ValueError as e:
                    logger.error(f"Failed to parse amount from line: {line}")
                    raise ValueError(f"Invalid amount format in: {line}")
                
        logger.error("No FINAL_AMOUNT found in response")
        raise ValueError("No FINAL_AMOUNT found in response")
    except Exception as e:
        logger.error("Tool error: %s", str(e))
        logger.error("Full traceback:", exc_info=True)
        return 0.0, str(e)

@tool
def check_nsf() -> Tuple[float, int, str]:
    """Check for NSF fees in bank statements."""
    logger.info("🔧 Tool check_nsf called")
    try:
        prompt = """
        Analyze these bank statements for NSF (Non-Sufficient Funds) fees.
        
        Instructions:
        1. Find all NSF fees in the statements
        2. List each occurrence with date and amount
        3. Calculate total count and sum
        4. Your response MUST end with these two lines in exactly this format:
        NSF_COUNT:3
        NSF_FEES:105.00
        """
        
        response_text = _llm.get_response(prompt=prompt)

        logger.debug("Raw response: %s", response_text)        
        
        lines = response_text.split('\n')
        nsf_count = None
        nsf_fees = None
        
        for line in lines:
            line = line.strip()
            logger.debug("Processing line: %s", line)
            
            if line.startswith('NSF_COUNT:'):
                try:
                    count_str = line.replace('NSF_COUNT:', '').strip()
                    nsf_count = int(count_str)
                    logger.info(f"Found count: {nsf_count}")
                except ValueError:
                    logger.error(f"Failed to parse count from line: {line}")
            elif line.startswith('NSF_FEES:'):
                try:
                    fees_str = line.replace('NSF_FEES:', '').strip()
                    nsf_fees = float(fees_str)
                    logger.info(f"Found fees: {nsf_fees}")
                except ValueError:
                    logger.error(f"Failed to parse fees from line: {line}")
                
        if nsf_count is None or nsf_fees is None:
            logger.error("Missing NSF info in response")
            raise ValueError("Missing NSF count or fees in response")
            
        return nsf_fees, nsf_count, response_text
    except Exception as e:
        logger.error("Tool error: %s", str(e))
        logger.error("Full traceback:", exc_info=True)
        return 0.0, 0, str(e) 