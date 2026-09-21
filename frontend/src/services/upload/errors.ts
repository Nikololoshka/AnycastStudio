import type { PublicationError } from '../../domain/publication/types';

export function toPublicationError(error: unknown): PublicationError {
  if (error && typeof error === 'object' && 'type' in error && 'message' in error) {
    return error as PublicationError;
  }
  return {
    type: 'unknown',
    message: error instanceof Error ? error.message : String(error),
  };
}
