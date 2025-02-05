import requests
import json
import os

def test_extract_invoice():
    url = "http://localhost:8080/underwrite"
    payload = {
        "file_paths": [
            "./Bank1.pdf",
            "./Bank2.pdf",
            "./Bank3.pdf"
        ],  # Changed to use local file path
        "debug": True
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        # Verify files exist before making request
        for file_path in payload["file_paths"]:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Invoice file not found at {file_path}")
                
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        print(data)
        # Format each response separately
        
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_extract_invoice()