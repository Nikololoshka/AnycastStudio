import type { Key, ReactElement } from 'react';
import { Button, Drawer, Tabs } from '@heroui/react';
import { Film } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { useGetAccountsQuery, useGetPlatformDefaultsQuery } from '../../api';
import type { AppDispatch, RootState } from '../../app/store';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import type { AvailablePlatform } from '../../domain/platform/order';
import { InstagramSettingsPanel } from '../../platforms/instagram';
import { getLabelFor } from '../../platforms/registry';
import { TikTokSettingsPanel } from '../../platforms/tiktok';
import { XSettingsPanel } from '../../platforms/x';
import { YouTubeSettingsPanel } from '../../platforms/youtube';
import { isChangedFrom, setPlatformSettings, togglePlatform } from './composerSlice';

const PLATFORM_PANELS: Record<AvailablePlatform, () => ReactElement> = {
  youtube: YouTubeSettingsPanel,
  tiktok: TikTokSettingsPanel,
  instagram: InstagramSettingsPanel,
  x: XSettingsPanel,
};

type PreviewShape = 'video' | 'vertical' | 'post';

const PREVIEW_SHAPES: Record<AvailablePlatform, PreviewShape> = {
  youtube: 'video',
  tiktok: 'vertical',
  instagram: 'vertical',
  x: 'post',
};

const SECTION = 'text-xs font-semibold tracking-wide text-muted uppercase';

export function PlatformSettingsDrawer({
  platform,
  onSelect,
  onClose,
}: {
  platform?: AvailablePlatform;
  onSelect: (platform: AvailablePlatform) => void;
  onClose: () => void;
}) {
  return (
    <Drawer isOpen={Boolean(platform)} onOpenChange={(open) => !open && onClose()}>
      <Drawer.Backdrop>
        <Drawer.Content placement="right">
          <Drawer.Dialog className="flex h-full w-full max-w-full flex-col p-0 sm:w-145">
            {platform && <DrawerPanel platform={platform} onSelect={onSelect} onClose={onClose} />}
          </Drawer.Dialog>
        </Drawer.Content>
      </Drawer.Backdrop>
    </Drawer>
  );
}

