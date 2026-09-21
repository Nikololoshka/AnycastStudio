import { useEffect, type PropsWithChildren } from 'react';
import { MotionConfig } from 'motion/react';
import { I18nextProvider } from 'react-i18next';
import { I18nProvider } from 'react-aria-components';
import { Provider, useSelector } from 'react-redux';
import { store, type RootState } from '../store';
import { i18next } from '../i18n';

const DARK_SCHEME_QUERY = '(prefers-color-scheme: dark)';

function applyColorScheme(isDark: boolean) {
  const root = document.documentElement;
  root.classList.toggle('dark', isDark);
  root.classList.toggle('light', !isDark);
  root.dataset.theme = isDark ? 'dark' : 'light';
}

function ThemeSync({ children }: PropsWithChildren) {
  const preference = useSelector((state: RootState) => state.settings.theme);

  useEffect(() => {
    if (preference !== 'system') {
      applyColorScheme(preference === 'dark');
      return;
    }

    const systemScheme = window.matchMedia(DARK_SCHEME_QUERY);
    applyColorScheme(systemScheme.matches);
    const followSystem = (event: MediaQueryListEvent) => applyColorScheme(event.matches);
    systemScheme.addEventListener('change', followSystem);
    return () => systemScheme.removeEventListener('change', followSystem);
  }, [preference]);

  return <>{children}</>;
}

function LanguageSync({ children }: PropsWithChildren) {
  const language = useSelector((state: RootState) => state.settings.language);

  useEffect(() => {
    void i18next.changeLanguage(language);
    document.documentElement.lang = language;
  }, [language]);

  return <I18nProvider locale={language}>{children}</I18nProvider>;
}

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <Provider store={store}>
      <I18nextProvider i18n={i18next}>
        <MotionConfig reducedMotion="user">
          <LanguageSync>
            <ThemeSync>{children}</ThemeSync>
          </LanguageSync>
        </MotionConfig>
      </I18nextProvider>
    </Provider>
  );
}
