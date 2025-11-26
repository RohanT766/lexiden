import React, { useState, useEffect, useRef } from 'react';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import './ChatInterface.css';

const ChatInterface = ({ sessionId, onDocumentGenerated }) => {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    setMessages([{
      id: 'initial',
      type: 'assistant',
      content: `I can help you create legal documents. What type of document do you need?`,
      timestamp: new Date()
    }]);
  }, [sessionId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentStreamingMessage]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async (message) => {
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: message,
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);

    setIsStreaming(true);
    setCurrentStreamingMessage('');
    let streamingDocContent = '';
    
    let currentMessage = '';
    let messageFinalized = false;
    
    try {
      const response = await fetch('http://localhost:5001/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          session_id: sessionId
        })
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }


      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data.trim()) {
              try {
                const parsed = JSON.parse(data);
                
                if (parsed.type === 'text') {
                  currentMessage += parsed.content;
                  setCurrentStreamingMessage(currentMessage);
                } else if (parsed.type === 'function_call') {
                  setMessages(prev => [...prev, {
                    id: `func-${Date.now()}`,
                    type: 'function',
                    function: parsed.function,
                    status: parsed.status,
                    timestamp: new Date()
                  }]);
                } else if (parsed.type === 'function_result') {
                  if (parsed.result?.document) {
                    onDocumentGenerated(parsed.result.document);
                  }
                  
                  setMessages(prev => {
                    const updated = [...prev];
                    const funcMsg = updated.find(m => m.type === 'function' && m.function === parsed.function);
                    if (funcMsg) {
                      funcMsg.result = parsed.result;
                      funcMsg.status = 'completed';
                    }
                    return updated;
                  });
                } else if (parsed.type === 'new_message') {
                  if (currentMessage && currentMessage.trim()) {
                    const finalMessage = currentMessage;
                    setMessages(prev => [...prev, {
                      id: Date.now(),
                      type: 'assistant',
                      content: finalMessage,
                      timestamp: new Date()
                    }]);
                    currentMessage = '';
                    setCurrentStreamingMessage('');
                  }
                } else if (parsed.type === 'document_start') {
                  streamingDocContent = '';
                  onDocumentGenerated('<<<DOCUMENT_START>>>', true);
                } else if (parsed.type === 'document_chunk') {
                  streamingDocContent = '<<<DOCUMENT_START>>>' + parsed.content;
                  onDocumentGenerated(streamingDocContent, true);
                } else if (parsed.type === 'document_complete') {
                  if (parsed.document) {
                    onDocumentGenerated(parsed.document, false);
                    streamingDocContent = '';
                  }
                } else if (parsed.type === 'document_generated') {
                  if (parsed.document) {
                    onDocumentGenerated(parsed.document);
                  }
                } else if (parsed.type === 'cleanup_chat') {
                  if (currentMessage && currentMessage.includes('<<<')) {
                    const cleanedText = currentMessage
                      .split('\n')
                      .filter(line => !line.includes('<<<DOCUMENT_START>>>') && !line.includes('<<<DOCUMENT_END>>>'))
                      .map(line => {
                        return line.replace(/<<<[^>]*>>>/g, '').replace(/^>+|>+$/g, '').trim();
                      })
                      .filter(line => line.length > 0)
                      .join('\n');
                    
                    currentMessage = cleanedText;
                    setCurrentStreamingMessage(cleanedText);
                  }
                } else if (parsed.type === 'done') {
                  if (currentMessage && currentMessage.trim()) {
                    const finalMessage = currentMessage;
                    setMessages(prev => [...prev, {
                      id: Date.now(),
                      type: 'assistant',
                      content: finalMessage,
                      timestamp: new Date()
                    }]);
                    setCurrentStreamingMessage('');
                    messageFinalized = true;
                  }
                } else if (parsed.type === 'error') {
                  setMessages(prev => [...prev, {
                    id: Date.now(),
                    type: 'error',
                    content: `Error: ${parsed.message}`,
                    timestamp: new Date()
                  }]);
                }
              } catch (e) {
              }
            }
          }
        }
      }
    } catch (error) {
      setMessages(prev => [...prev, {
        id: Date.now(),
        type: 'error',
        content: `Connection error: ${error.message}. Please check if the backend server is running.`,
        timestamp: new Date()
      }]);
    } finally {
      setIsStreaming(false);
      if (!messageFinalized && currentMessage && currentMessage.trim()) {
        setMessages(prev => [...prev, {
          id: Date.now(),
          type: 'assistant',
          content: currentMessage,
          timestamp: new Date()
        }]);
      }
      setCurrentStreamingMessage('');
    }
  };

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <h2>Chat</h2>
        {isStreaming && <span className="streaming-indicator">Processing...</span>}
      </div>
      
      <MessageList 
        messages={messages} 
        streamingMessage={currentStreamingMessage}
        isStreaming={isStreaming}
      />
      <div ref={messagesEndRef} />
      
      <MessageInput 
        onSendMessage={handleSendMessage}
        disabled={isStreaming}
        isFirstMessage={messages.length === 1}
      />
    </div>
  );
};

export default ChatInterface;
