import requests
import json
import os

def test_extract_invoice():
    url = "http://localhost:8080/extract-invoice"
    payload = {
        "file_path": "./Bank.pdf",  # Changed to use local file path
        "debug": True
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        # Verify file exists before making request
        if not os.path.exists(payload["file_path"]):
            raise FileNotFoundError(f"Invoice file not found at {payload['file_path']}")
        response = requests.post(url, json=payload)
        data = response.json()
        
        # Format each response separately
        print("\n=== Claude Response ===")
        print(data['claude_response'])
        
        print("\n=== Gemini Response ===")
        print(data['gemini_response'])
        
        print("\n=== Raw JSON (if needed) ===")
        print(json.dumps(data, indent=4))
                
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_extract_invoice()