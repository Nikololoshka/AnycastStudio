import { Card } from '@heroui/react';
import { Inbox } from 'lucide-react';
import { useTranslation } from 'react-i18next';

/** Placeholder until publishing moves to the server. */
export function PublicationsScreen() {
  const { t } = useTranslation('publications');

  return (
    <Card className="mt-6">
      <Card.Header>
        <Card.Title>{t('screen.title')}</Card.Title>
        <Card.Description>{t('screen.subtitle')}</Card.Description>
      </Card.Header>
      <Card.Content className="flex flex-col items-center gap-3 py-12 text-center">
        <Inbox className="size-8 text-muted" />
        <p className="text-sm text-muted">{t('screen.empty')}</p>
      </Card.Content>
    </Card>
  );
}
