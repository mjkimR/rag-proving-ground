import { useState, useEffect, useCallback, useReducer } from 'react';
import type { Message, Reference } from '../types';
import {
  extractMessageContentDelta,
  isRecord,
  extractString,
} from '../utils/messageParser';

import { AEGRA_API_URL } from '@/lib/config';

export interface UseChatStreamOptions {
  threadId: string | null;
  assistantId: string;
}

export interface UseChatStreamReturn {
  messages: Message[];
  isStreaming: boolean;
  sendMessage: (userText: string, configurable: Record<string, unknown>) => Promise<void>;
}

const getErrorMessage = (err: unknown, fallback: string) => {
  if (err instanceof Error) return err.message;
  if (typeof err === 'string') return err;
  if (isRecord(err) && typeof err.message === 'string') return err.message;
  return fallback;
};

type MessageAction =
  | { type: 'reset' }
  | { type: 'append'; message: Message }
  | {
      type: 'appendChunk';
      chunkId: string;
      content: string;
      thinking?: string;
      references?: Reference[];
    }
  | { type: 'setLastAiReferences'; references: Reference[] };

const messageReducer = (messages: Message[], action: MessageAction): Message[] => {
  switch (action.type) {
    case 'reset':
      return [];
    case 'append':
      return [...messages, action.message];
    case 'appendChunk': {
      const existingIndex = messages.findIndex((message) => message.id === action.chunkId);
      if (existingIndex > -1) {
        const updated = [...messages];
        updated[existingIndex] = {
          ...updated[existingIndex],
          content: updated[existingIndex].content + action.content,
          thinking: `${updated[existingIndex].thinking || ''}${action.thinking}`,
          ...(action.references ? { references: action.references } : {}),
        };
        return updated;
      }

      return [
        ...messages,
        {
          id: action.chunkId,
          type: 'ai',
          content: action.content,
          thinking: action.thinking || undefined,
          references: action.references,
        },
      ];
    }
    case 'setLastAiReferences': {
      let targetIndex = -1;
      for (let index = messages.length - 1; index >= 0; index--) {
        if (messages[index].type === 'ai') {
          targetIndex = index;
          break;
        }
      }
      if (targetIndex < 0) return messages;

      const updated = [...messages];
      updated[targetIndex] = {
        ...updated[targetIndex],
        references: action.references,
      };
      return updated;
    }
  }
};

