import { useEffect, useState } from 'react';
import { Button, Tooltip } from '@heroui/react';
import {
  FolderCog,
  Languages,
  Monitor,
  Moon,
  ScrollText,
  Sun,
  type LucideIcon,
} from 'lucide-react';
import { getVersion } from '@tauri-apps/api/app';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import type { AppDispatch, RootState } from '../../app/store';
import { nextLanguage } from '../../app/i18n';
import { changeLanguage, changeTheme, type ThemePreference } from '../../features/settings';
import { openLogsFolder } from '../../services/logs';
import { openAppDataFolder } from '../../services/persistence';
import { AppMark } from './AppMark';
import { WindowControls } from './WindowControls';

const THEME_CYCLE: Record<ThemePreference, ThemePreference> = {
  system: 'light',
  light: 'dark',
  dark: 'system',
};

const THEME_ICONS: Record<ThemePreference, LucideIcon> = {
  system: Monitor,
  light: Sun,
  dark: Moon,
};

export function AppTopBar() {
  const { t } = useTranslation();
  const dispatch = useDispatch<AppDispatch>();
  const theme = useSelector((state: RootState) => state.settings.theme);
  const language = useSelector((state: RootState) => state.settings.language);
  const [version, setVersion] = useState('');
  const ThemeIcon = THEME_ICONS[theme];

  const appDataLabel = t('topBar.appDataFolder');
  const logsLabel = t('topBar.logsFolder');
  const themeLabel = t(`topBar.theme.${theme}`);
  const languageLabel = t(`topBar.language.${language}`);

  useEffect(() => {
    getVersion().then(setVersion);
  }, []);

  return (
    <header data-tauri-drag-region className="flex h-11 shrink-0 items-center gap-3 pr-2 pl-4">
      <AppMark />
      <span
        data-tauri-drag-region
        className="font-display text-[17px] font-semibold tracking-tight"
      >
        {t('app.name')}
      </span>
      {version && (
        <span className="text-xs text-muted tabular-nums">{t('app.version', { version })}</span>
      )}

      <Tooltip delay={400}>
        <Button
          isIconOnly
          size="sm"
          variant="ghost"
          aria-label={appDataLabel}
          className="ml-auto"
          onPress={() => {
            void openAppDataFolder();
          }}
        >
          <FolderCog className="size-4" />
        </Button>
        <Tooltip.Content placement="bottom end">{appDataLabel}</Tooltip.Content>
      </Tooltip>

      <Tooltip delay={400}>
        <Button
          isIconOnly
          size="sm"
          variant="ghost"
          aria-label={logsLabel}
          onPress={() => {
            void openLogsFolder();
          }}
        >
          <ScrollText className="size-4" />
        </Button>
        <Tooltip.Content placement="bottom end">{logsLabel}</Tooltip.Content>
      </Tooltip>

      <Tooltip delay={400}>
        <Button
          isIconOnly
          size="sm"
          variant="ghost"
          aria-label={languageLabel}
          onPress={() => dispatch(changeLanguage(nextLanguage(language)))}
        >
          <span className="relative grid place-items-center">
            <Languages className="size-4" />
            <span className="absolute -right-2 -bottom-2 text-[9px] font-semibold uppercase text-muted">
              {language}
            </span>
          </span>
        </Button>
        <Tooltip.Content placement="bottom end">{languageLabel}</Tooltip.Content>
      </Tooltip>

      <Tooltip delay={400}>
        <Button
          isIconOnly
          size="sm"
          variant="ghost"
          aria-label={themeLabel}
          onPress={() => dispatch(changeTheme(THEME_CYCLE[theme]))}
        >
          <ThemeIcon className="size-4" />
        </Button>
        <Tooltip.Content placement="bottom end">{themeLabel}</Tooltip.Content>
      </Tooltip>
      <WindowControls />
    </header>
  );
}
