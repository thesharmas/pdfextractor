from flask import Flask, request, jsonify, Response
import requests
import base64
import anthropic
import os
from google.cloud import secretmanager
from dotenv import load_dotenv
import google.generativeai as genai
import traceback
import base64
from io import BytesIO
import json
from typing import List, Tuple
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage
from app.services.content_service import ContentService
from typing import List, Dict, Any, Tuple
import logging
from pydantic import BaseModel
from app.services.content_service import ContentService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add near the top of the file, after other imports
content_service = ContentService()

class ToolInput(BaseModel):
    file_contents: List[Dict]

def get_api_key():
    api_key = os.getenv('ANTHROPIC_API_KEY')
    return api_key
def get_gemini_api_key():
    api_key = os.getenv('GOOGLE_API_KEY')
    return api_key

app = Flask(__name__)
api_key = get_api_key()
claude = anthropic.Client(api_key=api_key)
gemini_api_key = get_gemini_api_key()
genai.configure(api_key=gemini_api_key)

@tool
def calculate_average_daily_balance(file_contents: List[Dict]) -> Tuple[float, str]:
    """Calculate the average daily balance from bank statements."""
    logger.info("🔧 Tool calculate_average_daily_balance called")
    try:
        # Create a new LLM instance for analysis
        analysis_llm = ChatAnthropic(model="claude-3-5-sonnet-latest")
        
        prompt = """
        Analyze these bank statements and calculate the average daily balance.
        
        Instructions:
        1. Extract all daily balances from the statements
        2. Calculate their average
        3. Show your work clearly
        4. Your response MUST end with a line in exactly this format:
        FINAL_AMOUNT:1234.56
        """
        
        messages = [
            HumanMessage(content=[
                {"type": "text", "text": prompt},
                *file_contents
            ])
        ]
        
        response = analysis_llm.invoke(messages)
        logger.debug("Tool response: %s", str(response))
        
        # Extract amount more carefully
        content = str(response.content)
        logger.debug("Looking for FINAL_AMOUNT in: %s", content)
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('FINAL_AMOUNT:'):
                try:
                    amount_str = line.replace('FINAL_AMOUNT:', '').strip()
                    amount = float(amount_str)
                    logger.info(f"Found amount: {amount}")
                    return amount, content
                except ValueError as e:
                    logger.error(f"Failed to parse amount from line: {line}")
                    raise ValueError(f"Invalid amount format in: {line}")
                
        logger.error("No FINAL_AMOUNT found in response")
        logger.debug("Response content: %s", content)
        raise ValueError("No FINAL_AMOUNT found in response")
    except Exception as e:
        logger.error("Tool error: %s", str(e))
        return 0.0, str(e)

@tool
def check_nsf(file_contents: List[Dict]) -> Tuple[float, int, str]:
    """Check for NSF fees in bank statements."""
    logger.info("🔧 Tool check_nsf called")
    try:
        # Create a new LLM instance for analysis
        analysis_llm = ChatAnthropic(model="claude-3-5-sonnet-latest")
        
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
        
        messages = [
            HumanMessage(content=[
                {"type": "text", "text": prompt},
                *file_contents
            ])
        ]
        
        response = analysis_llm.invoke(messages)
        logger.debug("Tool response: %s", str(response))
        
        content = str(response.content)
        logger.debug("Looking for NSF info in: %s", content)
        
        lines = content.split('\n')
        nsf_count = None
        nsf_fees = None
        
        for line in lines:
            line = line.strip()
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
            logger.debug("Response content: %s", content)
            raise ValueError("Missing NSF count or fees in response")
            
        return nsf_fees, nsf_count, content
    except Exception as e:
        logger.error("Tool error: %s", str(e))
        return 0.0, 0, str(e)


@app.route('/underwrite', methods=['POST'])
def underwrite():
    debug_mode = request.json.get('debug', False)
    file_paths = request.json.get('file_paths', [])

    if not file_paths:
        return jsonify({"error": "No file paths provided"}), 400

    try:
        # Create orchestrator LLM
        orchestrator_llm = ChatAnthropic(model="claude-3-5-sonnet-latest")
        orchestrator_llm = orchestrator_llm.bind_tools([calculate_average_daily_balance, check_nsf])
        
        # Process PDFs
        pdf_contents = content_service.prepare_file_content(file_paths)
        
        # Ask Claude which tools to use
        orchestration_message = HumanMessage(
            content="""I have bank statements in pdf_contents. 
            Tell me which of these tools I should call to analyze them:
            - calculate_average_daily_balance(file_contents)
            - check_nsf(file_contents)
            
            Just list the tool names you recommend, one per line."""
        )
        
        result = orchestrator_llm.invoke([orchestration_message])
        logger.info("Orchestration response: %s", str(result))
        
        # Track metrics
        balance = None
        balance_details = None
        nsf_fees = None
        nsf_count = None
        nsf_details = None
        
        # Parse recommended tools and call them
        recommended_tools = str(result.content).split('\n')
        for tool in recommended_tools:
            tool = tool.strip().lower()
            if 'calculate_average_daily_balance' in tool:
                logger.info("Calling calculate_average_daily_balance")
                balance, balance_details = calculate_average_daily_balance({
                "file_contents": pdf_contents
            })
            elif 'check_nsf' in tool:
                logger.info("Calling check_nsf")
                nsf_fees, nsf_count, nsf_details = check_nsf({
                "file_contents": pdf_contents})
        response_data = {
            "metrics": {
                "average_daily_balance": {
                    "amount": balance,
                    "details": balance_details
                },
                "nsf_information": {
                    "total_fees": nsf_fees,
                    "incident_count": nsf_count,
                    "details": nsf_details
                }
            }
        }

        return jsonify(response_data)
       
    except Exception as e:
        logger.error("Error in underwrite", exc_info=True)
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc() if debug_mode else None
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = bool(os.environ.get('LOCAL_DEV', False))
    app.run(host='0.0.0.0', port=port, debug=debug)