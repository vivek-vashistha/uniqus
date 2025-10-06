import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import { 
  CheckCircle, 
  XCircle, 
  AlertCircle, 
  FileText, 
  Download,
  Eye,
  Edit3,
  Save,
  RefreshCw
} from 'lucide-react';
import axios from 'axios';

const DocumentReview = () => {
  const { documentId } = useParams();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editingQuestion, setEditingQuestion] = useState(null);
  const [reviewerOverrides, setReviewerOverrides] = useState({});
  const [reviewerComments, setReviewerComments] = useState({});

  useEffect(() => {
    fetchAnalysis();
  }, [documentId]);

  const fetchAnalysis = async () => {
    try {
      const response = await axios.get(`http://localhost:8000/documents/${documentId}`);
      setAnalysis(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching analysis:', error);
      toast.error('Failed to load document analysis');
      setLoading(false);
    }
  };

  const handleReviewerOverride = async (questionId, override, comment = '') => {
    try {
      await axios.post(`http://localhost:8000/documents/${documentId}/review`, {
        question_id: questionId,
        reviewer_override: override,
        reviewer_comment: comment
      });

      setReviewerOverrides(prev => ({ ...prev, [questionId]: override }));
      setReviewerComments(prev => ({ ...prev, [questionId]: comment }));
      setEditingQuestion(null);
      
      toast.success('Reviewer decision saved');
    } catch (error) {
      console.error('Error saving reviewer decision:', error);
      toast.error('Failed to save reviewer decision');
    }
  };

  const handleReanalyze = async (questionId) => {
    try {
      const response = await axios.post(`http://localhost:8000/documents/${documentId}/reanalyze`, {
        question_id: questionId
      });
      
      toast.success('Question re-analyzed with LLM');
      // Refresh the analysis
      fetchAnalysis();
    } catch (error) {
      console.error('Error re-analyzing question:', error);
      toast.error('Failed to re-analyze question');
    }
  };

  const generateEvidenceBinder = async () => {
    try {
      const response = await axios.post(`http://localhost:8000/documents/${documentId}/evidence-binder`);
      toast.success('Evidence binder generated successfully');
      navigate(`/evidence/${response.data.binder_id}`);
    } catch (error) {
      console.error('Error generating evidence binder:', error);
      toast.error('Failed to generate evidence binder');
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

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return 'text-green-600';
    if (confidence >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-gray-600">Loading analysis...</span>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="text-center py-8">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">Analysis Not Found</h2>
        <p className="text-gray-600">The document analysis could not be loaded.</p>
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
              Document Review: {analysis.document_name}
            </h2>
            <p className="text-gray-600">
              Review AI-suggested answers and provide your expert judgment
            </p>
          </div>
          <div className="flex space-x-3">
            <button
              onClick={generateEvidenceBinder}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              <Download className="h-4 w-4" />
              <span>Generate Evidence Binder</span>
            </button>
          </div>
        </div>
      </div>

      {/* Document Sections */}
      <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Document Sections</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {analysis.extracted_sections?.map((section, index) => (
            <div key={index} className="p-4 bg-gray-50 rounded-lg">
              <h4 className="font-medium text-gray-900 mb-2">{section.section}</h4>
              <p className="text-sm text-gray-600">Page {section.page}</p>
              <p className="text-xs text-gray-500 mt-2 line-clamp-3">
                {section.content?.substring(0, 100)}...
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* ASC-606 Checklist */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-6">ASC-606 Compliance Checklist</h3>
        
        <div className="space-y-6">
          {analysis.checklist_answers?.map((answer, index) => (
            <div key={answer.question_id} className="border border-gray-200 rounded-lg p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <h4 className="font-medium text-gray-900 mb-2">
                    {answer.question_text}
                  </h4>
                  
                  <div className="flex items-center space-x-4 mb-3">
                    <div className="flex items-center space-x-2">
                      {getAnswerIcon(answer.suggested_answer)}
                      <span className="font-medium text-gray-900">
                        Suggested: {answer.suggested_answer}
                      </span>
                    </div>
                    
                    <div className={`text-sm font-medium ${getConfidenceColor(answer.confidence)}`}>
                      Confidence: {Math.round(answer.confidence * 100)}%
                    </div>
                  </div>
                </div>
                
                <div className="flex space-x-2">
                  <button
                    onClick={() => handleReanalyze(answer.question_id)}
                    className="flex items-center space-x-1 px-3 py-1 text-green-600 hover:text-green-800"
                  >
                    <RefreshCw className="h-4 w-4" />
                    <span>Re-analyze</span>
                  </button>
                  
                  <button
                    onClick={() => setEditingQuestion(editingQuestion === answer.question_id ? null : answer.question_id)}
                    className="flex items-center space-x-1 px-3 py-1 text-blue-600 hover:text-blue-800"
                  >
                    <Edit3 className="h-4 w-4" />
                    <span>Edit</span>
                  </button>
                </div>
              </div>

              {/* Clause Hits */}
              {answer.clause_hits && answer.clause_hits.length > 0 && (
                <div className="mb-4">
                  <h5 className="text-sm font-medium text-gray-700 mb-2">Supporting Evidence:</h5>
                  <div className="space-y-2">
                    {answer.clause_hits.map((hit, hitIndex) => (
                      <div key={hitIndex} className="p-3 bg-blue-50 border border-blue-200 rounded">
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

              {/* Reviewer Override */}
              {editingQuestion === answer.question_id && (
                <div className="border-t pt-4">
                  <h5 className="text-sm font-medium text-gray-700 mb-3">Reviewer Override:</h5>
                  
                  <div className="space-y-3">
                    <div className="flex space-x-3">
                      <button
                        onClick={() => handleReviewerOverride(answer.question_id, 'Yes')}
                        className={`flex items-center space-x-2 px-4 py-2 rounded-md border ${
                          reviewerOverrides[answer.question_id] === 'Yes'
                            ? 'bg-green-50 border-green-300 text-green-700'
                            : 'border-gray-300 hover:border-green-300'
                        }`}
                      >
                        <CheckCircle className="h-4 w-4" />
                        <span>Yes</span>
                      </button>
                      
                      <button
                        onClick={() => handleReviewerOverride(answer.question_id, 'No')}
                        className={`flex items-center space-x-2 px-4 py-2 rounded-md border ${
                          reviewerOverrides[answer.question_id] === 'No'
                            ? 'bg-red-50 border-red-300 text-red-700'
                            : 'border-gray-300 hover:border-red-300'
                        }`}
                      >
                        <XCircle className="h-4 w-4" />
                        <span>No</span>
                      </button>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Reviewer Comment:
                      </label>
                      <textarea
                        value={reviewerComments[answer.question_id] || ''}
                        onChange={(e) => setReviewerComments(prev => ({
                          ...prev,
                          [answer.question_id]: e.target.value
                        }))}
                        className="w-full p-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        rows={3}
                        placeholder="Add your reasoning for this decision..."
                      />
                    </div>
                    
                    <div className="flex space-x-2">
                      <button
                        onClick={() => handleReviewerOverride(
                          answer.question_id, 
                          reviewerOverrides[answer.question_id] || answer.suggested_answer,
                          reviewerComments[answer.question_id] || ''
                        )}
                        className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                      >
                        <Save className="h-4 w-4" />
                        <span>Save Decision</span>
                      </button>
                      
                      <button
                        onClick={() => setEditingQuestion(null)}
                        className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Final Answer Display */}
              {reviewerOverrides[answer.question_id] && (
                <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded">
                  <div className="flex items-center space-x-2">
                    <CheckCircle className="h-4 w-4 text-green-600" />
                    <span className="text-sm font-medium text-green-800">
                      Final Answer: {reviewerOverrides[answer.question_id]}
                    </span>
                  </div>
                  {reviewerComments[answer.question_id] && (
                    <p className="text-sm text-green-700 mt-1">
                      Comment: {reviewerComments[answer.question_id]}
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default DocumentReview;
