import { useCallback, useRef, useState } from 'react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

let _msgId = 0;
const nextId = () => ++_msgId;

export function useZeusSocket() {
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [streaming, setStreaming] = useState(false);
  const streamingRef = useRef(false);
  const sessionIdRef = useRef(null);

  // Keep refs in sync so WS callbacks always see current values
  const sync = (sid, isStreaming) => {
    sessionIdRef.current = sid;
    streamingRef.current = isStreaming;
  };

  const sendMessage = useCallback((prompt) => {
    if (streamingRef.current) return;

    const userMsgId = nextId();
    const zeusMsgId = nextId();

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', text: prompt },
      { id: zeusMsgId, role: 'zeus', text: '', tools: [], error: null },
    ]);
    setStreaming(true);
    streamingRef.current = true;

    const wsUrl = (BACKEND_URL || window.location.origin)
      .replace(/^https/, 'wss')
      .replace(/^http/, 'ws') + '/chat';

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      ws.send(JSON.stringify({ prompt, session_id: sessionIdRef.current }));
    };

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);

      if (data.type === 'text') {
        setMessages(prev => prev.map(m =>
          m.id === zeusMsgId ? { ...m, text: m.text + data.delta } : m
        ));
      } else if (data.type === 'tool') {
        setMessages(prev => prev.map(m => {
          if (m.id !== zeusMsgId) return m;
          const tools = [...(m.tools || [])];
          if (data.status === 'running') {
            tools.push({ name: data.name, path: data.path || '', status: 'running' });
          } else if (data.status === 'done') {
            // Mark last matching running tool as done
            for (let i = tools.length - 1; i >= 0; i--) {
              if (tools[i].name === data.name && tools[i].status === 'running') {
                tools[i] = { ...tools[i], status: 'done' };
                break;
              }
            }
          }
          return { ...m, tools };
        }));
      } else if (data.type === 'session_id') {
        setSessionId(data.value);
        sync(data.value, true);
      } else if (data.type === 'error') {
        setMessages(prev => prev.map(m =>
          m.id === zeusMsgId ? { ...m, error: data.message } : m
        ));
        setStreaming(false);
        streamingRef.current = false;
        ws.close();
      } else if (data.type === 'done') {
        setStreaming(false);
        streamingRef.current = false;
        ws.close();
      }
    };

    ws.onerror = () => {
      setMessages(prev => prev.map(m =>
        m.id === zeusMsgId
          ? { ...m, error: 'Connection failed. Is the backend running?' }
          : m
      ));
      setStreaming(false);
      streamingRef.current = false;
    };

    ws.onclose = () => {
      if (streamingRef.current) {
        setStreaming(false);
        streamingRef.current = false;
      }
    };
  }, []);

  const newSession = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    setStreaming(false);
    sync(null, false);
  }, []);

  const loadSession = useCallback((id, transcript) => {
    const msgs = transcript.map(entry => ({
      id: nextId(),
      role: entry.role === 'user' ? 'user' : 'zeus',
      text: entry.text,
      tools: [],
      error: null,
    }));
    setMessages(msgs);
    setSessionId(id);
    setStreaming(false);
    sync(id, false);
  }, []);

  return { messages, sessionId, streaming, sendMessage, newSession, loadSession };
}
