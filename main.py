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
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from app.services.content_service import ContentService
from typing import List, Dict, Any, Tuple
from langchain.tools import tool 
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Print to console
        logging.FileHandler('underwrite.log')  # Also save to file
    ]
)

logger = logging.getLogger(__name__)

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
    """Calculate the average daily balance from the bank statements you've already analyzed."""
    prompt = """
    Based on the bank statements I've shown you:
    1. Calculate the average daily balance
    2. Show your detailed calculation
    3. End with the final amount in this exact format:
    FINAL_AMOUNT:3495.16
    """
    
    # No need for ContentService since LLM already has the data
    messages = [HumanMessage(content=file_contents + [{"type": "text", "text": prompt}])]    
    response = claude.invoke(messages)
    
    # Extract the final amount
    try:
        lines = str(response.content).split('\n')
        for line in lines:
            if line.startswith('FINAL_AMOUNT:'):
                amount = line.replace('FINAL_AMOUNT:', '').strip()
                return float(amount), response.content
        raise ValueError("No FINAL_AMOUNT found in response")
    except Exception as e:
        raise ValueError(f"Could not parse response: {response.content}")

@tool
def check_nsf(file_contents: List[Dict]) -> Tuple[float, int, str]:
    """Check for NSF fees and count from the bank statements you've already analyzed."""
    prompt = """
    Based on the bank statements I've shown you:
    1. Find all NSF (Non-Sufficient Funds) fees
    2. Count the total number of NSF incidents
    3. Calculate the total fees
    4. Show your detailed analysis
    5. End with these exact format lines:
    NSF_COUNT:2
    NSF_FEES:70.00
    """
    
    messages = [HumanMessage(content=file_contents + [{"type": "text", "text": prompt}])]
    response = claude.invoke(messages)
    
    # Extract both NSF count and fees
    try:
        lines = str(response.content).split('\n')
        nsf_count = None
        nsf_fees = None
        
        for line in lines:
            if line.startswith('NSF_COUNT:'):
                count_str = line.replace('NSF_COUNT:', '').strip()
                nsf_count = int(count_str)
            elif line.startswith('NSF_FEES:'):
                fees_str = line.replace('NSF_FEES:', '').strip()
                nsf_fees = float(fees_str)
                
        if nsf_count is None or nsf_fees is None:
            raise ValueError("Missing NSF count or fees in response")
            
        return nsf_fees, nsf_count, response.content
        
    except Exception as e:
        raise ValueError(f"Could not parse response: {response.content}")

@app.route('/underwrite', methods=['POST'])
def underwrite():
    debug_mode = request.json.get('debug', False)
    file_paths = request.json.get('file_paths', [])

    if not file_paths:
        return jsonify({"error": "No file paths provided"}), 400

    try:
        # Debug: Log file paths
        logger.debug(f"Processing files: {file_paths}")
        
        pdf_contents = ContentService.prepare_file_content(file_paths)
        logger.debug(f"Number of PDFs processed: {len(pdf_contents)}")
        
        
        # Initialize LLM with tools
        llm = ChatAnthropic(model="claude-3-5-sonnet-latest")
        llm = llm.bind_tools([calculate_average_daily_balance, check_nsf])
        
        
        # Now ask LLM to use the tools
        analysis_message = HumanMessage(
            content="""use the tools to analyze the bank statements and present the results in a clear format. the files are in pdf_contents"""
        )
        
        result = llm.invoke([analysis_message])
        
        # Parse the results
        if isinstance(result, list):
            result_text = '\n'.join(result)
        else:
            result_text = str(result)
            
        lines = result_text.split('\n')
        
        balance = None
        nsf_fees = None
        nsf_count = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('FINAL_AMOUNT:'):
                try:
                    balance = float(line.replace('FINAL_AMOUNT:', '').strip())
                except ValueError:
                    pass
            elif line.startswith('NSF_COUNT:'):
                try:
                    nsf_count = int(line.replace('NSF_COUNT:', '').strip())
                except ValueError:
                    pass
            elif line.startswith('NSF_FEES:'):
                try:
                    nsf_fees = float(line.replace('NSF_FEES:', '').strip())
                except ValueError:
                    pass

        response_data = {
            "analysis": result_text,
            "metrics": {
                "average_daily_balance": balance,
                "nsf_information": {
                    "total_fees": nsf_fees,
                    "incident_count": nsf_count
                }
            }
        }
        
        formatted_response = json.dumps(response_data, 
            indent=4,
            ensure_ascii=False,
            separators=(',', ': ')
        )

        return Response(
            formatted_response,
            status=200,
            mimetype='application/json'
        )
       
    except Exception as e:
        logger.error("Error in underwrite", exc_info=True)  # This logs the full traceback
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc() if debug_mode else None,
            "debug": {
                "stage": "error occurred during processing",
                "file_paths": file_paths if 'file_paths' in locals() else None,
                "pdf_contents_length": len(pdf_contents) if 'pdf_contents' in locals() else None
            }
        }), 500








if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = bool(os.environ.get('LOCAL_DEV', False))
    app.run(host='0.0.0.0', port=port, debug=debug)