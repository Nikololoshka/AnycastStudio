import { Card } from '@heroui/react';
import { useTranslation } from 'react-i18next';
import { AVAILABLE_PLATFORMS } from '../../domain/platform/order';
import { getLabelFor } from '../../platforms/registry';
import { PlatformGlyph } from '../../components/PlatformGlyph';

/** Placeholder until the browser OAuth flow lands. */
export function AccountsScreen() {
  const { t } = useTranslation('accounts');

  return (
    <Card className="mt-6">
      <Card.Header>
        <Card.Title>{t('screen.title')}</Card.Title>
        <Card.Description>{t('screen.subtitle')}</Card.Description>
      </Card.Header>
      <Card.Content className="flex flex-col gap-3">
        {AVAILABLE_PLATFORMS.map((platform) => (
          <div
            key={platform}
            className="flex items-center gap-3 rounded-xl border border-border px-4 py-3"
          >
            <PlatformGlyph platform={platform} />
            <span className="font-medium">{getLabelFor(platform)}</span>
            <span className="ml-auto text-sm text-muted">{t('status.unavailable')}</span>
          </div>
        ))}
      </Card.Content>
    </Card>
  );
}