export function useChatStream({ threadId, assistantId }: UseChatStreamOptions): UseChatStreamReturn {
  const [messages, dispatchMessages] = useReducer(messageReducer, []);
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    dispatchMessages({ type: 'reset' });
  }, [threadId]);

  const sendMessage = useCallback(async (userText: string, configurable: Record<string, unknown>) => {
    if (!userText.trim() || !threadId || isStreaming) return;

    const userMsgId = `user-${Date.now()}`;
    dispatchMessages({
      type: 'append',
      message: { id: userMsgId, type: 'human', content: userText },
    });
    setIsStreaming(true);

    let runId: string | null = null;
    try {
      const response = await fetch(`${AEGRA_API_URL}/threads/${threadId}/runs/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          assistant_id: assistantId,
          input: {
            messages: [{ type: 'human', content: userText }],
          },
          stream_mode: ['messages-tuple'],
          config: {
            configurable,
          },
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned error code: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('Readable stream not supported by server response.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEvent = '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('event: ')) {
            currentEvent = trimmed.slice(7).trim();
          } else if (trimmed.startsWith('data: ')) {
            const dataStr = trimmed.slice(6).trim();

            if (currentEvent === 'metadata') {
              try {
                const parsed = JSON.parse(dataStr);
                if (parsed && parsed.run_id) {
                  runId = parsed.run_id;
                }
              } catch (e) {
                console.error('Failed to parse metadata event:', e);
              }
            } else if (currentEvent === 'messages') {
              try {
                const parsed = JSON.parse(dataStr);
                if (Array.isArray(parsed) && parsed.length > 0) {
                  const msgChunk = parsed[0];
                  if (msgChunk && msgChunk.content !== undefined) {
                    let chunkDelta = extractMessageContentDelta(msgChunk.content);
                    if (!chunkDelta.thinking && isRecord(msgChunk.additional_kwargs)) {
                      chunkDelta = {
                        ...chunkDelta,
                        thinking: extractString(msgChunk.additional_kwargs.reasoning_content),
                      };
                    }

                    const hasReferences = isRecord(msgChunk.additional_kwargs) && Array.isArray(msgChunk.additional_kwargs.references);
                    const references = hasReferences ? (msgChunk.additional_kwargs.references as Reference[]) : undefined;

                    if (!chunkDelta.content && !chunkDelta.thinking && !references) continue;

                    const chunkId = msgChunk.id || `ai-${Date.now()}`;

                    dispatchMessages({
                      type: 'appendChunk',
                      chunkId,
                      content: chunkDelta.content,
                      thinking: chunkDelta.thinking,
                      references,
                    });
                  }
                }
              } catch (e) {
                console.error('Failed to parse message event payload:', e);
              }
            } else if (currentEvent === 'error') {
              try {
                const parsed = JSON.parse(dataStr);
                let errMsg = parsed.message || parsed.error || 'An error occurred during execution.';

                if (runId && threadId) {
                  try {
                    const runRes = await fetch(`${AEGRA_API_URL}/threads/${threadId}/runs/${runId}`);
                    if (runRes.ok) {
                      const runData = await runRes.json();
                      if (runData.error_message || runData.error) {
                        errMsg = runData.error_message || runData.error;
                      }
                    }
                  } catch (fetchErr) {
                    console.error('Failed to fetch detailed run error:', fetchErr);
                  }
                }

                dispatchMessages({
                  type: 'append',
                  message: { id: `error-${Date.now()}`, type: 'error', content: errMsg },
                });
              } catch {
                dispatchMessages({
                  type: 'append',
                  message: { id: `error-${Date.now()}`, type: 'error', content: 'An error occurred during execution.' },
                });
              }
            }
          }
        }
      }

      // Stream finished successfully. Fetch final state to retrieve references.
      try {
        const stateRes = await fetch(`${AEGRA_API_URL}/threads/${threadId}/state`);
        if (stateRes.ok) {
          const stateData = await stateRes.json();
          const serverMessages = stateData?.values?.messages;
          if (Array.isArray(serverMessages) && serverMessages.length > 0) {
            const lastServerMsg = serverMessages[serverMessages.length - 1];
            if (lastServerMsg && (lastServerMsg.type === 'ai' || lastServerMsg.role === 'assistant')) {
              const refs = lastServerMsg.additional_kwargs?.references;
              if (Array.isArray(refs)) {
                dispatchMessages({ type: 'setLastAiReferences', references: refs });
              }
            }
          }
        }
      } catch (syncErr) {
        console.error('Failed to sync final thread state for references:', syncErr);
      }
    } catch (err) {
      console.error(err);
      let errMsg = getErrorMessage(err, 'An error occurred during streaming execution.');

      if (runId && threadId) {
        try {
          const runRes = await fetch(`${AEGRA_API_URL}/threads/${threadId}/runs/${runId}`);
          if (runRes.ok) {
            const runData = await runRes.json();
            if (runData.error_message || runData.error) {
              errMsg = runData.error_message || runData.error;
            }
          }
        } catch (fetchErr) {
          console.error('Failed to fetch detailed run error in catch block:', fetchErr);
        }
      }

      dispatchMessages({
        type: 'append',
        message: { id: `error-${Date.now()}`, type: 'error', content: errMsg },
      });
    } finally {
      setIsStreaming(false);
    }
  }, [threadId, assistantId, isStreaming]);

  return {
    messages,
    isStreaming,
    sendMessage,
  };
}
