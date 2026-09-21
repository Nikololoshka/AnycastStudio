import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch, RootState } from '../../app/store';
import { PLATFORMS } from '../../domain/platform/order';
import type { Platform } from '../../domain/platform/types';
import { togglePlatform } from '../../features/composer/composerSlice';
import { cancelScheduledPublication } from '../../features/publications';
import { UploadProgress } from './UploadProgress';
import { ROUTE_LINE_CLASSES, routeToneOf } from './routeTone';

export function UploadProgressList({
  selectedPlatforms,
  publicationId,
}: {
  selectedPlatforms: Platform[];
  publicationId?: string;
}) {
  const dispatch = useDispatch<AppDispatch>();
  const publication = useSelector((state: RootState) =>
    publicationId ? state.publications.items[publicationId] : undefined,
  );
  const accounts = useSelector((state: RootState) => state.accounts.items);

  const accountFor = (platform: Platform) =>
    Object.values(accounts).find((account) => account.platform === platform);

  const rows = PLATFORMS.filter(
    (platform) => accountFor(platform) || selectedPlatforms.includes(platform),
  ).map((platform) => {
    const upload = publication?.platforms.find((row) => row.platform === platform);
    const isEnabled = selectedPlatforms.includes(platform);

    return {
      platform,
      upload,
      isEnabled,
      account: accountFor(platform),
      tone: routeToneOf(upload?.status ?? 'idle', isEnabled),
    };
  });

  if (rows.length === 0) return null;

  const routeToneFrom = (index: number) =>
    rows.slice(index).find((row) => row.tone !== 'off')?.tone ?? 'off';

  return (
    <>
      <div
        aria-hidden
        className={`-mb-px ml-3 h-4 border-l-[1.5px] transition-colors duration-500 ${ROUTE_LINE_CLASSES[routeToneFrom(0)]}`}
      />
      <ul className="flex flex-col">
        {rows.map(({ platform, upload, isEnabled, account }, index) => (
          <UploadProgress
            key={platform}
            platform={platform}
            status={upload?.status ?? 'idle'}
            percent={upload?.progress}
            error={upload?.error}
            accountName={account?.displayName}
            scheduledAt={upload?.scheduledAt ?? publication?.scheduledAt}
            isEnabled={isEnabled}
            leadTone={routeToneFrom(index)}
            trailTone={routeToneFrom(index + 1)}
            onToggle={
              account && !publicationId ? () => dispatch(togglePlatform(platform)) : undefined
            }
            onCancelSchedule={
              publicationId && upload?.scheduledAt
                ? () => dispatch(cancelScheduledPublication({ id: publicationId, platform }))
                : undefined
            }
          />
        ))}
      </ul>
    </>
  );
}
