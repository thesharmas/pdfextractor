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

def get_api_key():
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key:
        # Fallback to Secret Manager if not found in environment
        return access_secret_version("anthropic-api-key", "latest")
        
    return api_key
def get_gemini_api_key():
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        # Fallback to Secret Manager if not found in environment
        return access_secret_version("gemini-api-key", "latest")
        
    return api_key

def access_secret_version(secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/pdfextractor-441603/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

app = Flask(__name__)
api_key = get_api_key()
claude = anthropic.Client(api_key=api_key)
gemini_api_key = get_gemini_api_key()
genai.configure(api_key=gemini_api_key)


def process_with_claude(file_paths):
    # Prepare all files for Claude
    file_contents = []
    for file_path in file_paths:
        try:
            with open(file_path, 'rb') as file:
                pdf_content = file.read()
                file_contents.append({
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.b64encode(pdf_content).decode()
                    }
                })
        except Exception as e:
            raise Exception(f"Failed to read file {file_path}: {str(e)}")

    content = [{"type": "text", "text": "Please calculate the average daily balance based on the bank statements provided"}]
    content.extend(file_contents)

    message = claude.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": content
        }]
    )
    
    return message.content[0].text

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

    prompt = "Please calculate the average daily balance based on these bank statements."
    response = model.generate_content([prompt, *contents])
    return response.text

@app.route('/extract-invoice', methods=['POST'])
def extract_invoice():
    debug_mode = request.json.get('debug', False)
    file_paths = request.json.get('file_paths', [])

    if not file_paths:
        return jsonify({"error": "No file paths provided"}), 400

    try:
        # Process with both models
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

def validate_files(file_paths):
    total_size = 0
    MAX_SIZE = 10 * 1024 * 1024  # 10MB example limit
    
    for path in file_paths:
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
        
        if not path.lower().endswith('.pdf'):
            raise ValueError(f"File must be PDF: {path}")
            
        size = os.path.getsize(path)
        total_size += size
        
        if total_size > MAX_SIZE:
            raise ValueError("Total file size exceeds limit")





if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = bool(os.environ.get('LOCAL_DEV', False))
    app.run(host='0.0.0.0', port=port, debug=debug)