from typing import List, Dict, Any
import base64

class ContentService:
    @staticmethod
    def prepare_file_content(file_paths: List[str]) -> List[Dict[str, Any]]:
        """Prepares file content in the format needed for LLMs"""
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

    @staticmethod
    def process_with_prompt(file_contents: List[Dict], prompt: str) -> List[Dict]:
        """Combines prompt with file contents for LLM processing"""
        content = [{"type": "text", "text": prompt}]
        content.extend(file_contents)
        return content 