import { configureStore } from '@reduxjs/toolkit';
import { baseApi } from '../../api';
import composerReducer from '../../features/composer';
import settingsReducer from '../../features/settings';
import { persistMiddleware } from './persistMiddleware';

export const store = configureStore({
  reducer: {
    [baseApi.reducerPath]: baseApi.reducer,
    composer: composerReducer,
    settings: settingsReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware()
      .prepend(persistMiddleware.middleware)
      .concat(baseApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
