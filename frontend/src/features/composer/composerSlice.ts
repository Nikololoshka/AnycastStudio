import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { PlatformSettings } from '../../domain/platform/types';
import type { AvailablePlatform } from '../../domain/platform/order';
import type { VideoFile } from '../../domain/video/types';
import type { Draft } from '../../api/draftsApi';
import { platformDefaultsApi, readPlatformDefaults } from '../../api/platformDefaultsApi';

export interface ComposerState {
  draftId?: string;

  video?: VideoFile;

  title: string;
  description: string;
  hashtags: string[];

  publishAt?: string;

  selectedPlatforms: AvailablePlatform[];

  platformSettings: Record<AvailablePlatform, PlatformSettings>;

  dirty: boolean;
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
    dirty: false,
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
      return { ...content, draftId: id, dirty: false };
    },
    draftSaved(state, action: PayloadAction<string>) {
      state.draftId = action.payload;
      state.dirty = false;
    },
    setVideo(state, action: PayloadAction<VideoFile>) {
      state.video = action.payload;
      state.dirty = true;
    },
    clearVideo(state) {
      state.video = undefined;
      state.dirty = true;
    },
    publicationCreated(state) {
      state.video = undefined;
      state.dirty = false;
    },
    setTitle(state, action: PayloadAction<string>) {
      state.title = action.payload;
      state.dirty = true;
    },
    setDescription(state, action: PayloadAction<string>) {
      state.description = action.payload;
      state.dirty = true;
    },
    setHashtags(state, action: PayloadAction<string[]>) {
      state.hashtags = action.payload;
      state.dirty = true;
    },
    setPublishAt(state, action: PayloadAction<string | undefined>) {
      state.publishAt = action.payload;
      state.dirty = true;
    },
    togglePlatform(state, action: PayloadAction<AvailablePlatform>) {
      const index = state.selectedPlatforms.indexOf(action.payload);
      if (index === -1) {
        state.selectedPlatforms.push(action.payload);
      } else {
        state.selectedPlatforms.splice(index, 1);
      }
      state.dirty = true;
    },
    setPlatformSettings(
      state,
      action: PayloadAction<{ platform: AvailablePlatform; settings: PlatformSettings }>,
    ) {
      const { platform, settings } = action.payload;
      state.platformSettings[platform] = { ...state.platformSettings[platform], ...settings };
      state.dirty = true;
    },
  },
  extraReducers: (builder) => {
    builder.addMatcher(
      platformDefaultsApi.endpoints.updatePlatformDefaults.matchFulfilled,
      (state, action) => {
        if (state.draftId || state.dirty) return;
        state.selectedPlatforms = action.payload.selected;
        state.platformSettings = action.payload.settings;
      },
    );
  },
});

export const {
  composerReset,
  draftLoaded,
  draftSaved,
  setVideo,
  clearVideo,
  publicationCreated,
  setTitle,
  setDescription,
  setHashtags,
  setPublishAt,
  togglePlatform,
  setPlatformSettings,
} = composerSlice.actions;

export default composerSlice.reducer;
