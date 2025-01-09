import requests
import json
import os

def test_extract_invoice():
    url = "http://localhost:8080/extract-invoice"
    payload = {
        "file_path": "./bank.pdf",  # Changed to use local file path
        "debug": True
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        # Verify file exists before making request
        if not os.path.exists(payload["file_path"]):
            raise FileNotFoundError(f"Invoice file not found at {payload['file_path']}")
        response = requests.post(url, json=payload, headers=headers)
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_extract_invoice()