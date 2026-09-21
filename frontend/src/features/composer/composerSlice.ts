import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { PlatformSettings } from '../../domain/platform/types';
import type { AvailablePlatform } from '../../domain/platform/order';
import { AVAILABLE_PLATFORMS } from '../../domain/platform/order';
import type { VideoFile } from '../../domain/video/types';
import { defaultPlatformSettings, normalizeAllPlatformSettings } from '../../platforms/settings';
import { readStored, STORAGE_KEYS } from '../../services/storage';

/**
 * The publication being written. This is the one part of the application the
 * browser genuinely owns: it exists only until the person presses Publish,
 * after which the server holds it.
 */
export interface ComposerState {
  video?: VideoFile;

  title: string;
  description: string;
  hashtags: string[];

  publishAt?: string;

  selectedPlatforms: AvailablePlatform[];

  platformSettings: Record<AvailablePlatform, PlatformSettings>;
}

function initialComposer(): ComposerState {
  const stored = readStored<unknown>(STORAGE_KEYS.platformSettings);
  return {
    title: '',
    description: '',
    hashtags: [],
    selectedPlatforms: [...AVAILABLE_PLATFORMS],
    platformSettings: stored === undefined
      ? defaultPlatformSettings()
      : normalizeAllPlatformSettings(stored),
  };
}

const composerSlice = createSlice({
  name: 'composer',
  initialState: initialComposer,
  reducers: {
    setVideo(state, action: PayloadAction<VideoFile>) {
      state.video = action.payload;
    },
    clearVideo(state) {
      state.video = undefined;
    },
    setTitle(state, action: PayloadAction<string>) {
      state.title = action.payload;
    },
    setDescription(state, action: PayloadAction<string>) {
      state.description = action.payload;
    },
    setHashtags(state, action: PayloadAction<string[]>) {
      state.hashtags = action.payload;
    },
    setPublishAt(state, action: PayloadAction<string | undefined>) {
      state.publishAt = action.payload;
    },
    togglePlatform(state, action: PayloadAction<AvailablePlatform>) {
      const index = state.selectedPlatforms.indexOf(action.payload);
      if (index === -1) {
        state.selectedPlatforms.push(action.payload);
      } else {
        state.selectedPlatforms.splice(index, 1);
      }
    },
    setPlatformSettings(
      state,
      action: PayloadAction<{ platform: AvailablePlatform; settings: PlatformSettings }>,
    ) {
      const { platform, settings } = action.payload;
      state.platformSettings[platform] = { ...state.platformSettings[platform], ...settings };
    },
  },
});

export const {
  setVideo,
  clearVideo,
  setTitle,
  setDescription,
  setHashtags,
  setPublishAt,
  togglePlatform,
  setPlatformSettings,
} = composerSlice.actions;

export default composerSlice.reducer;
