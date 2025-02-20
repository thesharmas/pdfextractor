import os
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

class LLMProvider(Enum):
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OPENAI = "openai"

class Config:
    LLM_PROVIDER = LLMProvider(os.getenv('LLM_PROVIDER', 'anthropic'))
    
    # Model configurations
    ANTHROPIC_MODEL = "claude-3-sonnet-20240229"
    GOOGLE_MODEL = "gemini-pro"
    OPENAI_MODEL = "gpt-4-turbo-preview"
    
    # API Keys
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Model parameters
    TEMPERATURE = 0.0
    
    # Model max token limits (for responses)
    ANTHROPIC_MAX_TOKENS = 4096     # Claude 3 Sonnet response limit
    GOOGLE_MAX_TOKENS = 2048        # Gemini Pro response limit
    OPENAI_MAX_TOKENS = 4096        # GPT-4 response limit

    # Model context limits (total tokens including prompt + response)
    ANTHROPIC_CONTEXT_LIMIT = 200000  # Claude 3 Sonnet context limit
    GOOGLE_CONTEXT_LIMIT = 32768      # Gemini Pro context limit
    OPENAI_CONTEXT_LIMIT = 128000     # GPT-4 context limit 