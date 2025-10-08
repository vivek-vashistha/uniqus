"""
FastAPI Backend for Contract→606 Intelligence & Autofill
Implements the POC plan for ASC-606 compliance automation
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal
import os
import time
import json
import uuid
from datetime import datetime
import logging
from dotenv import load_dotenv
from openai import OpenAI
from services.cache_manager import CacheManager
from services.markdown_analyzer import MarkdownAnalyzer

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI configuration
API_KEY = os.getenv("DIRECT_OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID")

if not API_KEY:
    raise RuntimeError("DIRECT_OPENAI_API_KEY missing in .env")

client = OpenAI(api_key=API_KEY)

# Initialize cache manager and markdown analyzer
cache_manager = CacheManager()
markdown_analyzer = MarkdownAnalyzer(client)

# Initialize existing projects from vector store map
def initialize_existing_projects():
    """Initialize existing projects from .vector_store_map.json"""
    try:
        vector_map_path = ".vector_store_map.json"
        if os.path.exists(vector_map_path):
            with open(vector_map_path, "r", encoding="utf-8") as f:
                vector_map = json.load(f)
            
            for project_id, vector_store_id in vector_map.items():
                # Check if project already exists in cache
                existing_project = cache_manager.get_project_by_id(project_id)
                if not existing_project:
                    # Create project entry in cache with original project_id
                    project_name = project_id.replace("_", " ").title()
                    # Create project using the cache manager's method
                    project = cache_manager.get_or_create_project(
                        project_name, 
                        [], 
                        vector_store_id
                    )
                    # Update the project ID to match the original
                    project.project_id = project_id
                    cache_manager._save_cache()
                    logger.info(f"Initialized existing project: {project_name} ({project_id})")
                        
    except Exception as e:
        logger.error(f"Error initializing existing projects: {e}")

# Initialize existing projects on startup
initialize_existing_projects()

app = FastAPI(
    title="Contract→606 Intelligence API",
    description="ASC-606 compliance automation with human-in-the-loop review",
    version="1.0.0"
)

# Base directory for analysis outputs (use backend/output to keep paths consistent)
OUTPUT_BASE_DIR = os.path.join(os.path.dirname(__file__), "output")

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class ClauseHit(BaseModel):
    clause_text: str
    page_number: int
    section: str
    confidence_score: float
    clause_type: str

class ChecklistAnswer(BaseModel):
    question_id: str
    question_text: str
    suggested_answer: str
    confidence: float
    clause_hits: List[ClauseHit]
    alternative_hits: Optional[List[ClauseHit]] = None
    reviewer_override: Optional[str] = None
    reviewer_comment: Optional[str] = None
    final_answer: Optional[str] = None

class ChecklistRow(BaseModel):
    """Schema for checklist responses from LLM"""
    description: str
    yes_no: Literal["Yes", "No", "N/A"]
    analysis: str

class DocumentAnalysis(BaseModel):
    document_id: str
    document_name: str
    upload_timestamp: datetime
    processing_status: str
    extracted_sections: List[Dict[str, Any]]
    clause_hits: List[ClauseHit]
    checklist_answers: List[ChecklistAnswer]
    vector_store_id: Optional[str] = None
    project_id: Optional[str] = None
    file_hash: Optional[str] = None

class Project(BaseModel):
    project_id: str
    project_name: str
    created_timestamp: datetime
    vector_store_id: str
    file_hashes: List[str]
    analysis_results: Dict[str, Any]
    last_updated: datetime

class UploadRequest(BaseModel):
    project_name: Optional[str] = None
    reuse_existing: bool = True

class EvidenceBinder(BaseModel):
    document_id: str
    generated_timestamp: datetime
    highlighted_clauses: List[Dict[str, Any]]
    checklist_summary: List[ChecklistAnswer]
    export_formats: Dict[str, str]  # CSV, JSON, PDF paths

# In-memory storage for demo (replace with database in production)
documents_db: Dict[str, DocumentAnalysis] = {}
evidence_binders: Dict[str, EvidenceBinder] = {}

# Vector store management
def create_file_in_vector_store(file_content: bytes, filename: str) -> str:
    """Upload file to OpenAI and return file ID"""
    try:
        file_obj = (filename, file_content)
        created = client.files.create(file=file_obj, purpose="assistants")
        logger.info(f"Uploaded file to OpenAI: {created.id}")
        return created.id
    except Exception as e:
        logger.error(f"Error uploading file to OpenAI: {e}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

def ensure_vector_store(existing_id: Optional[str], name: str = "contract_analysis") -> str:
    """Create or reuse a vector store"""
    if existing_id:
        logger.info(f"Reusing existing vector store: {existing_id}")
        return existing_id
    
    try:
        vs = client.vector_stores.create(name=name)
        logger.info(f"Created vector store: {vs.id}")
        return vs.id
    except Exception as e:
        logger.error(f"Error creating vector store: {e}")
        raise HTTPException(status_code=500, detail=f"Vector store creation failed: {str(e)}")

def add_file_to_vector_store(vector_store_id: str, file_id: str):
    """Add a file to the vector store"""
    try:
        added = client.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=file_id
        )
        logger.info(f"Added file {file_id} to vector store {vector_store_id}")
        return added
    except Exception as e:
        logger.error(f"Error adding file to vector store: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add file to vector store: {str(e)}")

def analyze_question_with_llm(question: str, vector_store_id: str) -> ChecklistRow:
    """Use LLM to analyze a question based on vector store content"""
    try:
        schema = ChecklistRow.model_json_schema()
        
        response = client.responses.create(
            model=MODEL,
            input=[
                {
                    "role": "system",
                    "content": (
                        """You are a contract review assistant specializing in ASC 606. Use File Search over the provided 
                        vector store and answer ONLY from those documents. If evidence is insufficient, 
                        return 'No' and explain why. Output must match the JSON schema.
                        JSON schema:
                        {
                            "description": "The description of the checklist row",
                            "yes_no": "Yes, No or N/A",
                            "analysis": "The analysis of the checklist row"
                        }
                        Example:
                        {
                            "description": "Is the contract approved and are the parties committed to their obligations (ASC 606-10-25-1(a))?",
                            "yes_no": "Yes",
                            "analysis": "The contract is approved and the parties are committed to their obligations (ASC 606-10-25-1(a))"
                        }
                        """
                    ),
                },
                {"role": "user", "content": question},
            ],
            tools=[{
                "type": "file_search",
                "vector_store_ids": [vector_store_id]
            }],
            reasoning={"effort": "low"},
        )
        
        # Parse the response
        try:
            response_data = json.loads(response.output_text)
            return ChecklistRow(**response_data)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return ChecklistRow(
                description=question,
                yes_no="N/A",
                analysis=f"LLM Response: {response.output_text}"
            )
            
    except Exception as e:
        logger.error(f"Error analyzing question with LLM: {e}")
        return ChecklistRow(
            description=question,
            yes_no="N/A",
            analysis=f"Error analyzing question: {str(e)}"
        )

# ASC-606 Question Set (10-15 high-value questions as per POC plan)
ASC_606_QUESTIONS = [
    {
        "id": "contract_approved",
        "text": "Is the contract approved and are the parties committed to their obligations (ASC 606-10-25-1(a))?",
        "clause_types": ["signature", "approval", "commitment"]
    },
    {
        "id": "payment_terms_identifiable",
        "text": "Can the payment terms for the goods and services be identified (ASC 606-10-25-1(c))?",
        "clause_types": ["payment_terms", "pricing", "invoicing"]
    },
    {
        "id": "commercial_substance",
        "text": "Has the contract commercial substance (ASC 606-10-25-1(d))?",
        "clause_types": ["commercial_terms", "business_purpose"]
    },
    {
        "id": "customer_acceptance",
        "text": "Is there customer acceptance present and what is its nature?",
        "clause_types": ["acceptance", "inspection", "approval"]
    },
    {
        "id": "termination_penalties",
        "text": "Are there termination penalties or early termination payments?",
        "clause_types": ["termination", "penalties", "early_termination"]
    },
    {
        "id": "refund_credits",
        "text": "Are there refund or credit provisions for failed acceptance?",
        "clause_types": ["refund", "credit", "remedy"]
    },
    {
        "id": "variable_consideration",
        "text": "Is there variable consideration that needs to be constrained?",
        "clause_types": ["variable_pricing", "contingencies", "adjustments"]
    },
    {
        "id": "performance_obligations",
        "text": "What are the distinct performance obligations?",
        "clause_types": ["deliverables", "services", "obligations"]
    },
    {
        "id": "over_time_indicators",
        "text": "Are there indicators that revenue should be recognized over time?",
        "clause_types": ["over_time", "milestones", "progress"]
    },
    {
        "id": "contract_modifications",
        "text": "Are there contract modifications or amendments?",
        "clause_types": ["modifications", "amendments", "changes"]
    }
]

@app.get("/")
async def root():
    return {"message": "Contract→606 Intelligence API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/questions")
async def get_asc_606_questions():
    """Get the ASC-606 question set for the POC"""
    return {"questions": ASC_606_QUESTIONS}

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    project_name: Optional[str] = None,
    reuse_existing: bool = True
):
    """Upload and process a contract document with caching"""
    try:
        # Read file content
        file_content = await file.read()
        
        # Calculate file hash for deduplication
        file_hash = cache_manager.calculate_file_hash(file_content)
        
        # Check if file is already cached
        cached_file = cache_manager.is_file_cached(file_content)
        
        if cached_file and reuse_existing:
            logger.info(f"File already cached: {file.filename} (hash: {file_hash[:8]}...)")
            
            # Find existing project
            project = None
            for p in cache_manager.projects_db.values():
                if file_hash in p.file_hashes:
                    project = p
                    break
            
            if project:
                # Return cached analysis
                return {
                    "document_id": cached_file.file_id,
                    "vector_store_id": project.vector_store_id,
                    "project_id": project.project_id,
                    "file_hash": file_hash,
                    "status": "cached",
                    "message": f"File already analyzed in project: {project.project_name}",
                    "cached": True
                }
        
        # Generate unique document ID
        document_id = str(uuid.uuid4())
        
        # Initialize document analysis
        analysis = DocumentAnalysis(
            document_id=document_id,
            document_name=file.filename,
            upload_timestamp=datetime.now(),
            processing_status="processing",
            extracted_sections=[],
            clause_hits=[],
            checklist_answers=[],
            file_hash=file_hash
        )
        
        # Store in memory
        documents_db[document_id] = analysis
        
        # Upload file to OpenAI vector store
        file_id = create_file_in_vector_store(file_content, file.filename)
        
        # Create or reuse vector store
        vector_store_id = ensure_vector_store(VECTOR_STORE_ID, f"contract_analysis_{document_id}")
        
        # Add file to vector store
        add_file_to_vector_store(vector_store_id, file_id)
        
        # Cache file metadata
        cache_manager.cache_file(file_id, file.filename, file_content, vector_store_id)
        
        # Create or get project
        project_name = project_name or f"Project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project = cache_manager.get_or_create_project(project_name, [file_hash], vector_store_id)
        
        # Update analysis with project info
        analysis.processing_status = "completed"
        analysis.vector_store_id = vector_store_id
        analysis.project_id = project.project_id
        analysis.extracted_sections = [
            {"section": "Document", "page": 1, "content": f"Uploaded {file.filename} to vector store {vector_store_id}"}
        ]
        
        # Generate real LLM-based checklist answers with caching
        for question in ASC_606_QUESTIONS:
            try:
                # Check if analysis is cached
                cached_analysis = cache_manager.get_cached_analysis(question["id"], [file_hash])
                
                if cached_analysis:
                    logger.info(f"Using cached analysis for question: {question['id']}")
                    # Use cached analysis
                    answer = ChecklistAnswer(
                        question_id=question["id"],
                        question_text=question["text"],
                        suggested_answer=cached_analysis.analysis_result.get("yes_no", "N/A"),
                        confidence=cached_analysis.confidence,
                        clause_hits=[
                            ClauseHit(
                                clause_text=cached_analysis.analysis_result.get("analysis", ""),
                                page_number=1,
                                section="Cached Analysis",
                                confidence_score=cached_analysis.confidence,
                                clause_type="cached_analysis"
                            )
                        ],
                        reviewer_override=None,
                        reviewer_comment=None,
                        final_answer=None
                    )
                else:
                    # Use LLM to analyze the question
                    llm_response = analyze_question_with_llm(question["text"], vector_store_id)
                    
                    # Cache the analysis
                    analysis_result = {
                        "yes_no": llm_response.yes_no,
                        "analysis": llm_response.analysis,
                        "description": llm_response.description
                    }
                    cache_manager.cache_analysis(
                        question["id"], 
                        question["text"], 
                        [file_hash], 
                        analysis_result, 
                        0.85
                    )
                    
                    # Convert LLM response to our format
                    answer = ChecklistAnswer(
                        question_id=question["id"],
                        question_text=question["text"],
                        suggested_answer=llm_response.yes_no,
                        confidence=0.85,
                        clause_hits=[
                            ClauseHit(
                                clause_text=llm_response.analysis,
                                page_number=1,
                                section="LLM Analysis",
                                confidence_score=0.85,
                                clause_type="llm_analysis"
                            )
                        ],
                        reviewer_override=None,
                        reviewer_comment=None,
                        final_answer=None
                    )
                
                analysis.checklist_answers.append(answer)
                
                # Update project with analysis result
                cache_manager.update_project_analysis(
                    project.project_id, 
                    question["id"], 
                    {
                        "suggested_answer": answer.suggested_answer,
                        "confidence": answer.confidence,
                        "analysis": answer.clause_hits[0].clause_text if answer.clause_hits else ""
                    }
                )
                
            except Exception as e:
                logger.error(f"Error analyzing question {question['id']}: {e}")
                # Add error answer
                answer = ChecklistAnswer(
                    question_id=question["id"],
                    question_text=question["text"],
                    suggested_answer="N/A",
                    confidence=0.0,
                    clause_hits=[],
                    reviewer_override=None,
                    reviewer_comment=f"Error: {str(e)}",
                    final_answer=None
                )
                analysis.checklist_answers.append(answer)
        
        documents_db[document_id] = analysis
        
        return {
            "document_id": document_id,
            "vector_store_id": vector_store_id,
            "project_id": project.project_id,
            "file_hash": file_hash,
            "status": "uploaded",
            "message": "Document uploaded and processed successfully with LLM analysis",
            "cached": False
        }
        
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/documents/{document_id}")
async def get_document_analysis(document_id: str):
    """Get analysis results for a specific document"""
    if document_id not in documents_db:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return documents_db[document_id]

@app.get("/documents")
async def list_documents():
    """List all uploaded documents"""
    return {"documents": list(documents_db.values())}

@app.post("/documents/{document_id}/review")
async def update_reviewer_decision(
    document_id: str,
    question_id: str,
    reviewer_override: str,
    reviewer_comment: Optional[str] = None
):
    """Update reviewer decision for a specific question"""
    if document_id not in documents_db:
        raise HTTPException(status_code=404, detail="Document not found")
    
    analysis = documents_db[document_id]
    
    # Find and update the specific answer
    for answer in analysis.checklist_answers:
        if answer.question_id == question_id:
            answer.reviewer_override = reviewer_override
            answer.reviewer_comment = reviewer_comment
            answer.final_answer = reviewer_override
            break
    else:
        raise HTTPException(status_code=404, detail="Question not found")
    
    return {"status": "updated", "message": "Reviewer decision recorded"}

@app.post("/documents/{document_id}/reanalyze")
async def reanalyze_question(
    document_id: str,
    question_id: str
):
    """Re-analyze a specific question using LLM"""
    if document_id not in documents_db:
        raise HTTPException(status_code=404, detail="Document not found")
    
    analysis = documents_db[document_id]
    
    if not analysis.vector_store_id:
        raise HTTPException(status_code=400, detail="No vector store found for this document")
    
    # Find the question
    question = None
    for q in ASC_606_QUESTIONS:
        if q["id"] == question_id:
            question = q
            break
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    try:
        # Use LLM to re-analyze the question
        llm_response = analyze_question_with_llm(question["text"], analysis.vector_store_id)
        
        # Update the answer
        for answer in analysis.checklist_answers:
            if answer.question_id == question_id:
                answer.suggested_answer = llm_response.yes_no
                answer.clause_hits = [
                    ClauseHit(
                        clause_text=llm_response.analysis,
                        page_number=1,
                        section="LLM Analysis",
                        confidence_score=0.85,
                        clause_type="llm_analysis"
                    )
                ]
                break
        
        return {
            "status": "reanalyzed",
            "message": "Question re-analyzed with LLM",
            "new_answer": llm_response.yes_no,
            "analysis": llm_response.analysis
        }
        
    except Exception as e:
        logger.error(f"Error re-analyzing question: {e}")
        raise HTTPException(status_code=500, detail=f"Re-analysis failed: {str(e)}")

@app.post("/documents/{document_id}/evidence-binder")
async def generate_evidence_binder(document_id: str):
    """Generate evidence binder with highlighted clauses and citations"""
    if document_id not in documents_db:
        raise HTTPException(status_code=404, detail="Document not found")
    
    analysis = documents_db[document_id]
    
    # Generate evidence binder
    binder_id = str(uuid.uuid4())
    binder = EvidenceBinder(
        document_id=document_id,
        generated_timestamp=datetime.now(),
        highlighted_clauses=[
            {
                "question": answer.question_text,
                "answer": answer.final_answer or answer.suggested_answer,
                "clause_hits": [hit.dict() for hit in answer.clause_hits],
                "page_references": [hit.page_number for hit in answer.clause_hits]
            }
            for answer in analysis.checklist_answers
        ],
        checklist_summary=analysis.checklist_answers,
        export_formats={
            "csv": f"exports/{binder_id}_checklist.csv",
            "json": f"exports/{binder_id}_analysis.json",
            "pdf": f"exports/{binder_id}_evidence_binder.pdf"
        }
    )
    
    evidence_binders[binder_id] = binder
    
    # TODO: Implement actual file generation
    # This would create:
    # 1. CSV file for portal import
    # 2. JSON file with full analysis
    # 3. PDF evidence binder with highlighted clauses
    
    return {
        "binder_id": binder_id,
        "status": "generated",
        "export_formats": binder.export_formats
    }

@app.get("/evidence-binders/{binder_id}")
async def get_evidence_binder(binder_id: str):
    """Get evidence binder details"""
    if binder_id not in evidence_binders:
        raise HTTPException(status_code=404, detail="Evidence binder not found")
    
    return evidence_binders[binder_id]

@app.get("/download/{binder_id}/{format}")
async def download_export(binder_id: str, format: str):
    """Download exported files (CSV, JSON, PDF)"""
    if binder_id not in evidence_binders:
        raise HTTPException(status_code=404, detail="Evidence binder not found")
    
    binder = evidence_binders[binder_id]
    
    if format not in binder.export_formats:
        raise HTTPException(status_code=404, detail="Export format not found")
    
    file_path = binder.export_formats[format]
    
    # TODO: Implement actual file generation and return
    # For now, return a placeholder response
    return {"message": f"Download {format} file", "path": file_path}

@app.get("/analytics")
async def get_analytics():
    """Get analytics and metrics for the POC"""
    total_documents = len(documents_db)
    total_binders = len(evidence_binders)
    
    # Calculate average processing metrics
    avg_confidence = 0
    total_answers = 0
    
    for analysis in documents_db.values():
        for answer in analysis.checklist_answers:
            avg_confidence += answer.confidence
            total_answers += 1
    
    if total_answers > 0:
        avg_confidence /= total_answers
    
    # Get cache statistics
    cache_stats = cache_manager.get_cache_stats()
    
    return {
        "total_documents": total_documents,
        "total_evidence_binders": total_binders,
        "average_confidence": round(avg_confidence, 2),
        "total_questions_processed": total_answers,
        "cache_stats": cache_stats
    }

@app.get("/projects")
async def list_projects():
    """List all projects"""
    projects = []
    for project in cache_manager.projects_db.values():
        projects.append({
            "project_id": project.project_id,
            "project_name": project.project_name,
            "created_timestamp": project.created_timestamp.isoformat(),
            "last_updated": project.last_updated.isoformat(),
            "vector_store_id": project.vector_store_id,
            "file_count": len(project.file_hashes),
            "analysis_count": len(project.analysis_results)
        })
    return {"projects": projects}

@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get details of a specific project"""
    project = cache_manager.get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get file details
    files = cache_manager.get_files_by_hashes(project.file_hashes)
    
    return {
        "project_id": project.project_id,
        "project_name": project.project_name,
        "created_timestamp": project.created_timestamp.isoformat(),
        "last_updated": project.last_updated.isoformat(),
        "vector_store_id": project.vector_store_id,
        "files": [
            {
                "file_id": f.file_id,
                "filename": f.filename,
                "file_hash": f.file_hash,
                "file_size": f.file_size,
                "upload_timestamp": f.upload_timestamp.isoformat()
            }
            for f in files
        ],
        "analysis_results": project.analysis_results
    }

