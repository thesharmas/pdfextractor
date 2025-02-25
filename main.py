from flask import Flask, request, jsonify, Response, render_template, url_for, send_from_directory, stream_with_context
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
from app.tools.analysis_tools import  check_nsf, set_llm,check_statement_continuity,extract_daily_balances,extract_monthly_closing_balances,analyze_credit_decision,analyze_monthly_financials
from app.services.llm_factory import LLMFactory
from app.config import Config, LLMProvider, ModelType
import json
import uuid
from werkzeug.utils import secure_filename
import shutil
from queue import Queue
import time

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

# Create a queue for status messages
status_queue = Queue()

def get_api_key():
    api_key = os.getenv('ANTHROPIC_API_KEY')
    return api_key
def get_gemini_api_key():
    api_key = os.getenv('GOOGLE_API_KEY')
    return api_key

# Create upload directory if it doesn't exist
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__, 
    static_folder='app/static',
    template_folder='app/templates'
)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload size

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({"error": "No files part in the request"}), 400
    
    files = request.files.getlist('files')
    
    if not files or files[0].filename == '':
        return jsonify({"error": "No files selected"}), 400
    
    file_paths = []
    
    for file in files:
        if file and file.filename.endswith('.pdf'):
            # Create a unique filename to avoid collisions
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            # Save the file
            file.save(file_path)
            file_paths.append(file_path)
    
    if not file_paths:
        return jsonify({"error": "No valid PDF files uploaded"}), 400
    
    return jsonify({"file_paths": file_paths})

@app.route('/underwrite', methods=['POST'])
def underwrite():
    logger.info("📥 Received underwrite request")
    send_status("start", "Processing", "Received underwrite request")
    
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
        # Create LLM
        send_status("llm_setup", "Processing", f"Initializing {provider} LLM")
        if provider:
            try:
                provider_value = provider.lower()
                provider = LLMProvider(provider_value)
                model_type = None
                analysis_llm = LLMFactory.create_llm(
                    provider=provider,
                    model_type=model_type
                )
                send_status("llm_setup", "Complete", f"Successfully initialized {provider} LLM")
            except ValueError as e:
                send_status("llm_setup", "Error", str(e))
                logger.error(f"Invalid configuration error: {str(e)}")
                return jsonify({"error": f"Invalid configuration"}), 400
        else:
            analysis_llm = LLMFactory.create_llm()
        
        set_llm(analysis_llm)
        analysis_llm.set_tools([extract_daily_balances, check_nsf, check_statement_continuity,extract_monthly_closing_balances,analyze_monthly_financials])

        # Process PDFs
        send_status("pdf_processing", "Processing", "Merging PDF files")
        merged_pdf_path = content_service.merge_pdfs(file_paths)
        send_status("pdf_processing", "Complete", "PDFs merged successfully")

        # Add PDF to LLM
        send_status("pdf_analysis", "Processing", "Adding PDF to LLM for analysis")
        analysis_llm.add_pdf(merged_pdf_path)
        send_status("pdf_analysis", "Complete", "PDF added to LLM")
        
        # Orchestration
        send_status("orchestration", "Processing", "Determining required analyses")
        orchestration_prompt = """Given the bank statements above, which of these analyses should I run? 
            Please respond with ONLY the analysis name, one per line:
            - balance (for average daily balance)
            - nsf (for NSF fee analysis)
            - continuity (for statement continuity analysis)
            - closing_balances (for monthly closing balances)
            - analyze_monthly_financials (for monthly financials analysis)
            Example response:
            balance
            nsf
            continuity
            closing_balances
            analyze_monthly_financials
            Do not explain or add any other text."""
        
        result_content = analysis_llm.get_response(prompt=orchestration_prompt)
        recommended_analyses = set(result_content.lower().split('\n'))
        send_status("orchestration", "Complete", f"Recommended analyses: {', '.join(recommended_analyses)}")
        
        # First check statement continuity
        send_status("continuity", "Processing", "Checking statement continuity")
        continuity_json = check_statement_continuity("None")
        continuity_data = json.loads(continuity_json)
        send_status("continuity", "Complete", "Statement continuity check finished")
        
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
            elif 'analyze_monthly_financials' in analysis and 'analyze_monthly_financials' not in completed_analyses:
                logger.info("Calling analyze_monthly_financials")
                monthly_financials_json = analyze_monthly_financials("None")
                master_response["metrics"]["monthly_financials"] = json.loads(monthly_financials_json)
                completed_analyses.add('monthly_financials')
        
        # Add orchestration info
        master_response["orchestration"] = "\n".join(completed_analyses)
        
        # Now switch to REASONING LLM for credit analysis
        logger.info("🔄 Switching to REASONING LLM for credit analysis")
        reasoning_llm = LLMFactory.create_llm(
            provider=LLMProvider.OPENAI,
            model_type=ModelType.REASONING
        )
        set_llm(reasoning_llm)
        # Feed the master_response to the reasoning LLM
        reasoning_llm.add_json(master_response)
        
        # Now use the analyze_credit_decision tool
        send_status("credit_analysis", "Processing", "Performing final credit analysis")
        credit_analysis = analyze_credit_decision(json.dumps(master_response))
        send_status("credit_analysis", "Complete", "Credit analysis finished")
        
        try:
            credit_analysis_json = json.loads(credit_analysis)
            master_response["credit_analysis"] = credit_analysis_json
            logger.info("✅ Credit analysis completed and added to master response")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error parsing credit analysis result: {str(e)}")
            master_response["credit_analysis"] = {
                "error": "Failed to parse credit analysis",
                "raw_response": credit_analysis
            }

        # Final response
        send_status("complete", "Success", "Analysis complete")
        return jsonify(master_response)

    except Exception as e:
        send_status("error", "Error", str(e))
        logger.error(f"Error in underwrite: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/clear-uploads', methods=['POST'])
def clear_uploads():
    try:
        # Clear the uploads directory
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.error(f"Error deleting {file_path}: {str(e)}")
        
        return jsonify({"message": "Uploads cleared successfully"}), 200
    except Exception as e:
        logger.error(f"Error clearing uploads: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Add new route for SSE
@app.route('/status')
def status_stream():
    def event_stream():
        while True:
            # Get message from queue
            if not status_queue.empty():
                message = status_queue.get()
                yield f"data: {json.dumps(message)}\n\n"
            time.sleep(0.5)  # Small delay to prevent CPU overuse
    
    return Response(stream_with_context(event_stream()), 
                   mimetype='text/event-stream')

# Helper function to send status updates
def send_status(step: str, status: str, details: str = None):
    status_message = {
        "step": step,
        "status": status,
        "details": details,
        "timestamp": time.time()
    }
    status_queue.put(status_message)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    # Enable debug mode for hot reloading
    app.run(host='0.0.0.0', port=port, debug=True)