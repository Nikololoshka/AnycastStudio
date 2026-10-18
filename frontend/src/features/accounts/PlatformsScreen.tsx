import { useEffect, useState } from 'react';
import { Alert, Avatar, Button, Chip, ListBox, Spinner } from '@heroui/react';
import { Info, Plug } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch } from 'react-redux';
import { useSearchParams } from 'react-router';
import {
  accountsApi,
  useDisconnectAccountMutation,
  useGetAccountsQuery,
  useGetPlatformDefaultsQuery,
  useStartConnectMutation,
  useUpdatePlatformDefaultsMutation,
  type ConnectedAccount,
} from '../../api';
import type { AppDispatch } from '../../app/store';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { SettingSelect } from '../../components/SettingSelect';
import { SettingSwitch } from '../../components/SettingSwitch';
import { AVAILABLE_PLATFORMS, type AvailablePlatform } from '../../domain/platform/order';
import { getLabelFor } from '../../platforms/registry';
import { toSelectOptions } from '../../platforms/selectOptions';
import { YOUTUBE_PRIVACY_OPTIONS, youtubeSettingsOf } from '../../platforms/youtube';

const CONNECT_CHANNEL = 'anycast-connect';
const CLOSE_POPUP = 'close';
const POPUP_FEATURES = 'popup,width=520,height=720';

const OUTCOMES = ['connected', 'cancelled', 'failed', 'invalid'] as const;

type Outcome = (typeof OUTCOMES)[number];

type State = 'connected' | 'needsReauth' | 'none';

const CHIP: Record<State, 'success' | 'danger' | 'default'> = {
  connected: 'success',
  needsReauth: 'danger',
  none: 'default',
};

function toOutcome(value: string | null): Outcome | undefined {
  return OUTCOMES.find((outcome) => outcome === value);
}

function toPlatform(value: string | null): AvailablePlatform {
  return AVAILABLE_PLATFORMS.find((platform) => platform === value) ?? AVAILABLE_PLATFORMS[0];
}

function stateOf(account?: ConnectedAccount): State {
  if (!account) return 'none';
  return account.needsReauth ? 'needsReauth' : 'connected';
}

export function AccountStateChip({ account }: { account?: ConnectedAccount }) {
  const { t } = useTranslation('accounts');
  const state = stateOf(account);
  return (
    <Chip size="sm" variant="soft" color={CHIP[state]}>
      {t(`state.${state}`)}
    </Chip>
  );
}

function useConnectPopupChannel() {
  const dispatch = useDispatch<AppDispatch>();
  const [params, setParams] = useSearchParams();
  const [landedWith] = useState(() => (toOutcome(params.get('result')) ? params.toString() : ''));

  useEffect(() => {
    const channel = new BroadcastChannel(CONNECT_CHANNEL);
    channel.onmessage = ({ data }: MessageEvent<string>) => {
      if (data === CLOSE_POPUP) {
        if (landedWith) window.close();
        return;
      }
      setParams(new URLSearchParams(data), { replace: true });
      dispatch(accountsApi.util.invalidateTags(['Account']));
      channel.postMessage(CLOSE_POPUP);
    };
    if (landedWith) channel.postMessage(landedWith);
    return () => channel.close();
  }, [dispatch, setParams, landedWith]);
}

function CallbackNotice() {
  const { t } = useTranslation('accounts');
  const [params, setParams] = useSearchParams();
  const outcome = toOutcome(params.get('result'));

  useEffect(() => {
    if (!outcome) return;
    const next = new URLSearchParams(params);
    next.delete('result');
    setParams(next, { replace: true });
  }, [outcome, params, setParams]);

  const [shown, setShown] = useState(outcome);
  if (outcome && outcome !== shown) setShown(outcome);
  if (!shown) return null;

  const isGood = shown === 'connected';

  return (
    <Alert status={isGood ? 'success' : 'danger'} role="status">
      <Alert.Indicator />
      <Alert.Content>
        <Alert.Title>{t(`callback.${shown}`)}</Alert.Title>
      </Alert.Content>
    </Alert>
  );
}

