import enAccounts from '../../locales/en/accounts.json';
import enCommon from '../../locales/en/common.json';
import enComposer from '../../locales/en/composer.json';
import enPlatforms from '../../locales/en/platforms.json';
import ruAccounts from '../../locales/ru/accounts.json';
import ruCommon from '../../locales/ru/common.json';
import ruComposer from '../../locales/ru/composer.json';
import ruPlatforms from '../../locales/ru/platforms.json';

export const DEFAULT_NAMESPACE = 'common';

export const resources = {
  en: {
    common: enCommon,
    composer: enComposer,
    accounts: enAccounts,
    platforms: enPlatforms,
  },
  ru: {
    common: ruCommon,
    composer: ruComposer,
    accounts: ruAccounts,
    platforms: ruPlatforms,
  },
} as const;
