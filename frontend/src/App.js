import React, { useState, useEffect } from 'react';
import ChatInterface from './components/ChatInterface';
import DocumentPreview from './components/DocumentPreview';
import { v4 as uuidv4 } from 'uuid';
import './App.css';

function App() {
  const [sessionId, setSessionId] = useState('');
  const [currentDocument, setCurrentDocument] = useState(null);
  const [documentVisible, setDocumentVisible] = useState(true);

  useEffect(() => {
    setSessionId(uuidv4());
  }, []);

  const handleDocumentGenerated = (document, isStreaming = false) => {
    setCurrentDocument(document);
    setDocumentVisible(true);
  };


  const handleHideDocument = () => {
    setDocumentVisible(false);
  };

  const handleShowDocument = () => {
    setDocumentVisible(true);
  };

  return (
    <div className="App">
      <header className="App-header">
        <div className="header-content">
          <h1>Legal Document Assistant</h1>
        </div>
      </header>
      
      <div className="main-container">
        <div className={currentDocument && documentVisible ? "chat-section" : "chat-section-full"}>
          <ChatInterface 
            sessionId={sessionId}
            onDocumentGenerated={handleDocumentGenerated}
          />
        </div>
        
        {currentDocument && documentVisible && (
          <div className="document-section">
            <DocumentPreview document={currentDocument} onClose={handleHideDocument} sessionId={sessionId} />
          </div>
        )}
        
        {currentDocument && !documentVisible && (
          <button 
            onClick={handleShowDocument} 
            className="floating-show-btn"
            title="Show Document"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3 1h7l3 3v10a1 1 0 01-1 1H3a1 1 0 01-1-1V2a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M10 1v3h3M5 7h6M5 10h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        )}
      </div>
      
      <footer className="App-footer">
        <p>Legal Document Assistant</p>
      </footer>
    </div>
  );
}

export default App;
