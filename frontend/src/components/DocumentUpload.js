import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import { Upload, FileText, CheckCircle, AlertCircle } from 'lucide-react';
import axios from 'axios';

const DocumentUpload = () => {
  const [uploading, setUploading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [projectName, setProjectName] = useState('');
  const navigate = useNavigate();

  const onDrop = useCallback(async (acceptedFiles) => {
    setUploading(true);
    
    try {
      // Create project ID from project name or generate one
      const projectId = projectName 
        ? projectName.toLowerCase().replace(/[^a-z0-9]/g, '_')
        : `project_${Date.now()}`;
      
      // Upload files to the new markdown analyzer endpoint
      const formData = new FormData();
      Array.from(acceptedFiles).forEach(file => {
        formData.append('files', file);
      });
      
      const response = await axios.post(
        `http://localhost:8000/projects/${projectId}/ingest`,
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      );
      
      const fileInfo = {
        id: projectId,
        name: `${acceptedFiles.length} files`,
        status: 'uploaded',
        timestamp: new Date().toISOString(),
        projectId: projectId,
        fileCount: acceptedFiles.length
      };
      
      setUploadedFiles(prev => [...prev, fileInfo]);
      toast.success(`Successfully uploaded ${acceptedFiles.length} files to project: ${projectName || projectId}`);
      
      // Navigate to markdown analyzer
      navigate('/markdown-analyzer');
      
    } catch (error) {
      console.error('Upload error:', error);
      toast.error(`Failed to upload files: ${error.response?.data?.detail || error.message}`);
    }
    
    setUploading(false);
  }, [navigate, projectName]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
      'text/plain': ['.txt']
    },
    multiple: true
  });

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-white rounded-lg shadow-sm border p-8">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Upload Contract Documents
          </h2>
          <p className="text-gray-600">
            Upload your MSA, Work Orders, and other contract documents for ASC-606 analysis
          </p>
        </div>

        {/* Project Name Input */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Project/Contract Name (Optional)
          </label>
          <input
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="Enter a name for this project or contract..."
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
          <p className="text-xs text-gray-500 mt-1">
            Group related contract documents together. Files with the same content will be automatically cached.
          </p>
        </div>

        {/* Upload Area */}
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-blue-400 bg-blue-50'
              : 'border-gray-300 hover:border-gray-400'
          } ${uploading ? 'opacity-50 pointer-events-none' : ''}`}
        >
          <input {...getInputProps()} />
          
          <div className="flex flex-col items-center space-y-4">
            <Upload className="h-12 w-12 text-gray-400" />
            
            {isDragActive ? (
              <p className="text-lg text-blue-600">Drop the files here...</p>
            ) : (
              <div>
                <p className="text-lg text-gray-600 mb-2">
                  Drag & drop files here, or click to select
                </p>
                <p className="text-sm text-gray-500">
                  Supports PDF, Word documents, and text files
                </p>
              </div>
            )}
            
            {uploading && (
              <div className="flex items-center space-x-2 text-blue-600">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                <span>Processing...</span>
              </div>
            )}
          </div>
        </div>

        {/* Recent Uploads */}
        {uploadedFiles.length > 0 && (
          <div className="mt-8">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Uploads</h3>
            <div className="space-y-3">
              {uploadedFiles.map((file) => (
                <div
                  key={file.id}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center space-x-3">
                    <FileText className="h-5 w-5 text-gray-400" />
                    <div>
                      <p className="font-medium text-gray-900">{file.name}</p>
                      <p className="text-sm text-gray-500">
                        Uploaded {new Date(file.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    {file.status === 'uploaded' ? (
                      <CheckCircle className="h-5 w-5 text-green-500" />
                    ) : file.status === 'cached' ? (
                      <FileText className="h-5 w-5 text-blue-500" />
                    ) : (
                      <AlertCircle className="h-5 w-5 text-red-500" />
                    )}
                    <span className="text-sm text-gray-500">
                      {file.status === 'cached' ? 'Cached' : file.status === 'uploaded' ? 'New' : 'Error'}
                    </span>
                    <button
                      onClick={() => navigate('/markdown-analyzer')}
                      className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                    >
                      Analyze
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* POC Information */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-blue-900 mb-2">
            POC Information
          </h3>
          <p className="text-blue-800 text-sm mb-4">
            This system analyzes contracts for ASC-606 compliance using AI-powered clause detection.
            The system will automatically identify relevant clauses and suggest answers to compliance questions.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <h4 className="font-medium text-blue-900 mb-2">Supported Document Types:</h4>
              <ul className="text-blue-800 space-y-1">
                <li>• Master Service Agreements (MSA)</li>
                <li>• Work Orders and SOWs</li>
                <li>• Contract Amendments</li>
                <li>• PDF and Word documents</li>
              </ul>
            </div>
            <div>
              <h4 className="font-medium text-blue-900 mb-2">Analysis Features:</h4>
              <ul className="text-blue-800 space-y-1">
                <li>• Clause detection and mapping</li>
                <li>• ASC-606 question auto-answering</li>
                <li>• Evidence binder generation</li>
                <li>• Export for portal integration</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocumentUpload;
