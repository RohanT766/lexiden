import React from 'react';
import ReactMarkdown from 'react-markdown';
import './MessageList.css';

const MessageList = ({ messages, streamingMessage, isStreaming }) => {
  const renderMessage = (message) => {
    if (message.type === 'function') {
      return (
        <div className="function-call">
          <span className="function-name">Processing: {message.function}</span>
          {message.status === 'completed' && message.result && (
            <span className="function-status">Complete</span>
          )}
        </div>
      );
    }

    if (message.type === 'error') {
      return (
        <div className="error-message">
          {message.content}
        </div>
      );
    }

    let content = message.content;
    content = content.replace(/# DOCUMENT START\s*/g, '');
    content = content.replace(/# DOCUMENT END\s*/g, '');
    content = content.replace(/# EDIT START\s*/g, '--- Changes Below ---\n');
    content = content.replace(/# EDIT END\s*/g, '--- End of Changes ---\n');
    
    const startMarker = '<<<DOCUMENT_START>>>';
    const endMarker = '<<<DOCUMENT_END>>>';
    const startIdx = content.indexOf(startMarker);
    const endIdx = content.indexOf(endMarker);
    
    if (startIdx !== -1 && endIdx !== -1) {
      const beforeDoc = content.substring(0, startIdx).trim();
      const afterDoc = content.substring(endIdx + endMarker.length).trim();
      content = beforeDoc + (afterDoc ? '\n\n' + afterDoc : '');
    } else if (startIdx !== -1) {
      content = content.substring(0, startIdx).trim();
    }

    return <ReactMarkdown>{content}</ReactMarkdown>;
  };

  return (
    <div className="message-list">
      {messages.map(message => (
        <div key={message.id} className={`message ${message.type}`}>
          <div className="message-header">
            <span className="message-sender">
              {message.type === 'user' ? 'You' : 'Assistant'}
            </span>
            <span className="message-time">
              {message.timestamp.toLocaleTimeString()}
            </span>
          </div>
          <div className="message-content">
            {renderMessage(message)}
          </div>
        </div>
      ))}
      
      {isStreaming && streamingMessage && (
        <div className="message assistant streaming">
          <div className="message-header">
            <span className="message-sender">Assistant</span>
            <span className="message-time">typing...</span>
          </div>
          <div className="message-content">
            <ReactMarkdown>{streamingMessage}</ReactMarkdown>
            <span className="typing-cursor">▊</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default MessageList;
