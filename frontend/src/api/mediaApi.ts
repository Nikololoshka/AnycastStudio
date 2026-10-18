import { baseApi } from './baseApi';
import type { VideoFile } from '../domain/video/types';

const API_URL = import.meta.env.VITE_API_URL ?? '';

export interface MediaAsset {
  id: number;
  filename: string;
  mimeType: string;
  sizeBytes: number;
  durationSeconds: number | null;
  width: number | null;
  height: number | null;
  status: string;
  createdAt: string;
  thumbnailUrl: string | null;
}

export function videoFileOf(asset: MediaAsset): VideoFile {
  return {
    id: String(asset.id),
    name: asset.filename,
    size: asset.sizeBytes,
    mimeType: asset.mimeType,
    duration: asset.durationSeconds ?? undefined,
    width: asset.width ?? undefined,
    height: asset.height ?? undefined,
    thumbnailUrl: asset.thumbnailUrl ? `${API_URL}${asset.thumbnailUrl}` : undefined,
    mediaAssetId: String(asset.id),
  };
}

export interface MediaLibrary {
  assets: MediaAsset[];
  usedBytes: number;
  quotaBytes: number;
}

interface MediaAssetsResponse extends MediaLibrary {
  status: string;
}

export const mediaApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getMediaAssets: build.query<MediaLibrary, void>({
      query: () => '/media/assets',
      transformResponse: ({ assets, usedBytes, quotaBytes }: MediaAssetsResponse) => ({
        assets,
        usedBytes,
        quotaBytes,
      }),
      providesTags: ['MediaAsset'],
    }),

    deleteMediaAsset: build.mutation<void, number>({
      query: (id) => ({ url: `/media/assets/${id}`, method: 'DELETE' }),
      invalidatesTags: ['MediaAsset'],
    }),
  }),
});

export const { useDeleteMediaAssetMutation, useGetMediaAssetsQuery } = mediaApi;
