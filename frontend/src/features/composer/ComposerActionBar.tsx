import { useState } from 'react';
import { Button, Spinner } from '@heroui/react';
import { Check, Save, Send } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router';
import {
  useCreatePublicationMutation,
  useDeleteDraftMutation,
  useGetAccountsQuery,
  useSaveDraftMutation,
} from '../../api';
import { messageOf, statusOf } from '../../api/errors';
import type { AppDispatch, RootState } from '../../app/store';
import { getDescriptorFor, getLabelFor } from '../../platforms/registry';
import { TikTokConsent } from '../../platforms/tiktok';
import { clearVideo, draftSaved } from './composerSlice';
import { uploadReset } from '../upload';
import { usePublishablePlatforms } from './usePublishablePlatforms';

export function ComposerActionBar() {
  const { t, i18n } = useTranslation('composer');
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();

  const composer = useSelector((state: RootState) => state.composer);
  const {
    draftId,
    video,
    title,
    description,
    hashtags,
    publishAt,
    platformSettings,
  } = composer;
  const uploadStatus = useSelector((state: RootState) => state.upload.status);

  const { data: accounts } = useGetAccountsQuery();
  const selectedPlatforms = usePublishablePlatforms();
  const [createPublication, { isLoading: isPublishing }] = useCreatePublicationMutation();
  const [saveDraft, { isLoading: isSaving }] = useSaveDraftMutation();
  const [deleteDraft] = useDeleteDraftMutation();
  const [savedAt, setSavedAt] = useState('');
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

      if (draftId) void deleteDraft(draftId);
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

  async function save() {
    const { draftId: id, ...content } = composer;
    const draft = await saveDraft({ ...content, id }).unwrap();
    setSavedAt(draft.updatedAt);
    if (!id) {
      await navigate(`/compose/${draft.id}`, { replace: true });
      dispatch(draftSaved(draft.id));
    }
  }

  return (
    <div
      className={[
        'sticky bottom-0 z-20 mt-auto -mb-12 flex flex-wrap items-center gap-3 py-3',
        'before:absolute before:inset-y-0 before:-inset-x-[100vmax] before:-z-10 before:bg-surface/75 before:shadow-[0_-1px_0_var(--border)] before:backdrop-blur-xl before:backdrop-saturate-150',
      ].join(' ')}
    >
      <div className="flex min-w-0 flex-[1_1_240px] flex-col gap-1 text-[13px]">
        {savedAt && (
          <p className="flex items-center gap-2 text-muted">
            <Check className="size-4 text-success" />
            {t('summary.draftSavedAt', {
              time: new Date(savedAt).toLocaleTimeString(i18n.language, {
                hour: '2-digit',
                minute: '2-digit',
              }),
            })}
          </p>
        )}
        {error ? (
          <p role="alert" className="text-danger">
            {error}
          </p>
        ) : (
          blocker && <p className="text-muted">{blocker}</p>
        )}
        {selectedPlatforms.includes('tiktok') && <TikTokConsent />}
      </div>

      <Button
        variant="secondary"
        size="lg"
        isDisabled={isSaving || isPublishing}
        onPress={() => void save()}
      >
        <Save className="size-4" />
        {t('summary.saveDraft')}
      </Button>

      <Button
        variant="primary"
        size="lg"
        isDisabled={Boolean(blocker) || isUploading || isPublishing}
        onPress={() => void publish()}
      >
        {isPublishing ? <Spinner size="sm" color="current" /> : <Send className="size-4" />}
        {publishAt
          ? t('summary.schedule', { count: selectedPlatforms.length })
          : t('summary.publish', { count: selectedPlatforms.length })}
      </Button>
    </div>
  );
}
