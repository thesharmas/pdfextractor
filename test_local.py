import requests
import json

def test_extract_invoice():
    url = "http://localhost:8080/extract-invoice"
    payload = {
        "pdf_url": "https://storage.googleapis.com/kanmon-issued-product-invoices-production/21813555-3703-4a46-80f4-e5f4125dea23/ec2ffc4d-a11e-42f3-811f-65fb551999e4-invoice-1731450559063.pdf?GoogleAccessId=retool%40kanmonos-prod.iam.gserviceaccount.com&Expires=1731472863&Signature=NDvY3kB%2FTWc0V9IUIou%2B6bfnwBdx4j6%2BzTGiG1gPRjZ5AgknTGfSFoMEntqAGKQtnk%2Fu1Y8WEEUywuyg%2FTrSevdV6BmXkBIalAYQHJGkPnaXkTygO7qJR1DMhr72Deo416oB9sOO%2F6p%2FwHm6viwuY54Aji46vibbPEksWXia96hIdBsVWJ9A4lRUG7P0Drs13u5IKgWgP%2Bh6m%2BWiOZAIUDq647X1HZcuLD16lAQvIdUKxyQ3%2BFdcRLwxsMeeN2s7ED718dt97%2BrYatkVPdBdqhd5A6UYEyOFP6FHXRYzvq9O5uJafNmDB1B09%2F37JSHZca4eXRytbR9UpNi9fG8OXg%3D%3D",
        "debug": True
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        # Print raw response text
        print("Raw Response:")
        print(response.text)
        
        # Try to parse JSON if possible
        try:
            json_response = response.json()
            print("\nJSON Response:")
            print(json.dumps(json_response, indent=2))
        except json.JSONDecodeError:
            print("\nCould not parse response as JSON")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_extract_invoice()