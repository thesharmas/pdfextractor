from flask import Flask, request, jsonify
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


@app.route('/extract-invoice', methods=['POST'])
def extract_invoice():
    debug_mode = request.json.get('debug', False)
    file_path = request.json.get('file_path')

    try:
        with open(file_path, 'rb') as file:
            pdf_content = file.read()
        pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
    except Exception as e:
        return jsonify({
            "error": f"Failed to download PDF: {str(e)}",
            "traceback": str(traceback.format_exc()) if debug_mode else None
        })
    pdf_data_for_gemini = {
        "mime_type": "application/pdf",
        "data": pdf_content
    }
    
    try:
        debug_mode = request.json.get('debug', False)
        
        prompt = f"""PLease calculate the average closing balance based on the bank statement provided 
        """
    
        claude_prompt = prompt + f"""
        PDF Content (base64): {pdf_base64}
        """
        message = claude.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=4096,
            temperature=0,
            messages=[{
                "role": "user",
                "content": claude_prompt
            }]
        )
        
        gemini_model = genai.GenerativeModel('gemini-1.5-pro')
        response = gemini_model.generate_content([prompt,pdf_data_for_gemini])
        response_text = response.text
        
        if debug_mode:
            return jsonify({
                "model": "claude-3-opus-20240229",
                "claude_response": message.content[0].text,
                "gemini_model": "gemini-1.5-pro",
                "gemini_response": response_text
            })
        else:
            return jsonify({"Claude": message.content[0].text, "Gemini": response_text})
        
    except Exception as e:
        return jsonify({
            "error": f"Error code: {str(e)}",
            "traceback": str(traceback.format_exc()) if debug_mode else None
        })
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = bool(os.environ.get('LOCAL_DEV', False))
    app.run(host='0.0.0.0', port=port, debug=debug)