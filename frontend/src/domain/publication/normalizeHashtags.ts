export function normalizeHashtags(input: string): string[] {
  const tokens = input
    .split(/[\s,]+/)
    .map((token) => token.replace(/^#/, '').trim().toLowerCase())
    .filter((token) => token.length > 0);

  return Array.from(new Set(tokens));
}
