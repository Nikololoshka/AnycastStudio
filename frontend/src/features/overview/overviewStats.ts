import type { Draft } from '../../api/draftsApi';
import type { MediaAsset } from '../../api/mediaApi';
import type { Publication } from '../../api/publicationsApi';
import { isAvailable } from '../../domain/platform/order';
import { categorizeVideos } from '../media/videoCategory';
import { publicationTab } from '../publications/publicationTab';

const RECENT_DAYS = 30;
const DAY_MS = 24 * 60 * 60 * 1000;

export interface OverviewStats {
  videos: number;
  unpublishedVideos: number;
  recentPublications: number;
  recentPlatforms: number;
  drafts: number;
  scheduled: number;
}

export function overviewStats(
  assets: MediaAsset[],
  publications: Publication[],
  drafts: Draft[],
  now: Date,
): OverviewStats {
  const since = now.getTime() - RECENT_DAYS * DAY_MS;
  const recent = publications.filter(
    (publication) => new Date(publication.createdAt).getTime() >= since,
  );
  const platforms = new Set(
    recent.flatMap((publication) =>
      publication.targets.map((target) => target.platform).filter(isAvailable),
    ),
  );
  return {
    videos: assets.length,
    unpublishedVideos: categorizeVideos(assets, publications, drafts).filter(
      (video) => video.category !== 'published',
    ).length,
    recentPublications: recent.length,
    recentPlatforms: platforms.size,
    drafts: drafts.length,
    scheduled: publications.filter((publication) => publicationTab(publication) === 'scheduled')
      .length,
  };
}
