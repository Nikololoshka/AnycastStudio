import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch, RootState } from '../../app/store';
import { PLATFORMS } from '../../domain/platform/order';
import { togglePlatform } from './composerSlice';

export function usePlatformShortcuts() {
  const dispatch = useDispatch<AppDispatch>();
  const accounts = useSelector((state: RootState) => state.accounts.items);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (!event.altKey || event.ctrlKey || event.metaKey) return;

      const platform = PLATFORMS.find((_, index) => event.code === `Digit${index + 1}`);
      if (!platform) return;

      const isConnected = Object.values(accounts).some((account) => account.platform === platform);
      if (!isConnected) return;

      event.preventDefault();
      dispatch(togglePlatform(platform));
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [accounts, dispatch]);
}
