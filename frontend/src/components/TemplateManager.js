import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';

const TemplateManager = () => {
  const [templates, setTemplates] = useState({});
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editedContent, setEditedContent] = useState('');
  const [saving, setSaving] = useState(false);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchTemplates();
  }, []);

  const fetchTemplates = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/templates`);
      if (!response.ok) {
        throw new Error('Failed to fetch templates');
      }
      const data = await response.json();
      setTemplates(data.templates);
    } catch (error) {
      console.error('Error fetching templates:', error);
      toast.error('Failed to fetch templates');
    } finally {
      setLoading(false);
    }
  };

  const selectTemplate = async (step) => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/templates/${step}`);
      if (!response.ok) {
        throw new Error('Failed to fetch template');
      }
      const data = await response.json();
      setSelectedTemplate(data);
      setEditedContent(data.content);
      setEditing(false);
    } catch (error) {
      console.error('Error fetching template:', error);
      toast.error('Failed to fetch template');
    } finally {
      setLoading(false);
    }
  };

  const saveTemplate = async () => {
    if (!selectedTemplate) return;

    try {
      setSaving(true);
      const response = await fetch(`${API_BASE_URL}/templates/${selectedTemplate.step}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(editedContent),
      });

      if (!response.ok) {
        throw new Error('Failed to save template');
      }

      const data = await response.json();
      toast.success(data.message);
      setEditing(false);
      
      // Refresh templates
      await fetchTemplates();
      
      // Update selected template
      setSelectedTemplate(prev => ({
        ...prev,
        content: editedContent,
        last_modified: Date.now() / 1000
      }));
    } catch (error) {
      console.error('Error saving template:', error);
      toast.error('Failed to save template');
    } finally {
      setSaving(false);
    }
  };

  const resetTemplate = async () => {
    if (!selectedTemplate) return;

    try {
      setSaving(true);
      const response = await fetch(`${API_BASE_URL}/templates/${selectedTemplate.step}/reset`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to reset template');
      }

      const data = await response.json();
      toast.success(data.message);
      
      // Refresh the selected template
      await selectTemplate(selectedTemplate.step);
    } catch (error) {
      console.error('Error resetting template:', error);
      toast.error('Failed to reset template');
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (timestamp) => {
    if (!timestamp) return 'Unknown';
    return new Date(timestamp * 1000).toLocaleString();
  };

  const getStepDescription = (step) => {
    const descriptions = {
      step1: 'Identifying contract with the customer',
      step2: 'Identifying the performance obligation in a contract',
      step3: 'Determining transaction price',
      step4: 'Allocate the transaction price to the performance obligations',
      step5: 'Recognize revenue when (or as) each performance obligation is satisfied'
    };
    return descriptions[step] || 'Unknown step';
  };

  if (loading && Object.keys(templates).length === 0) {
    return (
      <div className="flex justify-center items-center min-h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Template Manager</h1>
        <p className="text-gray-600">
          View and edit ASC 606 form templates. Modify the question sets used for contract analysis.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Template List */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Available Templates</h2>
            </div>
            <div className="p-4">
              <div className="space-y-2">
                {Object.entries(templates).map(([step, template]) => (
                  <button
                    key={step}
                    onClick={() => selectTemplate(step)}
                    className={`w-full text-left p-3 rounded-lg border transition-colors ${
                      selectedTemplate?.step === step
                        ? 'bg-blue-50 border-blue-200 text-blue-900'
                        : 'bg-white border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    <div className="font-medium text-sm">{template.title}</div>
                    <div className="text-xs text-gray-500 mt-1">
                      {template.length} characters
                    </div>
                    {template.last_modified && (
                      <div className="text-xs text-gray-400 mt-1">
                        Modified: {formatDate(template.last_modified)}
                      </div>
                    )}
                    {template.error && (
                      <div className="text-xs text-red-500 mt-1">
                        {template.error}
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Template Editor */}
        <div className="lg:col-span-2">
          {selectedTemplate ? (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200">
              <div className="p-4 border-b border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">
                      {selectedTemplate.title}
                    </h2>
                    <p className="text-sm text-gray-500 mt-1">
                      {getStepDescription(selectedTemplate.step)}
                    </p>
                  </div>
                  <div className="flex space-x-2">
                    {!editing ? (
                      <button
                        onClick={() => setEditing(true)}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                      >
                        Edit Template
                      </button>
                    ) : (
                      <>
                        <button
                          onClick={() => {
                            setEditing(false);
                            setEditedContent(selectedTemplate.content);
                          }}
                          className="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={saveTemplate}
                          disabled={saving}
                          className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
                        >
                          {saving ? 'Saving...' : 'Save Changes'}
                        </button>
                      </>
                    )}
                    <button
                      onClick={resetTemplate}
                      disabled={saving}
                      className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors disabled:opacity-50"
                    >
                      Reset
                    </button>
                  </div>
                </div>
              </div>

              <div className="p-4">
                {editing ? (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Template Content
                      </label>
                      <textarea
                        value={editedContent}
                        onChange={(e) => setEditedContent(e.target.value)}
                        className="w-full h-96 p-3 border border-gray-300 rounded-lg font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        placeholder="Enter template content..."
                      />
                    </div>
                    <div className="text-sm text-gray-500">
                      {editedContent.length} characters
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-gray-700">Preview</span>
                        <span className="text-xs text-gray-500">
                          {selectedTemplate.length} characters
                        </span>
                      </div>
                      <div className="max-h-96 overflow-y-auto">
                        <pre className="whitespace-pre-wrap text-sm text-gray-800 font-mono">
                          {selectedTemplate.content}
                        </pre>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
              <div className="text-gray-400 mb-4">
                <svg className="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Select a Template</h3>
              <p className="text-gray-500">
                Choose a template from the list to view and edit its content.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Help Section */}
      <div className="mt-8 bg-blue-50 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-blue-900 mb-2">Template Management Help</h3>
        <div className="text-sm text-blue-800 space-y-2">
          <p>
            <strong>Viewing Templates:</strong> Click on any template in the list to view its content.
          </p>
          <p>
            <strong>Editing Templates:</strong> Click "Edit Template" to modify the content. Use the text editor to make changes.
          </p>
          <p>
            <strong>Saving Changes:</strong> Click "Save Changes" to update the template. A backup will be created automatically.
          </p>
          <p>
            <strong>Resetting Templates:</strong> Click "Reset" to restore the template to its original version from the backup.
          </p>
          <p>
            <strong>Template Format:</strong> Templates use Markdown format with placeholders in curly braces {} for dynamic content.
          </p>
        </div>
      </div>
    </div>
  );
};

export default TemplateManager;
