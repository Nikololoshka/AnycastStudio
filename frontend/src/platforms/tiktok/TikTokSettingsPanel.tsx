import { Alert, Spinner } from '@heroui/react';
import { skipToken } from '@reduxjs/toolkit/query';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { useGetAccountsQuery, useGetCreatorInfoQuery, type CreatorInfo } from '../../api';
import type { AppDispatch, RootState } from '../../app/store';
import { SettingNumber } from '../../components/SettingNumber';
import { SettingSelect } from '../../components/SettingSelect';
import { SettingSwitch } from '../../components/SettingSwitch';
import { setPlatformSettings } from '../../features/composer/composerSlice';
import { toSelectOptions } from '../selectOptions';
import {
  TIKTOK_PRIVACY_OPTIONS,
  tiktokSettingsOf,
  type TikTokPrivacy,
  type TikTokSettings,
} from './settings';

type InteractionKey = 'disableComment' | 'disableDuet' | 'disableStitch';

const INTERACTIONS: { key: InteractionKey; turnedOffBy: keyof CreatorInfo }[] = [
  { key: 'disableComment', turnedOffBy: 'commentDisabled' },
  { key: 'disableDuet', turnedOffBy: 'duetDisabled' },
  { key: 'disableStitch', turnedOffBy: 'stitchDisabled' },
];

function useTikTokSettings() {
  const dispatch = useDispatch<AppDispatch>();
  const settings = tiktokSettingsOf(
    useSelector((state: RootState) => state.composer.platformSettings.tiktok),
  );
  const update = (patch: Partial<TikTokSettings>) => {
    dispatch(setPlatformSettings({ platform: 'tiktok', settings: patch }));
  };
  return { settings, update };
}

function disclosureHintKey(settings: TikTokSettings) {
  if (settings.brandContent) return 'tiktok.disclosure.paidPartnership' as const;
  if (settings.brandOrganic) return 'tiktok.disclosure.promotional' as const;
  return 'tiktok.disclosure.chooseOne' as const;
}

function isOffered(value: TikTokPrivacy, creator: CreatorInfo, isBranded: boolean): boolean {
  return creator.privacyLevelOptions.includes(value) && !(isBranded && value === 'SELF_ONLY');
}

function CreatorSettings({ creator }: { creator: CreatorInfo }) {
  const { t } = useTranslation('platforms');
  const { settings, update } = useTikTokSettings();
  const duration = useSelector((state: RootState) => state.composer.video?.duration);

  const isBranded = settings.discloseContent && settings.brandContent;
  const privacyOptions = TIKTOK_PRIVACY_OPTIONS.filter(({ value }) =>
    isOffered(value, creator, isBranded),
  );
  const limit = creator.maxVideoPostDurationSec;
  const isTooLong = Boolean(limit && duration && duration > limit);

  const setBrandContent = (brandContent: boolean) => {
    const leavesPrivateBranded = brandContent && settings.privacyLevel === 'SELF_ONLY';
    update(leavesPrivateBranded ? { brandContent, privacyLevel: null } : { brandContent });
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted">
        {t('tiktok.creator.postingAs', { name: creator.nickname || creator.username })}
      </p>

      {isTooLong && (
        <Alert status="warning">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Title>{t('tiktok.creator.tooLong', { seconds: limit })}</Alert.Title>
          </Alert.Content>
        </Alert>
      )}

      <SettingSelect
        label={t('tiktok.privacy.label')}
        description={t('tiktok.privacy.description')}
        placeholder={t('tiktok.privacy.placeholder')}
        value={settings.privacyLevel}
        options={toSelectOptions(privacyOptions, t)}
        onChange={(privacyLevel) => update({ privacyLevel })}
      />

      <div className="flex flex-col divide-y divide-separator">
        {INTERACTIONS.map(({ key, turnedOffBy }) => {
          const isTurnedOff = Boolean(creator[turnedOffBy]);
          return (
            <SettingSwitch
              key={key}
              label={t(`tiktok.${key}.label`)}
              description={
                isTurnedOff ? t('tiktok.creator.turnedOff') : t(`tiktok.${key}.description`)
              }
              isSelected={settings[key] || isTurnedOff}
              isDisabled={isTurnedOff}
              onChange={(checked) => update({ [key]: checked })}
            />
          );
        })}
        <SettingSwitch
          label={t('tiktok.isAigc.label')}
          description={t('tiktok.isAigc.description')}
          isSelected={settings.isAigc}
          onChange={(isAigc) => update({ isAigc })}
        />
      </div>

      <section className="flex flex-col gap-1 rounded-xl border border-border px-4 py-2">
        <SettingSwitch
          label={t('tiktok.discloseContent.label')}
          description={t('tiktok.discloseContent.description')}
          isSelected={settings.discloseContent}
          onChange={(discloseContent) => update({ discloseContent })}
        />
        {settings.discloseContent && (
          <div className="flex flex-col divide-y divide-separator border-t border-separator">
            <SettingSwitch
              label={t('tiktok.brandOrganic.label')}
              description={t('tiktok.brandOrganic.description')}
              isSelected={settings.brandOrganic}
              onChange={(brandOrganic) => update({ brandOrganic })}
            />
            <SettingSwitch
              label={t('tiktok.brandContent.label')}
              description={t('tiktok.brandContent.description')}
              isSelected={settings.brandContent}
              onChange={setBrandContent}
            />
            <p className="py-2 text-xs text-muted">{t(disclosureHintKey(settings))}</p>
          </div>
        )}
      </section>

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

export function TikTokSettingsPanel() {
  const { t } = useTranslation('platforms');
  const { data: accounts } = useGetAccountsQuery();
  const account = accounts?.find(
    (candidate) => candidate.platform === 'tiktok' && !candidate.needsReauth,
  );
  const { data: creator, isLoading, isError } = useGetCreatorInfoQuery(account?.id ?? skipToken);

  if (!account) {
    return <p className="text-sm text-muted">{t('tiktok.creator.notConnected')}</p>;
  }
  if (isLoading) {
    return <Spinner size="sm" />;
  }
  if (isError || !creator) {
    return (
      <Alert status="danger">
        <Alert.Indicator />
        <Alert.Content>
          <Alert.Title>{t('tiktok.creator.unavailable')}</Alert.Title>
        </Alert.Content>
      </Alert>
    );
  }
  return <CreatorSettings creator={creator} />;
}
