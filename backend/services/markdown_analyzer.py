"""
ASC 606 Markdown Analyzer Service
Integrates the finalized approach from asc606_markdown_filler.py
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MarkdownAnalyzer:
    """Service for running ASC 606 analysis using markdown templates"""
    
    def __init__(self, client, vector_store_map_path: str = ".vector_store_map.json"):
        self.client = client
        self.vector_store_map_path = vector_store_map_path
        self.model = "gpt-4o"  # Default model
    
    def load_vector_map(self) -> Dict[str, str]:
        """Load vector store mapping from file"""
        if not os.path.exists(self.vector_store_map_path):
            return {}
        with open(self.vector_store_map_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def save_vector_map(self, mapping: Dict[str, str]) -> None:
        """Save vector store mapping to file"""
        with open(self.vector_store_map_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2)
    
    def ensure_vector_store(self, project_id: str) -> str:
        """Create or get existing vector store for project"""
        mapping = self.load_vector_map()
        if project_id in mapping:
            return mapping[project_id]
        
        # Create new vector store
        vs = self.client.vector_stores.create(name=f"asc606_{project_id}")
        mapping[project_id] = vs.id
        self.save_vector_map(mapping)
        return vs.id
    
    def add_files_to_store(self, vector_store_id: str, file_paths: List[str]) -> None:
        """Add files to vector store"""
        file_streams = []
        for path in file_paths:
            file_streams.append(open(path, "rb"))
        
        try:
            # Batch upload and poll until indexed
            self.client.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store_id,
                files=file_streams
            )
        finally:
            for fs in file_streams:
                try:
                    fs.close()
                except Exception:
                    pass
    
    def load_markdown_template(self, step: str) -> str:
        """Load markdown template for a given step"""
        possible_paths = [
            f"questionset/{step}.md",
            f"../questionset/{step}.md",
            f"../../questionset/{step}.md"
        ]
        
        for template_path in possible_paths:
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    return f.read()
        
        raise FileNotFoundError(f"Template not found in any of: {possible_paths}")
    
    def build_context_for_step(self, step: int, output_dir: str) -> str:
        """Build context by including previous step outputs"""
        context_parts = []
        
        for i in range(1, step):
            step_output_path = os.path.join(output_dir, f"step{i}_filled.md")
            if os.path.exists(step_output_path):
                with open(step_output_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        context_parts.append(f"## Step {i} Results:\n{content}")
        
        return "\n\n".join(context_parts)
    
    def ask_rag_with_template(self, vector_store_id: str, template: str, 
                            context: str, project_id: str) -> str:
        """Use markdown template as prompt and get filled response"""
        # Build the full prompt
        if context:
            full_prompt = f"""Based on the attached contract files and the previous step results below, please fill out the following ASC 606 form:

{context}

---

{template}

Please replace all placeholders (marked with curly braces {{}}) with actual answers based on the contract documents. Provide specific evidence and citations where possible."""
        else:
            full_prompt = f"""Based on the attached contract files, please fill out the following ASC 606 form:

{template}

