from typing import Any
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import Config, LLMProvider

class LLMFactory:
    @staticmethod
    def create_llm() -> Any:
        """
        Factory method that produces different LLM instances based on configuration.
        """
        match Config.LLM_PROVIDER:
            case LLMProvider.CLAUDE:
                return LLMFactory._create_claude_llm()
            case LLMProvider.GEMINI:
                return LLMFactory._create_gemini_llm()
            case _:
                raise ValueError(f"Unsupported LLM provider: {Config.LLM_PROVIDER}")

    @staticmethod
    def _create_claude_llm() -> ChatAnthropic:
        """Creates a configured Claude instance"""
        return ChatAnthropic(
            model=Config.CLAUDE_MODEL,
            anthropic_api_key=Config.ANTHROPIC_API_KEY,
            temperature=Config.TEMPERATURE
        )

    @staticmethod
    def _create_gemini_llm() -> ChatGoogleGenerativeAI:
        """Creates a configured Gemini instance"""
        return ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=Config.TEMPERATURE
        ) 