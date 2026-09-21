import { Button, Separator, Tooltip } from '@heroui/react';
import { Languages, LogOut, Monitor, Moon, Sun, type LucideIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { NavLink, useNavigate } from 'react-router';
import { useGetSessionQuery, useLogoutMutation } from '../../api';
import { nextLanguage } from '../../app/i18n';
import type { AppDispatch, RootState } from '../../app/store';
import { changeLanguage, changeTheme, type ThemePreference } from '../../features/settings';
import { AppMark } from './AppMark';

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

const NAV_ITEMS = [
  { to: '/compose', key: 'nav.compose' },
  { to: '/publications', key: 'nav.publications' },
  { to: '/settings/accounts', key: 'nav.accounts' },
] as const;

function navClass({ isActive }: { isActive: boolean }): string {
  return [
    'rounded-lg px-3 py-1.5 text-sm transition-colors',
    isActive ? 'bg-surface text-foreground' : 'text-muted hover:text-foreground',
  ].join(' ');
}

export function AppTopBar() {
  const { t } = useTranslation();
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();
  const theme = useSelector((state: RootState) => state.settings.theme);
  const language = useSelector((state: RootState) => state.settings.language);
  const { data: user } = useGetSessionQuery();
  const [logout] = useLogoutMutation();

  const ThemeIcon = THEME_ICONS[theme];
  const themeLabel = t(`topBar.theme.${theme}`);
  const languageLabel = t(`topBar.language.${language}`);
  const signOutLabel = t('topBar.signOut');

  async function signOut() {
    await logout().unwrap().catch(() => undefined);
    void navigate('/login', { replace: true });
  }

  return (
    <header className="mx-auto flex h-14 w-full max-w-6xl shrink-0 items-center gap-3 px-4">
      <AppMark />
      <span className="font-display text-[17px] font-semibold tracking-tight">{t('app.name')}</span>

      <Separator orientation="vertical" className="mx-1 h-6" />

      <nav className="flex items-center gap-1">
        {NAV_ITEMS.map((item) => (
          <NavLink key={item.to} to={item.to} className={navClass}>
            {t(item.key)}
          </NavLink>
        ))}
      </nav>

      <Tooltip delay={400}>
        <Button
          isIconOnly
          size="sm"
          variant="ghost"
          aria-label={languageLabel}
          className="ml-auto"
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

      {user && (
        <>
          <Separator orientation="vertical" className="mx-1 h-6" />
          <span className="max-w-40 truncate text-sm text-muted">{user.name}</span>
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
        </>
      )}
    </header>
  );
}
