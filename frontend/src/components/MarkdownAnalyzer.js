import React, { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'react-toastify';
import { 
  Play, 
  FileText, 
  Edit3, 
  Save, 
  MessageCircle,
  CheckCircle,
  AlertCircle,
  Loader,
  X,
  LucideSendHorizonal
} from 'lucide-react';
import axios from 'axios';

import { marked } from 'marked';
import ReactMarkdown from 'react-markdown';

// Get API base URL from environment variables
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

// Configure marked for GitHub Flavored Markdown
marked.setOptions({
  gfm: true,
  breaks: true,
  tables: true
});
// Note: For GFM (tables, task lists), consider installing `remark-gfm`
// and passing it to ReactMarkdown. Keeping it minimal to avoid extra deps.

const MarkdownAnalyzer = () => {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [steps, setSteps] = useState({});
  const [activeStep, setActiveStep] = useState('step1');
  const [editingStep, setEditingStep] = useState(null);
  const [stepContent, setStepContent] = useState({});
  const [chatMessage, setChatMessage] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [chatType, setChatType] = useState('general'); // 'general' or 'step'
  const [chatLoading, setChatLoading] = useState(false);
  const [analysisLogs, setAnalysisLogs] = useState([]);
  const [stepStatuses, setStepStatuses] = useState({});
  const eventSourceRef = useRef(null);
  const [isChatOpen, setIsChatOpen] = useState(false);

  const fetchProjects = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/projects`);
      setProjects(response.data.projects || []);
    } catch (error) {
      console.error('Error fetching projects:', error);
      toast.error('Failed to load projects');
    }
  };

  const fetchProjectSteps = useCallback(async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/projects/${selectedProject}/steps`);
      setSteps(response.data.steps || {});
      
      // Load content for each step
      const contentPromises = Object.keys(response.data.steps).map(async (step) => {
        if (response.data.steps[step].exists) {
          const stepResponse = await axios.get(`${API_BASE_URL}/projects/${selectedProject}/steps/${step}`);
          return { step, content: stepResponse.data.content };
        }
        return { step, content: null };
      });
      
      const contents = await Promise.all(contentPromises);
      const contentMap = {};
      contents.forEach(({ step, content }) => {
        contentMap[step] = content;
      });
      setStepContent(contentMap);
    } catch (error) {
      console.error('Error fetching project steps:', error);
      toast.error('Failed to load project steps');
    }
  }, [selectedProject]);

  useEffect(() => {
    fetchProjects();
  }, []);

  useEffect(() => {
    if (selectedProject) {
      fetchProjectSteps();
    }
  }, [selectedProject, fetchProjectSteps]);

  const handleFileUpload = async (files) => {
    if (!selectedProject) {
      toast.error('Please select a project first');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    Array.from(files).forEach(file => {
      formData.append('files', file);
    });

    try {
      await axios.post(
        `${API_BASE_URL}/projects/${selectedProject}/ingest`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      
      toast.success(`Successfully uploaded ${files.length} files`);
      fetchProjectSteps(); // Refresh steps
    } catch (error) {
      console.error('Upload error:', error);
      toast.error('Failed to upload files');
    } finally {
      setUploading(false);
    }
  };

  const runAnalysis = () => {
    if (!selectedProject) {
      toast.error('Please select a project first');
      return;
    }

    try {
      setAnalyzing(true);
      setAnalysisLogs([]);
      setStepStatuses({});
      if (eventSourceRef.current) {
        try { eventSourceRef.current.close(); } catch {}
      }

      const url = `${API_BASE_URL}/projects/${selectedProject}/analyze/stream`;
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.addEventListener('log', (e) => {
        setAnalysisLogs((prev) => [...prev, e.data]);
      });

      es.addEventListener('step', (e) => {
        setAnalysisLogs((prev) => [...prev, e.data]);
        const text = (e.data || '').toString();
        if (text.startsWith('START ')) {
          const step = text.replace('START ', '').trim();
          setStepStatuses((prev) => ({ ...prev, [step]: 'running' }));
        } else if (text.startsWith('DONE ')) {
          const step = text.replace('DONE ', '').trim();
          setStepStatuses((prev) => ({ ...prev, [step]: 'done' }));
        }
      });

      es.addEventListener('error', (e) => {
        setAnalysisLogs((prev) => [...prev, `ERROR ${e?.message || ''}`]);
        setAnalyzing(false);
        try { es.close(); } catch {}
      });

      es.addEventListener('done', () => {
        setAnalysisLogs((prev) => [...prev, 'Analysis completed']);
        setAnalyzing(false);
        try { es.close(); } catch {}
        fetchProjectSteps();
        toast.success('Analysis completed successfully');
      });
    } catch (error) {
      console.error('Analysis error:', error);
      toast.error('Failed to run analysis');
      setAnalyzing(false);
    }
  };

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        try { eventSourceRef.current.close(); } catch {}
      }
    };
  }, []);

  const saveStepContent = async (step) => {
    try {
      await axios.put(`${API_BASE_URL}/projects/${selectedProject}/steps/${step}`, {
        content: stepContent[step]
      });
      toast.success('Step content saved successfully');
      setEditingStep(null);
    } catch (error) {
      console.error('Save error:', error);
      toast.error('Failed to save step content');
    }
  };

  const sendChatMessage = async () => {
    if (!chatMessage.trim() || !selectedProject) return;

    setChatLoading(true);
    const userMessage = chatMessage;
    setChatMessage('');

    try {
      // Immediately render user message and a thinking placeholder
      const userMsg = {
        id: Date.now(),
        type: 'user',
        content: userMessage,
        timestamp: new Date()
      };
      const placeholderMsg = {
        id: Date.now() + 1,
        type: 'bot',
        content: 'Thinking...',
        timestamp: new Date(),
        thinking: true
      };
      setChatHistory(prev => [...prev, userMsg, placeholderMsg]);

      // Stream response via SSE
      const url = (chatType === 'step' && activeStep)
        ? `${API_BASE_URL}/projects/${selectedProject}/steps/${activeStep}/chat/stream?message=${encodeURIComponent(userMessage)}`
        : `${API_BASE_URL}/projects/${selectedProject}/chat/stream?message=${encodeURIComponent(userMessage)}`;

      const es = new EventSource(url);
      let accumulated = '';

      es.addEventListener('token', (e) => {
        accumulated += e.data;
        setChatHistory(prev => prev.map(m => (
          m.thinking ? { ...m, content: accumulated } : m
        )));
      });

      es.addEventListener('done', () => {
        setChatHistory(prev => prev.map(m => (
          m.thinking ? { ...m, content: accumulated, thinking: false } : m
        )));
        try { es.close(); } catch {}
        setChatLoading(false);
      });

      es.addEventListener('error', () => {
        setChatHistory(prev => prev.map(m => (
          m.thinking ? { ...m, content: 'Error: failed to get response', thinking: false } : m
        )));
        try { es.close(); } catch {}
        setChatLoading(false);
      });
    } catch (error) {
      console.error('Chat error:', error);
      toast.error('Failed to send message');
      // Turn placeholder into error message if present
      setChatHistory(prev => prev.map(m => (
        m.thinking ? { ...m, content: 'Error: failed to get response', thinking: false } : m
      )));
    } finally {
      // loading state is cleared on stream done/error
    }
  };

  const getStepStatus = (step) => {
    if (!steps[step]) return 'not_started';
    if (steps[step].exists) return 'completed';
    return 'error';
  };

  const getStepIcon = (step) => {
    const status = getStepStatus(step);
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'error':
        return <AlertCircle className="h-5 w-5 text-red-500" />;
      default:
        return <FileText className="h-5 w-5 text-gray-400" />;
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">
          ASC 606 Form Filler
        </h1>
        
        {/* Project Selector */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select Project
          </label>
          <select
            value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Choose a project...</option>
            {projects.map((project) => (
              <option key={project.project_id} value={project.project_id}>
                {project.project_name} ({project.file_count} files)
              </option>
            ))}
          </select>
        </div>

        {/* Analysis Button */}
        {selectedProject && (
          <button
            onClick={runAnalysis}
            disabled={analyzing}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {analyzing ? (
              <Loader className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            <span>{analyzing ? 'Filling...' : 'Fill ASC 606 Form'}</span>
          </button>
        )}

        {/* Live Analysis Logs */}
        {selectedProject && analyzing && (
          <div className="mt-4 border rounded-lg p-3 bg-gray-50 max-h-64 overflow-y-auto text-sm text-gray-700">
            {analysisLogs.length === 0 ? (
              <p>Starting analysis...</p>
            ) : (
              analysisLogs.map((line, idx) => (
                <div key={idx}>{line}</div>
              ))
            )}
          </div>
        )}
      </div>

      {selectedProject && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Steps Panel */}
          <div className="lg:col-span-3">
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Analysis Steps</h2>
              
              {/* Step Tabs */}
              <div className="flex space-x-1 mb-6">
                {['step1', 'step2', 'step3', 'step4', 'step5'].map((step) => (
                  <button
                    key={step}
                    onClick={() => setActiveStep(step)}
                    className={`flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium ${
                      activeStep === step
                        ? 'bg-blue-100 text-blue-700'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    {getStepIcon(step)}
                    <span>{step.toUpperCase()}</span>
                  </button>
                ))}
              </div>

              {/* Step Content */}
              <div className="border rounded-lg p-4 min-h-96">
                {steps[activeStep]?.exists ? (
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-medium text-gray-900">
                        {activeStep.toUpperCase()} Content
                      </h3>
                      <div className="flex space-x-2">
                        {editingStep === activeStep ? (
                          <>
                            <button
                              onClick={() => saveStepContent(activeStep)}
                              className="flex items-center space-x-1 px-3 py-1 text-green-600 hover:text-green-800"
                            >
                              <Save className="h-4 w-4" />
                              <span>Save</span>
                            </button>
                            <button
                              onClick={() => setEditingStep(null)}
                              className="px-3 py-1 text-gray-600 hover:text-gray-800"
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => setEditingStep(activeStep)}
                            className="flex items-center space-x-1 px-3 py-1 text-blue-600 hover:text-blue-800"
                          >
                            <Edit3 className="h-4 w-4" />
                            <span>Edit</span>
                          </button>
                        )}
                      </div>
                    </div>

                    {editingStep === activeStep ? (
                      <textarea
                        value={stepContent[activeStep] || ''}
                        onChange={(e) => setStepContent(prev => ({
                          ...prev,
                          [activeStep]: e.target.value
                        }))}
                        className="w-full h-96 p-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                        placeholder="Enter markdown content..."
                      />
                    ) : (
                      <div 
                        className="prose max-w-none prose-headings:text-gray-900 prose-p:text-gray-700 
                        prose-strong:text-gray-900 prose-ul:text-gray-700 prose-ol:text-gray-700"
                        dangerouslySetInnerHTML={{
                          __html: marked(stepContent[activeStep] || 'No content available')
                        }}
                      />
                      //   <ReactMarkdown className="prose max-w-none prose-headings:text-gray-900 prose-p:text-gray-700 prose-strong:text-gray-900 prose-ul:text-gray-700 prose-ol:text-gray-700">
                      //   {stepContent[activeStep] || 'No content available'}
                      // </ReactMarkdown>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <FileText className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                    <p>No content available for {activeStep}</p>
                    <p className="text-sm">Run analysis to generate content</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Floating Chat Button */}
      <button
        type="button"
        onClick={() => setIsChatOpen((prev) => !prev)}
        className="fixed bottom-6 right-6 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg p-4 flex items-center justify-center"
        aria-label="Open Chat Assistant"
      >
        <MessageCircle className="h-6 w-6" />
      </button>

      {/* Chat Popup (anchored above the button) with smooth open/close animation */}
      <div
        className={`fixed z-50 bottom-24 right-6 w-[90%] max-w-md transform origin-bottom-right transition-all duration-700 ease-in-out will-change-transform will-change-opacity ${
          isChatOpen
            ? 'opacity-100 scale-100 translate-y-0 pointer-events-auto'
            : 'opacity-0 scale-95 translate-y-2 pointer-events-none'
        }`}
        aria-hidden={!isChatOpen}
      >
          <div className="bg-white rounded-lg shadow-xl border">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <div>
                <h3 className="text-sm font-medium text-gray-700">Chat Assistant</h3>
                {chatType === 'step' && (
                  <p className="text-xs text-gray-500">Chat about {activeStep} content</p>
                )}
              </div>
              <div className="flex items-center space-x-2">
                <select
                  value={chatType}
                  onChange={(e) => setChatType(e.target.value)}
                  className="text-sm border rounded px-2 py-1 text-gray-700"
                >
                  <option value="general">General</option>
                  <option value="step">Step-specific</option>
                </select>
                <button
                  className="p-1 rounded hover:bg-gray-100"
                  onClick={() => setIsChatOpen(false)}
                  aria-label="Close"
                >
                  <X className="h-4 w-4 text-gray-600" />
                </button>
              </div>
            </div>

            {/* Chat History */}
            <div className="h-[26rem] overflow-y-auto px-4 py-3 bg-gray-50">
              {chatHistory.length === 0 ? (
                <p className="text-gray-500 text-sm">Start a conversation...</p>
              ) : (
                chatHistory.map((message) => (
                  <div
                    key={message.id}
                    className={`mb-3 ${message.type === 'user' ? 'text-right' : 'text-left'}`}
                  >
                    <div
                      className={`inline-block max-w-[80%] p-2 rounded-lg text-sm ${
                        message.type === 'user'
                          ? 'bg-blue-600 text-white'
                          : 'bg-white border text-gray-900'
                      }`}
                    >
                      {message.thinking ? (
                        <span className="inline-flex items-center"><Loader className="h-4 w-4 animate-spin mr-2" /> Thinking...</span>
                      ) : (
                        message.content
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      {message.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                ))
              )}
            </div>

            {/* Chat Input */}
            <div className="px-4 py-3 border-t flex items-center space-x-2">
              <input
                type="text"
                value={chatMessage}
                onChange={(e) => setChatMessage(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && sendChatMessage()}
                placeholder="Ask a question..."
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={chatLoading}
              />
              <button
                onClick={sendChatMessage}
                disabled={!chatMessage.trim() || chatLoading}
                className="px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {chatLoading ? (
                  <Loader className="h-4 w-4 animate-spin" />
                ) : (
                  // <CornerDownLeft className="h-4 w-4" />
                  <LucideSendHorizonal className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>
      </div>
    </div>
  );
};

export default MarkdownAnalyzer;