function DrawerPanel({
  platform,
  onSelect,
  onClose,
}: {
  platform: AvailablePlatform;
  onSelect: (platform: AvailablePlatform) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation('composer');
  const dispatch = useDispatch<AppDispatch>();
  const selectedPlatforms = useSelector((state: RootState) => state.composer.selectedPlatforms);
  const platformSettings = useSelector((state: RootState) => state.composer.platformSettings);
  const { data: defaults } = useGetPlatformDefaultsQuery();
  const { data: accounts } = useGetAccountsQuery();
  const account = accounts?.find((candidate) => candidate.platform === platform);
  const label = getLabelFor(platform);
  const SettingsPanel = PLATFORM_PANELS[platform];
  const isChanged = (candidate: AvailablePlatform) =>
    isChangedFrom(platformSettings[candidate], defaults?.settings[candidate]);
  const next =
    selectedPlatforms[(selectedPlatforms.indexOf(platform) + 1) % selectedPlatforms.length];

  function resetAll() {
    if (!defaults) return;
    dispatch(setPlatformSettings({ platform, settings: defaults.settings[platform] }));
  }

  function exclude() {
    dispatch(togglePlatform(platform));
    onClose();
  }

  return (
    <Tabs
      selectedKey={platform}
      onSelectionChange={(key: Key) => onSelect(key as AvailablePlatform)}
      className="flex min-h-0 flex-1 flex-col gap-0"
    >
      <Drawer.Header className="flex flex-col gap-3 border-b border-separator px-5 pt-4 pb-3">
        <div className="flex items-center gap-3">
          <PlatformGlyph platform={platform} size="lg" />
          <div className="min-w-0 flex-1">
            <Drawer.Heading className="text-lg font-semibold">{label}</Drawer.Heading>
            <p className="truncate text-[13px] text-muted">
              {account ? `${account.displayName} · ` : ''}
              {t('drawer.subtitle')}
            </p>
          </div>
          <Drawer.CloseTrigger aria-label={t('drawer.close')} />
        </div>
        {selectedPlatforms.length > 1 && (
          <Tabs.ListContainer className="max-w-full">
            <Tabs.List aria-label={t('drawer.switcher')} className="w-full">
              {selectedPlatforms.map((candidate) => (
                <Tabs.Tab key={candidate} id={candidate} className="gap-1.5 whitespace-nowrap">
                  {getLabelFor(candidate)}
                  {isChanged(candidate) && (
                    <span
                      aria-label={t('drawer.changed')}
                      className="size-1.5 rounded-full bg-warning"
                    />
                  )}
                  <Tabs.Indicator />
                </Tabs.Tab>
              ))}
            </Tabs.List>
          </Tabs.ListContainer>
        )}
      </Drawer.Header>

      <Drawer.Body className="min-h-0 flex-1 overflow-y-auto p-0">
        <Tabs.Panel id={platform} className="flex flex-col gap-7 p-5">
          <PostPreview platform={platform} accountName={account?.displayName} />

          <section aria-labelledby="platform-only" className="flex flex-col gap-2">
            <h3 id="platform-only" className={SECTION}>
              {t('drawer.only', { platform: label })}
            </h3>
            <SettingsPanel />
          </section>

          <Button variant="ghost" size="sm" className="self-start text-danger" onPress={exclude}>
            {t('drawer.exclude', { platform: label })}
          </Button>
        </Tabs.Panel>
      </Drawer.Body>

      <Drawer.Footer className="flex items-center gap-3 border-t border-separator px-5 py-3.5">
        <Button variant="tertiary" isDisabled={!isChanged(platform)} onPress={resetAll}>
          {t('drawer.reset')}
        </Button>
        <span className="flex-1" />
        {selectedPlatforms.length > 1 && (
          <Button variant="tertiary" onPress={() => onSelect(next)}>
            {t('drawer.next')}
          </Button>
        )}
        <Button variant="primary" onPress={onClose}>
          {t('drawer.done')}
        </Button>
      </Drawer.Footer>
    </Tabs>
  );
}

function PostPreview({
  platform,
  accountName,
}: {
  platform: AvailablePlatform;
  accountName?: string;
}) {
  const { t } = useTranslation('composer');
  const video = useSelector((state: RootState) => state.composer.video);
  const title = useSelector((state: RootState) => state.composer.title);
  const description = useSelector((state: RootState) => state.composer.description);
  const hashtags = useSelector((state: RootState) => state.composer.hashtags);
  const shape = PREVIEW_SHAPES[platform];
  const tags = hashtags.map((tag) => `#${tag}`).join(' ');
  const caption = [title.trim(), description.trim()].filter(Boolean).join('\n\n');
  const name = accountName ?? getLabelFor(platform);

  const frame = (className: string) => (
    <div
      className={`relative grid flex-none place-items-center overflow-hidden bg-surface-tertiary ${className}`}
    >
      {video?.thumbnailDataUrl ? (
        <img
          src={video.thumbnailDataUrl}
          alt=""
          className="absolute inset-0 size-full object-cover"
        />
      ) : (
        <Film className="size-6 text-muted" />
      )}
    </div>
  );

  return (
    <section
      aria-label={t('drawer.preview')}
      className="flex flex-wrap items-start gap-4 rounded-[14px] bg-surface-secondary p-4"
    >
      {shape === 'vertical' && (
        <div className="relative h-66.5 w-37.5 flex-none overflow-hidden rounded-[14px]">
          {frame('size-full')}
          <div className="absolute inset-x-0 bottom-0 bg-black/60 p-2.5 text-[11px] leading-snug text-white">
            <div className="mb-0.5 font-semibold">{name}</div>
            <p className="line-clamp-4 whitespace-pre-line">{caption}</p>
            {tags && <p className="mt-0.5 line-clamp-2 text-accent-soft">{tags}</p>}
          </div>
        </div>
      )}
      {shape === 'video' && (
        <div className="w-60 flex-none">
          {frame('aspect-video w-full rounded-xl')}
          <p className="mt-2 line-clamp-2 text-[13px] leading-snug font-semibold">
            {title || t('drawer.noTitle')}
          </p>
          <p className="mt-0.5 text-[11px] text-muted">{name}</p>
        </div>
      )}
      {shape === 'post' && (
        <div className="w-60 flex-none rounded-xl bg-surface p-3">
          <p className="text-[13px] font-semibold">{name}</p>
          <p className="mt-1 line-clamp-4 text-[13px] whitespace-pre-line">{caption}</p>
          {tags && <p className="line-clamp-2 text-[13px] text-accent">{tags}</p>}
          {frame('mt-2 aspect-video w-full rounded-lg')}
        </div>
      )}
      <div className="flex min-w-0 flex-[1_1_180px] flex-col gap-2 text-[13px]">
        <span className={SECTION}>{t('drawer.preview')}</span>
        <span>{t('drawer.previewLead', { platform: getLabelFor(platform) })}</span>
        <span className="text-muted">{t(`drawer.note.${platform}`)}</span>
      </div>
    </section>
  );
}
