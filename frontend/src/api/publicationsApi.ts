import { baseApi } from './baseApi';
import type { Platform, PlatformCapabilities } from '../domain/platform/types';
import type { PublicationError, PublicationStatus } from '../domain/publication/types';

export interface PublicationTarget {
  id: number;
  platform: Platform;
  socialAccountId: number;
  settings: Record<string, unknown>;
  status: PublicationStatus;
  progress: number;
  uploadedBytes: number;
  totalBytes: number;
  publishedUrl: string;
  error: PublicationError | null;
  attemptCount: number;
  isActive: boolean;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface Publication {
  id: number;
  title: string;
  description: string;
  hashtags: string[];
  publishAt: string | null;
  createdAt: string;
  mediaAssetId: number;
  filename: string;
  targets: PublicationTarget[];
  /** True while anything is still running; the browser polls only until then. */
  isActive: boolean;
}

export interface CreatePublicationBody {
  mediaAssetId: number;
  title: string;
  description: string;
  hashtags: string[];
  publishAt?: string;
  targets: { platform: Platform; socialAccountId: number; settings: Record<string, unknown> }[];
}

interface PublicationResponse {
  status: string;
  publication: Publication;
}

interface PublicationsResponse {
  status: string;
  publications: Publication[];
}

interface PlatformsResponse {
  status: string;
  platforms: Record<string, PlatformCapabilities>;
}

export const publicationsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getPublications: build.query<Publication[], void>({
      query: () => '/publications',
      transformResponse: (response: PublicationsResponse) => response.publications,
      providesTags: ['Publication'],
    }),

    getPublication: build.query<Publication, number>({
      query: (id) => `/publications/${id}`,
      transformResponse: (response: PublicationResponse) => response.publication,
      providesTags: ['Publication'],
    }),

    createPublication: build.mutation<Publication, CreatePublicationBody>({
      query: (body) => ({ url: '/publications/create', method: 'POST', body }),
      transformResponse: (response: PublicationResponse) => response.publication,
      invalidatesTags: ['Publication', 'MediaAsset'],
    }),

    cancelTarget: build.mutation<Publication, number>({
      query: (id) => ({ url: `/targets/${id}/cancel`, method: 'POST' }),
      transformResponse: (response: PublicationResponse) => response.publication,
      invalidatesTags: ['Publication'],
    }),

    retryTarget: build.mutation<Publication, number>({
      query: (id) => ({ url: `/targets/${id}/retry`, method: 'POST' }),
      transformResponse: (response: PublicationResponse) => response.publication,
      invalidatesTags: ['Publication'],
    }),

    getPlatforms: build.query<Record<string, PlatformCapabilities>, void>({
      query: () => '/platforms',
      transformResponse: (response: PlatformsResponse) => response.platforms,
    }),
  }),
});

export const {
  useCancelTargetMutation,
  useCreatePublicationMutation,
  useGetPlatformsQuery,
  useGetPublicationQuery,
  useGetPublicationsQuery,
  useRetryTargetMutation,
} = publicationsApi;

/**
 * How often to ask again.
 *
 * Polling rather than a live connection: two seconds of latency on a progress
 * bar costs nothing, and a server-sent stream would mean an async view, a
 * pub/sub channel and proxy buffering rules for the same result.
 */
export const ACTIVE_POLL_MS = 2000;
