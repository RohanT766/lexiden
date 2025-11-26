import React, { useState, useRef, useEffect } from 'react';
import './MessageInput.css';

const MessageInput = ({ onSendMessage, disabled, isFirstMessage }) => {
  const [message, setMessage] = useState('');
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [message]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (message.trim() && !disabled) {
      onSendMessage(message);
      setMessage('');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const suggestions = [
    "I need to appoint John Smith as a director",
    "Create an NDA between two companies",
    "Help me draft an employment agreement",
    "Generate a service agreement"
  ];

  const handleSuggestionClick = (suggestion) => {
    setMessage(suggestion);
    textareaRef.current?.focus();
  };

  return (
    <div className="message-input-container">
      {message === '' && !disabled && isFirstMessage && (
        <div className="suggestions">
          <span className="suggestions-label">Quick start:</span>
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              className="suggestion-chip"
              onClick={() => handleSuggestionClick(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="message-input-form">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={disabled ? "Waiting for response..." : "Type your message here... (Shift+Enter for new line)"}
          disabled={disabled}
          className="message-input"
          rows="1"
        />
        <button 
          type="submit" 
          disabled={disabled || !message.trim()}
          className="send-button"
        >
          {disabled ? (
            <span>Wait</span>
          ) : (
            <span>Send</span>
          )}
        </button>
      </form>
    </div>
  );
};

export default MessageInput;
