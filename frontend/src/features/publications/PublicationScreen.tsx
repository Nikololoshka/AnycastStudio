import { Card, Spinner } from '@heroui/react';
import { CalendarClock, Hash, Zap } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Navigate, useParams } from 'react-router';
import { ACTIVE_POLL_MS, useGetPublicationQuery } from '../../api/publicationsApi';
import { TargetRow } from './TargetRow';

export function PublicationScreen() {
  const { t, i18n } = useTranslation('publications');
  const { id } = useParams();
  const publicationId = Number(id);

  const { data: publication, isLoading, isError } = useGetPublicationQuery(publicationId, {
    skip: !Number.isFinite(publicationId),
    pollingInterval: ACTIVE_POLL_MS,
    skipPollingIfUnfocused: true,
  });

  if (!Number.isFinite(publicationId) || isError) return <Navigate to="/publications" replace />;

  if (isLoading || !publication) {
    return (
      <div className="grid place-items-center py-16">
        <Spinner />
      </div>
    );
  }

  return (
    <Card className="mt-6">
      <Card.Header>
        <Card.Title>{publication.title}</Card.Title>
        <Card.Description>{publication.filename}</Card.Description>
      </Card.Header>

      <Card.Content className="flex flex-col gap-4">
        <p className="flex items-center gap-2 text-sm text-muted">
          {publication.publishAt ? (
            <>
              <CalendarClock className="size-4" />
              <span className="tabular-nums">
                {new Date(publication.publishAt).toLocaleString(i18n.language)}
              </span>
            </>
          ) : (
            <>
              <Zap className="size-4" />
              {t('detail.immediate')}
            </>
          )}
        </p>

        {publication.description && (
          <p className="whitespace-pre-wrap text-sm">{publication.description}</p>
        )}

        {publication.hashtags.length > 0 && (
          <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
            <Hash className="size-4" />
            {publication.hashtags.join(', ')}
          </p>
        )}

        <div className="flex flex-col gap-2">
          {publication.targets.map((target) => (
            <TargetRow key={target.id} target={target} />
          ))}
        </div>
      </Card.Content>
    </Card>
  );
}
