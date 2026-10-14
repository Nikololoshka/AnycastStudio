import { Button, Popover, SearchField, Tooltip } from '@heroui/react';
import { Bell, Languages, LogOut, Monitor, Moon, Sun, type LucideIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { useLocation, useNavigate } from 'react-router';
import { useLogoutMutation } from '../../api';
import { nextLanguage } from '../../app/i18n';
import type { AppDispatch, RootState } from '../../app/store';
import { changeLanguage, changeTheme, type ThemePreference } from '../../features/settings';
import { NAV_ITEMS } from './navItems';
import { useScrolled } from './useScrolled';

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
  const navigate = useNavigate();
  const theme = useSelector((state: RootState) => state.settings.theme);
  const language = useSelector((state: RootState) => state.settings.language);
  const [logout] = useLogoutMutation();
  const { pathname } = useLocation();
  const scrolled = useScrolled(4);
  const page = NAV_ITEMS.find((item) => pathname.startsWith(item.to));

  const ThemeIcon = THEME_ICONS[theme];
  const themeLabel = t(`topBar.theme.${theme}`);
  const languageLabel = t(`topBar.language.${language}`);
  const signOutLabel = t('topBar.signOut');
  const notificationsLabel = t('topBar.notifications');

  async function signOut() {
    await logout()
      .unwrap()
      .catch(() => undefined);
    void navigate('/login', { replace: true });
  }

  return (
    <header
      className={[
        'sticky top-0 z-30 flex h-16 items-center gap-2 border-b px-4 backdrop-blur-xl backdrop-saturate-150 transition-[background-color,border-color,box-shadow] motion-reduce:transition-none sm:px-6 lg:px-10',
        scrolled ? 'border-border bg-surface/70 shadow-sm' : 'border-transparent',
      ].join(' ')}
    >
      <span
        aria-hidden={!scrolled}
        className={[
          'min-w-0 flex-1 truncate text-base font-semibold transition-opacity motion-reduce:transition-none',
          scrolled ? 'opacity-100' : 'opacity-0',
        ].join(' ')}
      >
        {page && t(page.key)}
      </span>

      <SearchField aria-label={t('topBar.search')} className="w-65 min-w-0 shrink">
        <SearchField.Group>
          <SearchField.SearchIcon />
          <SearchField.Input placeholder={t('topBar.search')} />
          <SearchField.ClearButton />
        </SearchField.Group>
      </SearchField>

      <Popover>
        <Button isIconOnly variant="ghost" aria-label={notificationsLabel}>
          <Bell className="size-5" strokeWidth={1.8} />
        </Button>
        <Popover.Content placement="bottom end">
          <Popover.Dialog aria-label={notificationsLabel} className="w-64 p-4 text-sm text-muted">
            {t('topBar.notificationsEmpty')}
          </Popover.Dialog>
        </Popover.Content>
      </Popover>

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

      <Tooltip delay={400}>
        <Button
          isIconOnly
          size="sm"
          variant="ghost"
          aria-label={signOutLabel}
          onPress={() => void signOut()}
        >
          <LogOut className="size-4" />
        </Button>
        <Tooltip.Content placement="bottom end">{signOutLabel}</Tooltip.Content>
      </Tooltip>
    </header>
  );
}
