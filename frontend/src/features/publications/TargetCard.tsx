import { Alert, Button, Chip, Disclosure, ProgressBar } from '@heroui/react';
import { Check, ExternalLink, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  useCancelTargetMutation,
  useRetryTargetMutation,
  type Publication,
  type PublicationTarget,
} from '../../api/publicationsApi';
import type { PlatformDefaults } from '../../api/platformDefaultsApi';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { INDETERMINATE_STATUSES } from '../../domain/publication/status';
import type { AvailablePlatform } from '../../domain/platform/order';
import { getLabelFor } from '../../platforms/registry';
import { toneOf } from './publicationMarks';
import { finalText, settingRows, type SettingRow } from './targetDetails';

const SECTION = 'text-xs font-semibold tracking-wide text-muted uppercase';

export function TargetCard({
  publication,
  target,
  accountName,
  defaults,
}: {
  publication: Publication;
  target: PublicationTarget;
  accountName?: string;
  defaults?: PlatformDefaults;
}) {
  const { t, i18n } = useTranslation('publications');
  const { t: tPlatforms } = useTranslation('platforms');
  const [cancel, { isLoading: isCancelling }] = useCancelTargetMutation();
  const [retry, { isLoading: isRetrying }] = useRetryTargetMutation();

  const platform = target.platform as AvailablePlatform;
  const label = getLabelFor(platform);
  const isIndeterminate = INDETERMINATE_STATUSES.includes(target.status);
  const canRetry = target.status === 'failed' || target.status === 'cancelled';
  const canCancel = target.isActive && target.status !== 'processing';
  const when = target.finishedAt ?? target.startedAt ?? publication.publishAt;
  const rows = settingRows(platform, target.settings, defaults?.settings[platform], tPlatforms);
  const text = finalText(platform, publication, target.settings);

  return (
    <Disclosure className="overflow-hidden rounded-[14px] bg-surface shadow-surface">
      {({ isExpanded }) => (
        <>
          <div className="flex flex-wrap items-center gap-3 px-4 py-3.5">
            <Disclosure.Heading className="m-0 min-w-0 flex-[1_1_260px]">
              <Disclosure.Trigger className="flex min-h-11 w-full items-center gap-3 text-left">
                <PlatformGlyph platform={platform} />
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">{label}</span>
                  <span className="block truncate text-[13px] font-normal text-muted">
                    {[
                      accountName,
                      when &&
                        new Date(when).toLocaleString(i18n.language, {
                          day: '2-digit',
                          month: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                        }),
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </span>
                <Disclosure.Indicator className="size-4 text-muted" />
              </Disclosure.Trigger>
            </Disclosure.Heading>

            <Chip size="sm" variant="soft" color={toneOf(target)}>
              {t(`status.${target.status}`)}
            </Chip>

            {target.publishedUrl && (
              <a
                href={target.publishedUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-surface-secondary px-3 text-sm font-medium hover:bg-surface-tertiary"
              >
                {t('actions.open')}
                <ExternalLink className="size-3.5" />
              </a>
            )}

            {canCancel && (
              <Button
                size="sm"
                variant="ghost"
                isDisabled={isCancelling}
                onPress={() => void cancel(target.id)}
              >
                {t('actions.cancel')}
              </Button>
            )}

            {canRetry && (
              <Button
                size="sm"
                variant="primary"
                isDisabled={isRetrying}
                onPress={() => void retry(target.id)}
              >
                {t('actions.retry')}
              </Button>
            )}
          </div>

          {target.isActive && (
            <ProgressBar
              aria-label={t(`status.${target.status}`)}
              value={isIndeterminate ? undefined : target.progress}
              isIndeterminate={isIndeterminate}
              className="px-4 pb-3.5"
            />
          )}

          {target.error && (
            <Alert status="danger" className="mx-4 mb-3.5 w-auto">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Title>
                  {t(`error.${target.error.failure}`, { defaultValue: target.error.message })}
                </Alert.Title>
              </Alert.Content>
            </Alert>
          )}

          {!isExpanded && rows.some((row) => typeof row.value === 'string') && (
            <div className="flex flex-wrap gap-1.5 px-4 pb-3.5">
              {rows
                .filter((row) => typeof row.value === 'string')
                .slice(0, 3)
                .map((row) => (
                  <Chip key={row.key} size="sm" variant="soft">
                    {row.value}
                  </Chip>
                ))}
            </div>
          )}

          <Disclosure.Content>
            <Disclosure.Body className="flex flex-col gap-5 border-t border-separator p-4">
              {text.length > 0 && (
                <section className="flex flex-col gap-2.5">
                  <h3 className={SECTION}>{t('detail.finalText')}</h3>
                  {text.map((part) => (
                    <div key={part.kind} className="flex flex-col gap-1">
                      <span className="text-xs text-muted">{t(`detail.text.${part.kind}`)}</span>
                      <p className="rounded-xl border border-separator bg-surface-secondary px-3.5 py-3 text-sm whitespace-pre-wrap">
                        {part.text}
                      </p>
                    </div>
                  ))}
                </section>
              )}

              <section className="flex flex-col gap-3">
                <h3 className={SECTION}>{t('detail.settings', { platform: label })}</h3>
                <dl className="grid grid-cols-[repeat(auto-fill,minmax(210px,1fr))] gap-x-6 gap-y-4">
                  {rows.map((row) => (
                    <SettingValue key={row.key} row={row} />
                  ))}
                </dl>
              </section>
            </Disclosure.Body>
          </Disclosure.Content>
        </>
      )}
    </Disclosure>
  );
}

function SettingValue({ row }: { row: SettingRow }) {
  const { t } = useTranslation('publications');

  return (
    <div className="min-w-0">
      <dt className="mb-1 text-xs text-muted">{row.label}</dt>
      <dd className="flex flex-wrap items-center gap-2 text-sm">
        {typeof row.value === 'boolean' ? (
          <span className={`flex items-center gap-1.5 ${row.value ? '' : 'text-muted'}`}>
            {row.value ? (
              <Check className="size-4 text-success" />
            ) : (
              <X className="size-4 text-muted" />
            )}
            {t(row.value ? 'detail.yes' : 'detail.no')}
          </span>
        ) : (
          <span>
            {typeof row.value === 'number'
              ? t('detail.seconds', { seconds: row.value })
              : row.value}
          </span>
        )}
        {row.isChanged && (
          <Chip size="sm" variant="soft" color="accent">
            {t('detail.changed')}
          </Chip>
        )}
      </dd>
    </div>
  );
}
