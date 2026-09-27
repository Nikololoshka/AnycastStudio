import { Separator } from '@heroui/react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { SettingSwitch } from '../../components/SettingSwitch';
import type { AppDispatch, RootState } from '../../app/store';
import type { AvailablePlatform } from '../../domain/platform/order';
import { getShortcutFor } from '../../domain/platform/order';
import { InstagramSettingsPanel } from '../../platforms/instagram';
import { getLabelFor } from '../../platforms/registry';
import { TikTokSettingsPanel } from '../../platforms/tiktok';
import { YouTubeSettingsPanel } from '../../platforms/youtube';
import { togglePlatform } from './composerSlice';

const PLATFORM_PANELS: Record<AvailablePlatform, () => React.ReactElement> = {
  youtube: YouTubeSettingsPanel,
  tiktok: TikTokSettingsPanel,
  instagram: InstagramSettingsPanel,
};

export function PlatformTab({ platform }: { platform: AvailablePlatform }) {
  const { t } = useTranslation('composer');
  const dispatch = useDispatch<AppDispatch>();
  const selectedPlatforms = useSelector((state: RootState) => state.composer.selectedPlatforms);
  const SettingsPanel = PLATFORM_PANELS[platform];
  const label = getLabelFor(platform);

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-2xl border border-border bg-surface-secondary p-5">
        <SettingSwitch
          label={t('platformTab.publishTo', { platform: label })}
          description={t('platformTab.publishToHint', {
            platform: label,
            shortcut: getShortcutFor(platform),
          })}
          isSelected={selectedPlatforms.includes(platform)}
          onChange={() => dispatch(togglePlatform(platform))}
        />
      </div>

      <Separator />

      <section className="flex flex-col gap-3 px-1">
        <h2 className="font-display text-base font-semibold tracking-tight">
          {t('platformTab.options', { platform: label })}
        </h2>
        <SettingsPanel />
      </section>
    </div>
  );
}
