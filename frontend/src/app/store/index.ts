import { configureStore } from '@reduxjs/toolkit';
import accountsReducer from '../../features/accounts';
import composerReducer from '../../features/composer';
import publicationsReducer from '../../features/publications';
import settingsReducer from '../../features/settings';
import { loggingMiddleware } from './loggingMiddleware';

export const store = configureStore({
  reducer: {
    accounts: accountsReducer,
    composer: composerReducer,
    publications: publicationsReducer,
    settings: settingsReducer,
  },
  middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(loggingMiddleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
