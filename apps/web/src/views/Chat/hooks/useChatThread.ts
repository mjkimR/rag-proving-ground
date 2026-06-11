import { useEffect, useCallback, useReducer, useRef } from 'react';

import { AEGRA_API_URL } from '@/lib/config';

export interface UseChatThreadReturn {
  threadId: string | null;
  isInitializing: boolean;
  errorMsg: string | null;
  resetThread: () => Promise<void>;
}

interface ChatThreadState {
  threadId: string | null;
  isInitializing: boolean;
  errorMsg: string | null;
}

type ChatThreadAction =
  | { type: 'start' }
  | { type: 'success'; threadId: string }
  | { type: 'error'; errorMsg: string };

const chatThreadReducer = (_state: ChatThreadState, action: ChatThreadAction): ChatThreadState => {
  switch (action.type) {
    case 'start':
      return { threadId: null, isInitializing: true, errorMsg: null };
    case 'success':
      return { threadId: action.threadId, isInitializing: false, errorMsg: null };
    case 'error':
      return { threadId: null, isInitializing: false, errorMsg: action.errorMsg };
  }
};

export function useChatThread(assistantId: string): UseChatThreadReturn {
  const abortControllerRef = useRef<AbortController | null>(null);

  const cancelPending = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  const [{ threadId, isInitializing, errorMsg }, dispatchThread] = useReducer(chatThreadReducer, {
    threadId: null,
    isInitializing: true,
    errorMsg: null,
  });

  const createNewThread = useCallback(async () => {
    cancelPending();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    dispatchThread({ type: 'start' });

    try {
      const res = await fetch(`${AEGRA_API_URL}/threads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error('Failed to create a conversation thread.');
      }

      const data = await res.json();
      dispatchThread({ type: 'success', threadId: data.thread_id });
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      console.error(err);
      const msg = err instanceof Error ? err.message : 'Could not reach the Aegra server. Please verify it is running on port 2026.';
      dispatchThread({ type: 'error', errorMsg: msg });
    }
  }, [cancelPending]);

  // Initialize new thread on mount/assistant change
  useEffect(() => {
    cancelPending();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    dispatchThread({ type: 'start' });

    const fetchThread = async () => {
      try {
        const res = await fetch(`${AEGRA_API_URL}/threads`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
          signal: controller.signal,
        });
        if (!res.ok) throw new Error('Failed to create a conversation thread.');
        const data = await res.json();
        dispatchThread({ type: 'success', threadId: data.thread_id });
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        console.error(err);
        const msg = err instanceof Error ? err.message : 'Could not reach the Aegra server. Please verify it is running on port 2026.';
        dispatchThread({ type: 'error', errorMsg: msg });
      }
    };
    
    fetchThread();
    return () => {
      controller.abort();
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
    };
  }, [assistantId, cancelPending]);

  return {
    threadId,
    isInitializing,
    errorMsg,
    resetThread: createNewThread,
  };
}
