from typing import List, Dict, Any, Union
import base64
import os
import google.generativeai as genai
from app.config import Config, LLMProvider
import logging
import traceback
from PyPDF2 import PdfMerger

logger = logging.getLogger(__name__)

class ContentService:
    def __init__(self):
        """Initialize the service with Gemini if needed"""
        if Config.LLM_PROVIDER == LLMProvider.GEMINI:
            genai.configure(api_key=Config.GOOGLE_API_KEY)

    def prepare_file_content(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        logger.info("🔄 Preparing file content...")
        contents = []
        
        for file_path in file_paths:
            try:
                logger.info(f"�� Processing file: {file_path}")
                contents.append({
                    "type": "text",
                    "file_path": file_path  # Just pass the file path
                })
                
            except Exception as e:
                logger.error(f"❌ Error processing file {file_path}: {str(e)}")
                logger.error(traceback.format_exc())
            
        logger.info(f"✅ Processed {len(contents)} files")
        return contents

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

    def merge_pdfs(self, file_paths: List[str], output_path: str = "merged.pdf") -> str:
        """Merge multiple PDFs into one file"""
        logger.info(f"🔄 Merging {len(file_paths)} PDFs...")
        
        merger = PdfMerger()
        
        try:
            # Add each PDF to the merger
            for file_path in file_paths:
                logger.info(f"📄 Adding file: {file_path}")
                merger.append(file_path)
            
            # Write the merged PDF
            logger.info(f"💾 Writing merged PDF to: {output_path}")
            merger.write(output_path)
            merger.close()
            
            logger.info("✅ PDF merge complete")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Error merging PDFs: {str(e)}")
            logger.error(traceback.format_exc())
            raise

   