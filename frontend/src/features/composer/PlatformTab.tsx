import type { ReactElement } from 'react';
import { Separator } from '@heroui/react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { PlatformAccountConnector } from '../../components/PlatformAccountConnector';
import { SettingSwitch } from '../../components/SettingSwitch';
import type { AppDispatch, RootState } from '../../app/store';
import type { Platform } from '../../domain/platform/types';
import { getLabelFor } from '../../platforms/capabilities';
import { getShortcutFor } from '../../domain/platform/order';
import { selectAccountByPlatform } from '../accounts/accountsSlice';
import { YouTubeSettingsPanel } from '../../platforms/youtube';
import { XSettingsPanel } from '../../platforms/x';
import { InstagramSettingsPanel } from '../../platforms/instagram';
import { TikTokSettingsPanel } from '../../platforms/tiktok';
import { togglePlatform } from './composerSlice';

const PLATFORM_PANELS: Record<Platform, () => ReactElement> = {
  youtube: YouTubeSettingsPanel,
  x: XSettingsPanel,
  instagram: InstagramSettingsPanel,
  tiktok: TikTokSettingsPanel,
};

export function PlatformTab({ platform }: { platform: Platform }) {
  const { t } = useTranslation('composer');
  const dispatch = useDispatch<AppDispatch>();
  const account = useSelector((state: RootState) => selectAccountByPlatform(state, platform));
  const selectedPlatforms = useSelector((state: RootState) => state.composer.selectedPlatforms);
  const SettingsPanel = PLATFORM_PANELS[platform];
  const label = getLabelFor(platform);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 rounded-2xl border border-border bg-surface-secondary p-5">
        <PlatformAccountConnector platform={platform} />
        <Separator />
        <SettingSwitch
          label={t('platformTab.publishTo', { platform: label })}
          description={
            account
              ? t('platformTab.publishToHint', {
                  platform: label,
                  shortcut: getShortcutFor(platform),
                })
              : t('platformTab.connectHint', { platform: label })
          }
          isSelected={selectedPlatforms.includes(platform)}
          isDisabled={!account}
          onChange={() => dispatch(togglePlatform(platform))}
        />
      </div>

      <section className="flex flex-col gap-3 px-1">
        <h2 className="font-display text-base font-semibold tracking-tight">
          {t('platformTab.options', { platform: label })}
        </h2>
        <SettingsPanel />
      </section>
    </div>
  );
}