function PlatformDetail({
  platform,
  account,
}: {
  platform: AvailablePlatform;
  account?: ConnectedAccount;
}) {
  const { t, i18n } = useTranslation('accounts');
  const [startConnect, { isLoading: isConnecting, isError: connectFailed }] =
    useStartConnectMutation();
  const [disconnect, { isLoading: isDisconnecting }] = useDisconnectAccountMutation();
  const [isConfirming, setIsConfirming] = useState(false);
  const label = getLabelFor(platform);

  async function connect() {
    const popup = window.open('', CONNECT_CHANNEL, POPUP_FEATURES);
    if (popup) popup.opener = null;
    const { data: authUrl } = await startConnect(platform);
    if (!authUrl) {
      popup?.close();
      return;
    }
    if (popup) popup.location.assign(authUrl);
    else window.location.assign(authUrl);
  }

  async function confirmDisconnect() {
    if (account) await disconnect(account.id);
    setIsConfirming(false);
  }

  return (
    <section
      aria-labelledby="platform-heading"
      className="flex min-w-0 flex-[2_1_460px] flex-col gap-5 rounded-[14px] bg-surface p-6 shadow-surface"
    >
      <div className="flex flex-wrap items-center gap-3.5">
        <PlatformGlyph platform={platform} size="lg" />
        <div className="min-w-40 flex-1">
          <h2 id="platform-heading" className="text-xl font-semibold">
            {label}
          </h2>
          {account ? (
            <p className="flex items-center gap-2 text-sm text-muted">
              {account.avatarUrl && (
                <Avatar size="sm" className="size-5">
                  <Avatar.Image src={account.avatarUrl} alt="" />
                  <Avatar.Fallback>{account.displayName.charAt(0)}</Avatar.Fallback>
                </Avatar>
              )}
              <span className="truncate">{account.displayName}</span>
              <span aria-hidden>·</span>
              <span className="whitespace-nowrap">
                {t('detail.connectedAt', {
                  date: new Date(account.connectedAt).toLocaleDateString(i18n.language, {
                    day: 'numeric',
                    month: 'long',
                    year: 'numeric',
                  }),
                })}
              </span>
            </p>
          ) : (
            <p className="text-sm text-muted">{t('state.none')}</p>
          )}
        </div>
        {account ? (
          <Button
            variant="danger-soft"
            isDisabled={isDisconnecting}
            onPress={() => setIsConfirming(true)}
          >
            {t('actions.disconnect')}
          </Button>
        ) : (
          <Button variant="primary" isDisabled={isConnecting} onPress={() => void connect()}>
            <Plug className="size-4" />
            {t('actions.connect')}
          </Button>
        )}
      </div>

      {connectFailed && (
        <Alert status="danger" role="alert">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Description>{t('detail.connectFailed', { platform: label })}</Alert.Description>
          </Alert.Content>
        </Alert>
      )}

      {account?.needsReauth && (
        <Alert status="danger">
          <Alert.Indicator />
          <Alert.Content>
            <Alert.Description>{t('detail.expired', { platform: label })}</Alert.Description>
          </Alert.Content>
          <Button
            size="sm"
            variant="danger"
            isDisabled={isConnecting}
            onPress={() => void connect()}
          >
            {t('actions.reconnect')}
          </Button>
        </Alert>
      )}

      {account ? (
        <PlatformDefaults platform={platform} />
      ) : (
        <div className="flex flex-col items-center gap-2 rounded-xl bg-surface-secondary px-6 py-7 text-center">
          <p className="text-[15px] font-semibold">{t('detail.emptyTitle', { platform: label })}</p>
          <p className="max-w-105 text-sm text-muted">{t('detail.emptyBody')}</p>
        </div>
      )}

      <ConfirmDialog
        isOpen={isConfirming}
        heading={t('confirm.heading', { platform: label })}
        body={t('confirm.body', { name: account?.displayName ?? '' })}
        confirmLabel={t('actions.disconnect')}
        isPending={isDisconnecting}
        onConfirm={() => void confirmDisconnect()}
        onCancel={() => setIsConfirming(false)}
      />
    </section>
  );
}

