import { baseApi } from './baseApi';

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
