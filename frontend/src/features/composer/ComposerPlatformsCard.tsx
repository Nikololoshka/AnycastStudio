import { useState } from 'react';
import { Button, Chip, Switch } from '@heroui/react';
import { SlidersHorizontal } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router';
import { useGetAccountsQuery, useGetPlatformDefaultsQuery } from '../../api';
import type { AppDispatch, RootState } from '../../app/store';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { AVAILABLE_PLATFORMS, type AvailablePlatform } from '../../domain/platform/order';
import { getLabelFor } from '../../platforms/registry';
import { toSelectOptions } from '../../platforms/selectOptions';
import { YOUTUBE_PRIVACY_OPTIONS, youtubeSettingsOf } from '../../platforms/youtube';
import { isChangedFrom, togglePlatform } from './composerSlice';
import { PlatformSettingsDrawer } from './PlatformSettingsDrawer';
import { usePublishablePlatforms } from './usePublishablePlatforms';

export function ComposerPlatformsCard() {
  const { t } = useTranslation('composer');
  const selectedPlatforms = usePublishablePlatforms();
  const [openPlatform, setOpenPlatform] = useState<AvailablePlatform>();
  const visiblePlatform =
    openPlatform && selectedPlatforms.includes(openPlatform) ? openPlatform : undefined;

  return (
    <section aria-labelledby="platforms-heading" className="flex flex-col gap-3">
      <h2 id="platforms-heading" className="text-lg font-semibold">
        {t('platforms.title')}
      </h2>
      <ul className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3">
        {AVAILABLE_PLATFORMS.map((platform) => (
          <PlatformCard
            key={platform}
            platform={platform}
            isSelected={selectedPlatforms.includes(platform)}
            isOpen={visiblePlatform === platform}
            onConfigure={() => setOpenPlatform(platform)}
          />
        ))}
      </ul>

      <PlatformSettingsDrawer
        platform={visiblePlatform}
        onSelect={setOpenPlatform}
        onClose={() => setOpenPlatform(undefined)}
      />
    </section>
  );
}

function PlatformCard({
  platform,
  isSelected,
  isOpen,
  onConfigure,
}: {
  platform: AvailablePlatform;
  isSelected: boolean;
  isOpen: boolean;
  onConfigure: () => void;
}) {
  const { t } = useTranslation('composer');
  const dispatch = useDispatch<AppDispatch>();
  const { data: accounts } = useGetAccountsQuery();
  const account = accounts?.find((candidate) => candidate.platform === platform);
  const isUsable = Boolean(account && !account.needsReauth);
  const label = getLabelFor(platform);

  return (
    <li
      className={[
        'flex flex-col gap-3 rounded-[14px] bg-surface p-3.5 shadow-surface',
        isOpen ? 'ring-2 ring-accent' : '',
      ].join(' ')}
    >
      <div className={['flex items-center gap-2.5', isSelected ? '' : 'opacity-60'].join(' ')}>
        <PlatformGlyph platform={platform} />
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-medium">{label}</span>
          {!account ? (
            <span className="text-xs text-muted">{t('platforms.notConnected')}</span>
          ) : account.needsReauth ? (
            <span className="text-xs text-danger">{t('platforms.expired')}</span>
          ) : (
            <span className="truncate text-xs text-muted">{account.displayName}</span>
          )}
        </div>
        <Switch
          aria-label={t('platforms.publishTo', { platform: label })}
          isSelected={isSelected}
          isDisabled={!isUsable}
          onChange={() => dispatch(togglePlatform(platform))}
        >
          <Switch.Content>
            <Switch.Control>
              <Switch.Thumb />
            </Switch.Control>
          </Switch.Content>
        </Switch>
      </div>

      <PlatformSummary platform={platform} isSelected={isSelected} />

      <div className="mt-auto flex flex-col gap-2">
        {isSelected && (
          <Button
            variant="secondary"
            size="sm"
            className="w-full"
            aria-label={t('platforms.configureAria', { platform: label })}
            onPress={onConfigure}
          >
            <SlidersHorizontal className="size-4" />
            {t('platforms.configure')}
          </Button>
        )}
        {account?.needsReauth && (
          <Link
            to="/platforms"
            className="grid h-8 place-items-center rounded-xl bg-danger-soft text-sm font-medium text-danger-soft-foreground"
          >
            {t('platforms.reconnect')}
          </Link>
        )}
      </div>
    </li>
  );
}

function PlatformSummary({
  platform,
  isSelected,
}: {
  platform: AvailablePlatform;
  isSelected: boolean;
}) {
  const { t } = useTranslation('composer');
  const { t: tPlatforms } = useTranslation('platforms');
  const settings = useSelector((state: RootState) => state.composer.platformSettings[platform]);
  const { data: defaults } = useGetPlatformDefaultsQuery();

  if (!isSelected) {
    return (
      <div className="flex min-h-6 flex-wrap gap-1">
        <Chip size="sm" variant="soft">
          {t('platforms.chip.skipped')}
        </Chip>
      </div>
    );
  }

  const youtubePrivacy =
    platform === 'youtube'
      ? toSelectOptions(YOUTUBE_PRIVACY_OPTIONS, tPlatforms).find(
          (option) => option.value === youtubeSettingsOf(settings).privacyStatus,
        )?.label
      : undefined;

  return (
    <div className="flex min-h-6 flex-wrap gap-1">
      {youtubePrivacy && (
        <Chip size="sm" variant="soft">
          {youtubePrivacy}
        </Chip>
      )}
      {platform === 'tiktok' && settings.privacyLevel == null && (
        <Chip size="sm" variant="soft" color="warning">
          {t('platforms.chip.needsPrivacy')}
        </Chip>
      )}
      {isChangedFrom(settings, defaults?.settings[platform]) ? (
        <Chip size="sm" variant="soft" color="warning">
          {t('platforms.chip.changed')}
        </Chip>
      ) : (
        <Chip size="sm" variant="soft">
          {t('platforms.chip.defaults')}
        </Chip>
      )}
    </div>
  );
}
