import requests
import json
from pprint import pprint
import os
from dotenv import load_dotenv

load_dotenv()

def test_underwrite(file_paths, provider=None):
    url = "http://localhost:8080/underwrite"
    
    payload = {
        "file_paths": file_paths,
        "debug": True
    }
    
    if provider:
        payload["provider"] = provider
    
    response = requests.post(url, json=payload)
    return response.json()

def compare_responses(gemini_response, claude_response):
    print("\n=== Comparison of Responses ===\n")
    
    # Compare metrics
    print("📊 METRICS COMPARISON:")
    
    # Compare average daily balance
    g_balance = gemini_response["metrics"]["average_daily_balance"]["amount"]
    c_balance = claude_response["metrics"]["average_daily_balance"]["amount"]
    print(f"\nAverage Daily Balance:")
    print(f"Gemini: ${g_balance:,.2f}")
    print(f"Claude: ${c_balance:,.2f}")
    print(f"Difference: ${abs(g_balance - c_balance):,.2f}")
    
    # Compare NSF information
    g_nsf = gemini_response["metrics"]["nsf_information"]
    c_nsf = claude_response["metrics"]["nsf_information"]
    print(f"\nNSF Information:")
    print(f"Gemini: {g_nsf['incident_count']} incidents, ${g_nsf['total_fees']:,.2f} in fees")
    print(f"Claude: {c_nsf['incident_count']} incidents, ${c_nsf['total_fees']:,.2f} in fees")
    print(f"Difference: {abs(g_nsf['incident_count'] - c_nsf['incident_count'])} incidents, "
          f"${abs(g_nsf['total_fees'] - c_nsf['total_fees']):,.2f} in fees")
    
    # Compare orchestration decisions
    print("\n🤖 ORCHESTRATION DECISIONS:")
    print("\nGemini recommended:")
    print(gemini_response["orchestration"])
    print("\nClaude recommended:")
    print(claude_response["orchestration"])

def main():
    # File paths to test
    file_paths = [
        "data/bank_statement_1.pdf",
        "data/bank_statement_2.pdf"
    ]
    
    print("\n🚀 Testing with Gemini...")
    gemini_response = test_underwrite(file_paths, provider="gemini")
    
    print("\n🚀 Testing with Claude...")
    claude_response = test_underwrite(file_paths, provider="claude")
    
    # Compare the responses
    compare_responses(gemini_response, claude_response)

if __name__ == "__main__":
    main()