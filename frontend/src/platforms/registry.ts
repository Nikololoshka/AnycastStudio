import type { PlatformCapabilities } from '../domain/platform/types';
import type { AvailablePlatform } from '../domain/platform/order';
import type { PlatformDescriptor } from './PlatformDescriptor';
import { YouTubeDescriptor } from './youtube/YouTubeDescriptor';

const descriptors: Record<AvailablePlatform, PlatformDescriptor> = {
  youtube: new YouTubeDescriptor(),
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
