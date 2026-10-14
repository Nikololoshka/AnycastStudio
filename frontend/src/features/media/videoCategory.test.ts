import { describe, expect, it } from 'vitest';
import type { Draft } from '../../api/draftsApi';
import type { MediaAsset } from '../../api/mediaApi';
import type { Publication, PublicationTarget } from '../../api/publicationsApi';
import type { Platform } from '../../domain/platform/types';
import type { PublicationStatus } from '../../domain/publication/types';
import { bytesByCategory, categorizeVideos, sortVideos } from './videoCategory';

function asset(id: number, filename: string, sizeBytes: number, createdAt: string): MediaAsset {
  return { id, filename, sizeBytes, createdAt } as MediaAsset;
}

function publicationOf(
  mediaAssetId: number,
  ...targets: [Platform, PublicationStatus][]
): Publication {
  return {
    mediaAssetId,
    targets: targets.map(([platform, status]) => ({ platform, status }) as PublicationTarget),
  } as Publication;
}

function draftWith(mediaAssetId: string): Draft {
  return { video: { mediaAssetId } } as Draft;
}

const clip = asset(1, 'clip 10.mp4', 300, '2026-01-03T00:00:00Z');
const teaser = asset(2, 'clip 9.mp4', 100, '2026-01-01T00:00:00Z');
const raw = asset(3, 'raw.mov', 200, '2026-01-02T00:00:00Z');

describe('categorizeVideos', () => {
  it('marks a video used by a publication as published with the platforms that finished', () => {
    const [video] = categorizeVideos(
      [clip],
      [
        publicationOf(1, ['x', 'completed'], ['youtube', 'failed']),
        publicationOf(1, ['tiktok', 'completed'], ['x', 'completed']),
      ],
      [draftWith('1')],
    );
    expect(video.category).toBe('published');
    expect(video.platforms).toEqual(['tiktok', 'x']);
  });

  it('marks a video held only by a draft as draft', () => {
    expect(categorizeVideos([teaser], [publicationOf(1)], [draftWith('2')])[0].category).toBe(
      'draft',
    );
  });

  it('marks a video nothing refers to as unused', () => {
    const [video] = categorizeVideos([raw], [publicationOf(1)], [{} as Draft]);
    expect(video.category).toBe('unused');
    expect(video.platforms).toEqual([]);
  });
});

describe('bytesByCategory', () => {
  it('sums sizes per category', () => {
    const videos = categorizeVideos([clip, teaser, raw], [publicationOf(1)], [draftWith('2')]);
    expect(bytesByCategory(videos)).toEqual({ published: 300, draft: 100, unused: 200 });
  });
});

describe('sortVideos', () => {
  const videos = categorizeVideos([clip, teaser, raw], [], []);
  const names = (sort: Parameters<typeof sortVideos>[1]) =>
    sortVideos(videos, sort).map((video) => video.asset.filename);

  it('puts the newest upload first', () => {
    expect(names('newest')).toEqual(['clip 10.mp4', 'raw.mov', 'clip 9.mp4']);
  });

  it('puts the largest file first', () => {
    expect(names('largest')).toEqual(['clip 10.mp4', 'raw.mov', 'clip 9.mp4']);
  });

  it('orders names with numbers naturally', () => {
    expect(names('name')).toEqual(['clip 9.mp4', 'clip 10.mp4', 'raw.mov']);
  });
});
