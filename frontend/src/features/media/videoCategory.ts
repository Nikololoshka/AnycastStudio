import type { Draft } from '../../api/draftsApi';
import type { MediaAsset } from '../../api/mediaApi';
import type { Publication } from '../../api/publicationsApi';
import { AVAILABLE_PLATFORMS, type AvailablePlatform } from '../../domain/platform/order';

export type VideoCategory = 'published' | 'draft' | 'unused';
export type VideoSort = 'newest' | 'largest' | 'name';

export interface LibraryVideo {
  asset: MediaAsset;
  category: VideoCategory;
  platforms: AvailablePlatform[];
}

export function categorizeVideos(
  assets: MediaAsset[],
  publications: Publication[],
  drafts: Draft[],
): LibraryVideo[] {
  const draftAssetIds = new Set(drafts.map((draft) => draft.video?.mediaAssetId));
  return assets.map((asset) => {
    const own = publications.filter((publication) => publication.mediaAssetId === asset.id);
    const done = new Set(
      own.flatMap((publication) =>
        publication.targets
          .filter((target) => target.status === 'completed')
          .map((target) => target.platform),
      ),
    );
    return {
      asset,
      category: own.length ? 'published' : draftAssetIds.has(String(asset.id)) ? 'draft' : 'unused',
      platforms: AVAILABLE_PLATFORMS.filter((platform) => done.has(platform)),
    };
  });
}

export function bytesByCategory(videos: LibraryVideo[]): Record<VideoCategory, number> {
  const totals: Record<VideoCategory, number> = { published: 0, draft: 0, unused: 0 };
  for (const video of videos) totals[video.category] += video.asset.sizeBytes;
  return totals;
}

export function sortVideos(videos: LibraryVideo[], sort: VideoSort): LibraryVideo[] {
  const compare: Record<VideoSort, (a: MediaAsset, b: MediaAsset) => number> = {
    newest: (a, b) => b.createdAt.localeCompare(a.createdAt),
    largest: (a, b) => b.sizeBytes - a.sizeBytes,
    name: (a, b) => a.filename.localeCompare(b.filename, undefined, { numeric: true }),
  };
  return [...videos].sort((a, b) => compare[sort](a.asset, b.asset));
}
