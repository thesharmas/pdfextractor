import requests
import json

def test_extract_invoice():
    url = "http://localhost:8080/extract-invoice"
    payload = {
        "pdf_url": "https://storage.googleapis.com/kanmon-issued-product-invoices-production/7c1faa6f-568c-44fc-886e-0806d17b2332/e7fa076b-267f-484e-a5c9-d103732e3c8e-invoice-1734107283528.pdf?GoogleAccessId=retool%40kanmonos-prod.iam.gserviceaccount.com&Expires=1734550571&Signature=SsRZADcRyZljc5B73MVBK29TG3OE3VNOqHU9tFhK77SssETe%2F0wfuO%2BD1U6Onf4qZg8ddYkT0refMnaLhoOHE46N2eYlqT0SnCRfkNafJK%2BlPf0K%2BPLw2wfmzCuyg2eWvBwHlM%2B7FV47jbNVOFqb1pVZrA6VIjszdTVbU7YvdHqxUDOp65fLfbyaUWoIwgl6NjITmorG%2B7TzA5iuwcccqwhl2rDoATMGxB1RIusfBnZQ3DkM51LyTEvOpLEgJzBPKXSssXqwbiE93Vq%2FuDysrJHbbr3WAE3LEgQCCxRaT6aKx56l4htcz2IWAE%2BtUPWG1EePTTW9KvnmAQga5FKBMQ%3D%3D",
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