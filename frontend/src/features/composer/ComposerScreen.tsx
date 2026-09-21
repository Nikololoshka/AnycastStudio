import { useState, type Key } from 'react';
import { Tabs } from '@heroui/react';
import { AnimatePresence, motion } from 'motion/react';
import { PenLine } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { Platform } from '../../domain/platform/types';
import { PLATFORMS } from '../../domain/platform/order';
import { getLabelFor } from '../../platforms/capabilities';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { ComposerCommonTab } from './ComposerCommonTab';
import { usePlatformShortcuts } from './platformShortcuts';
import { PlatformTab } from './PlatformTab';

type ComposerTab = 'common' | Platform;

export function ComposerScreen() {
  const { t } = useTranslation('composer');
  const [tab, setTab] = useState<ComposerTab>('common');
  usePlatformShortcuts();

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="shrink-0 px-8 pt-7 pb-4">
        <h1 className="font-display text-xl font-semibold tracking-tight">{t('screen.title')}</h1>
        <p className="mt-1 text-sm text-muted">{t('screen.subtitle')}</p>
      </header>

      <Tabs
        selectedKey={tab}
        onSelectionChange={(key: Key) => setTab(key as ComposerTab)}
        className="flex min-h-0 flex-1 flex-col"
      >
        <Tabs.ListContainer className="mx-8 shrink-0">
          <Tabs.List aria-label={t('screen.tabsLabel')} className="w-full">
            <Tabs.Tab id="common" className="gap-2">
              <PenLine className="size-4" />
              {t('screen.postTab')}
              <Tabs.Indicator />
            </Tabs.Tab>
            {PLATFORMS.map((platform) => (
              <Tabs.Tab key={platform} id={platform} className="gap-2">
                <PlatformGlyph platform={platform} size="sm" />
                {getLabelFor(platform)}
                <Tabs.Indicator />
              </Tabs.Tab>
            ))}
          </Tabs.List>
        </Tabs.ListContainer>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={tab}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <Tabs.Panel id={tab} className="px-8 py-6">
                {tab === 'common' ? <ComposerCommonTab /> : <PlatformTab platform={tab} />}
              </Tabs.Panel>
            </motion.div>
          </AnimatePresence>
        </div>
      </Tabs>
    </div>
  );
}
