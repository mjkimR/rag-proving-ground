import { useState, useEffect, useCallback } from 'react';

import { AEGRA_API_URL } from '@/lib/config';

export interface UseChatThreadReturn {
  threadId: string | null;
  isInitializing: boolean;
  errorMsg: string | null;
  resetThread: () => Promise<void>;
}

export function useChatThread(assistantId: string): UseChatThreadReturn {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const createNewThread = useCallback(async () => {
    setIsInitializing(true);
    setErrorMsg(null);

    try {
      const res = await fetch(`${AEGRA_API_URL}/threads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });

      if (!res.ok) {
        throw new Error('Failed to create a conversation thread.');
      }

      const data = await res.json();
      setThreadId(data.thread_id);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || 'Could not reach the Aegra server. Please verify it is running on port 2026.');
    } finally {
      setIsInitializing(false);
    }
  }, []);

  // Initialize new thread on mount/assistant change
  useEffect(() => {
    createNewThread();
  }, [assistantId, createNewThread]);

  return {
    threadId,
    isInitializing,
    errorMsg,
    resetThread: createNewThread,
  };
}
