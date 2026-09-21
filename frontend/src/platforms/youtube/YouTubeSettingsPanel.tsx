import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch, RootState } from '../../app/store';
import { SettingSelect } from '../../components/SettingSelect';
import { SettingSwitch } from '../../components/SettingSwitch';
import { changePlatformSettings } from '../../features/composer/composerSlice';
import { toSelectOptions } from '../selectOptions';
import {
  YOUTUBE_CATEGORY_OPTIONS,
  YOUTUBE_LICENSE_OPTIONS,
  YOUTUBE_PRIVACY_OPTIONS,
  youtubeSettingsOf,
  type YouTubeSettings,
} from './settings';

type YouTubeToggleKey = {
  [K in keyof YouTubeSettings]: YouTubeSettings[K] extends boolean ? K : never;
}[keyof YouTubeSettings];

const SWITCH_KEYS: YouTubeToggleKey[] = [
  'madeForKids',
  'containsSyntheticMedia',
  'notifySubscribers',
  'hashtagsInDescription',
  'embeddable',
  'publicStatsViewable',
];

export function YouTubeSettingsPanel() {
  const { t } = useTranslation('platforms');
  const dispatch = useDispatch<AppDispatch>();
  const settings = youtubeSettingsOf(
    useSelector((state: RootState) => state.composer.platformSettings.youtube),
  );

  const update = (patch: Partial<YouTubeSettings>) => {
    dispatch(changePlatformSettings({ platform: 'youtube', settings: patch }));
  };

  return (
    <div className="flex flex-col gap-4">
      <SettingSelect
        label={t('youtube.privacy.label')}
        description={t('youtube.privacy.description')}
        value={settings.privacyStatus}
        options={toSelectOptions(YOUTUBE_PRIVACY_OPTIONS, t)}
        onChange={(privacyStatus) => update({ privacyStatus })}
      />
      <SettingSelect
        label={t('youtube.category.label')}
        value={settings.categoryId}
        options={toSelectOptions(YOUTUBE_CATEGORY_OPTIONS, t)}
        onChange={(categoryId) => update({ categoryId })}
      />
      <SettingSelect
        label={t('youtube.license.label')}
        value={settings.license}
        options={toSelectOptions(YOUTUBE_LICENSE_OPTIONS, t)}
        onChange={(license) => update({ license })}
      />
      <div className="flex flex-col divide-y divide-separator">
        {SWITCH_KEYS.map((key) => (
          <SettingSwitch
            key={key}
            label={t(`youtube.${key}.label`)}
            description={t(`youtube.${key}.description`)}
            isSelected={settings[key]}
            onChange={(checked) => update({ [key]: checked })}
          />
        ))}
      </div>
    </div>
  );
}
