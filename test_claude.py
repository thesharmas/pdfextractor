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
        # Send the value exactly as defined in the enum
        payload["provider"] = provider.value  # Don't modify the case
        
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

def compare_responses(gemini_response, claude_response):
    logger.info("\n=== Comparison of Responses ===\n")
    
    # First, print raw responses if there are errors
    if 'error' in gemini_response or 'error' in claude_response:
        logger.error("⚠️ Errors detected in responses:\n")
        if 'error' in gemini_response:
            logger.error(f"Gemini Error: {gemini_response.get('error')}")
            logger.error(f"Traceback: {gemini_response.get('traceback', 'No traceback')}")
        if 'error' in claude_response:
            logger.error(f"Claude Error: {claude_response.get('error')}")
            logger.error(f"Traceback: {claude_response.get('traceback', 'No traceback')}")
        return

    # Print full responses for debugging
    logger.info("Full Gemini Response:")
    logger.info(json.dumps(gemini_response, indent=2))
    logger.info("\nFull Claude Response:")
    logger.info(json.dumps(claude_response, indent=2))
    
    try:
        # Compare metrics
        logger.info("\n📊 METRICS COMPARISON:")
        
        # Compare average daily balance
        g_balance = gemini_response.get("metrics", {}).get("average_daily_balance", {}).get("amount", 0)
        c_balance = claude_response.get("metrics", {}).get("average_daily_balance", {}).get("amount", 0)
        logger.info(f"\nAverage Daily Balance:")
        logger.info(f"Gemini: ${g_balance:,.2f}")
        logger.info(f"Claude: ${c_balance:,.2f}")
        logger.info(f"Difference: ${abs(g_balance - c_balance):,.2f}")
        
        # Compare NSF information
        g_nsf = gemini_response.get("metrics", {}).get("nsf_information", {})
        c_nsf = claude_response.get("metrics", {}).get("nsf_information", {})
        logger.info(f"\nNSF Information:")
        logger.info(f"Gemini: {g_nsf.get('incident_count', 0)} incidents, ${g_nsf.get('total_fees', 0):,.2f} in fees")
        logger.info(f"Claude: {c_nsf.get('incident_count', 0)} incidents, ${c_nsf.get('total_fees', 0):,.2f} in fees")
        logger.info(f"Difference: {abs(g_nsf.get('incident_count', 0) - c_nsf.get('incident_count', 0))} incidents, "
                   f"${abs(g_nsf.get('total_fees', 0) - c_nsf.get('total_fees', 0)):,.2f} in fees")
        
        # Compare orchestration decisions
        logger.info("\n🤖 ORCHESTRATION DECISIONS:")
        logger.info("\nGemini recommended:")
        logger.info(gemini_response.get("orchestration", "No orchestration data"))
        logger.info("\nClaude recommended:")
        logger.info(claude_response.get("orchestration", "No orchestration data"))

    except Exception as e:
        logger.error(f"\n⚠️ Error while comparing responses: {str(e)}")
        logger.error("\nRaw Responses:")
        logger.error("\nGemini Response:")
        logger.error(json.dumps(gemini_response, indent=2))
        logger.error("\nClaude Response:")
        logger.error(json.dumps(claude_response, indent=2))

def main():
    # Use local PDF files
    file_paths = [
        "./Bank5.pdf",
        "./Bank6.pdf",
        "./Bank8.pdf",
        "./Bank10.pdf"
    ]
    
    # Verify files exist
    for path in file_paths:
        if not os.path.exists(path):
            logger.warning(f"⚠️ Warning: File not found: {path}")
    
    
    
    logger.info("\n🚀 Testing with Claude...")
    claude_response = test_underwrite(file_paths, provider=LLMProvider.CLAUDE)
    
  

if __name__ == "__main__":
    main()