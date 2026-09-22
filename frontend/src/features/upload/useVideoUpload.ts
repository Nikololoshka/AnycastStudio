import { useCallback, useEffect, useRef } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch, RootState } from '../../app/store';
import { setVideo } from '../composer';
import { describeVideoFile } from '../../services/files';
import {
  abortUpload,
  matchesSession,
  readUploadStatus,
  uploadFile,
  UploadError,
  type UploadSession,
} from '../../services/upload/chunkedUpload';
import { readStored, removeStored, writeStored } from '../../services/storage';
import {
  hashingStarted,
  resumeOffered,
  uploadCancelled,
  uploadFailed,
  uploadFinished,
  uploadProgressed,
  uploadReset,
  uploadStarted,
} from './uploadSlice';

const PENDING_UPLOAD_KEY = 'pendingUpload';

function describeFailure(error: unknown): string {
  return error instanceof UploadError ? error.status : 'network';
}

/**
 * Drives one video from "picked in the browser" to "stored on the server".
 *
 * The transfer itself lives in the chunked upload service; this hook starts it,
 * reports it, and remembers enough to pick it up after a reload.
 */
export function useVideoUpload() {
  const dispatch = useDispatch<AppDispatch>();
  const upload = useSelector((state: RootState) => state.upload);
  const controller = useRef<AbortController | null>(null);

  // On mount, ask the server whether an interrupted transfer is still open.
  useEffect(() => {
    const uploadId = readStored<string>(PENDING_UPLOAD_KEY);
    if (!uploadId) return;

    let abandoned = false;
    void readUploadStatus(uploadId)
      .then((session) => {
        if (!abandoned && session.offset > 0) dispatch(resumeOffered(session));
      })
      .catch(() => removeStored(PENDING_UPLOAD_KEY));

    return () => {
      abandoned = true;
    };
  }, [dispatch]);

  const send = useCallback(
    async (file: File, resume?: UploadSession) => {
      controller.current?.abort();
      const abort = new AbortController();
      controller.current = abort;

      dispatch(hashingStarted());

      try {
        const video = await describeVideoFile(file);

        const asset = await uploadFile(file, {
          resume,
          signal: abort.signal,
          details: {
            durationSeconds: video.duration,
            width: video.width,
            height: video.height,
          },
          onSession: (session) => {
            writeStored(PENDING_UPLOAD_KEY, session.uploadId);
            dispatch(
              uploadStarted({ uploadId: session.uploadId, totalBytes: session.sizeBytes }),
            );
          },
          onProgress: (progress) => dispatch(uploadProgressed(progress)),
        });

        dispatch(setVideo({ ...video, mediaAssetId: String(asset.id) }));
        dispatch(uploadFinished());
        removeStored(PENDING_UPLOAD_KEY);
      } catch (error) {
        if (abort.signal.aborted) {
          dispatch(uploadCancelled());
          return;
        }
        dispatch(uploadFailed(describeFailure(error)));
      }
    },
    [dispatch],
  );

  const start = useCallback((file: File) => void send(file), [send]);

  /** Continue the offered transfer if this is the same file it was carrying. */
  const resumeWith = useCallback(
    (file: File) => {
      const session = upload.resumable;
      if (!session || !matchesSession(file, session)) return false;
      void send(file, session);
      return true;
    },
    [send, upload.resumable],
  );

  const cancel = useCallback(() => {
    controller.current?.abort();
    if (upload.uploadId) void abortUpload(upload.uploadId);
    removeStored(PENDING_UPLOAD_KEY);
    dispatch(uploadReset());
  }, [dispatch, upload.uploadId]);

  const dismissResume = useCallback(() => {
    if (upload.resumable) void abortUpload(upload.resumable.uploadId);
    removeStored(PENDING_UPLOAD_KEY);
    dispatch(resumeOffered(undefined));
  }, [dispatch, upload.resumable]);

  return { upload, start, resumeWith, cancel, dismissResume };
}
