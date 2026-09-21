import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type { Platform, PlatformSettings } from '../../domain/platform/types';
import type { VideoFile } from '../../domain/video/types';
import type { RootState } from '../../app/store';
import { defaultPlatformSettings, normalizeAllPlatformSettings } from '../../platforms/settings';
import {
  loadPersistedPlatformSettings,
  savePersistedPlatformSettings,
} from '../../services/persistence';

export interface ComposerState {
  video?: VideoFile;

  title: string;
  description: string;
  hashtags: string[];

  scheduledAt?: string;

  selectedPlatforms: Platform[];

  platformSettings: Record<Platform, PlatformSettings>;
}

const initialState: ComposerState = {
  title: '',
  description: '',
  hashtags: [],
  selectedPlatforms: [],
  platformSettings: defaultPlatformSettings(),
};

export const restorePlatformSettings = createAsyncThunk<Record<Platform, PlatformSettings>>(
  'composer/restorePlatformSettings',
  async () => normalizeAllPlatformSettings(await loadPersistedPlatformSettings()),
);

export const changePlatformSettings = createAsyncThunk<
  void,
  { platform: Platform; settings: PlatformSettings }
>('composer/changePlatformSettings', async (payload, { dispatch, getState }) => {
  dispatch(setPlatformSettings(payload));
  await savePersistedPlatformSettings((getState() as RootState).composer.platformSettings);
});

const composerSlice = createSlice({
  name: 'composer',
  initialState,
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
    setScheduledAt(state, action: PayloadAction<string | undefined>) {
      state.scheduledAt = action.payload;
    },
    togglePlatform(state, action: PayloadAction<Platform>) {
      const platform = action.payload;
      const index = state.selectedPlatforms.indexOf(platform);
      if (index === -1) {
        state.selectedPlatforms.push(platform);
      } else {
        state.selectedPlatforms.splice(index, 1);
      }
    },
    setPlatformSettings(
      state,
      action: PayloadAction<{ platform: Platform; settings: PlatformSettings }>,
    ) {
      const { platform, settings } = action.payload;
      state.platformSettings[platform] = {
        ...state.platformSettings[platform],
        ...settings,
      };
    },
  },
  extraReducers: (builder) => {
    builder.addCase(restorePlatformSettings.fulfilled, (state, action) => {
      state.platformSettings = action.payload;
    });
  },
});

export const {
  setVideo,
  clearVideo,
  setTitle,
  setDescription,
  setHashtags,
  setScheduledAt,
  togglePlatform,
  setPlatformSettings,
} = composerSlice.actions;

export default composerSlice.reducer;
