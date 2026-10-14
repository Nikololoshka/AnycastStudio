import type { ReactElement } from 'react';
import { Card, Chip, Disclosure, Switch } from '@heroui/react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router';
import { useGetAccountsQuery } from '../../api';
import type { AppDispatch, RootState } from '../../app/store';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { AVAILABLE_PLATFORMS, type AvailablePlatform } from '../../domain/platform/order';
import { InstagramSettingsPanel } from '../../platforms/instagram';
import { getLabelFor } from '../../platforms/registry';
import { TikTokSettingsPanel } from '../../platforms/tiktok';
import { XSettingsPanel } from '../../platforms/x';
import { YouTubeSettingsPanel } from '../../platforms/youtube';
import { togglePlatform } from './composerSlice';

const PLATFORM_PANELS: Record<AvailablePlatform, () => ReactElement> = {
  youtube: YouTubeSettingsPanel,
  tiktok: TikTokSettingsPanel,
  instagram: InstagramSettingsPanel,
  x: XSettingsPanel,
};

const PLATFORMS_LINK = 'text-[13px] font-medium text-accent hover:underline';

export function ComposerPlatformsCard() {
  const { t } = useTranslation('composer');
  const selectedPlatforms = useSelector((state: RootState) => state.composer.selectedPlatforms);

  return (
    <Card className="gap-1 rounded-[14px] bg-surface p-5 shadow-surface">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{t('platforms.title')}</h2>
        <Chip size="sm" variant="soft" color="accent">
          {t('platforms.selected', { count: selectedPlatforms.length })}
        </Chip>
      </div>
      <ul className="flex flex-col divide-y divide-separator">
        {AVAILABLE_PLATFORMS.map((platform) => (
          <PlatformRow
            key={platform}
            platform={platform}
            isSelected={selectedPlatforms.includes(platform)}
          />
        ))}
      </ul>
    </Card>
  );
}

function PlatformRow({
  platform,
  isSelected,
}: {
  platform: AvailablePlatform;
  isSelected: boolean;
}) {
  const { t } = useTranslation('composer');
  const dispatch = useDispatch<AppDispatch>();
  const { data: accounts } = useGetAccountsQuery();
  const account = accounts?.find((candidate) => candidate.platform === platform);
  const isUsable = Boolean(account && !account.needsReauth);
  const label = getLabelFor(platform);
  const SettingsPanel = PLATFORM_PANELS[platform];

  return (
    <li className="flex flex-col gap-2 py-3">
      <div className="flex items-center gap-3">
        <PlatformGlyph platform={platform} />
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-medium">{label}</span>
          {!account ? (
            <span className="text-xs text-muted">
              {t('platforms.notConnected')} ·{' '}
              <Link to="/platforms" className={PLATFORMS_LINK}>
                {t('platforms.connect')}
              </Link>
            </span>
          ) : account.needsReauth ? (
            <span className="text-xs text-danger">
              {t('platforms.expired')} ·{' '}
              <Link to="/platforms" className={PLATFORMS_LINK}>
                {t('platforms.reconnect')}
              </Link>
            </span>
          ) : (
            <span className="truncate text-xs text-muted">{account.displayName}</span>
          )}
        </div>
        <Switch
          aria-label={t('platforms.publishTo', { platform: label })}
          isSelected={isSelected}
          isDisabled={!isUsable && !isSelected}
          onChange={() => dispatch(togglePlatform(platform))}
        >
          <Switch.Control>
            <Switch.Thumb />
          </Switch.Control>
        </Switch>
      </div>

      {isSelected && (
        <Disclosure className="ml-12">
          <Disclosure.Heading>
            <Disclosure.Trigger className="flex w-full items-center gap-2 rounded-lg py-1 text-[13px] font-medium text-muted-strong hover:text-foreground">
              {t('platforms.settings', { platform: label })}
              <Disclosure.Indicator />
            </Disclosure.Trigger>
          </Disclosure.Heading>
          <Disclosure.Content>
            <Disclosure.Body className="pt-3 pb-1">
              <SettingsPanel />
            </Disclosure.Body>
          </Disclosure.Content>
        </Disclosure>
      )}
    </li>
  );
}