@app.post("/projects/{project_id}/add-file")
async def add_file_to_project(
    project_id: str,
    file: UploadFile = File(...)
):
    """Add a file to an existing project"""
    project = cache_manager.get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        # Read file content
        file_content = await file.read()
        file_hash = cache_manager.calculate_file_hash(file_content)
        
        # Check if file is already in project
        if file_hash in project.file_hashes:
            return {
                "status": "already_exists",
                "message": "File already exists in this project",
                "file_hash": file_hash
            }
        
        # Upload file to OpenAI
        file_id = create_file_in_vector_store(file_content, file.filename)
        
        # Add to vector store
        add_file_to_vector_store(project.vector_store_id, file_id)
        
        # Cache file metadata
        cache_manager.cache_file(file_id, file.filename, file_content, project.vector_store_id)
        
        # Add to project
        project.file_hashes.append(file_hash)
        project.last_updated = datetime.now()
        cache_manager._save_cache()
        
        return {
            "status": "added",
            "message": "File added to project successfully",
            "file_hash": file_hash,
            "project_id": project_id
        }
        
    except Exception as e:
        logger.error(f"Error adding file to project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add file: {str(e)}")

@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    return cache_manager.get_cache_stats()

@app.post("/cache/cleanup")
async def cleanup_cache(max_age_hours: int = 168):
    """Clean up expired cache entries"""
    cache_manager.cleanup_expired_cache(max_age_hours)
    return {
        "status": "cleaned",
        "message": f"Cleaned up cache entries older than {max_age_hours} hours"
    }

