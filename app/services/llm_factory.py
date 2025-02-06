from typing import Any, Union, List, Dict
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from app.config import Config, LLMProvider

class LLMWrapper:
    """Base wrapper class for LLMs"""
    def get_response(self, messages: Union[List[HumanMessage], List[Dict]], prompt: str = None) -> str:
        raise NotImplementedError

class ClaudeWrapper(LLMWrapper):
    def __init__(self, model: ChatAnthropic):
        self.model = model

    def get_response(self, messages: Union[List[HumanMessage], List[Dict]], prompt: str = None) -> str:
        result = self.model.invoke(messages)
        return result.content

class GeminiWrapper(LLMWrapper):
    def __init__(self, model: Any):
        self.model = model

    def get_response(self, messages: Union[List[HumanMessage], List[Dict]], prompt: str = None) -> str:
        result = self.model.generate_content([*messages, prompt])
        return result.text

class LLMFactory:
    @staticmethod
    def create_llm() -> LLMWrapper:
        """Factory method that produces wrapped LLM instances"""
        if Config.LLM_PROVIDER == LLMProvider.CLAUDE:
            model = ChatAnthropic(
                model=Config.CLAUDE_MODEL,
                anthropic_api_key=Config.ANTHROPIC_API_KEY,
                temperature=Config.TEMPERATURE
            )
            return ClaudeWrapper(model)
        elif Config.LLM_PROVIDER == LLMProvider.GEMINI:
            import google.generativeai as genai
            genai.configure(api_key=Config.GOOGLE_API_KEY)
            model = genai.GenerativeModel(Config.GEMINI_MODEL)
            return GeminiWrapper(model)
        else:
            raise ValueError(f"Unsupported LLM provider: {Config.LLM_PROVIDER}")