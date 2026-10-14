import { describe, expect, it } from 'vitest';
import type { Publication, PublicationTarget } from '../../api/publicationsApi';
import type { PublicationStatus } from '../../domain/publication/types';
import { publicationTab } from './publicationTab';

function publicationWith(...statuses: PublicationStatus[]): Publication {
  return {
    targets: statuses.map((status) => ({ status }) as PublicationTarget),
  } as Publication;
}

describe('publicationTab', () => {
  it('files a publication that is still running under published', () => {
    expect(publicationTab(publicationWith('completed', 'failed', 'uploading'))).toBe('published');
  });

  it('files a settled publication with a failed target under errors', () => {
    expect(publicationTab(publicationWith('completed', 'failed'))).toBe('error');
  });

  it('files a cancelled publication under errors', () => {
    expect(publicationTab(publicationWith('cancelled'))).toBe('error');
  });

  it('files a publication waiting for its time under scheduled', () => {
    expect(publicationTab(publicationWith('completed', 'scheduled'))).toBe('scheduled');
  });

  it('files a fully published publication under published', () => {
    expect(publicationTab(publicationWith('completed', 'completed'))).toBe('published');
  });
});
