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
from typing import List
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from app.services.content_service import ContentService
from typing import List, Dict, Any, Tuple
from langchain.tools import tool 



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
def calculate_average_daily_balance(file_content: List[Dict[str, Any]]) -> Tuple[float, str]:
    """Calculate average daily balance from file content"""
    prompt = """
    Calculate the average daily balance based on the bank statements provided.
    Show your detailed calculation, and then on a new line provide the final amount in this exact format:
    FINAL_AMOUNT:3495.16
    """
    
    content = ContentService.process_with_prompt(file_content, prompt)
    messages = [HumanMessage(content=content)]
    response = llm.invoke(messages)
    
    # Extract the final amount
    try:
        lines = response.content.split('\n')
        for line in lines:
            if line.startswith('FINAL_AMOUNT:'):
                amount = line.replace('FINAL_AMOUNT:', '').strip()
                return float(amount), response.content
        raise ValueError("No FINAL_AMOUNT found in response")
    except Exception as e:
        raise ValueError(f"Could not parse response: {response.content}")

@tool
def check_nsf(file_content: List[Dict[str, Any]]) -> Tuple[float, int, str]:
    """Check for NSF fees and count from bank statements"""
    prompt = """
    Analyze the bank statements for NSF (Non-Sufficient Funds) fees.
    Show your detailed analysis, and then on new lines provide the results in this exact format:
    NSF_COUNT:2
    NSF_FEES:70.00
    """
    
    content = ContentService.process_with_prompt(file_content, prompt)
    messages = [HumanMessage(content=content)]
    response = llm.invoke(messages)
    
    # Extract both NSF count and fees
    try:
        lines = response.content.split('\n')
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

llm = ChatAnthropic(model="claude-3-5-sonnet-latest")
llm = llm.bind_tools([calculate_average_daily_balance, check_nsf])


def process_with_gemini(file_paths):
    model = genai.GenerativeModel('gemini-1.5-pro')
    
    contents = []
    for file_path in file_paths:
        try:
            with open(file_path, 'rb') as file:
                pdf_content = file.read()
                contents.append({
                    "mime_type": "application/pdf",
                    "data": pdf_content
                })
        except Exception as e:
            raise Exception(f"Failed to read file {file_path}: {str(e)}")

    prompt = "Please calculate the average daily balance over the entier period based on these bank statements."
    response = model.generate_content([prompt, *contents])
    return response.text

@app.route('/underwrite', methods=['POST'])
def underwrite():
    debug_mode = request.json.get('debug', False)
    file_paths = request.json.get('file_paths', [])

    if not file_paths:
        return jsonify({"error": "No file paths provided"}), 400

    try:
        file_content = ContentService.prepare_file_content(file_paths)
        
        # Use tools through LLM
        result = llm.invoke("""
            Use the tools provided to:
            1. Calculate the average daily balance
            2. Check for NSF fees
            Return the results in a clear, structured format.
            """)
        
        # Convert result to string if it's a list
        result_text = '\n'.join(result) if isinstance(result, list) else str(result)
        lines = result_text.split('\n')
        
        balance = None
        nsf_fees = None
        nsf_count = None
        
        for line in lines:
            if line.startswith('FINAL_AMOUNT:'):
                balance = float(line.replace('FINAL_AMOUNT:', '').strip())
            elif line.startswith('NSF_COUNT:'):
                nsf_count = int(line.replace('NSF_COUNT:', '').strip())
            elif line.startswith('NSF_FEES:'):
                nsf_fees = float(line.replace('NSF_FEES:', '').strip())

        response_data = {
            "analysis": result_text,  # Full analysis from Claude
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
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc() if debug_mode else None
        }), 500








if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = bool(os.environ.get('LOCAL_DEV', False))
    app.run(host='0.0.0.0', port=port, debug=debug)