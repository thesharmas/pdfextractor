import requests
import json

def test_extract_invoice():
    url = "http://localhost:8080/extract-invoice"
    payload = {
        "pdf_url": "https://storage.googleapis.com/kanmon-issued-product-invoices-production/7c1faa6f-568c-44fc-886e-0806d17b2332/e7fa076b-267f-484e-a5c9-d103732e3c8e-invoice-1734107283528.pdf?GoogleAccessId=retool%40kanmonos-prod.iam.gserviceaccount.com&Expires=1734498487&Signature=CCko1ejPaRkadJq6xqWxEo0f0xb%2Bc0pZluUskRXyUgR6hNxkXHFOphL4v5zxvzaMBVtQpVVMKU8Juw4TdTfJuaZoeODz1%2F4bxgquje06%2B64Gb5K1%2BukgIxRD8X6phHMhTNc5vWH3s30i7iRg%2BAPYl8v3drwP0urtFPR11l0%2FomIT%2B3pwH3xKCfcYCiH9ye%2BDU8UX%2BWC0gms6hre7ZAOundMuVgqrq%2FfWu9DhYXI6qc9OEuWw1r33rj3THYFfmZRo2s0EXvoQZvYKcaXAIbT00O75ZLr4LVJr4HiMNLIey%2FdvcDQ2%2Fl%2FpFkdBeyJb9nN7NR67BeYrLjZ8SLNHGRxTJQ%3D%3D",
        "debug": True
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(response.json())
        
        # Try to parse JSON if possible

            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_extract_invoice()