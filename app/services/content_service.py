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

   