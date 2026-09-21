import { Avatar, Button } from '@heroui/react';
import { AlertCircle, LogOut, Plug, X } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch, RootState } from '../../app/store';
import type { Platform } from '../../domain/platform/types';
import { getLabelFor } from '../../platforms/capabilities';
import {
  connectPlatform,
  disconnectPlatform,
  selectAccountByPlatform,
  selectIsDisconnecting,
} from '../../features/accounts/accountsSlice';
import { PlatformGlyph } from '../PlatformGlyph';

function initialsOf(name: string): string {
  return name
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase())
    .join('');
}

export function PlatformAccountConnector({ platform }: { platform: Platform }) {
  const { t } = useTranslation('accounts');
  const dispatch = useDispatch<AppDispatch>();
  const account = useSelector((state: RootState) => selectAccountByPlatform(state, platform));
  const pending = useSelector((state: RootState) =>
    state.accounts.pendingPlatforms.includes(platform),
  );
  const disconnecting = useSelector((state: RootState) =>
    account ? selectIsDisconnecting(state, account.id) : false,
  );
  const error = useSelector((state: RootState) => state.accounts.errors[platform]);
  const label = getLabelFor(platform);
  const runningConnect = useRef<{ abort: () => void } | null>(null);

  useEffect(() => () => runningConnect.current?.abort(), []);

  const statusText = pending
    ? t('status.waiting')
    : disconnecting
      ? t('status.disconnecting')
      : account
        ? t('status.signedIn', { name: account.displayName })
        : t('status.none');

  const startConnect = () => {
    runningConnect.current = dispatch(connectPlatform(platform));
  };

  const cancelConnect = () => {
    runningConnect.current?.abort();
    runningConnect.current = null;
  };

  return (
    <div className="flex items-center gap-4">
      <div className="relative">
        <PlatformGlyph platform={platform} size="lg" />
        {account && (
          <Avatar size="sm" className="absolute -right-2 -bottom-2 size-6 ring-2 ring-surface">
            <Avatar.Image src={account.avatarUrl} alt="" />
            <Avatar.Fallback className="text-[10px]">
              {initialsOf(account.displayName)}
            </Avatar.Fallback>
          </Avatar>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <p className="font-display text-lg font-semibold tracking-tight">{label}</p>
        {error ? (
          <p className="flex items-center gap-1.5 text-sm text-danger">
            <AlertCircle className="size-3.5 shrink-0" />
            <span className="truncate">{error}</span>
          </p>
        ) : (
          <p className="truncate text-sm text-muted">{statusText}</p>
        )}
      </div>

      {account ? (
        <Button
          variant="tertiary"
          size="sm"
          isPending={disconnecting}
          onPress={() => dispatch(disconnectPlatform(account.id))}
        >
          <LogOut className="size-4" />
          {disconnecting ? t('actions.disconnecting') : t('actions.disconnect')}
        </Button>
      ) : pending ? (
        <Button variant="danger-soft" size="sm" onPress={cancelConnect}>
          <X className="size-4" />
          {t('actions.cancel')}
        </Button>
      ) : (
        <Button variant="primary" size="sm" onPress={startConnect}>
          <Plug className="size-4" />
          {t('actions.connect', { platform: label })}
        </Button>
      )}
    </div>
  );
}
