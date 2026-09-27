import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch, RootState } from '../../app/store';
import { SettingSelect } from '../../components/SettingSelect';
import { SettingSwitch } from '../../components/SettingSwitch';
import { setPlatformSettings } from '../../features/composer/composerSlice';
import { toSelectOptions } from '../selectOptions';
import { X_REPLY_AUDIENCE_OPTIONS, xSettingsOf, type XSettings } from './settings';

type DisclosureKey = 'madeWithAi' | 'paidPartnership' | 'superFollowersOnly';

const DISCLOSURES: DisclosureKey[] = ['madeWithAi', 'paidPartnership', 'superFollowersOnly'];

export function XSettingsPanel() {
  const { t } = useTranslation('platforms');
  const dispatch = useDispatch<AppDispatch>();
  const settings = xSettingsOf(
    useSelector((state: RootState) => state.composer.platformSettings.x),
  );
  const update = (patch: Partial<XSettings>) => {
    dispatch(setPlatformSettings({ platform: 'x', settings: patch }));
  };

  return (
    <div className="flex flex-col gap-4">
      <SettingSelect
        label={t('x.replyAudience.label')}
        value={settings.replyAudience}
        options={toSelectOptions(X_REPLY_AUDIENCE_OPTIONS, t)}
        onChange={(replyAudience) => update({ replyAudience })}
      />
      <div className="flex flex-col divide-y divide-separator">
        {DISCLOSURES.map((key) => (
          <SettingSwitch
            key={key}
            label={t(`x.${key}.label`)}
            description={t(`x.${key}.description`)}
            isSelected={settings[key]}
            onChange={(checked) => update({ [key]: checked })}
          />
        ))}
      </div>
    </div>
  );
}
