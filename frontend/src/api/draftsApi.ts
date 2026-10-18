import { baseApi } from './baseApi';
import type { ComposerState } from '../features/composer/composerSlice';
import { readStored, STORAGE_KEYS, writeStored } from '../services/storage';

export type DraftContent = Omit<ComposerState, 'draftId' | 'dirty'>;

export interface Draft extends DraftContent {
  id: string;
  updatedAt: string;
}

function readDrafts(): Draft[] {
  return readStored<Draft[]>(STORAGE_KEYS.drafts) ?? [];
}

export const draftsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getDrafts: build.query<Draft[], void>({
      queryFn: () => ({ data: readDrafts() }),
      providesTags: ['Draft'],
    }),

    getDraft: build.query<Draft, string>({
      queryFn: (id) => {
        const draft = readDrafts().find((candidate) => candidate.id === id);
        return draft
          ? { data: draft }
          : {
              error: {
                status: 404,
                data: { status: 'not_found', message: `draft ${id} not found` },
              },
            };
      },
      providesTags: ['Draft'],
    }),

    saveDraft: build.mutation<Draft, DraftContent & { id?: string }>({
      queryFn: ({ id, ...content }) => {
        const draft: Draft = {
          ...content,
          id: id ?? crypto.randomUUID(),
          updatedAt: new Date().toISOString(),
        };
        writeStored(STORAGE_KEYS.drafts, [
          draft,
          ...readDrafts().filter((existing) => existing.id !== draft.id),
        ]);
        return { data: draft };
      },
      invalidatesTags: ['Draft'],
    }),

    deleteDraft: build.mutation<null, string>({
      queryFn: (id) => {
        writeStored(
          STORAGE_KEYS.drafts,
          readDrafts().filter((existing) => existing.id !== id),
        );
        return { data: null };
      },
      invalidatesTags: ['Draft'],
    }),
  }),
});

export const { useDeleteDraftMutation, useGetDraftQuery, useGetDraftsQuery, useSaveDraftMutation } =
  draftsApi;
