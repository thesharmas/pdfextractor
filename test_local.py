import requests
import json
from pprint import pprint
import os
import logging
from dotenv import load_dotenv
from app.config import LLMProvider
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

def test_underwrite(file_paths, provider=None):
    url = "http://localhost:8080/underwrite"
    
    # Debug print the enum values
    logger.info("Available providers:")
    for p in LLMProvider:
        logger.info(f"- {p.name}: {p.value}")
    
    payload = {
        "file_paths": file_paths,
        "debug": True
    }
    
    if provider:
        payload["provider"] = provider.value
        
    logger.info("🔄 Making request to /underwrite:")
    logger.info(f"URL: {url}")
    logger.info(f"Provider: {payload.get('provider', 'default')}")
    logger.info("Payload:")
    logger.info(json.dumps(payload, indent=2))
    
    response = requests.post(url, json=payload)
    
    logger.info(f"📥 Response status: {response.status_code}")
    if response.status_code != 200:
        logger.error(f"Response content: {response.text}")
    return response.json()


def parse_response(response_data):
    """Parse raw response into standardized format and pretty print"""
    if isinstance(response_data, str):
        try:
            parsed = json.loads(response_data)
        except json.JSONDecodeError:
            parsed = json.loads(response_data.replace('\\"', '"'))
    else:
        parsed = response_data

    # Get and parse the details string
    details_str = parsed.get("metrics", {}).get("average_daily_balance", {}).get("details")
    if isinstance(details_str, str):
        details = json.loads(details_str)
    else:
        details = details_str or {}
    
    # Convert daily balances to transactions
    transactions = []
    daily_balances = details.get("daily_balances", {})
    for date, balance in sorted(daily_balances.items()):
        transactions.append({
            "date": date,
            "balance": balance,
            "is_business_day": datetime.strptime(date, '%Y-%m-%d').weekday() < 5
        })
    
    # Pretty print the transactions
    if transactions:
        logger.info("\n📝 Extracted Transactions:")
        logger.info("-" * 80)
        for trans in transactions[:5]:  # Show first 5 transactions
            logger.info(f"Date: {trans['date']:<12} | Balance: ${trans['balance']:>10,.2f} | Business Day: {str(trans['is_business_day']):>5}")
        if len(transactions) > 5:
            logger.info("...")
        logger.info(f"Total transactions: {len(transactions)}")
        logger.info("-" * 80)
    
    return transactions



def save_response(response_data, model_name):
    """Save both raw and parsed responses to disk with model name prefix"""
    raw_filename = f"{model_name.lower()}_raw_response.json"
    
    try:
        # Save raw response
        with open(raw_filename, 'w') as f:
            json.dump(response_data, f, indent=2)
        logger.info(f"✍️  Saved raw response to {raw_filename}")
        
    except Exception as e:
        logger.error(f"❌ Failed to save responses: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Test LLM providers')
    parser.add_argument('--provider', type=str, choices=['claude', 'gemini', 'openai', 'all'],
                       default='all', help='Specify which LLM provider to test')
    args = parser.parse_args()

    # Use local PDF files
    file_paths = [
        "./1.pdf",
        "./2.pdf",
        "./3.pdf",
        "./6.pdf",
        "./4.pdf",
        "./5.pdf"
    ]
    
    # Verify files exist
    for path in file_paths:
        if not os.path.exists(path):
            logger.warning(f"⚠️ Warning: File not found: {path}")
    
    if args.provider == 'all':
        logger.info("\n🚀 Testing with all providers...")
        
        gemini_response = test_underwrite(file_paths, provider=LLMProvider.GEMINI)
        save_response(gemini_response, "gemini")
        
        claude_response = test_underwrite(file_paths, provider=LLMProvider.CLAUDE)
        save_response(claude_response, "claude")
        
        openai_response = test_underwrite(file_paths, provider=LLMProvider.OPENAI)
        save_response(openai_response, "openai")
        
    
        
    else:
        # Run single provider
        provider = LLMProvider(args.provider)
        logger.info(f"\n🚀 Testing with {provider.name}...")
        response = test_underwrite(file_paths, provider=provider)
        save_response(response, provider.name)

       

if __name__ == "__main__":
    main()