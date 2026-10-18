import { baseApi } from './baseApi';
import { videoFileOf, type MediaAsset } from './mediaApi';
import type { ComposerState } from '../features/composer/composerSlice';
import { AVAILABLE_PLATFORMS, type AvailablePlatform } from '../domain/platform/order';
import type { PlatformSettings } from '../domain/platform/types';
import { normalizePlatformSettings } from '../platforms/settings';

export type DraftContent = Omit<ComposerState, 'draftId' | 'dirty'>;

export interface Draft extends DraftContent {
  id: number;
  updatedAt: string;
}

interface ServerDraft {
  id: number;
  video: MediaAsset | null;
  title: string;
  description: string;
  hashtags: string[];
  publishAt: string | null;
  selectedPlatforms: AvailablePlatform[];
  platformSettings: Partial<Record<AvailablePlatform, PlatformSettings>>;
  updatedAt: string;
}

interface DraftResponse {
  status: string;
  draft: ServerDraft;
}

interface DraftsResponse {
  status: string;
  drafts: ServerDraft[];
}

function draftOf(draft: ServerDraft): Draft {
  return {
    id: draft.id,
    updatedAt: draft.updatedAt,
    video: draft.video ? videoFileOf(draft.video) : undefined,
    title: draft.title,
    description: draft.description,
    hashtags: draft.hashtags,
    publishAt: draft.publishAt ?? undefined,
    selectedPlatforms: draft.selectedPlatforms,
    platformSettings: Object.fromEntries(
      AVAILABLE_PLATFORMS.map((platform) => [
        platform,
        normalizePlatformSettings(platform, draft.platformSettings[platform]),
      ]),
    ) as Record<AvailablePlatform, PlatformSettings>,
  };
}

function bodyOf(content: DraftContent) {
  return {
    mediaAssetId: content.video?.mediaAssetId ? Number(content.video.mediaAssetId) : null,
    title: content.title,
    description: content.description,
    hashtags: content.hashtags,
    publishAt: content.publishAt ?? null,
    selectedPlatforms: content.selectedPlatforms,
    platformSettings: content.platformSettings,
  };
}

export const draftsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getDrafts: build.query<Draft[], void>({
      query: () => '/drafts',
      transformResponse: (response: DraftsResponse) => response.drafts.map(draftOf),
      providesTags: ['Draft'],
    }),

    getDraft: build.query<Draft, number>({
      query: (id) => `/drafts/${id}`,
      transformResponse: (response: DraftResponse) => draftOf(response.draft),
      providesTags: ['Draft'],
    }),

    saveDraft: build.mutation<Draft, DraftContent & { id?: number }>({
      query: ({ id, ...content }) => ({
        url: id ? `/drafts/${id}/update` : '/drafts/create',
        method: 'POST',
        body: bodyOf(content),
      }),
      transformResponse: (response: DraftResponse) => draftOf(response.draft),
      invalidatesTags: ['Draft', 'MediaAsset'],
    }),

    deleteDraft: build.mutation<null, number>({
      query: (id) => ({ url: `/drafts/${id}/delete`, method: 'DELETE' }),
      transformResponse: () => null,
      invalidatesTags: ['Draft', 'MediaAsset'],
    }),
  }),
});

export const { useDeleteDraftMutation, useGetDraftQuery, useGetDraftsQuery, useSaveDraftMutation } =
  draftsApi;
