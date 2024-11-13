from flask import Flask, request, jsonify
import requests
import base64
import anthropic
import os
from google.cloud import secretmanager


def access_secret_version(secret_id, version_id="latest"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/harkerbot-436722/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

app = Flask(__name__)
anthropic_api_key = access_secret_version("anthropic-api-key", "latest")
claude = anthropic.Client(anthropic_api_key)

@app.route('/extract-invoice', methods=['POST'])
def extract_invoice():
    try:
        # Get URL from request
        data = request.get_json()
        if not data or 'pdf_url' not in data:
            return jsonify({'error': 'PDF URL is required'}), 400
            
        pdf_url = data['pdf_url']
        
        # Download PDF from URL
        response = requests.get(pdf_url)
        if response.status_code != 200:
            return jsonify({'error': 'Failed to download PDF'}), 400
            
        # Convert PDF to base64
        pdf_base64 = base64.b64encode(response.content).decode('utf-8')
            
        # Send to Claude for invoice number extraction
        prompt = """Please analyze this PDF invoice and extract all invoice numbers.
        Only return the invoice numbers, nothing else."""
        
        completion = claude.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            messages=[
                {
                    "role": "user", 
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "file",
                            "file_data": {
                                "type": "application/pdf",
                                "base64": pdf_base64
                            }
                        }
                    ]
                }
            ]
        )
        
        invoice_numbers = completion.content[0].text
        
        return jsonify({
            'invoice_numbers': invoice_numbers
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

