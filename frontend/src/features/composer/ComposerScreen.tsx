import { useEffect } from 'react';
import { Spinner } from '@heroui/react';
import { skipToken } from '@reduxjs/toolkit/query';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { Navigate, useParams } from 'react-router';
import { useGetDraftQuery } from '../../api';
import type { AppDispatch, RootState } from '../../app/store';
import { ComposerActionBar } from './ComposerActionBar';
import { ComposerFileCard, ComposerTextCard } from './ComposerContentCards';
import { ComposerPlatformsCard } from './ComposerPlatformsCard';
import { ComposerTimingCard } from './ComposerTimingCard';
import { composerReset, draftLoaded } from './composerSlice';
import { uploadReset } from '../upload';

export function ComposerScreen() {
  const dispatch = useDispatch<AppDispatch>();
  const { draftId } = useParams();
  const loadedDraftId = useSelector((state: RootState) => state.composer.draftId);
  const { data: draft, isError } = useGetDraftQuery(draftId ?? skipToken);

  useEffect(() => {
    if (draftId === loadedDraftId) return;
    if (!draftId) {
      dispatch(composerReset());
      dispatch(uploadReset());
    } else if (draft?.id === draftId) {
      dispatch(draftLoaded(draft));
      dispatch(uploadReset());
    }
  }, [dispatch, draft, draftId, loadedDraftId]);

  if (isError) return <Navigate to="/compose" replace />;

  if (draftId !== loadedDraftId) {
    return (
      <div className="grid place-items-center py-16">
        <Spinner />
      </div>
    );
  }

  return <ComposerForm key={draftId ?? 'new'} />;
}

function ComposerForm() {
  const { t } = useTranslation('composer');

  return (
    <div className="flex flex-1 flex-col gap-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">{t('screen.title')}</h1>
        <p className="mt-1 text-[15px] text-muted">{t('screen.subtitle')}</p>
      </header>

      <ComposerPlatformsCard />

      <div className="flex flex-wrap items-start gap-6">
        <div className="flex min-w-0 flex-[3_1_520px] flex-col gap-6">
          <ComposerFileCard />
          <ComposerTextCard />
        </div>
        <div className="flex min-w-0 flex-[2_1_340px] flex-col gap-6">
          <ComposerTimingCard />
        </div>
      </div>

      <ComposerActionBar />
    </div>
  );
}
