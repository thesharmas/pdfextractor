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
from app.tools.analysis_tools import calculate_average_daily_balance, check_nsf, set_llm,check_statement_continuity,extract_daily_balances
from app.services.llm_factory import LLMFactory
from app.config import Config, LLMProvider
import json
# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create logger for this module
logger = logging.getLogger(__name__)

# Set specific loggers to DEBUG level
logging.getLogger('app.services.llm_factory').setLevel(logging.DEBUG)

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

        llm.set_tools([extract_daily_balances, check_nsf, check_statement_continuity])

        # Process PDFs once and store in the LLM
        merged_pdf_path = content_service.merge_pdfs(file_paths)
        pdf_contents = content_service.prepare_file_content([merged_pdf_path])
        llm.set_file_contents(pdf_contents)
        set_llm(llm)
        
        # Ask which tools to use
        orchestration_prompt = """Given the bank statements above, which of these analyses should I run? 
            Please respond with ONLY the analysis name, one per line:
            - balance (for average daily balance)
            - nsf (for NSF fee analysis)
            - continuity (for statement continuity analysis)
            
            Example response:
            balance
            nsf
            continuity
            Do not explain or add any other text."""
        
        result_content = llm.get_response(prompt=orchestration_prompt)
        logger.info("Orchestration response: %s", result_content)
        
        # Parse recommended analyses
        recommended_analyses = set(result_content.lower().split('\n'))
        
        # First check statement continuity
        logger.info("Checking statement continuity...")
        continuity_json = check_statement_continuity("None")
        continuity_data = json.loads(continuity_json)
        
        is_contiguous = continuity_data.get("analysis", {}).get("is_contiguous", False)
        explanation = continuity_data.get("analysis", {}).get("explanation", "No explanation provided")
        gap_details = continuity_data.get("analysis", {}).get("gap_details", [])
        
        if not is_contiguous:
            logger.warning("❌ Bank statements are not contiguous!")
            logger.warning(f"Analysis: {explanation}")
            if gap_details:
                logger.warning(f"Found gaps: {gap_details}")
            return {
                "metrics": {
                    "statement_continuity": continuity_data
                },
                "debug": {
                    "files_processed": len(file_paths)
                },
                "orchestration": "continuity_check"
            }
        
        # If statements are contiguous, proceed with analysis
        logger.info("✅ Bank statements are contiguous, proceeding with analysis...")
        master_response = {
            "metrics": {
                "statement_continuity": continuity_data
            },
            "debug": {
                "files_processed": len(file_paths)
            }
        }
        
        # Track which analyses have been run
        completed_analyses = set()
        
        for analysis in recommended_analyses:
            analysis = analysis.strip()
            
            if 'balance' in analysis and 'balance' not in completed_analyses:
                logger.info("Calling extract_daily_balances")
                input_data = json.dumps({"continuity_data": continuity_data})
                balances_json = extract_daily_balances(input_data)
                master_response["metrics"]["daily_balances"] = json.loads(balances_json)
                completed_analyses.add('balance')
                
            elif 'nsf' in analysis and 'nsf' not in completed_analyses:
                logger.info("Calling check_nsf")
                nsf_json = check_nsf("None")
                master_response["metrics"]["nsf_information"] = json.loads(nsf_json)
                completed_analyses.add('nsf')
        
        # Add orchestration info
        master_response["orchestration"] = "\n".join(completed_analyses)
        
        # Dynamic model mapping using enum values
        logger.info("\nBreakdown by Model:")
     
        
        # Log final token usage at the end
        logger.info(f"\n💰 Token Usage for {Config.LLM_PROVIDER}:")
        logger.info(f"Input tokens: {llm.input_tokens:,}")
        logger.info(f"Output tokens: {llm.output_tokens:,}")
        logger.info(f"Total tokens: {llm.input_tokens + llm.output_tokens:,}")
        
        # Print function-level summary
        llm.print_function_summary()
        
        return jsonify(master_response)

    except Exception as e:
        logger.error(f"Error in underwrite: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    # Enable debug mode for hot reloading
    app.run(host='0.0.0.0', port=port, debug=True)