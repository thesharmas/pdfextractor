import json
import logging
from pathlib import Path
from datetime import datetime
from test_local import compare_balances, parse_response  # Import both functions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("🔍 Loading and comparing saved responses...")
    responses = {}
    
    # Load and parse each response file
    for file in Path('.').glob('*_raw_response.json'):
        model_name = file.name.split('_')[0].capitalize()
        logger.info(f"\nLoading {model_name} response:")
        
        try:
            with open(file) as f:
                raw_response = json.load(f)
            responses[model_name] = parse_response(raw_response)
        except Exception as e:
            logger.error(f"❌ Failed to load {file.name}: {str(e)}")
    
    if len(responses) == 3:  # Make sure we have all three responses
        # Compare the responses
        compare_balances(
            responses["Gemini"],
            responses["Claude"],
            responses["Openai"]
        )
    else:
        logger.error("❌ Missing some response files. Need all three (Gemini, Claude, OpenAI).")

if __name__ == "__main__":
    main() 