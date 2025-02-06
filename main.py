from flask import Flask, request, jsonify, Response
import os
from dotenv import load_dotenv
import google.generativeai as genai
import traceback
from io import BytesIO
from typing import List, Tuple
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage
from app.services.content_service import ContentService
from typing import List, Dict, Any, Tuple
import logging
from pydantic import BaseModel
from app.services.content_service import ContentService
from app.tools.analysis_tools import calculate_average_daily_balance, check_nsf
from app.services.llm_factory import LLMFactory
from app.config import Config, LLMProvider

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add near the top of the file, after other imports
content_service = ContentService()



def get_api_key():
    api_key = os.getenv('ANTHROPIC_API_KEY')
    return api_key
def get_gemini_api_key():
    api_key = os.getenv('GOOGLE_API_KEY')
    return api_key

app = Flask(__name__)




@app.route('/underwrite', methods=['POST'])
def underwrite():
    debug_mode = request.json.get('debug', False)
    file_paths = request.json.get('file_paths', [])

    if not file_paths:
        return jsonify({"error": "No file paths provided"}), 400

    try:
        # Create orchestrator LLM using factory
       
        orchestrator_llm = LLMFactory.create_llm()
        if Config.LLM_PROVIDER == LLMProvider.CLAUDE:
            orchestrator_llm = orchestrator_llm.bind_tools([calculate_average_daily_balance, check_nsf])
        else:
            orchestrator_llm.tools = [{
                "function_declarations": [{
                    "name": "calculate_average_daily_balance",
                    "description": "Calculate the average daily balance from bank statements",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_contents": {
                                "type": "array",
                                "description": "List of bank statement contents"
                            }
                        }
                    }
                }, {
                    "name": "check_nsf",
                    "description": "Check for NSF fees in bank statements",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_contents": {
                                "type": "array",
                                "description": "List of bank statement contents"
                            }
                        }
                    }
                }]
            }]
            

        
        # Process PDFs using the correct method
        content_service = ContentService()
        pdf_contents = content_service.prepare_file_content(file_paths)
        
        # Ask Claude which tools to use
        orchestration_prompt = """I have bank statements in pdf_contents. 
        Tell me which of these tools I should call to analyze them:
        - calculate_average_daily_balance()
        - check_nsf()
        
        Just list the tool names you recommend, one per line."""
        
        result_content = orchestrator_llm.get_response(pdf_contents, orchestration_prompt)
        logger.info("Orchestration response: %s", result_content)
        
        # Parse recommended analyses
        recommended_analyses = result_content.split('\n')
        
        # Track metrics
        balance = None
        balance_details = None
        nsf_fees = None
        nsf_count = None
        nsf_details = None
        
        for analysis in recommended_analyses:
            analysis = analysis.strip().lower()
            if 'average' in analysis or 'balance' in analysis:
                logger.info("Calling calculate_average_daily_balance")
                balance, balance_details = calculate_average_daily_balance({
                "file_contents": pdf_contents})
            elif 'nsf' in analysis or 'non-sufficient' in analysis:
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
            },
            "orchestration": result_content,
            "debug": {
                "files_processed": len(pdf_contents)
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