Please replace all placeholders (marked with curly braces {{}}) with actual answers based on the contract documents. Provide specific evidence and citations where possible."""

        system_msg = (
            "You are an ASC 606 accounting expert. Analyze the attached contract files and fill out the form completely. "
            "Replace all placeholders with specific answers based on the contract content. "
            "Always provide evidence and citations from the contract documents. "
            "Return the complete filled form in markdown format with proper formatting including: "
            "- Use **bold** for important terms and Yes/No answers "
            "- Use # for main headings, ## for subheadings "
            "- Use tables with proper markdown table syntax "
            "- Use bullet points and numbered lists where appropriate "
            "- Preserve all original markdown structure from the template"
        )

        # Use Responses API with file search
        resp = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": full_prompt}
            ],
            tools=[{
                "type": "file_search",
                "vector_store_ids": [vector_store_id]
            }],
            metadata={"project_id": project_id, "step": "markdown_fill"}
        )

        try:
            return resp.output_text.strip()
        except Exception:
            try:
                return resp.output[0].content[0].text.strip()
            except Exception:
                return "Error: Could not extract response content"
    
    def run_analysis(self, project_id: str, output_dir: str) -> Dict[str, Any]:
        """Run complete ASC 606 analysis using markdown templates"""
        vector_store_id = self.ensure_vector_store(project_id)
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        results = {
            "project_id": project_id,
            "vector_store_id": vector_store_id,
            "output_dir": str(output_path),
            "steps": {},
            "status": "running"
        }
        
        logger.info(f"Starting ASC 606 analysis for project: {project_id}")
        
        # Process each step sequentially with progressive context
        for step_num in range(1, 6):
            step_name = f"step{step_num}"
            logger.info(f"Processing {step_name.upper()}...")
            
            try:
                # Load template
                template = self.load_markdown_template(step_name)
                logger.info(f"Loaded template: {len(template)} characters")
                
                # Build context from previous steps
                context = self.build_context_for_step(step_num, str(output_path))
                if context:
                    logger.info(f"Context from previous steps: {len(context)} characters")
                
                # Get filled response
                start_time = time.time()
                filled_content = self.ask_rag_with_template(
                    vector_store_id, template, context, project_id
                )
                elapsed = time.time() - start_time
                logger.info(f"API call completed in {elapsed:.2f} seconds")
                
                # Validate response
                if not filled_content or len(filled_content.strip()) < 100:
                    logger.warning(f"Response seems too short ({len(filled_content)} chars)")
                
                # Save filled content
                output_file = output_path / f"{step_name}_filled.md"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(filled_content)
                
                results["steps"][step_name] = {
                    "status": "completed",
                    "output_file": str(output_file),
                    "content_length": len(filled_content),
                    "processing_time": elapsed
                }
                
                logger.info(f"Saved {output_file} ({len(filled_content)} characters)")
                
            except Exception as e:
                logger.error(f"Error processing {step_name}: {str(e)}")
                # Create error file to maintain sequence
                output_file = output_path / f"{step_name}_filled.md"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(f"# Error in {step_name}\n\nError: {str(e)}")
                
                results["steps"][step_name] = {
                    "status": "error",
                    "output_file": str(output_file),
                    "error": str(e)
                }
                continue
            
            # Add delay to avoid rate limiting
            time.sleep(2)
        
        results["status"] = "completed"
        logger.info(f"Analysis complete! Output saved to: {output_path}")
        
        return results
    
    def get_step_content(self, project_id: str, step: str, output_dir: str) -> Optional[str]:
        """Get content of a specific step"""
        step_file = Path(output_dir) / f"{step}_filled.md"
        logger.info(f"Looking for step file: {step_file}")
        logger.info(f"File exists: {step_file.exists()}")
        if step_file.exists():
            with open(step_file, "r", encoding="utf-8") as f:
                return f.read()
        return None
    
    def update_step_content(self, project_id: str, step: str, content: str, output_dir: str) -> bool:
        """Update content of a specific step"""
        try:
            step_file = Path(output_dir) / f"{step}_filled.md"
            with open(step_file, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Error updating step content: {e}")
            return False
    
    def chat_with_vector_store(self, project_id: str, message: str) -> str:
        """Chat with the vector store for general questions"""
        vector_store_id = self.ensure_vector_store(project_id)
        
        system_msg = (
            "You are an ASC 606 accounting expert. Answer questions based on the attached contract files. "
            "Provide specific evidence and citations from the documents when possible."
        )
        
        resp = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": message}
            ],
            tools=[{
                "type": "file_search",
                "vector_store_ids": [vector_store_id]
            }],
            metadata={"project_id": project_id, "chat_type": "general"}
        )
        
        try:
            return resp.output_text.strip()
        except Exception:
            try:
                return resp.output[0].content[0].text.strip()
            except Exception:
                return "Error: Could not extract response content"
    
    def chat_with_step(self, project_id: str, step: str, message: str, output_dir: str) -> str:
        """Chat about a specific step's content"""
        step_content = self.get_step_content(project_id, step, output_dir)
        if not step_content:
            return "Step content not found."
        
        context_prompt = f"""Based on the following ASC 606 analysis step content and the attached contract files, please answer the user's question:

## Step {step} Content:
{step_content}

## User Question:
{message}

Please provide a helpful response based on both the step analysis and the original contract documents."""

        vector_store_id = self.ensure_vector_store(project_id)
        
        system_msg = (
            "You are an ASC 606 accounting expert. Answer questions about the analysis step content "
            "and provide additional insights based on the contract documents."
        )
        
        resp = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": context_prompt}
            ],
            tools=[{
                "type": "file_search",
                "vector_store_ids": [vector_store_id]
            }],
            metadata={"project_id": project_id, "chat_type": "step_specific", "step": step}
        )
        
        try:
            return resp.output_text.strip()
        except Exception:
            try:
                return resp.output[0].content[0].text.strip()
            except Exception:
                return "Error: Could not extract response content"
