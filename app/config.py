import os
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

class LLMProvider(Enum):
    CLAUDE = "claude"
    GEMINI = "gemini"
    OPENAI = "openai"

class Config:
    LLM_PROVIDER = LLMProvider(os.getenv('LLM_PROVIDER', 'claude'))
    
    # Model configurations
    CLAUDE_MODEL = "claude-3-5-sonnet-latest"
    GEMINI_MODEL = "gemini-1.5-flash"
    OPENAI_MODEL = "chatgpt-4o-latest"
    
    # API Keys
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    
    # Model parameters
    TEMPERATURE = 0.7 
    
    # Model max token limits (for responses)
    CLAUDE_MAX_TOKENS = 4096     # Claude 3 Sonnet response limit
    GEMINI_MAX_TOKENS = 2048     # Gemini Pro response limit
    OPENAI_MAX_TOKENS = 4096     # GPT-4 response limit

    # Model context limits (total tokens including prompt + response)
    CLAUDE_CONTEXT_LIMIT = 200000  # Claude 3 Sonnet context limit
    GEMINI_CONTEXT_LIMIT = 32768   # Gemini Pro context limit
    OPENAI_CONTEXT_LIMIT = 128000  # GPT-4 context limit 