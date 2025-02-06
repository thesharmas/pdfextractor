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
from app.tools.analysis_tools import calculate_average_daily_balance, check_nsf, set_llm
from app.services.llm_factory import LLMFactory
from app.config import Config, LLMProvider
import json

# Configure logging
logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Set httpcore to only show WARNING and above
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
    
    # Get our application logger
logger = logging.getLogger('app')
logger.setLevel(logging.INFO)

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
    logger.info("📥 Received underwrite request")
    logger.info(f"Request JSON: {json.dumps(request.json, indent=2)}")
    
    debug_mode = request.json.get('debug', False)
    file_paths = request.json.get('file_paths', [])
    provider = request.json.get('provider')
    
    logger.info(f"Debug mode: {debug_mode}")
    logger.info(f"File paths: {file_paths}")
    logger.info(f"Provider requested: {provider}")
    logger.info(f"Provider type: {type(provider)}")
    
    if not file_paths:
        logger.error("No file paths provided")
        return jsonify({"error": "No file paths provided"}), 400

    try:
        # Create LLM with optional provider override
        if provider:
            try:
                logger.info(f"Converting provider string '{provider}' to enum")
                logger.info(f"Valid providers: {[p.value for p in LLMProvider]}")
                provider = LLMProvider(provider)
                logger.info(f"Provider converted to: {provider}")
                llm = LLMFactory.create_llm(provider=provider)
            except ValueError as e:
                logger.error(f"Invalid provider error: {str(e)}")
                return jsonify({
                    "error": f"Invalid provider: {provider}. Valid options are: {[p.value for p in LLMProvider]}"
                }), 400
        else:
            logger.info(f"Using default provider from config: {Config.LLM_PROVIDER}")
            llm = LLMFactory.create_llm()

        llm.set_tools([calculate_average_daily_balance, check_nsf])

        # Process PDFs once and store in the LLM
        merged_pdf_path = content_service.merge_pdfs(file_paths)
        pdf_contents = content_service.prepare_file_content([merged_pdf_path])
        llm.set_file_contents(pdf_contents)
        set_llm(llm)
        
        # Ask which tools to use
        orchestration_prompt = """I have bank statements provided above. 
        Tell me which of these tools I should call to analyze them:
        - calculate_average_daily_balance()
        - check_nsf()
        
        Just list the tool names you recommend, one per line."""
        
        result_content = llm.get_response(prompt=orchestration_prompt)
        logger.info("Orchestration response: %s", result_content)
        
        # Parse recommended analyses
        recommended_analyses = result_content.split('\n')
        
        balance = None
        balance_details = None
        nsf_fees = None
        nsf_count = None
        nsf_details = None
        
        for analysis in recommended_analyses:
            analysis = analysis.strip().lower()
            if 'average' in analysis or 'balance' in analysis:
                logger.info("Calling calculate_average_daily_balance")
                balance, balance_details = calculate_average_daily_balance("None")
            elif 'nsf' in analysis or 'non-sufficient' in analysis:
                logger.info("Calling check_nsf")
                nsf_fees, nsf_count, nsf_details = check_nsf("None")

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