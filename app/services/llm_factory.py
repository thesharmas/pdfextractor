import logging
import base64
from typing import Any, List, Dict
from app.config import Config, LLMProvider
import json
from anthropic import Anthropic
import google.generativeai as genai
from openai import OpenAI
import PyPDF2
from app.services.rate_limiter import RATE_LIMITERS

logger = logging.getLogger(__name__)

class LLMWrapper:
    """Base wrapper class for LLMs with conversation memory"""
    def __init__(self):
        self.messages = []
        self.tools = []

    def add_pdf(self, file_path: str) -> None:
        """Add PDF content to conversation history"""
        raise NotImplementedError

    def add_json(self, data: dict) -> None:
        """Add JSON content to conversation history"""
        raise NotImplementedError

    def set_tools(self, tools: List[Any]):
        """Configure tools for the LLM"""
        logger.info(f"🔧 Setting tools: {[t.name for t in tools]}")
        self._bind_tools(tools)
        return self

    def _bind_tools(self, tools: List[Any]):
        """Base implementation for binding tools"""
        logger.info(f"🔧 Binding tools: {[t.name for t in tools]}")
        self.tools = tools

    def get_response(self, prompt: str) -> str:
        """Get response for a prompt, maintaining conversation history"""
        raise NotImplementedError

class AnthropicWrapper(LLMWrapper):
    def __init__(self):
        super().__init__()
        self.model = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        logger.info("🤖 Initialized Anthropic wrapper")

    def add_pdf(self, file_path: str) -> None:
        try:
            with open(file_path, 'rb') as file:
                pdf_data = base64.b64encode(file.read()).decode('utf-8')
                self.messages.append({
                    "role": "user",
                    "content": [{
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_data
                        }
                    }]
                })
            logger.info("📄 Added PDF to conversation")
        except Exception as e:
            logger.error(f"Error adding PDF: {str(e)}")
            raise

    def add_json(self, data: dict) -> None:
        try:
            self.messages.append({
                "role": "user",
                "content": [{
                    "type": "text",
                    "text": f"JSON content:\n{json.dumps(data, indent=2)}"
                }]
            })
            logger.info("📄 Added JSON to conversation")
        except Exception as e:
            logger.error(f"Error adding JSON: {str(e)}")
            raise

    def get_response(self, prompt: str) -> str:
        try:
            if not prompt:
                return ""
            
            self.messages.append({
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            })
            
            result = self.model.messages.create(
                model=Config.ANTHROPIC_MODEL,
                messages=self.messages,
                max_tokens=Config.ANTHROPIC_MAX_TOKENS,
                temperature=Config.TEMPERATURE
            )
            
            response_text = result.content[0].text
            self.messages.append({
                "role": "assistant",
                "content": response_text
            })
            
            return response_text
            
        except Exception as e:
            logger.error(f"❌ Error from Anthropic: {str(e)}")
            raise

class GoogleWrapper(LLMWrapper):
    def __init__(self):
        super().__init__()
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(Config.GOOGLE_MODEL)
        self.chat = self.model.start_chat()
        self.rate_limiter = RATE_LIMITERS["google"]
        logger.info(f"🤖 Initialized Google wrapper")

    def add_pdf(self, file_path: str) -> None:
        try:
            content = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    content += page.extract_text() + "\n\n"
            
            self.chat.send_message(f"PDF content:\n{content}")
            logger.info("📄 Added PDF to conversation")
        except Exception as e:
            logger.error(f"Error adding PDF: {str(e)}")
            raise

    def add_json(self, data: dict) -> None:
        try:
            self.chat.send_message(
                f"JSON content:\n{json.dumps(data, indent=2)}"
            )
            logger.info("📄 Added JSON to conversation")
        except Exception as e:
            logger.error(f"Error adding JSON: {str(e)}")
            raise

    def get_response(self, prompt: str) -> str:
        try:
            if not prompt:
                return ""
            
            response = self.chat.send_message(prompt)
            response_text = response.text
            
            if response_text.count('{') != response_text.count('}'):
                logger.warning("⚠️ Incomplete JSON detected, requesting completion")
                completion = self.chat.send_message(
                    "Please complete the JSON response. Return ONLY the complete JSON."
                )
                response_text = completion.text
            
            return response_text
            
        except Exception as e:
            logger.error(f"❌ Error from Google: {str(e)}")
            raise

class OpenAIWrapper(LLMWrapper):
    def __init__(self):
        super().__init__()
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
        self.rate_limiter = RATE_LIMITERS["openai"]
        logger.info(f"🤖 Initialized OpenAI wrapper")

    def add_pdf(self, file_path: str) -> None:
        try:
            content = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    content += page.extract_text() + "\n\n"
            
            self.messages.append({
                "role": "user",
                "content": f"PDF content:\n{content}"
            })
            logger.info("📄 Added PDF to conversation")
        except Exception as e:
            logger.error(f"Error adding PDF: {str(e)}")
            raise

    def add_json(self, data: dict) -> None:
        try:
            self.messages.append({
                "role": "user",
                "content": f"JSON content:\n{json.dumps(data, indent=2)}"
            })
            logger.info("📄 Added JSON to conversation")
        except Exception as e:
            logger.error(f"Error adding JSON: {str(e)}")
            raise

    def get_response(self, prompt: str) -> str:
        try:
            if not prompt:
                return ""
            
            self.messages.append({
                "role": "user",
                "content": prompt
            })
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                max_tokens=Config.OPENAI_MAX_TOKENS,
                temperature=Config.TEMPERATURE
            )
            
            response_text = response.choices[0].message.content
            self.messages.append({
                "role": "assistant",
                "content": response_text
            })
            
            return response_text
            
        except Exception as e:
            logger.error(f"❌ Error in OpenAI wrapper: {str(e)}")
            raise

class LLMFactory:
    @staticmethod
    def create_llm(provider: LLMProvider = None) -> LLMWrapper:
        """Factory method that produces wrapped LLM instances"""
        provider = provider or Config.LLM_PROVIDER
        
        logger.info(f"🏭 Creating new LLM instance for provider: {provider}")
        
        if provider == LLMProvider.ANTHROPIC:
            return AnthropicWrapper()
        elif provider == LLMProvider.GOOGLE:
            return GoogleWrapper()
        elif provider == LLMProvider.OPENAI:
            return OpenAIWrapper()
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")