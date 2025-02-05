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



llm = ChatAnthropic(model="claude-3-5-sonnet-latest")

def calculate_average_daily_balance(file_content: List[Dict[str, Any]]) -> Tuple[float, str]:
    """Calculate average daily balance from file content"""
    prompt = """
    Calculate the average daily balance based on the bank statements provided.
    Provide your detailed calculation, but end your response with a single line starting with 'FINAL_AMOUNT:' 
    followed by only the number without any currency symbols or commas.
    Example: FINAL_AMOUNT:3495.16
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

def check_nsf(file_content: List[Dict[str, Any]]) -> Tuple[float, int, str]:
    """Check for NSF fees and count from bank statements"""
    prompt = """
    Check for NSF (Non-Sufficient Funds) fees in the bank statements provided.
    Count the total number of NSF incidents and calculate the total fees.
    Provide your detailed analysis, but end your response with TWO lines:
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
        # Process with both models

        file_content = ContentService.prepare_file_content(file_paths)
        balance, detailed_response = calculate_average_daily_balance(file_content)
        
        response_data = {
            "average_daily_balance": balance,
            "detailed_calculation": detailed_response
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
    """
        claude_response = process_with_claude(file_paths)
        gemini_response = process_with_gemini(file_paths)

        response_data = {
            "model": "claude-3-opus-20240229",
            "claude_response": claude_response,
            "gemini_model": "gemini-1.5-pro",
            "gemini_response": gemini_response
        }
        
        # Format the response with proper indentation
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
  """








if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = bool(os.environ.get('LOCAL_DEV', False))
    app.run(host='0.0.0.0', port=port, debug=debug)