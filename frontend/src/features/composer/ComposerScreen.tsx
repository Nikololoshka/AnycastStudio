import { useState, type Key } from 'react';
import { Tabs } from '@heroui/react';
import { AnimatePresence, motion } from 'motion/react';
import { PenLine } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { AVAILABLE_PLATFORMS, type AvailablePlatform } from '../../domain/platform/order';
import { getLabelFor } from '../../platforms/registry';
import { PlatformGlyph } from '../../components/PlatformGlyph';
import { ComposerCommonTab } from './ComposerCommonTab';
import { PlatformTab } from './PlatformTab';
import { SummaryPanel } from './SummaryPanel';

type ComposerTab = 'common' | AvailablePlatform;

export function ComposerScreen() {
  const { t } = useTranslation('composer');
  const [tab, setTab] = useState<ComposerTab>('common');

  return (
    <div className="grid gap-6 pt-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="rounded-2xl border border-border bg-surface">
        <header className="px-6 pt-6 pb-4">
          <h1 className="font-display text-xl font-semibold tracking-tight">{t('screen.title')}</h1>
          <p className="mt-1 text-sm text-muted">{t('screen.subtitle')}</p>
        </header>

        <Tabs
          selectedKey={tab}
          onSelectionChange={(key: Key) => setTab(key as ComposerTab)}
          className="flex flex-col"
        >
          <Tabs.ListContainer className="mx-6">
            <Tabs.List aria-label={t('screen.tabsLabel')} className="w-full">
              <Tabs.Tab id="common" className="gap-2">
                <PenLine className="size-4" />
                {t('screen.postTab')}
                <Tabs.Indicator />
              </Tabs.Tab>
              {AVAILABLE_PLATFORMS.map((platform) => (
                <Tabs.Tab key={platform} id={platform} className="gap-2">
                  <PlatformGlyph platform={platform} size="sm" />
                  {getLabelFor(platform)}
                  <Tabs.Indicator />
                </Tabs.Tab>
              ))}
            </Tabs.List>
          </Tabs.ListContainer>

          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={tab}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <Tabs.Panel id={tab} className="px-6 py-6">
                {tab === 'common' ? <ComposerCommonTab /> : <PlatformTab platform={tab} />}
              </Tabs.Panel>
            </motion.div>
          </AnimatePresence>
        </Tabs>
      </div>

      <SummaryPanel />
    </div>
  );
}