function PlatformDefaults({ platform }: { platform: AvailablePlatform }) {
  const { t } = useTranslation('accounts');
  const { t: tPlatforms } = useTranslation('platforms');
  const { data: defaults } = useGetPlatformDefaultsQuery();
  const [updateDefaults] = useUpdatePlatformDefaultsMutation();
  const label = getLabelFor(platform);

  if (!defaults) return null;

  const isDefault = defaults.selected.includes(platform);

  function changeSelected(isSelected: boolean) {
    if (!defaults) return;
    void updateDefaults({
      ...defaults,
      selected: AVAILABLE_PLATFORMS.filter((candidate) =>
        candidate === platform ? isSelected : defaults.selected.includes(candidate),
      ),
    });
  }

  function changeYouTubePrivacy(privacyStatus: string) {
    if (!defaults) return;
    void updateDefaults({
      ...defaults,
      settings: { ...defaults.settings, youtube: { ...defaults.settings.youtube, privacyStatus } },
    });
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-xl border border-separator bg-background px-4 py-2.5">
        <SettingSwitch
          label={t('defaults.selected')}
          description={t('defaults.selectedHint')}
          isSelected={isDefault}
          onChange={changeSelected}
        />
      </div>

      {platform === 'youtube' && (
        <div className="max-w-80">
          <SettingSelect
            label={t('defaults.visibility')}
            description={t('defaults.visibilityHint')}
            value={youtubeSettingsOf(defaults.settings.youtube).privacyStatus}
            options={toSelectOptions(YOUTUBE_PRIVACY_OPTIONS, tPlatforms)}
            onChange={changeYouTubePrivacy}
          />
        </div>
      )}

      {platform === 'tiktok' && (
        <p className="text-sm text-muted">{t('defaults.tiktokVisibility')}</p>
      )}

      <p className="flex items-start gap-3 rounded-xl bg-accent-soft px-3.5 py-3 text-[13px] text-accent-soft-foreground">
        <Info className="mt-px size-4.5 flex-none" />
        <span>{t('defaults.perPost', { platform: label })}</span>
      </p>
    </div>
  );
}

export function PlatformsScreen() {
  const { t } = useTranslation('accounts');
  const { data: accounts, isLoading } = useGetAccountsQuery();
  const [params, setParams] = useSearchParams();
  useConnectPopupChannel();
  const selected = toPlatform(params.get('platform'));
  const accountOf = (platform: AvailablePlatform) =>
    accounts?.find((candidate) => candidate.platform === platform);

  function select(platform: AvailablePlatform) {
    const next = new URLSearchParams(params);
    next.set('platform', platform);
    setParams(next, { replace: true });
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">{t('screen.title')}</h1>
        <p className="mt-1 text-[15px] text-muted">{t('screen.subtitle')}</p>
      </header>

      <CallbackNotice />

      {isLoading ? (
        <div className="grid place-items-center py-16">
          <Spinner />
        </div>
      ) : (
        <div className="flex flex-wrap items-start gap-6">
          <ListBox
            aria-label={t('list.label')}
            selectionMode="single"
            disallowEmptySelection
            selectedKeys={[selected]}
            onSelectionChange={(keys) => {
              const [key] = [...keys];
              select(toPlatform(String(key)));
            }}
            className="min-w-0 flex-[1_1_300px] gap-0.5 rounded-[14px] bg-surface p-2 shadow-surface min-[900px]:sticky min-[900px]:top-22"
          >
            {AVAILABLE_PLATFORMS.map((platform) => {
              const account = accountOf(platform);
              const state = stateOf(account);
              return (
                <ListBox.Item
                  key={platform}
                  id={platform}
                  textValue={getLabelFor(platform)}
                  className="gap-3 rounded-xl p-2.5 data-[selected=true]:bg-surface-secondary"
                >
                  <PlatformGlyph
                    platform={platform}
                    className={state === 'none' ? 'opacity-50' : ''}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium">{getLabelFor(platform)}</span>
                    <span className="block truncate text-xs text-muted">
                      {account?.displayName || t('state.none')}
                    </span>
                  </span>
                  <AccountStateChip account={account} />
                </ListBox.Item>
              );
            })}
          </ListBox>

          <PlatformDetail key={selected} platform={selected} account={accountOf(selected)} />
        </div>
      )}
    </div>
  );
}
