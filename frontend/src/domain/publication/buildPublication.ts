import type { ComposerState } from '../../features/composer/composerSlice';
import type { Publication, PlatformPublication } from './types';

export function buildPublicationFromComposer(composer: ComposerState, id: string): Publication {
  if (!composer.video) throw new Error('no video selected');
  if (composer.selectedPlatforms.length === 0) throw new Error('no platforms selected');

  const platforms: PlatformPublication[] = composer.selectedPlatforms.map((platform) => ({
    platform,
    enabled: true,
    settings: composer.platformSettings[platform],
    status: 'idle',
    progress: 0,
  }));

  return {
    id,
    video: composer.video,
    title: composer.title,
    description: composer.description,
    hashtags: composer.hashtags,
    scheduledAt: composer.scheduledAt,
    platforms,
  };
}
