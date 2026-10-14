import { describe, expect, it } from 'vitest';
import type { Draft } from '../../api/draftsApi';
import type { MediaAsset } from '../../api/mediaApi';
import type { Publication, PublicationTarget } from '../../api/publicationsApi';
import type { Platform } from '../../domain/platform/types';
import type { PublicationStatus } from '../../domain/publication/types';
import { overviewStats } from './overviewStats';

const NOW = new Date('2026-10-14T12:00:00Z');

function asset(id: number): MediaAsset {
  return { id } as MediaAsset;
}

function publicationOf(
  mediaAssetId: number,
  createdAt: string,
  ...targets: [Platform, PublicationStatus][]
): Publication {
  return {
    mediaAssetId,
    createdAt,
    targets: targets.map(([platform, status]) => ({ platform, status }) as PublicationTarget),
  } as Publication;
}

function draftWith(mediaAssetId: string): Draft {
  return { video: { mediaAssetId } } as Draft;
}

describe('overviewStats', () => {
  it('counts what happened in the last 30 days and what is still waiting', () => {
    // Given four videos: one published, one only in a draft, one never used, one published long ago
    const assets = [asset(1), asset(2), asset(3), asset(4)];
    const publications = [
      publicationOf(1, '2026-10-10T00:00:00Z', ['youtube', 'completed'], ['tiktok', 'completed']),
      publicationOf(1, '2026-09-20T00:00:00Z', ['x', 'scheduled']),
      publicationOf(2, '2026-08-01T00:00:00Z', ['instagram', 'completed']),
    ];
    const drafts = [draftWith('3'), {} as Draft];

    // When the overview is aggregated
    const stats = overviewStats(assets, publications, drafts, NOW);

    // Then old publications are left out of the 30-day numbers
    expect(stats).toEqual({
      videos: 4,
      unpublishedVideos: 2,
      recentPublications: 2,
      recentPlatforms: 3,
      drafts: 2,
      scheduled: 1,
    });
  });

  it('returns zeros for an empty account', () => {
    expect(overviewStats([], [], [], NOW)).toEqual({
      videos: 0,
      unpublishedVideos: 0,
      recentPublications: 0,
      recentPlatforms: 0,
      drafts: 0,
      scheduled: 0,
    });
  });
});
