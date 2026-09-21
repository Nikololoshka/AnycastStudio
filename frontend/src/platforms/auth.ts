import type { Platform } from '../domain/platform/types';
import type { PlatformAuth } from '../services/auth/PlatformAuth';
import { YouTubeAuth } from './youtube';
import { TikTokAuth } from './tiktok';
import { XAuth } from './x';
import { InstagramAuth } from './instagram';

const auths: Record<Platform, PlatformAuth> = {
  youtube: new YouTubeAuth(),
  x: new XAuth(),
  instagram: new InstagramAuth(),
  tiktok: new TikTokAuth(),
};

export function getAuthFor(platform: Platform): PlatformAuth {
  return auths[platform];
}
