import type { PlatformCapabilities } from '../domain/platform/types';
import type { AvailablePlatform } from '../domain/platform/order';
import type { PlatformDescriptor } from './PlatformDescriptor';
import { InstagramDescriptor } from './instagram/InstagramDescriptor';
import { TikTokDescriptor } from './tiktok/TikTokDescriptor';
import { YouTubeDescriptor } from './youtube/YouTubeDescriptor';

const descriptors: Record<AvailablePlatform, PlatformDescriptor> = {
  youtube: new YouTubeDescriptor(),
  tiktok: new TikTokDescriptor(),
  instagram: new InstagramDescriptor(),
};

export function getDescriptorFor(platform: AvailablePlatform): PlatformDescriptor {
  return descriptors[platform];
}

export function getCapabilitiesFor(platform: AvailablePlatform): PlatformCapabilities {
  return descriptors[platform].getCapabilities();
}

export function getLabelFor(platform: AvailablePlatform): string {
  return descriptors[platform].getCapabilities().label;
}
