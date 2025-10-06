"""
Document Processing Service
Handles PDF/Word document ingestion, OCR, and section detection
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import fitz  # PyMuPDF
from docx import Document
import pytesseract
from PIL import Image
import io

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Handles document processing including OCR and section detection"""
    
    def __init__(self):
        self.supported_formats = ['.pdf', '.docx', '.doc', '.txt']
        
    def process_document(self, file_path: str) -> Dict[str, Any]:
        """Process a document and extract sections, text, and metadata"""
        try:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.pdf':
                return self._process_pdf(file_path)
            elif file_ext in ['.docx', '.doc']:
                return self._process_word(file_path)
            elif file_ext == '.txt':
                return self._process_text(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")
                
        except Exception as e:
            logger.error(f"Error processing document {file_path}: {str(e)}")
            raise
    
    def _process_pdf(self, file_path: str) -> Dict[str, Any]:
        """Process PDF documents with OCR for scanned content"""
        doc = fitz.open(file_path)
        sections = []
        full_text = ""
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Extract text
            text = page.get_text()
            full_text += text + "\n"
            
            # If text is minimal, try OCR
            if len(text.strip()) < 50:
                logger.info(f"Low text content on page {page_num + 1}, attempting OCR")
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                ocr_text = pytesseract.image_to_string(img)
                text = ocr_text
                full_text += text + "\n"
            
            # Detect sections based on headers and formatting
            page_sections = self._detect_sections(text, page_num + 1)
            sections.extend(page_sections)
        
        doc.close()
        
        return {
            "document_type": "pdf",
            "total_pages": len(doc),
            "full_text": full_text,
            "sections": sections,
            "metadata": {
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "creator": doc.metadata.get("creator", "")
            }
        }
    
    def _process_word(self, file_path: str) -> Dict[str, Any]:
        """Process Word documents"""
        doc = Document(file_path)
        sections = []
        full_text = ""
        
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if text:
                full_text += text + "\n"
                
                # Detect sections based on heading styles
                if paragraph.style.name.startswith('Heading'):
                    sections.append({
                        "section_name": text,
                        "page_number": 1,  # Word doesn't have easy page numbers
                        "content": text,
                        "style": paragraph.style.name
                    })
        
        return {
            "document_type": "word",
            "total_pages": 1,  # Approximation
            "full_text": full_text,
            "sections": sections,
            "metadata": {
                "title": "",
                "author": "",
                "subject": "",
                "creator": ""
            }
        }
    
    def _process_text(self, file_path: str) -> Dict[str, Any]:
        """Process plain text documents"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        sections = self._detect_sections(content, 1)
        
        return {
            "document_type": "text",
            "total_pages": 1,
            "full_text": content,
            "sections": sections,
            "metadata": {
                "title": "",
                "author": "",
                "subject": "",
                "creator": ""
            }
        }
    
    def _detect_sections(self, text: str, page_number: int) -> List[Dict[str, Any]]:
        """Detect document sections based on headers and formatting"""
        sections = []
        lines = text.split('\n')
        
        # Common section headers for contracts
        section_keywords = [
            "acceptance", "payment", "termination", "deliverables", 
            "obligations", "liability", "confidentiality", "intellectual property",
            "warranty", "indemnification", "governing law", "dispute resolution"
        ]
        
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if line looks like a section header
            is_header = False
            for keyword in section_keywords:
                if keyword.lower() in line.lower() and len(line) < 100:
                    is_header = True
                    break
            
            # Also check for numbered sections (e.g., "1. Acceptance", "Section 8")
            if any(pattern in line for pattern in ["Section", "Article", "Clause"]) and len(line) < 100:
                is_header = True
            
            if is_header:
                # Save previous section
                if current_section:
                    sections.append({
                        "section_name": current_section,
                        "page_number": page_number,
                        "content": "\n".join(current_content),
                        "style": "header"
                    })
                
                # Start new section
                current_section = line
                current_content = [line]
            else:
                if current_section:
                    current_content.append(line)
                else:
                    # Content before first section
                    if not sections:
                        sections.append({
                            "section_name": "Introduction",
                            "page_number": page_number,
                            "content": line,
                            "style": "content"
                        })
                    else:
                        sections[-1]["content"] += "\n" + line
        
        # Save last section
        if current_section:
            sections.append({
                "section_name": current_section,
                "page_number": page_number,
                "content": "\n".join(current_content),
                "style": "header"
            })
        
        return sections
    
    def extract_clauses(self, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract specific clauses relevant to ASC-606 analysis"""
        clauses = []
        
        for section in sections:
            section_name = section["section_name"].lower()
            content = section["content"]
            
            # Map sections to clause types
            clause_type = self._map_section_to_clause_type(section_name)
            if clause_type:
                clauses.append({
                    "clause_type": clause_type,
                    "section_name": section["section_name"],
                    "page_number": section["page_number"],
                    "content": content,
                    "relevance_score": self._calculate_relevance_score(content, clause_type)
                })
        
        return clauses
    
    def _map_section_to_clause_type(self, section_name: str) -> Optional[str]:
        """Map section names to ASC-606 clause types"""
        mapping = {
            "acceptance": "acceptance",
            "payment": "payment_terms",
            "termination": "termination",
            "deliverables": "performance_obligations",
            "obligations": "performance_obligations",
            "warranty": "warranty",
            "liability": "liability",
            "intellectual property": "ip_transfer",
            "confidentiality": "confidentiality"
        }
        
        for keyword, clause_type in mapping.items():
            if keyword in section_name:
                return clause_type
        
        return None
    
    def _calculate_relevance_score(self, content: str, clause_type: str) -> float:
        """Calculate relevance score for a clause based on keywords"""
        keywords_by_type = {
            "acceptance": ["accept", "approve", "examine", "inspect", "30 days", "remedy"],
            "payment_terms": ["payment", "invoice", "30 days", "net", "due"],
            "termination": ["terminate", "termination", "penalty", "early termination"],
            "performance_obligations": ["deliver", "obligation", "service", "work"],
            "warranty": ["warranty", "guarantee", "defect", "remedy"],
            "liability": ["liability", "damages", "indemnify", "hold harmless"],
            "ip_transfer": ["intellectual property", "ownership", "license", "transfer"],
            "confidentiality": ["confidential", "proprietary", "non-disclosure"]
        }
        
        if clause_type not in keywords_by_type:
            return 0.5
        
        keywords = keywords_by_type[clause_type]
        content_lower = content.lower()
        
        matches = sum(1 for keyword in keywords if keyword in content_lower)
        return min(matches / len(keywords), 1.0)
