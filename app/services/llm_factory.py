import logging
from typing import Any, Union, List, Dict
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from app.config import Config, LLMProvider

logger = logging.getLogger(__name__)

class LLMWrapper:
    """Base wrapper class for LLMs with conversation memory"""
    def __init__(self):
        self.file_contents = None
        self.messages = []
        
    def set_file_contents(self, file_contents):
        """Store file contents and initialize conversation"""
        logger.info("🔄 Initializing LLM conversation with PDF contents")
        self.file_contents = file_contents
        self.messages = list(file_contents)
        logger.info(f"📄 PDF content added to conversation (size: {len(file_contents)} items)")

    def set_tools(self, tools: List[Any]):
        """Configure tools for the LLM"""
        logger.info(f"�� Setting tools: {[t.name for t in tools]}")
        self._bind_tools(tools)
        return self

    def _bind_tools(self, tools: List[Any]):
        """To be implemented by specific LLM wrappers"""
        raise NotImplementedError

    def get_response(self, prompt: str = None) -> str:
        raise NotImplementedError

class ClaudeWrapper(LLMWrapper):
    def __init__(self, model: ChatAnthropic):
        super().__init__()
        self.model = model
        logger.info("🤖 Initialized Claude LLM wrapper")

    def _bind_tools(self, tools: List[Any]):
        """Bind tools for Claude"""
        logger.info("🔧 Binding tools for Claude")
        self.model = self.model.bind_tools(tools)

    def get_response(self, prompt: str = None) -> str:
        if prompt:
            logger.info("➕ Adding new prompt to conversation")
            logger.debug(f"Prompt: {prompt[:100]}...")
            self.messages.append({"type": "text", "text": prompt})
        
        logger.info(f"📨 Sending conversation to Claude (messages: {len(self.messages)})")
        result = self.model.invoke(self.messages)
        
        logger.info("📥 Received response from Claude")
        logger.debug(f"Response: {result.content[:100]}...")
        self.messages.append({"type": "text", "text": result.content})
        return result.content

class GeminiWrapper(LLMWrapper):
    def __init__(self, model: Any):
        super().__init__()
        self.model = model
        logger.info("🤖 Initialized Gemini LLM wrapper")

    def _bind_tools(self, tools: List[Any]):
        """Configure tools for Gemini"""
        logger.info("🔧 Binding tools for Gemini")
        self.tools = [{
            "function_declarations": [{
                "name": tool.name,
                "description": tool.description
            } for tool in tools]
        }]

    def get_response(self, prompt: str = None) -> str:
        if prompt:
            logger.info("➕ Adding new prompt to conversation")
            logger.debug(f"Prompt: {prompt[:100]}...")
            self.messages.append(prompt)
            
        logger.info(f"📨 Sending conversation to Gemini (messages: {len(self.messages)})")
        result = self.model.generate_content(self.messages)
        
        logger.info("📥 Received response from Gemini")
        logger.debug(f"Response: {result.text[:100]}...")
        self.messages.append(result.text)
        return result.text

class LLMFactory:
    @staticmethod
    def create_llm() -> LLMWrapper:
        """Factory method that produces wrapped LLM instances"""
        logger.info(f"🏭 Creating new LLM instance for provider: {Config.LLM_PROVIDER}")
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