# ------------------------
# Markdown-based Analysis Endpoints
# ------------------------

@app.post("/projects/{project_id}/ingest")
async def ingest_project_files(
    project_id: str,
    files: List[UploadFile] = File(...)
):
    """Ingest contract files for a project using markdown approach"""
    try:
        # Ensure vector store exists
        vector_store_id = markdown_analyzer.ensure_vector_store(project_id)
        
        # Save uploaded files temporarily
        temp_files = []
        for file in files:
            content = await file.read()
            temp_path = f"temp_{file.filename}"
            with open(temp_path, "wb") as f:
                f.write(content)
            temp_files.append(temp_path)
        
        # Add files to vector store
        markdown_analyzer.add_files_to_store(vector_store_id, temp_files)
        
        # Clean up temp files
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except:
                pass
        
        return {
            "status": "ingested",
            "project_id": project_id,
            "vector_store_id": vector_store_id,
            "file_count": len(files),
            "message": f"Successfully ingested {len(files)} files"
        }
        
    except Exception as e:
        logger.error(f"Error ingesting files: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.post("/projects/{project_id}/analyze")
async def run_markdown_analysis(
    project_id: str,
    output_dir: Optional[str] = None
):
    """Run ASC 606 analysis using markdown templates"""
    try:
        if not output_dir:
            output_dir = os.path.join(OUTPUT_BASE_DIR, project_id)
        
        # Run the analysis
        results = markdown_analyzer.run_analysis(project_id, output_dir)
        
        return {
            "status": "completed",
            "project_id": project_id,
            "output_dir": output_dir,
            "results": results,
            "message": "Analysis completed successfully"
        }
        
    except Exception as e:
        logger.error(f"Error running analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

def _sse_event(event: str, data: str) -> bytes:
    """Format a Server-Sent Event (SSE) message."""
    # Ensure data is single-line chunks per SSE spec
    lines = data.splitlines() or [""]
    payload = [f"event: {event}"] + [f"data: {line}" for line in lines]
    return ("\n".join(payload) + "\n\n").encode("utf-8")

@app.get("/projects/{project_id}/analyze/stream")
def run_markdown_analysis_stream(project_id: str, output_dir: Optional[str] = None):
    """Stream ASC 606 analysis progress using Server-Sent Events (SSE)."""
    try:
        if not output_dir:
            output_dir = os.path.join(OUTPUT_BASE_DIR, project_id)

        def event_generator():
            try:
                # Ensure vector store exists
                vector_store_id = markdown_analyzer.ensure_vector_store(project_id)
                logger.info(f"Initialized vector store: {vector_store_id}")
                yield _sse_event("log", f"Initialized vector store: {vector_store_id}")

                os.makedirs(output_dir, exist_ok=True)
                logger.info(f"Output directory: {output_dir}")
                yield _sse_event("log", f"Output directory: {output_dir}")

                # Process each step with progress logs
                for step_num in range(1, 6):
                    step_name = f"step{step_num}"
                    logger.info(f"START {step_name}")
                    yield _sse_event("step", f"START {step_name}")
                    try:
                        template = markdown_analyzer.load_markdown_template(step_name)
                        logger.info(f"Loaded template for {step_name} ({len(template)} chars)")
                        yield _sse_event("log", f"Loaded template for {step_name} ({len(template)} chars)")

                        context = markdown_analyzer.build_context_for_step(step_num, output_dir)
                        if context:
                            logger.info(f"Context size for {step_name}: {len(context)} chars")
                            yield _sse_event("log", f"Context size for {step_name}: {len(context)} chars")

                        start_ts = time.time()
                        filled_content = markdown_analyzer.ask_rag_with_template(
                            vector_store_id, template, context, project_id
                        )
                        elapsed = time.time() - start_ts
                        logger.info(f"Model call for {step_name} completed in {elapsed:.2f}s")
                        yield _sse_event("log", f"Model call for {step_name} completed in {elapsed:.2f}s")

                        output_file = os.path.join(output_dir, f"{step_name}_filled.md")
                        with open(output_file, "w", encoding="utf-8") as f:
                            f.write(filled_content)
                        logger.info(f"Saved {output_file} ({len(filled_content)} chars)")
                        yield _sse_event("log", f"Saved {output_file} ({len(filled_content)} chars)")
                        logger.info(f"DONE {step_name}")
                        yield _sse_event("step", f"DONE {step_name}")
                    except Exception as step_err:
                        # Write an error file to keep sequence consistent
                        output_file = os.path.join(output_dir, f"{step_name}_filled.md")
                        try:
                            with open(output_file, "w", encoding="utf-8") as f:
                                f.write(f"# Error in {step_name}\n\nError: {str(step_err)}")
                        except Exception:
                            pass
                        logger.error(f"{step_name} error: {str(step_err)}")
                        yield _sse_event("error", f"{step_name}: {str(step_err)}")
                        # Continue to next step

                    # Gentle delay to avoid rate limiting
                    time.sleep(2)

                logger.info("Analysis completed")
                yield _sse_event("done", "Analysis completed")
            except Exception as e:
                logger.error(f"Analysis failed: {str(e)}")
                yield _sse_event("error", f"Analysis failed: {str(e)}")

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except Exception as e:
        logger.error(f"Error starting analysis stream: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start analysis stream: {str(e)}")

@app.get("/projects/{project_id}/steps")
async def get_project_steps(project_id: str, output_dir: Optional[str] = None):
    """Get all analysis steps for a project"""
    try:
        if not output_dir:
            output_dir = os.path.join(OUTPUT_BASE_DIR, project_id)
        
        steps = {}
        for step_num in range(1, 6):
            step_name = f"step{step_num}"
            content = markdown_analyzer.get_step_content(project_id, step_name, output_dir)
            if content:
                steps[step_name] = {
                    "content": content,
                    "length": len(content),
                    "exists": True
                }
            else:
                steps[step_name] = {
                    "content": None,
                    "length": 0,
                    "exists": False
                }
        
        return {
            "project_id": project_id,
            "output_dir": output_dir,
            "steps": steps
        }
        
    except Exception as e:
        logger.error(f"Error getting project steps: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get steps: {str(e)}")

@app.get("/projects/{project_id}/steps/{step}")
async def get_step_content(
    project_id: str, 
    step: str, 
    output_dir: Optional[str] = None
):
    """Get content of a specific step"""
    try:
        if not output_dir:
            output_dir = os.path.join(OUTPUT_BASE_DIR, project_id)
        
        content = markdown_analyzer.get_step_content(project_id, step, output_dir)
        if not content:
            raise HTTPException(status_code=404, detail="Step content not found")
        
        return {
            "project_id": project_id,
            "step": step,
            "content": content,
            "length": len(content)
        }
        
    except Exception as e:
        logger.error(f"Error getting step content: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get step content: {str(e)}")

@app.put("/projects/{project_id}/steps/{step}")
async def update_step_content(
    project_id: str,
    step: str,
    content: str,
    output_dir: Optional[str] = None
):
    """Update content of a specific step"""
    try:
        if not output_dir:
            output_dir = os.path.join(OUTPUT_BASE_DIR, project_id)
        
        success = markdown_analyzer.update_step_content(project_id, step, content, output_dir)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update step content")
        
        return {
            "status": "updated",
            "project_id": project_id,
            "step": step,
            "message": "Step content updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error updating step content: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update step content: {str(e)}")

@app.post("/projects/{project_id}/chat")
async def chat_with_project(
    project_id: str,
    message: str
):
    """Chat with the project's vector store"""
    try:
        response = markdown_analyzer.chat_with_vector_store(project_id, message)
        
        return {
            "project_id": project_id,
            "message": message,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in project chat: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

@app.post("/projects/{project_id}/steps/{step}/chat")
async def chat_with_step(
    project_id: str,
    step: str,
    message: str,
    output_dir: Optional[str] = None
):
    """Chat about a specific step's content"""
    try:
        if not output_dir:
            output_dir = os.path.join(OUTPUT_BASE_DIR, project_id)
        
        response = markdown_analyzer.chat_with_step(project_id, step, message, output_dir)
        
        return {
            "project_id": project_id,
            "step": step,
            "message": message,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in step chat: {e}")
        raise HTTPException(status_code=500, detail=f"Step chat failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
