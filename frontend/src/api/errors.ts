import type { FetchBaseQueryError } from '@reduxjs/toolkit/query';
import type { ApiEnvelope } from './types';

function envelopeOf(error: unknown): ApiEnvelope | undefined {
  const data = (error as FetchBaseQueryError | undefined)?.data;
  return typeof data === 'object' && data !== null ? (data as ApiEnvelope) : undefined;
}

/** The `status` string the server answered with, or 'unknown' if it never replied. */
export function statusOf(error: unknown): string {
  return envelopeOf(error)?.status ?? 'unknown';
}

export function messageOf(error: unknown): string | undefined {
  const envelope = envelopeOf(error);
  return envelope?.message ?? envelope?.errors?.[0]?.message;
}
