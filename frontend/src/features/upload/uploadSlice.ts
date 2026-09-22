import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { UploadProgress, UploadSession } from '../../services/upload/chunkedUpload';

export type UploadStatus = 'idle' | 'hashing' | 'uploading' | 'done' | 'failed' | 'cancelled';

export interface UploadState {
  status: UploadStatus;
  uploadId?: string;
  uploadedBytes: number;
  totalBytes: number;
  percent: number;
  error?: string;

  /**
   * A transfer that was interrupted, usually by a reload. The browser loses the
   * File handle, so the person is asked for the same file again rather than
   * losing what already reached the server.
   */
  resumable?: UploadSession;
}

const initialState: UploadState = {
  status: 'idle',
  uploadedBytes: 0,
  totalBytes: 0,
  percent: 0,
};

const uploadSlice = createSlice({
  name: 'upload',
  initialState,
  reducers: {
    uploadStarted(state, action: PayloadAction<{ uploadId: string; totalBytes: number }>) {
      state.status = 'uploading';
      state.uploadId = action.payload.uploadId;
      state.totalBytes = action.payload.totalBytes;
      state.uploadedBytes = 0;
      state.percent = 0;
      state.error = undefined;
      state.resumable = undefined;
    },
    hashingStarted(state) {
      state.status = 'hashing';
      state.error = undefined;
    },
    uploadProgressed(state, action: PayloadAction<UploadProgress>) {
      state.status = 'uploading';
      state.uploadedBytes = action.payload.uploadedBytes;
      state.totalBytes = action.payload.totalBytes;
      state.percent = action.payload.percent;
    },
    uploadFinished(state) {
      state.status = 'done';
      state.percent = 100;
      state.resumable = undefined;
    },
    uploadFailed(state, action: PayloadAction<string>) {
      state.status = 'failed';
      state.error = action.payload;
    },
    uploadCancelled(state) {
      return { ...initialState, resumable: state.resumable };
    },
    resumeOffered(state, action: PayloadAction<UploadSession | undefined>) {
      state.resumable = action.payload;
    },
    uploadReset() {
      return initialState;
    },
  },
});

export const {
  hashingStarted,
  resumeOffered,
  uploadCancelled,
  uploadFailed,
  uploadFinished,
  uploadProgressed,
  uploadReset,
  uploadStarted,
} = uploadSlice.actions;

export default uploadSlice.reducer;
