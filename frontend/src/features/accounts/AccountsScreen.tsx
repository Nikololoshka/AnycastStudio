import { useEffect, useState } from 'react';
import { Button, Card, Spinner } from '@heroui/react';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';
import {
  useDisconnectAccountMutation,
  useGetAccountsQuery,
  useStartConnectMutation,
  type ConnectedAccount,
} from '../../api';
import { AVAILABLE_PLATFORMS, type AvailablePlatform } from '../../domain/platform/order';
import { getLabelFor } from '../../platforms/registry';
import { PlatformGlyph } from '../../components/PlatformGlyph';

const OUTCOMES = ['connected', 'cancelled', 'failed', 'invalid'] as const;

type Outcome = (typeof OUTCOMES)[number];

function toOutcome(value: string | null): Outcome | undefined {
  return OUTCOMES.find((outcome) => outcome === value);
}

/** The banner the OAuth callback redirects back with. */
function CallbackNotice() {
  const { t } = useTranslation('accounts');
  const [params, setParams] = useSearchParams();
  const outcome = toOutcome(params.get('result'));

  useEffect(() => {
    if (!outcome) return;
    // Clear it so a reload does not show the same banner again.
    const next = new URLSearchParams(params);
    next.delete('result');
    next.delete('platform');
    setParams(next, { replace: true });
  }, [outcome, params, setParams]);

  const [shown] = useState(outcome);
  if (!shown) return null;

  const isGood = shown === 'connected';

  return (
    <p
      role="status"
      className={`flex items-center gap-2 rounded-xl px-4 py-3 text-sm ${
        isGood ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'
      }`}
    >
      {isGood ? <CheckCircle2 className="size-4" /> : <AlertTriangle className="size-4" />}
      {t(`callback.${shown}`)}
    </p>
  );
}

function AccountRow({
  platform,
  account,
}: {
  platform: AvailablePlatform;
  account?: ConnectedAccount;
}) {
  const { t } = useTranslation('accounts');
  const [startConnect, { isLoading: isConnecting }] = useStartConnectMutation();
  const [disconnect, { isLoading: isDisconnecting }] = useDisconnectAccountMutation();
  const label = getLabelFor(platform);

  async function connect() {
    const authUrl = await startConnect(platform).unwrap();
    window.location.assign(authUrl);
  }

  return (
    <div className="flex items-center gap-4 rounded-xl border border-border px-4 py-3">
      {account?.avatarUrl ? (
        <img src={account.avatarUrl} alt="" className="size-9 rounded-full" />
      ) : (
        <PlatformGlyph platform={platform} />
      )}

      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{account?.displayName || label}</p>
        <p className="truncate text-sm text-muted">
          {!account
            ? t('status.none')
            : account.needsReauth
              ? t('status.needsReauth')
              : t('status.signedIn', { name: account.displayName })}
        </p>
      </div>

      {account ? (
        <div className="flex items-center gap-2">
          {account.needsReauth && (
            <Button size="sm" variant="primary" isDisabled={isConnecting} onPress={() => void connect()}>
              {t('actions.reconnect')}
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            isDisabled={isDisconnecting}
            onPress={() => void disconnect(account.id)}
          >
            {isDisconnecting ? t('actions.disconnecting') : t('actions.disconnect')}
          </Button>
        </div>
      ) : (
        <Button size="sm" variant="primary" isDisabled={isConnecting} onPress={() => void connect()}>
          {t('actions.connect', { platform: label })}
        </Button>
      )}
    </div>
  );
}

export function AccountsScreen() {
  const { t } = useTranslation('accounts');
  const { data: accounts, isLoading } = useGetAccountsQuery();

  return (
    <Card className="mt-6">
      <Card.Header>
        <Card.Title>{t('screen.title')}</Card.Title>
        <Card.Description>{t('screen.subtitle')}</Card.Description>
      </Card.Header>

      <Card.Content className="flex flex-col gap-3">
        <CallbackNotice />

        {isLoading ? (
          <div className="grid place-items-center py-8">
            <Spinner />
          </div>
        ) : (
          AVAILABLE_PLATFORMS.map((platform) => (
            <AccountRow
              key={platform}
              platform={platform}
              account={accounts?.find((candidate) => candidate.platform === platform)}
            />
          ))
        )}
      </Card.Content>
    </Card>
  );
}
