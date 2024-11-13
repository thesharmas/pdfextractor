from flask import Flask, request, jsonify
import requests
import base64
import anthropic
import os
from google.cloud import secretmanager
from dotenv import load_dotenv


def get_api_key():
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    if not api_key:
        # Fallback to Secret Manager if not found in environment
        return access_secret_version("anthropic-api-key", "latest")
        
    return api_key

def access_secret_version(secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/pdfextractor-441603/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

app = Flask(__name__)
api_key = get_api_key()
claude = anthropic.Client(api_key=api_key)

@app.route('/extract-invoice', methods=['POST'])
def extract_invoice():
    try:
        pdf_url = request.json.get('pdf_url')
        debug_mode = request.json.get('debug', False)
        
        prompt = f"""Please list all invoice numbers from this PDF.
        
        First, describe what you see in the document.
        Then, explain how you identify invoice numbers.
        Finally, list all invoice numbers you found.

        PDF URL: {pdf_url}"""

        message = claude.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=4096,
            temperature=0,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        if debug_mode:
            return jsonify({
                "full_response": message.content[0].text,
                "model": "claude-3-opus-20240229",
                "prompt": prompt,
                "status": message.status
            })
        else:
            return jsonify({"response": message.content[0].text})
        
    except Exception as e:
        return jsonify({
            "error": f"Error code: {str(e)}",
            "traceback": str(traceback.format_exc()) if debug_mode else None
        })
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug = bool(os.environ.get('LOCAL_DEV', False))
    app.run(host='0.0.0.0', port=port, debug=debug)