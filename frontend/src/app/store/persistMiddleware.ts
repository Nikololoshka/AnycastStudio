import { createListenerMiddleware, isAnyOf } from '@reduxjs/toolkit';
import { changeLanguage, changeTheme } from '../../features/settings';
import { setPlatformSettings } from '../../features/composer';
import { STORAGE_KEYS, writeStored } from '../../services/storage';
import type { RootState } from './index';

/**
 * Mirrors the slices that must survive a reload into browser storage.
 *
 * Reducers stay pure: the write happens here, after the state is already what
 * it should be, so what lands in storage is never a half-applied action.
 */
export const persistMiddleware = createListenerMiddleware();

persistMiddleware.startListening({
  matcher: isAnyOf(changeTheme, changeLanguage),
  effect: (_action, api) => {
    const { language, theme } = (api.getState() as RootState).settings;
    writeStored(STORAGE_KEYS.language, language);
    writeStored(STORAGE_KEYS.theme, theme);
  },
});

persistMiddleware.startListening({
  matcher: isAnyOf(setPlatformSettings),
  effect: (_action, api) => {
    writeStored(STORAGE_KEYS.platformSettings, (api.getState() as RootState).composer.platformSettings);
  },
});
