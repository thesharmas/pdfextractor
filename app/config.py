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