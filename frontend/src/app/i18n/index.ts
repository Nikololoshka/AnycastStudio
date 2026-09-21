import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
import { FALLBACK_LANGUAGE } from './languages';
import { DEFAULT_NAMESPACE, resources } from './resources';

void i18next.use(initReactI18next).init({
  resources,
  lng: FALLBACK_LANGUAGE,
  fallbackLng: FALLBACK_LANGUAGE,
  defaultNS: DEFAULT_NAMESPACE,
  interpolation: { escapeValue: false },
});

export { i18next };
export * from './languages';
