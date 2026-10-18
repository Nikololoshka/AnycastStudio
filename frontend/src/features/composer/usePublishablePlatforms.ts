import { useSelector } from 'react-redux';
import { useGetAccountsQuery } from '../../api';
import type { RootState } from '../../app/store';
import type { AvailablePlatform } from '../../domain/platform/order';

export function usePublishablePlatforms(): AvailablePlatform[] {
  const selectedPlatforms = useSelector((state: RootState) => state.composer.selectedPlatforms);
  const { data: accounts } = useGetAccountsQuery();
  return selectedPlatforms.filter((platform) =>
    accounts?.some((account) => account.platform === platform && !account.needsReauth),
  );
}
