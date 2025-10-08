import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { toast } from 'react-toastify';
import { 
  Download, 
  CheckCircle, 
  XCircle, 
  AlertCircle
} from 'lucide-react';
import axios from 'axios';

const EvidenceBinder = () => {
  const { binderId } = useParams();
  const [binder, setBinder] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBinder();
  }, [fetchBinder]);

  const fetchBinder = useCallback(async () => {
    try {
      const response = await axios.get(`http://localhost:8000/evidence-binders/${binderId}`);
      setBinder(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching evidence binder:', error);
      toast.error('Failed to load evidence binder');
      setLoading(false);
    }
  }, [binderId]);

  const downloadFile = async (format) => {
    try {
      const response = await axios.get(`http://localhost:8000/download/${binderId}/${format}`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `evidence_binder.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success(`${format.toUpperCase()} file downloaded`);
    } catch (error) {
      console.error('Error downloading file:', error);
      toast.error(`Failed to download ${format.toUpperCase()} file`);
    }
  };

  const getAnswerIcon = (answer) => {
    switch (answer) {
      case 'Yes':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'No':
        return <XCircle className="h-5 w-5 text-red-500" />;
      default:
        return <AlertCircle className="h-5 w-5 text-yellow-500" />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-gray-600">Loading evidence binder...</span>
      </div>
    );
  }

  if (!binder) {
    return (
      <div className="text-center py-8">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Evidence Binder Not Found</h2>
        <p className="text-gray-600">The evidence binder could not be loaded.</p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Evidence Binder
            </h2>
            <p className="text-gray-600">
              Generated on {new Date(binder.generated_timestamp).toLocaleString()}
            </p>
          </div>
          
          <div className="flex space-x-3">
            <button
              onClick={() => downloadFile('csv')}
              className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
            >
              <Download className="h-4 w-4" />
              <span>Download CSV</span>
            </button>
            
            <button
              onClick={() => downloadFile('json')}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              <Download className="h-4 w-4" />
              <span>Download JSON</span>
            </button>
            
            <button
              onClick={() => downloadFile('pdf')}
              className="flex items-center space-x-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
            >
              <Download className="h-4 w-4" />
              <span>Download PDF</span>
            </button>
          </div>
        </div>
      </div>

      {/* Export Information */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-6">
        <h3 className="text-lg font-semibold text-blue-900 mb-4">Export Information</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white p-4 rounded-lg border border-blue-200">
            <h4 className="font-medium text-blue-900 mb-2">CSV Export</h4>
            <p className="text-sm text-blue-800 mb-3">
              Ready for portal import with all checklist answers and metadata
            </p>
            <button
              onClick={() => downloadFile('csv')}
              className="flex items-center space-x-2 text-blue-600 hover:text-blue-800"
            >
              <Download className="h-4 w-4" />
              <span>Download</span>
            </button>
          </div>
          
          <div className="bg-white p-4 rounded-lg border border-blue-200">
            <h4 className="font-medium text-blue-900 mb-2">JSON Export</h4>
            <p className="text-sm text-blue-800 mb-3">
              Complete analysis data with clause hits and confidence scores
            </p>
            <button
              onClick={() => downloadFile('json')}
              className="flex items-center space-x-2 text-blue-600 hover:text-blue-800"
            >
              <Download className="h-4 w-4" />
              <span>Download</span>
            </button>
          </div>
          
          <div className="bg-white p-4 rounded-lg border border-blue-200">
            <h4 className="font-medium text-blue-900 mb-2">PDF Evidence Binder</h4>
            <p className="text-sm text-blue-800 mb-3">
              Auditable evidence binder with highlighted clauses and citations
            </p>
            <button
              onClick={() => downloadFile('pdf')}
              className="flex items-center space-x-2 text-blue-600 hover:text-blue-800"
            >
              <Download className="h-4 w-4" />
              <span>Download</span>
            </button>
          </div>
        </div>
      </div>

      {/* Checklist Summary */}
      <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Checklist Summary</h3>
        
        <div className="space-y-4">
          {binder.checklist_summary?.map((answer, index) => (
            <div key={index} className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <h4 className="font-medium text-gray-900 mb-2">
                    {answer.question_text}
                  </h4>
                  
                  <div className="flex items-center space-x-3">
                    {getAnswerIcon(answer.suggested_answer)}
                    <span className="font-medium text-gray-900">
                      Answer: {answer.suggested_answer}
                    </span>
                    <span className="text-sm text-gray-500">
                      Confidence: {Math.round(answer.confidence * 100)}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Supporting Evidence */}
              {answer.clause_hits && answer.clause_hits.length > 0 && (
                <div className="mt-3">
                  <h5 className="text-sm font-medium text-gray-700 mb-2">Supporting Evidence:</h5>
                  <div className="space-y-2">
                    {answer.clause_hits.map((hit, hitIndex) => (
                      <div key={hitIndex} className="p-3 bg-gray-50 border border-gray-200 rounded">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <p className="text-sm text-gray-900 mb-1">
                              <strong>Page {hit.page_number}</strong> - {hit.section}
                            </p>
                            <p className="text-sm text-gray-700 italic">
                              "{hit.clause_text}"
                            </p>
                          </div>
                          <div className="text-xs text-gray-500 ml-2">
                            {Math.round(hit.confidence_score * 100)}%
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Highlighted Clauses */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Highlighted Clauses</h3>
        
        <div className="space-y-4">
          {binder.highlighted_clauses?.map((clause, index) => (
            <div key={index} className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <h4 className="font-medium text-gray-900 mb-2">
                    {clause.question}
                  </h4>
                  
                  <div className="flex items-center space-x-3">
                    {getAnswerIcon(clause.answer)}
                    <span className="font-medium text-gray-900">
                      Answer: {clause.answer}
                    </span>
                  </div>
                </div>
              </div>

              {/* Clause Hits */}
              {clause.clause_hits && clause.clause_hits.length > 0 && (
                <div className="mt-3">
                  <h5 className="text-sm font-medium text-gray-700 mb-2">Relevant Clauses:</h5>
                  <div className="space-y-2">
                    {clause.clause_hits.map((hit, hitIndex) => (
                      <div key={hitIndex} className="p-3 bg-yellow-50 border border-yellow-200 rounded">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <p className="text-sm text-gray-900 mb-1">
                              <strong>Page {hit.page_number}</strong> - {hit.section}
                            </p>
                            <p className="text-sm text-gray-700 italic">
                              "{hit.clause_text}"
                            </p>
                          </div>
                          <div className="text-xs text-gray-500 ml-2">
                            {Math.round(hit.confidence_score * 100)}%
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Page References */}
              {clause.page_references && clause.page_references.length > 0 && (
                <div className="mt-3">
                  <h5 className="text-sm font-medium text-gray-700 mb-2">Page References:</h5>
                  <div className="flex flex-wrap gap-2">
                    {clause.page_references.map((page, pageIndex) => (
                      <span
                        key={pageIndex}
                        className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded"
                      >
                        Page {page}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default EvidenceBinder;
