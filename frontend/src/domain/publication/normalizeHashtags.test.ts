import { describe, expect, it } from 'vitest';
import { normalizeHashtags } from './normalizeHashtags';

describe('normalizeHashtags', () => {
  it('reads the same list from hashes and from commas', () => {
    expect(normalizeHashtags('#video #technology #tutorial')).toEqual(
      normalizeHashtags('video, technology, tutorial'),
    );
  });

  it('strips the leading hash and lowercases', () => {
    expect(normalizeHashtags('#Video')).toEqual(['video']);
  });

  it('drops duplicates, keeping the first occurrence', () => {
    expect(normalizeHashtags('video, Video, VIDEO, clip')).toEqual(['video', 'clip']);
  });

  it('ignores empty entries and stray separators', () => {
    expect(normalizeHashtags('  ,,  video ,, , clip  ')).toEqual(['video', 'clip']);
  });

  it('returns nothing for input that is only separators', () => {
    expect(normalizeHashtags(' , , ')).toEqual([]);
  });
});
