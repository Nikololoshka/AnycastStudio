import { useState } from 'react';
import { Button } from '@heroui/react';
import { CalendarClock, Clapperboard, Send, Zap } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router';
import { useCreatePublicationMutation, useGetAccountsQuery } from '../../api';
import { messageOf, statusOf } from '../../api/errors';
import type { AppDispatch, RootState } from '../../app/store';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { getDescriptorFor, getLabelFor } from '../../platforms/registry';
import { TikTokConsent } from '../../platforms/tiktok';
import { clearVideo } from './composerSlice';
import { uploadReset } from '../upload';

const SCHEDULE_FORMAT: Intl.DateTimeFormatOptions = {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
};

export function SummaryPanel() {
  const { t, i18n } = useTranslation('composer');
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();

  const { video, title, description, hashtags, publishAt, selectedPlatforms, platformSettings } =
    useSelector((state: RootState) => state.composer);
  const uploadStatus = useSelector((state: RootState) => state.upload.status);

  const { data: accounts } = useGetAccountsQuery();
  const [createPublication, { isLoading: isPublishing }] = useCreatePublicationMutation();
  const [error, setError] = useState('');

  const targets = selectedPlatforms.flatMap((platform) => {
    const account = accounts?.find(
      (candidate) => candidate.platform === platform && !candidate.needsReauth,
    );
    return account
      ? [{ platform, socialAccountId: account.id, settings: platformSettings[platform] }]
      : [];
  });

  const isUploading = uploadStatus === 'hashing' || uploadStatus === 'uploading';

  const withoutAccount = selectedPlatforms.find(
    (platform) => !targets.some((target) => target.platform === platform),
  );

  const draftError = selectedPlatforms.flatMap((platform) =>
    getDescriptorFor(platform)
      .validate({
        video,
        title,
        description,
        hashtags,
        publishAt,
        settings: platformSettings[platform],
      })
      .errors.map((code) => ({ platform, code })),
  )[0];

  const blocker = !video
    ? t('summary.needsVideo')
    : !video.mediaAssetId
      ? t('summary.needsUpload')
      : selectedPlatforms.length === 0
        ? t('summary.needsPlatform')
        : withoutAccount
          ? t('summary.needsAccount', { platform: getLabelFor(withoutAccount) })
          : draftError
            ? t(`summary.invalid.${draftError.code}`, {
                platform: getLabelFor(draftError.platform),
              })
            : undefined;

  async function publish() {
    if (!video?.mediaAssetId) return;
    setError('');
    try {
      const publication = await createPublication({
        mediaAssetId: Number(video.mediaAssetId),
        title,
        description,
        hashtags,
        publishAt,
        targets,
      }).unwrap();

      // The server owns it now; the composer starts empty for the next one.
      dispatch(clearVideo());
      dispatch(uploadReset());
      void navigate(`/publications/${publication.id}`);
    } catch (cause) {
      const status = statusOf(cause);
      setError(
        status === 'quota_exceeded'
          ? t('summary.error.dailyLimit')
          : status === 'conflict'
            ? t('summary.error.accountNeedsReauth')
            : (messageOf(cause) ?? t('summary.error.unknown')),
      );
    }
  }

  return (
    <aside className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-5">
      <h2 className="font-display text-lg font-semibold tracking-tight">{t('summary.title')}</h2>

      <div className="overflow-hidden rounded-xl border border-border bg-surface-secondary">
        <div className="relative aspect-video bg-surface-tertiary">
          {video?.thumbnailDataUrl ? (
            <img src={video.thumbnailDataUrl} alt="" className="size-full object-cover" />
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-muted">
              <Clapperboard className="size-6" />
              <span className="text-sm">{t('summary.noVideo')}</span>
            </div>
          )}
        </div>
        <div className="px-4 py-3">
          <p className={`truncate font-medium ${title ? '' : 'text-muted'}`}>
            {title || t('summary.untitled')}
          </p>
          <p className="truncate text-xs text-muted">{video?.name ?? t('summary.chooseVideo')}</p>
        </div>
      </div>

      {selectedPlatforms.length > 0 && (
        <section className="flex flex-col gap-2">
          <p className="text-sm font-medium">{t('summary.platformsTitle')}</p>
          <ul className="flex flex-col gap-1.5">
            {selectedPlatforms.map((platform) => (
              <li key={platform} className="flex items-center gap-2 text-sm text-muted">
                <PlatformGlyph platform={platform} size="sm" />
                {getLabelFor(platform)}
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="flex items-center gap-2 text-sm text-muted">
        {publishAt ? (
          <>
            <CalendarClock className="size-4" />
            <span className="tabular-nums">
              {new Date(publishAt).toLocaleString(i18n.language, SCHEDULE_FORMAT)}
            </span>
          </>
        ) : (
          <>
            <Zap className="size-4" />
            {t('summary.immediate')}
          </>
        )}
      </p>

      <Button
        variant="primary"
        size="lg"
        fullWidth
        isDisabled={Boolean(blocker) || isUploading || isPublishing}
        onPress={() => void publish()}
      >
        <Send className="size-4" />
        {publishAt ? t('summary.schedule') : t('summary.publish')}
      </Button>

      {selectedPlatforms.includes('tiktok') && <TikTokConsent />}

      {error ? (
        <p role="alert" className="text-center text-xs text-danger">
          {error}
        </p>
      ) : (
        blocker && <p className="text-center text-xs text-muted">{blocker}</p>
      )}
    </aside>
  );
}
