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
    GEMINI_MODEL = "gemini-2.0-flash-lite-preview-02-05"
    
    # API Keys
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    
    # Model parameters
    TEMPERATURE = 0.7 