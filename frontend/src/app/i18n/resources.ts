import enAccounts from '../../locales/en/accounts.json';
import enAuth from '../../locales/en/auth.json';
import enCommon from '../../locales/en/common.json';
import enComposer from '../../locales/en/composer.json';
import enPlatforms from '../../locales/en/platforms.json';
import enPublications from '../../locales/en/publications.json';
import ruAccounts from '../../locales/ru/accounts.json';
import ruAuth from '../../locales/ru/auth.json';
import ruCommon from '../../locales/ru/common.json';
import ruComposer from '../../locales/ru/composer.json';
import ruPlatforms from '../../locales/ru/platforms.json';
import ruPublications from '../../locales/ru/publications.json';

export const DEFAULT_NAMESPACE = 'common';

export const resources = {
  en: {
    common: enCommon,
    auth: enAuth,
    composer: enComposer,
    accounts: enAccounts,
    platforms: enPlatforms,
    publications: enPublications,
  },
  ru: {
    common: ruCommon,
    auth: ruAuth,
    composer: ruComposer,
    accounts: ruAccounts,
    platforms: ruPlatforms,
    publications: ruPublications,
  },
} as const;
