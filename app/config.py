import os
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

class LLMProvider(Enum):
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OPENAI = "openai"

class ModelType(Enum):
    REASONING = "reasoning"
    ANALYSIS = "analysis"

class Config:
    # Default configurations
    DEFAULT_PROVIDER = LLMProvider(os.getenv('LLM_PROVIDER', 'openai'))
    DEFAULT_MODEL_TYPE = ModelType.ANALYSIS
    
    # API Keys
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Temperature setting
    TEMPERATURE = 0.0
    
    # Model configurations
    MODEL_CONFIGS = {
        LLMProvider.ANTHROPIC: {
            ModelType.REASONING: {
                "name": "claude-3-opus-20240229",
                "max_tokens": 4096,
                "context_limit": 200000
            },
            ModelType.ANALYSIS: {
                "name": "claude-3-sonnet-20240229",
                "max_tokens": 4096,
                "context_limit": 200000
            }
        },
        LLMProvider.GOOGLE: {
            ModelType.REASONING: {
                "name": "gemini-pro-advanced",
                "max_tokens": 2048,
                "context_limit": 32768
            },
            ModelType.ANALYSIS: {
                "name": "gemini-pro",
                "max_tokens": 2048,
                "context_limit": 32768
            }
        },
        LLMProvider.OPENAI: {
            ModelType.REASONING: {
                "name": "o3-mini",
                "max_tokens": 4096,
                "context_limit": 200000
            },
            ModelType.ANALYSIS: {
                "name": "chatgpt-4o-latest",
                "max_tokens": 4096,
                "context_limit": 200000
            }
        }
    }

    @classmethod
    def get_model_config(cls, provider: LLMProvider, model_type: ModelType = None):
        """Get model configuration for given provider and type"""
        model_type = model_type or cls.DEFAULT_MODEL_TYPE
        return cls.MODEL_CONFIGS[provider][model_type] 