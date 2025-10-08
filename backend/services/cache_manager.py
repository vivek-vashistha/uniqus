"""
Cache Manager for Contract→606 Intelligence
Handles file deduplication, vector store management, and analysis caching
"""

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class FileMetadata:
    """Metadata for uploaded files"""
    file_id: str
    filename: str
    file_hash: str
    file_size: int
    upload_timestamp: datetime
    vector_store_id: Optional[str] = None

@dataclass
class Project:
    """Project grouping related contract files"""
    project_id: str
    project_name: str
    created_timestamp: datetime
    vector_store_id: str
    file_hashes: List[str]
    analysis_results: Dict[str, Any]  # question_id -> analysis
    last_updated: datetime

@dataclass
class CachedAnalysis:
    """Cached analysis result"""
    question_id: str
    question_text: str
    analysis_result: Dict[str, Any]
    confidence: float
    created_timestamp: datetime
    file_hashes: List[str]  # Files used for this analysis

class CacheManager:
    """Manages file deduplication, vector stores, and analysis caching"""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        self.files_db: Dict[str, FileMetadata] = {}  # file_hash -> FileMetadata
        self.projects_db: Dict[str, Project] = {}  # project_id -> Project
        self.analysis_cache: Dict[str, CachedAnalysis] = {}  # cache_key -> CachedAnalysis
        
        # Create cache directory
        os.makedirs(cache_dir, exist_ok=True)
        os.makedirs(f"{cache_dir}/files", exist_ok=True)
        os.makedirs(f"{cache_dir}/projects", exist_ok=True)
        os.makedirs(f"{cache_dir}/analyses", exist_ok=True)
        
        # Load existing data
        self._load_cache()
    
    def _load_cache(self):
        """Load cached data from disk"""
        try:
            # Load files cache
            files_cache_path = f"{self.cache_dir}/files.json"
            if os.path.exists(files_cache_path):
                with open(files_cache_path, 'r') as f:
                    files_data = json.load(f)
                    for file_hash, file_data in files_data.items():
                        file_data['upload_timestamp'] = datetime.fromisoformat(file_data['upload_timestamp'])
                        if file_data.get('last_updated'):
                            file_data['last_updated'] = datetime.fromisoformat(file_data['last_updated'])
                        self.files_db[file_hash] = FileMetadata(**file_data)
            
            # Load projects cache
            projects_cache_path = f"{self.cache_dir}/projects.json"
            if os.path.exists(projects_cache_path):
                with open(projects_cache_path, 'r') as f:
                    projects_data = json.load(f)
                    for project_key, project_data in projects_data.items():
                        project_data['created_timestamp'] = datetime.fromisoformat(project_data['created_timestamp'])
                        project_data['last_updated'] = datetime.fromisoformat(project_data['last_updated'])
                        # Use the project_id as the key, not the generated key
                        self.projects_db[project_data['project_id']] = Project(**project_data)
            
            # Load analysis cache
            analyses_cache_path = f"{self.cache_dir}/analyses.json"
            if os.path.exists(analyses_cache_path):
                with open(analyses_cache_path, 'r') as f:
                    analyses_data = json.load(f)
                    for cache_key, analysis_data in analyses_data.items():
                        analysis_data['created_timestamp'] = datetime.fromisoformat(analysis_data['created_timestamp'])
                        self.analysis_cache[cache_key] = CachedAnalysis(**analysis_data)
            
            logger.info(f"Loaded cache: {len(self.files_db)} files, {len(self.projects_db)} projects, {len(self.analysis_cache)} analyses")
            
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
    
    def _save_cache(self):
        """Save cached data to disk"""
        try:
            # Save files cache
            files_data = {}
            for file_hash, file_metadata in self.files_db.items():
                file_data = asdict(file_metadata)
                file_data['upload_timestamp'] = file_metadata.upload_timestamp.isoformat()
                files_data[file_hash] = file_data
            
            with open(f"{self.cache_dir}/files.json", 'w') as f:
                json.dump(files_data, f, indent=2)
            
            # Save projects cache
            projects_data = {}
            for project_id, project in self.projects_db.items():
                project_data = asdict(project)
                project_data['created_timestamp'] = project.created_timestamp.isoformat()
                project_data['last_updated'] = project.last_updated.isoformat()
                projects_data[project_id] = project_data
            
            with open(f"{self.cache_dir}/projects.json", 'w') as f:
                json.dump(projects_data, f, indent=2)
            
            # Save analysis cache
            analyses_data = {}
            for cache_key, analysis in self.analysis_cache.items():
                analysis_data = asdict(analysis)
                analysis_data['created_timestamp'] = analysis.created_timestamp.isoformat()
                analyses_data[cache_key] = analysis_data
            
            with open(f"{self.cache_dir}/analyses.json", 'w') as f:
                json.dump(analyses_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    def calculate_file_hash(self, file_content: bytes) -> str:
        """Calculate SHA-256 hash of file content"""
        return hashlib.sha256(file_content).hexdigest()
    
    def is_file_cached(self, file_content: bytes) -> Optional[FileMetadata]:
        """Check if file is already cached"""
        file_hash = self.calculate_file_hash(file_content)
        return self.files_db.get(file_hash)
    
    def cache_file(self, file_id: str, filename: str, file_content: bytes, vector_store_id: str = None) -> FileMetadata:
        """Cache file metadata"""
        file_hash = self.calculate_file_hash(file_content)
        
        file_metadata = FileMetadata(
            file_id=file_id,
            filename=filename,
            file_hash=file_hash,
            file_size=len(file_content),
            upload_timestamp=datetime.now(),
            vector_store_id=vector_store_id
        )
        
        self.files_db[file_hash] = file_metadata
        self._save_cache()
        
        logger.info(f"Cached file: {filename} (hash: {file_hash[:8]}...)")
        return file_metadata
    
    def create_project(self, project_name: str, file_hashes: List[str], vector_store_id: str) -> Project:
        """Create a new project"""
        project_id = f"project_{hash(project_name + str(datetime.now()))}"
        
        project = Project(
            project_id=project_id,
            project_name=project_name,
            created_timestamp=datetime.now(),
            vector_store_id=vector_store_id,
            file_hashes=file_hashes,
            analysis_results={},
            last_updated=datetime.now()
        )
        
        self.projects_db[project_id] = project
        self._save_cache()
        
        logger.info(f"Created project: {project_name} (ID: {project_id})")
        return project
    
    def get_or_create_project(self, project_name: str, file_hashes: List[str], vector_store_id: str) -> Project:
        """Get existing project or create new one"""
        # Check if project with same name exists
        for project in self.projects_db.values():
            if project.project_name == project_name:
                logger.info(f"Reusing existing project: {project.project_id}")
                # Add new files to existing project
                for file_hash in file_hashes:
                    if file_hash not in project.file_hashes:
                        project.file_hashes.append(file_hash)
                project.last_updated = datetime.now()
                self._save_cache()
                return project
        
        # Create new project
        return self.create_project(project_name, file_hashes, vector_store_id)
    
    def get_analysis_cache_key(self, question_id: str, file_hashes: List[str]) -> str:
        """Generate cache key for analysis"""
        sorted_hashes = sorted(file_hashes)
        return f"{question_id}_{hash(tuple(sorted_hashes))}"
    
    def get_cached_analysis(self, question_id: str, file_hashes: List[str]) -> Optional[CachedAnalysis]:
        """Get cached analysis if available"""
        cache_key = self.get_analysis_cache_key(question_id, file_hashes)
        cached = self.analysis_cache.get(cache_key)
        
        if cached:
            # Check if cache is still valid (not older than 24 hours)
            if datetime.now() - cached.created_timestamp < timedelta(hours=24):
                logger.info(f"Using cached analysis for question: {question_id}")
                return cached
            else:
                # Remove expired cache
                del self.analysis_cache[cache_key]
                self._save_cache()
        
        return None
    
    def cache_analysis(self, question_id: str, question_text: str, file_hashes: List[str], 
                      analysis_result: Dict[str, Any], confidence: float) -> CachedAnalysis:
        """Cache analysis result"""
        cache_key = self.get_analysis_cache_key(question_id, file_hashes)
        
        cached_analysis = CachedAnalysis(
            question_id=question_id,
            question_text=question_text,
            analysis_result=analysis_result,
            confidence=confidence,
            created_timestamp=datetime.now(),
            file_hashes=file_hashes
        )
        
        self.analysis_cache[cache_key] = cached_analysis
        self._save_cache()
        
        logger.info(f"Cached analysis for question: {question_id}")
        return cached_analysis
    
    def get_project_by_id(self, project_id: str) -> Optional[Project]:
        """Get project by ID"""
        return self.projects_db.get(project_id)
    
    def get_project_by_name(self, project_name: str) -> Optional[Project]:
        """Get project by name"""
        for project in self.projects_db.values():
            if project.project_name == project_name:
                return project
        return None
    
    def update_project_analysis(self, project_id: str, question_id: str, analysis_result: Dict[str, Any]):
        """Update project with new analysis result"""
        project = self.projects_db.get(project_id)
        if project:
            project.analysis_results[question_id] = analysis_result
            project.last_updated = datetime.now()
            self._save_cache()
    
    def get_files_by_hashes(self, file_hashes: List[str]) -> List[FileMetadata]:
        """Get file metadata by hashes"""
        return [self.files_db[file_hash] for file_hash in file_hashes if file_hash in self.files_db]
    
    def cleanup_expired_cache(self, max_age_hours: int = 168):  # 7 days default
        """Clean up expired cache entries"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        # Clean up expired analyses
        expired_keys = []
        for cache_key, analysis in self.analysis_cache.items():
            if analysis.created_timestamp < cutoff_time:
                expired_keys.append(cache_key)
        
        for key in expired_keys:
            del self.analysis_cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
            self._save_cache()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "total_files": len(self.files_db),
            "total_projects": len(self.projects_db),
            "total_analyses": len(self.analysis_cache),
            "cache_size_mb": self._get_cache_size_mb()
        }
    
    def _get_cache_size_mb(self) -> float:
        """Calculate cache directory size in MB"""
        total_size = 0
        for root, dirs, files in os.walk(self.cache_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
        return total_size / (1024 * 1024)  # Convert to MB
