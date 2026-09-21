import { Alert } from '@heroui/react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch, RootState } from '../../app/store';
import { SettingNumber } from '../../components/SettingNumber';
import { SettingSwitch } from '../../components/SettingSwitch';
import { changePlatformSettings } from '../../features/composer/composerSlice';
import { tiktokSettingsOf, type TikTokSettings } from './settings';

type TikTokToggleKey = {
  [K in keyof TikTokSettings]: TikTokSettings[K] extends boolean ? K : never;
}[keyof TikTokSettings];

const SWITCH_KEYS: TikTokToggleKey[] = [
  'disableDuet',
  'disableComment',
  'disableStitch',
  'isAigc',
  'brandOrganicToggle',
];

export function TikTokSettingsPanel() {
  const { t } = useTranslation('platforms');
  const dispatch = useDispatch<AppDispatch>();
  const settings = tiktokSettingsOf(
    useSelector((state: RootState) => state.composer.platformSettings.tiktok),
  );

  const update = (patch: Partial<TikTokSettings>) => {
    dispatch(changePlatformSettings({ platform: 'tiktok', settings: patch }));
  };

  return (
    <div className="flex flex-col gap-4">
      <Alert status="warning">
        <Alert.Indicator />
        <Alert.Content>
          <Alert.Title>{t('tiktok.sandboxNotice.title')}</Alert.Title>
          <Alert.Description>{t('tiktok.sandboxNotice.description')}</Alert.Description>
        </Alert.Content>
      </Alert>
      <div className="flex flex-col divide-y divide-separator">
        {SWITCH_KEYS.map((key) => (
          <SettingSwitch
            key={key}
            label={t(`tiktok.${key}.label`)}
            description={t(`tiktok.${key}.description`)}
            isSelected={settings[key]}
            onChange={(checked) => update({ [key]: checked })}
          />
        ))}
      </div>
      <SettingNumber
        label={t('coverFrame.label')}
        description={t('coverFrame.description')}
        value={settings.coverFrameSeconds}
        minValue={0}
        step={1}
        onChange={(coverFrameSeconds) => update({ coverFrameSeconds })}
      />
    </div>
  );
}
