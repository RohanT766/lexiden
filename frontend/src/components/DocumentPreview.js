import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import './DocumentPreview.css';

const DocumentPreview = ({ document, onClose, sessionId }) => {
  const [pdfUrl, setPdfUrl] = useState(null);
  const [pdfError, setPdfError] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    const hasEndMarker = document && document.includes('<<<DOCUMENT_END>>>');
    const hasStartMarker = document && document.includes('<<<DOCUMENT_START>>>');
    
    if (hasStartMarker && !hasEndMarker) {
      setIsStreaming(true);
      setPdfUrl(null);
    } else if (sessionId && document && !hasStartMarker) {
      setIsStreaming(false);
      const timer = setTimeout(() => {
        setPdfUrl(`http://localhost:5001/document/${sessionId}/pdf?t=${Date.now()}`);
        setPdfError(false);
      }, 500);
      
      return () => clearTimeout(timer);
    }
  }, [sessionId, document]);

  return (
    <div className="document-preview">
      <div className="preview-header">
        <h2>Document Preview</h2>
        {onClose && (
          <button onClick={onClose} className="action-button close-button">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M10.5 3.5L3.5 10.5M3.5 3.5L10.5 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        )}
      </div>
      
      <div className="preview-content">
        {document ? (
          isStreaming || pdfError || !pdfUrl ? (
            <div className="document-content" style={{ padding: '1.5rem', overflowY: 'auto' }}>
              {isStreaming && (
                <div style={{ marginBottom: '1rem', color: '#3b82f6', fontSize: '0.875rem' }}>
                  Generating document...
                </div>
              )}
              <ReactMarkdown>
                {document.replace(/<<<DOCUMENT_START>>>/g, '').replace(/<<<DOCUMENT_END>>>/g, '')}
              </ReactMarkdown>
            </div>
          ) : (
            <iframe 
              src={pdfUrl}
              className="pdf-viewer"
              title="Document Preview"
              width="100%"
              height="100%"
              onError={() => {
                setPdfError(true);
              }}
            />
          )
        ) : (
          <div className="empty-state">
            <p>Your generated document will appear here</p>
            <p className="empty-hint">Start a conversation to create a legal document</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentPreview;
