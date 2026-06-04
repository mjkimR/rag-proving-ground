export const formatShortId = (value: string) => (value.length > 12 ? `${value.slice(0, 8)}...${value.slice(-4)}` : value);
