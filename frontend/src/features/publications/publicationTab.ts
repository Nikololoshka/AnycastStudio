import type { Publication } from '../../api/publicationsApi';
import { overallStatus } from '../../domain/publication/status';

export type PublicationTab = 'published' | 'scheduled' | 'error';

export function publicationTab(publication: Publication): PublicationTab {
  const status = overallStatus(publication.targets.map((target) => target.status));
  if (status === 'failed' || status === 'cancelled') return 'error';
  if (status === 'scheduled') return 'scheduled';
  return 'published';
}
