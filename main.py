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
from app.tools.analysis_tools import  check_nsf, set_llm,check_statement_continuity,extract_daily_balances,extract_monthly_closing_balances
from app.services.llm_factory import LLMFactory
from app.config import Config, LLMProvider, ModelType
import json
# Configure logging
logging.basicConfig(
    level=logging.INFO,  
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create logger for this module
logger = logging.getLogger(__name__)

# Set specific loggers to DEBUG level

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
    model_type = request.json.get('model_type')  # Can be 'reasoning' or 'analysis'
    
    logger.info(f"Debug mode: {debug_mode}")
    logger.info(f"File paths: {file_paths}")
    logger.info(f"Provider requested: {provider}")
    logger.info(f"Provider type: {type(provider)}")
    logger.info(f"Model type: {model_type}")
    
    if not file_paths:
        logger.error("No file paths provided")
        return jsonify({"error": "No file paths provided"}), 400

    try:
        # Create LLM with optional provider and model type override
        if provider:
            try:
                provider = LLMProvider(provider)
                model_type = ModelType(model_type) if model_type else None
                llm = LLMFactory.create_llm(
                    provider=provider,
                    model_type=model_type
                )
            except ValueError as e:
                logger.error(f"Invalid configuration error: {str(e)}")
                return jsonify({
                    "error": f"Invalid configuration. Valid providers: {[p.value for p in LLMProvider]}, "
                            f"Valid model types: {[t.value for t in ModelType]}"
                }), 400
        else:
            llm = LLMFactory.create_llm()  # Will use DEFAULT_PROVIDER and DEFAULT_MODEL_TYPE (ANALYSIS)

        llm.set_tools([extract_daily_balances, check_nsf, check_statement_continuity,extract_monthly_closing_balances])

        # Process PDFs once and store in the LLM
        merged_pdf_path = content_service.merge_pdfs(file_paths)
        #pdf_contents = content_service.prepare_file_content([merged_pdf_path])
        llm.add_pdf(merged_pdf_path)
        set_llm(llm)
        
        # Ask which tools to use
        orchestration_prompt = """Given the bank statements above, which of these analyses should I run? 
            Please respond with ONLY the analysis name, one per line:
            - balance (for average daily balance)
            - nsf (for NSF fee analysis)
            - continuity (for statement continuity analysis)
            - closing_balances (for monthly closing balances)
            Example response:
            balance
            nsf
            continuity
            closing_balances
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
            elif 'closing_balances' in analysis and 'closing_balances' not in completed_analyses:
                logger.info("Calling extract_monthly_closing_balances")
                closing_balances_json = extract_monthly_closing_balances("None")
                master_response["metrics"]["closing_balances"] = json.loads(closing_balances_json)
                completed_analyses.add('closing_balances')
        
        # Add orchestration info
        master_response["orchestration"] = "\n".join(completed_analyses)
        
        # Dynamic model mapping using enum values
        logger.info("\nBreakdown by Model:")
     
        # Create a reasoning LLM for credit analysis
        reasoning_llm = LLMFactory.create_llm(
            provider=LLMProvider.OPENAI,
            model_type=ModelType.REASONING
        )
        logger.info("Created reasoning LLM")
        # Feed the analysis data
        reasoning_llm.add_json(master_response)
        logger.info("Added JSON to reasoning LLM")
        # Craft the credit analysis prompt
        credit_prompt = """
        You are a conservative commercial loan underwriter. Analyze the provided financial data and determine if this business 
        qualifies for a term loan with these parameters:
        - Term: 12 months
        - Payment Frequency: Monthly
        - Annual Interest Rate: 19%
        
        Focus on:
        1. Cash flow adequacy for monthly payments
        2. Bank statement analysis trends
        3. NSF/overdraft risk indicators
        4. Statement continuity and completeness
        5. Overall financial health indicators
        
        Be conservative in your analysis. Consider:
        - Minimum 1.25x monthly payment coverage from average daily balances
        - Trending of balances (growing, stable, or declining)
        - Impact of any NSFs on credit quality
        - Seasonal patterns and lowest balance periods
        
        Provide your analysis and recommendation in this JSON format:
        {
            "loan_recommendation": {
                "approval_decision": boolean,
                "confidence_score": float (0-1),
                "monthly_payment_amount": float,
                "key_metrics": {
                    "payment_coverage_ratio": float,
                    "average_daily_balance_trend": "increasing|stable|decreasing",
                    "lowest_monthly_balance": float,
                    "highest_nsf_month_count": integer
                },
                "risk_factors": [string],
                "mitigating_factors": [string],
                "detailed_analysis": string,
                "conditions_if_approved": [string]
            }
        }
        """
        logger.info("Sending credit prompt to reasoning LLM")
        credit_analysis = reasoning_llm.get_response(credit_prompt)
        
        # Add the credit analysis to the master response
        try:
            credit_analysis_json = json.loads(credit_analysis)
            master_response["credit_analysis"] = credit_analysis_json
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing credit analysis JSON: {str(e)}")
            master_response["credit_analysis"] = {"error": "Failed to parse credit analysis"}

        return jsonify(master_response)

    except Exception as e:
        logger.error(f"Error in underwrite: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    # Enable debug mode for hot reloading
    app.run(host='0.0.0.0', port=port, debug=True)