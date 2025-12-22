import { useState, useRef, useEffect } from 'react';
import { Button, Input, Loading } from '@/components/ui';
import { useAuthStore } from '@/stores';
import { queryRAG, listKnowledgeBases } from '@/api';
import type { ChatMessage, ChunkResult, KnowledgeBase } from '@/types';

export function GuidanceChat() {
  const { selectedOrg } = useAuthStore();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKBId, setSelectedKBId] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch knowledge bases on mount
  useEffect(() => {
    const fetchKBs = async () => {
      try {
        const response = await listKnowledgeBases();
        setKnowledgeBases(response.knowledge_bases);
      } catch (error) {
        console.error('Failed to fetch knowledge bases:', error);
      }
    };
    fetchKBs();
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    // Add loading placeholder for assistant
    const loadingId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      {
        id: loadingId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isLoading: true,
      },
    ]);

    try {
      const response = await queryRAG({
        query: userMessage.content,
        kb_id: selectedKBId || undefined,
        top_k: 5,
        min_similarity: 0.3,
        include_metadata: true,
      });

      // Format the response from chunks
      const assistantMessage: ChatMessage = {
        id: loadingId,
        role: 'assistant',
        content: formatRAGResponse(response.results),
        sources: response.results,
        timestamp: new Date(),
      };

      setMessages((prev) => prev.map((msg) => (msg.id === loadingId ? assistantMessage : msg)));
    } catch (error) {
      console.error('Failed to query RAG:', error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === loadingId
            ? {
                ...msg,
                content: 'Sorry, I encountered an error while searching. Please try again.',
                isLoading: false,
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const formatRAGResponse = (results: ChunkResult[]): string => {
    if (results.length === 0) {
      return "I couldn't find any relevant information in the knowledge base for your question. Try rephrasing your question or ask about a different topic.";
    }

    // Combine the most relevant chunks into a response
    const topResults = results.slice(0, 3);
    let response = "Here's what I found:\n\n";

    topResults.forEach((result, index) => {
      response += `**${index + 1}. From "${result.doc_name}":**\n`;
      response += `${result.chunk_text}\n\n`;
    });

    return response;
  };

  return (
    <div className="h-full flex flex-col">
      {/* KB Selector */}
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Search in:</span>
          <select
            value={selectedKBId}
            onChange={(e) => setSelectedKBId(e.target.value)}
            className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          >
            <option value="">All Knowledge Bases</option>
            {knowledgeBases.map((kb) => (
              <option key={kb.kb_id} value={kb.kb_id}>
                {kb.kb_name}
              </option>
            ))}
          </select>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          Get answers from {selectedOrg?.org_name}'s knowledge base
        </p>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-500">
            <svg
              className="w-16 h-16 text-gray-300 mb-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
            <p className="text-lg font-medium">Start a conversation</p>
            <p className="text-sm mt-1 text-center px-4">
              Ask a question to search the knowledge base
            </p>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 p-4 bg-white">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Ask a question..."
            disabled={isLoading}
            className="flex-1"
          />
          <Button type="submit" disabled={isLoading || !inputValue.trim()}>
            {isLoading ? <Loading size="sm" /> : 'Send'}
          </Button>
        </form>
      </div>
    </div>
  );
}

// Message bubble component
function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-3 ${
          isUser ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-900'
        }`}
      >
        {message.isLoading ? (
          <div className="flex items-center gap-2">
            <Loading size="sm" />
            <span className="text-gray-500">Searching...</span>
          </div>
        ) : (
          <>
            <div className="whitespace-pre-wrap text-sm">{message.content}</div>
            {message.sources && message.sources.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-200">
                <p className="text-xs text-gray-500 mb-2">
                  Sources ({message.sources.length} results)
                </p>
                <div className="space-y-1">
                  {message.sources.slice(0, 3).map((source, idx) => (
                    <div key={source.chunk_id} className="text-xs text-gray-500">
                      {idx + 1}. {source.doc_name} ({Math.round(source.similarity * 100)}% match)
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
