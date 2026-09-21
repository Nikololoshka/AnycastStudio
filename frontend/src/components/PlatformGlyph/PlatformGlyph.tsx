import { siInstagram, siTiktok, siX, siYoutube, type SimpleIcon } from 'simple-icons';
import type { Platform } from '../../domain/platform/types';

const PLATFORM_ICONS: Record<Platform, SimpleIcon> = {
  youtube: siYoutube,
  x: siX,
  tiktok: siTiktok,
  instagram: siInstagram,
};

const TILE_BACKGROUNDS: Record<Platform, string> = {
  youtube: '#FF0033',
  x: 'var(--brand-x)',
  tiktok: 'var(--brand-tiktok)',
  instagram:
    'linear-gradient(135deg, #FEDA75 0%, #FA7E1E 25%, #D62976 55%, #962FBF 80%, #4F5BD5 100%)',
};

const GLYPH_COLORS: Record<Platform, string> = {
  youtube: '#FFFFFF',
  x: 'var(--background)',
  tiktok: 'var(--background)',
  instagram: '#FFFFFF',
};

const TILE_SIZES = {
  sm: { tile: 'size-6 rounded-md', glyph: 'size-3.5' },
  md: { tile: 'size-9 rounded-lg', glyph: 'size-[18px]' },
  lg: { tile: 'size-11 rounded-xl', glyph: 'size-6' },
};

export function PlatformGlyph({
  platform,
  size = 'md',
  className = '',
}: {
  platform: Platform;
  size?: keyof typeof TILE_SIZES;
  className?: string;
}) {
  const { tile, glyph } = TILE_SIZES[size];

  return (
    <span
      aria-hidden
      className={`inline-grid shrink-0 place-items-center ${tile} ${className}`}
      style={{ background: TILE_BACKGROUNDS[platform], color: GLYPH_COLORS[platform] }}
    >
      <svg viewBox="0 0 24 24" className={`${glyph} fill-current`}>
        <path d={PLATFORM_ICONS[platform].path} />
      </svg>
    </span>
  );
}
