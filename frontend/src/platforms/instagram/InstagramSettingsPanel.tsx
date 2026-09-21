import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch, RootState } from '../../app/store';
import { SettingNumber } from '../../components/SettingNumber';
import { SettingSwitch } from '../../components/SettingSwitch';
import { changePlatformSettings } from '../../features/composer/composerSlice';
import { instagramSettingsOf, type InstagramSettings } from './settings';

export function InstagramSettingsPanel() {
  const { t } = useTranslation('platforms');
  const dispatch = useDispatch<AppDispatch>();
  const settings = instagramSettingsOf(
    useSelector((state: RootState) => state.composer.platformSettings.instagram),
  );

  const update = (patch: Partial<InstagramSettings>) => {
    dispatch(changePlatformSettings({ platform: 'instagram', settings: patch }));
  };

  return (
    <div className="flex flex-col gap-4">
      <SettingSwitch
        label={t('instagram.shareToFeed.label')}
        description={t('instagram.shareToFeed.description')}
        isSelected={settings.shareToFeed}
        onChange={(shareToFeed) => update({ shareToFeed })}
      />
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
