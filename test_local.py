import requests
import json
from pprint import pprint
import os
import logging
from dotenv import load_dotenv
from app.config import LLMProvider

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

def compare_responses(gemini_response, claude_response, openai_response):
    logger.info("\n=== Comparison of Responses ===\n")
    
    # First, print raw responses if there are errors
    if any('error' in resp for resp in [gemini_response, claude_response, openai_response]):
        logger.error("⚠️ Errors detected in responses:\n")
        for name, resp in [("Gemini", gemini_response), ("Claude", claude_response), ("OpenAI", openai_response)]:
            if 'error' in resp:
                logger.error(f"{name} Error: {resp.get('error')}")
                logger.error(f"Traceback: {resp.get('traceback', 'No traceback')}")
        return

    # Print full responses for debugging
    for name, resp in [("Gemini", gemini_response), ("Claude", claude_response), ("OpenAI", openai_response)]:
        logger.info(f"\nFull {name} Response:")
        logger.info(json.dumps(resp, indent=2))
    
    try:
        # Compare metrics
        logger.info("\n📊 METRICS COMPARISON:")
        
        # Compare average daily balance
        balances = {
            "Gemini": gemini_response.get("metrics", {}).get("average_daily_balance", {}).get("amount", 0),
            "Claude": claude_response.get("metrics", {}).get("average_daily_balance", {}).get("amount", 0),
            "OpenAI": openai_response.get("metrics", {}).get("average_daily_balance", {}).get("amount", 0)
        }
        
        logger.info(f"\nAverage Daily Balance:")
        for name, balance in balances.items():
            logger.info(f"{name}: ${balance:,.2f}")
        
        # Compare NSF information
        nsf_info = {
            "Gemini": gemini_response.get("metrics", {}).get("nsf_information", {}),
            "Claude": claude_response.get("metrics", {}).get("nsf_information", {}),
            "OpenAI": openai_response.get("metrics", {}).get("nsf_information", {})
        }
        
        logger.info(f"\nNSF Information:")
        for name, nsf in nsf_info.items():
            logger.info(f"{name}: {nsf.get('incident_count', 0)} incidents, ${nsf.get('total_fees', 0):,.2f} in fees")
        
        # Compare orchestration decisions
        logger.info("\n🤖 ORCHESTRATION DECISIONS:")
        for name, resp in [("Gemini", gemini_response), ("Claude", claude_response), ("OpenAI", openai_response)]:
            logger.info(f"\n{name} recommended:")
            logger.info(resp.get("orchestration", "No orchestration data"))

    except Exception as e:
        logger.error(f"\n⚠️ Error while comparing responses: {str(e)}")
        logger.error("\nRaw Responses:")
        for name, resp in [("Gemini", gemini_response), ("Claude", claude_response), ("OpenAI", openai_response)]:
            logger.error(f"\n{name} Response:")
            logger.error(json.dumps(resp, indent=2))

def main():
    # Use local PDF files
    file_paths = [
        "./Bank5.pdf",
        "./Bank6.pdf",
        "./Bank8.pdf",
        "./Bank10.pdf",
        "./Bank11.pdf"
    ]
    
    # Verify files exist
    for path in file_paths:
        if not os.path.exists(path):
            logger.warning(f"⚠️ Warning: File not found: {path}")
    
    logger.info("\n🚀 Testing with Gemini...")
    gemini_response = test_underwrite(file_paths, provider=LLMProvider.GEMINI)
    
    logger.info("\n🚀 Testing with Claude...")
    claude_response = test_underwrite(file_paths, provider=LLMProvider.CLAUDE)
    
    logger.info("\n🚀 Testing with OpenAI...")
    openai_response = test_underwrite(file_paths, provider=LLMProvider.OPENAI)
    
    # Compare all three responses
    compare_responses(gemini_response, claude_response, openai_response)

if __name__ == "__main__":
    main()