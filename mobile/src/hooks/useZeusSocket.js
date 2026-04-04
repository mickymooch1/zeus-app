import { useCallback, useRef, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

// On Android emulator, 10.0.2.2 maps to the host machine's localhost
const DEFAULT_URL = 'http://10.0.2.2:8000';

let _msgId = 0;
const nextId = () => ++_msgId;

export function useZeusSocket() {
  const [backendUrl, setBackendUrl] = useState(DEFAULT_URL);
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [streaming, setStreaming] = useState(false);
  const streamingRef = useRef(false);
  const sessionIdRef = useRef(null);

  useEffect(() => {
    AsyncStorage.getItem('zeus_backend_url').then(url => {
      if (url) setBackendUrl(url);
    });
  }, []);

  const updateBackendUrl = useCallback(async (url) => {
    const trimmed = url.trim();
    await AsyncStorage.setItem('zeus_backend_url', trimmed);
    setBackendUrl(trimmed);
  }, []);

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

    const wsUrl = backendUrl
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
            // Try name match first; fall back to last running tool
            let matched = false;
            for (let i = tools.length - 1; i >= 0; i--) {
              if (tools[i].name === data.name && tools[i].status === 'running') {
                tools[i] = { ...tools[i], status: 'done' };
                matched = true;
                break;
              }
            }
            if (!matched) {
              for (let i = tools.length - 1; i >= 0; i--) {
                if (tools[i].status === 'running') {
                  tools[i] = { ...tools[i], status: 'done' };
                  break;
                }
              }
            }
          }
          return { ...m, tools };
        }));
      } else if (data.type === 'session_id') {
        setSessionId(data.value);
        sessionIdRef.current = data.value;
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
          ? { ...m, error: 'Connection failed. Check backend URL in Settings.' }
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
  }, [backendUrl]);

  const newSession = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    sessionIdRef.current = null;
    setStreaming(false);
    streamingRef.current = false;
  }, []);

  return {
    messages, sessionId, streaming,
    sendMessage, newSession,
    backendUrl, updateBackendUrl,
  };
}
