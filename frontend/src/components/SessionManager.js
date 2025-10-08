import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import { 
  FolderOpen, 
  FileText, 
  Clock, 
  Database,
  Trash2,
  RefreshCw
} from 'lucide-react';
import axios from 'axios';

const ProjectManager = () => {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedProject, setSelectedProject] = useState(null);
  const [cacheStats, setCacheStats] = useState(null);

  useEffect(() => {
    fetchProjects();
    fetchCacheStats();
  }, []);

  const fetchProjects = async () => {
    try {
      const response = await axios.get('http://localhost:8000/projects');
      setProjects(response.data.projects);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching projects:', error);
      toast.error('Failed to load projects');
      setLoading(false);
    }
  };

  const fetchCacheStats = async () => {
    try {
      const response = await axios.get('http://localhost:8000/cache/stats');
      setCacheStats(response.data);
    } catch (error) {
      console.error('Error fetching cache stats:', error);
    }
  };

  const fetchProjectDetails = async (projectId) => {
    try {
      const response = await axios.get(`http://localhost:8000/projects/${projectId}`);
      setSelectedProject(response.data);
    } catch (error) {
      console.error('Error fetching project details:', error);
      toast.error('Failed to load project details');
    }
  };

  const cleanupCache = async () => {
    try {
      await axios.post('http://localhost:8000/cache/cleanup');
      toast.success('Cache cleaned up successfully');
      fetchCacheStats();
    } catch (error) {
      console.error('Error cleaning cache:', error);
      toast.error('Failed to clean cache');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-gray-600">Loading projects...</span>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Projects</h2>
            <p className="text-gray-600">Manage your contract analysis projects and cache</p>
          </div>
          
          <div className="flex space-x-3">
            <button
              onClick={cleanupCache}
              className="flex items-center space-x-2 px-4 py-2 bg-yellow-600 text-white rounded-md hover:bg-yellow-700"
            >
              <Trash2 className="h-4 w-4" />
              <span>Clean Cache</span>
            </button>
            
            <button
              onClick={() => { fetchProjects(); fetchCacheStats(); }}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              <RefreshCw className="h-4 w-4" />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </div>

      {/* Cache Statistics */}
      {cacheStats && (
        <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Cache Statistics</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <Database className="h-8 w-8 text-blue-600 mx-auto mb-2" />
              <p className="text-2xl font-bold text-blue-900">{cacheStats.total_files}</p>
              <p className="text-sm text-blue-700">Cached Files</p>
            </div>
            
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <FolderOpen className="h-8 w-8 text-green-600 mx-auto mb-2" />
              <p className="text-2xl font-bold text-green-900">{cacheStats.total_projects}</p>
              <p className="text-sm text-green-700">Projects</p>
            </div>
            
            <div className="text-center p-4 bg-purple-50 rounded-lg">
              <FileText className="h-8 w-8 text-purple-600 mx-auto mb-2" />
              <p className="text-2xl font-bold text-purple-900">{cacheStats.total_analyses}</p>
              <p className="text-sm text-purple-700">Cached Analyses</p>
            </div>
            
            <div className="text-center p-4 bg-yellow-50 rounded-lg">
              <Clock className="h-8 w-8 text-yellow-600 mx-auto mb-2" />
              <p className="text-2xl font-bold text-yellow-900">{cacheStats.cache_size_mb.toFixed(1)}MB</p>
              <p className="text-sm text-yellow-700">Cache Size</p>
            </div>
          </div>
        </div>
      )}

      {/* Sessions List */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Projects</h3>
        
        {projects.length === 0 ? (
          <div className="text-center py-8">
            <FolderOpen className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">No projects found</p>
            <p className="text-sm text-gray-500">Upload documents to create your first project</p>
          </div>
        ) : (
          <div className="space-y-4">
            {projects.map((project) => (
              <div
                key={project.project_id}
                className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 cursor-pointer"
                onClick={() => fetchProjectDetails(project.project_id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <h4 className="font-medium text-gray-900">{project.project_name}</h4>
                    <p className="text-sm text-gray-600">
                      Created: {new Date(project.created_timestamp).toLocaleString()}
                    </p>
                    <p className="text-sm text-gray-500">
                      {project.file_count} files • {project.analysis_count} analyses
                    </p>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <span className="text-xs text-gray-500">
                      {project.vector_store_id}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        fetchProjectDetails(project.project_id);
                      }}
                      className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                    >
                      View Details
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Project Details Modal */}
      {selectedProject && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-semibold text-gray-900">
                  Project Details: {selectedProject.project_name}
                </h3>
                <button
                  onClick={() => setSelectedProject(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>
              
              <div className="space-y-6">
                {/* Project Info */}
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">Project Information</h4>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-600">Project ID:</span>
                      <p className="font-mono text-xs">{selectedProject.project_id}</p>
                    </div>
                    <div>
                      <span className="text-gray-600">Vector Store ID:</span>
                      <p className="font-mono text-xs">{selectedProject.vector_store_id}</p>
                    </div>
                    <div>
                      <span className="text-gray-600">Created:</span>
                      <p>{new Date(selectedProject.created_timestamp).toLocaleString()}</p>
                    </div>
                    <div>
                      <span className="text-gray-600">Last Updated:</span>
                      <p>{new Date(selectedProject.last_updated).toLocaleString()}</p>
                    </div>
                  </div>
                </div>
                
                {/* Files */}
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">Files ({selectedProject.files.length})</h4>
                  <div className="space-y-2">
                    {selectedProject.files.map((file, index) => (
                      <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                        <div>
                          <p className="font-medium text-gray-900">{file.filename}</p>
                          <p className="text-sm text-gray-500">
                            {file.file_size} bytes • {file.file_hash.substring(0, 8)}...
                          </p>
                        </div>
                        <span className="text-xs text-gray-500">
                          {new Date(file.upload_timestamp).toLocaleDateString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* Analysis Results */}
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">Analysis Results</h4>
                  <div className="space-y-2">
                    {Object.entries(selectedProject.analysis_results).map(([questionId, result]) => (
                      <div key={questionId} className="p-3 bg-blue-50 rounded">
                        <p className="font-medium text-blue-900">{questionId}</p>
                        <p className="text-sm text-blue-700">
                          Answer: {result.suggested_answer} (Confidence: {Math.round(result.confidence * 100)}%)
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectManager;
