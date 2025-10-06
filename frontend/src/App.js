import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// Components
import Header from './components/Header';
import DocumentUpload from './components/DocumentUpload';
import DocumentReview from './components/DocumentReview';
import EvidenceBinder from './components/EvidenceBinder';
import Analytics from './components/Analytics';
import ProjectManager from './components/SessionManager';

// Styles
import './App.css';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Header />
        
        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<DocumentUpload />} />
            <Route path="/review/:documentId" element={<DocumentReview />} />
            <Route path="/evidence/:binderId" element={<EvidenceBinder />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/projects" element={<ProjectManager />} />
          </Routes>
        </main>
        
        <ToastContainer
          position="top-right"
          autoClose={5000}
          hideProgressBar={false}
          newestOnTop={false}
          closeOnClick
          rtl={false}
          pauseOnFocusLoss
          draggable
          pauseOnHover
        />
      </div>
    </Router>
  );
}

export default App;
