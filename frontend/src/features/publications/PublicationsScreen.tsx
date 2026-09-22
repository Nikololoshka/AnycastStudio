import { Card, Spinner } from '@heroui/react';
import { Inbox } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import {
  ACTIVE_POLL_MS,
  useGetPublicationsQuery,
  type Publication,
} from '../../api/publicationsApi';
import { TargetRow } from './TargetRow';

function PublicationCard({ publication }: { publication: Publication }) {
  const { i18n } = useTranslation();

  return (
    <Card>
      <Card.Header className="flex-row items-baseline justify-between gap-4">
        <Link to={`/publications/${publication.id}`} className="min-w-0">
          <Card.Title className="truncate">{publication.title}</Card.Title>
        </Link>
        <span className="shrink-0 text-xs text-muted tabular-nums">
          {new Date(publication.createdAt).toLocaleString(i18n.language)}
        </span>
      </Card.Header>
      <Card.Content className="flex flex-col gap-2">
        {publication.targets.map((target) => (
          <TargetRow key={target.id} target={target} />
        ))}
      </Card.Content>
    </Card>
  );
}

export function PublicationsScreen() {
  const { t } = useTranslation('publications');
  const { data: publications, isLoading } = useGetPublicationsQuery(undefined, {
    // Keep asking only while something is still moving.
    pollingInterval: ACTIVE_POLL_MS,
    skipPollingIfUnfocused: true,
  });

  if (isLoading) {
    return (
      <div className="grid place-items-center py-16">
        <Spinner />
      </div>
    );
  }

  if (!publications?.length) {
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

  return (
    <div className="mt-6 flex flex-col gap-4">
      <header>
        <h1 className="font-display text-xl font-semibold tracking-tight">{t('screen.title')}</h1>
        <p className="mt-1 text-sm text-muted">{t('screen.subtitle')}</p>
      </header>

      {publications.map((publication) => (
        <PublicationCard key={publication.id} publication={publication} />
      ))}
    </div>
  );
}
