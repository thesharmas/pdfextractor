from typing import List, Dict, Any, Union
import base64
import os
import google.generativeai as genai
from app.config import Config, LLMProvider

class ContentService:
    def __init__(self):
        """Initialize the service with Gemini if needed"""
        if Config.LLM_PROVIDER == LLMProvider.GEMINI:
            genai.configure(api_key=Config.GOOGLE_API_KEY)

    def prepare_file_content(self, file_paths: List[str]) -> Union[List[Dict], List[Any]]:
        """
        Prepares file content based on the LLM provider.
        Returns either a list of dicts for Claude or a list of Gemini file objects.
        """
        if Config.LLM_PROVIDER == LLMProvider.CLAUDE:
            return self._prepare_for_claude(file_paths)
        elif Config.LLM_PROVIDER == LLMProvider.GEMINI:
            return self._prepare_for_gemini(file_paths)
        else:
            raise ValueError(f"Unsupported LLM provider: {Config.LLM_PROVIDER}")

    def _prepare_for_claude(self, file_paths: List[str]) -> List[Dict]:
        """Prepares content in Claude's format"""
        file_contents = []
        for file_path in file_paths:
            try:
                with open(file_path, 'rb') as file:
                    pdf_content = file.read()
                    file_contents.append({
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64.b64encode(pdf_content).decode()
                        }
                    })
            except Exception as e:
                raise Exception(f"Failed to read file {file_path}: {str(e)}")
        return file_contents

    def _prepare_for_gemini(self, file_paths: List[str]) -> List[Any]:
        """Prepares content in Gemini's format using file parts"""
        file_contents = []

        for file_path in file_paths:
            try:
                with open(file_path, 'rb') as file:
                    pdf_content = file.read()
                    file_contents.append({
                        'mime_type': 'application/pdf',
                        'data': pdf_content
                    })
            except Exception as e:
                raise Exception(f"Failed to process file {file_path}: {str(e)}")
        return file_contents

    def add_prompt(self, file_contents: List[Union[Dict, Any]], prompt: str) -> List[Union[Dict, Any]]:
        """Combines prompt with file contents for LLM processing"""
        if Config.LLM_PROVIDER == LLMProvider.CLAUDE:
            return [{"type": "text", "text": prompt}] + file_contents
        elif Config.LLM_PROVIDER == LLMProvider.GEMINI:
            prompt_dict = {    
                "type": "text",
                "text": prompt
            }
            return file_contents + [prompt_dict]  # Gemini expects prompt at the end
        else:
            raise ValueError(f"Unsupported LLM provider: {Config.LLM_PROVIDER}")

   