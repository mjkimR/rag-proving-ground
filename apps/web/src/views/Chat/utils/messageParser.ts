export const THINKING_CONTENT_BLOCK_TYPES = new Set(['thinking', 'reasoning']);

export interface MessageContentDelta {
  content: string;
  thinking: string;
}

export const emptyDelta = (): MessageContentDelta => ({ content: '', thinking: '' });

export const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null
);

export const mergeDelta = (left: MessageContentDelta, right: MessageContentDelta): MessageContentDelta => ({
  content: left.content + right.content,
  thinking: left.thinking + right.thinking,
});

export const extractString = (value: unknown): string => (
  typeof value === 'string' ? value : ''
);

export const extractMessageContentDelta = (content: unknown): MessageContentDelta => {
  if (typeof content === 'string') {
    return { content, thinking: '' };
  }

  if (Array.isArray(content)) {
    return content.reduce(
      (delta, item) => mergeDelta(delta, extractMessageContentDelta(item)),
      emptyDelta(),
    );
  }

  if (!isRecord(content)) {
    return emptyDelta();
  }

  const blockType = typeof content.type === 'string' ? content.type : undefined;
  if (blockType && THINKING_CONTENT_BLOCK_TYPES.has(blockType)) {
    return {
      content: '',
      thinking: extractString(content.thinking)
        || extractString(content.reasoning)
        || extractString(content.text)
        || extractMessageContentDelta(content.content).content,
    };
  }

  if (typeof content.text === 'string') {
    return { content: content.text, thinking: '' };
  }

  if (typeof content.content === 'string' || Array.isArray(content.content)) {
    return extractMessageContentDelta(content.content);
  }

  return emptyDelta();
};
