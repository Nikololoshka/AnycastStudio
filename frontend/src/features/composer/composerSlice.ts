import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { PlatformSettings } from '../../domain/platform/types';
import type { AvailablePlatform } from '../../domain/platform/order';
import type { VideoFile } from '../../domain/video/types';
import type { Draft } from '../../api/draftsApi';
import { readPlatformDefaults } from '../../api/platformDefaultsApi';

export interface ComposerState {
  draftId?: string;

  video?: VideoFile;

  title: string;
  description: string;
  hashtags: string[];

  publishAt?: string;

  selectedPlatforms: AvailablePlatform[];

  platformSettings: Record<AvailablePlatform, PlatformSettings>;
}

export function isChangedFrom(settings: PlatformSettings, defaults?: PlatformSettings): boolean {
  if (!defaults) return false;
  return Object.keys(defaults).some(
    (key) => defaults[key] !== null && settings[key] !== defaults[key],
  );
}

function initialComposer(): ComposerState {
  const defaults = readPlatformDefaults();
  return {
    title: '',
    description: '',
    hashtags: [],
    selectedPlatforms: defaults.selected,
    platformSettings: defaults.settings,
  };
}

const composerSlice = createSlice({
  name: 'composer',
  initialState: initialComposer,
  reducers: {
    composerReset() {
      return initialComposer();
    },
    draftLoaded(_state, action: PayloadAction<Draft>) {
      const { id, updatedAt: _updatedAt, ...content } = action.payload;
      return { ...content, draftId: id };
    },
    draftSaved(state, action: PayloadAction<string>) {
      state.draftId = action.payload;
    },
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
  composerReset,
  draftLoaded,
  draftSaved,
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
