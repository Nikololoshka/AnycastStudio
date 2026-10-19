import enAccount from '../../locales/en/account.json';
import enAccounts from '../../locales/en/accounts.json';
import enAuth from '../../locales/en/auth.json';
import enLegal from '../../locales/en/legal.json';
import enCommon from '../../locales/en/common.json';
import enComposer from '../../locales/en/composer.json';
import enMedia from '../../locales/en/media.json';
import enOverview from '../../locales/en/overview.json';
import enPlatforms from '../../locales/en/platforms.json';
import enPublications from '../../locales/en/publications.json';
import ruAccount from '../../locales/ru/account.json';
import ruAccounts from '../../locales/ru/accounts.json';
import ruAuth from '../../locales/ru/auth.json';
import ruLegal from '../../locales/ru/legal.json';
import ruCommon from '../../locales/ru/common.json';
import ruComposer from '../../locales/ru/composer.json';
import ruMedia from '../../locales/ru/media.json';
import ruOverview from '../../locales/ru/overview.json';
import ruPlatforms from '../../locales/ru/platforms.json';
import ruPublications from '../../locales/ru/publications.json';

export const DEFAULT_NAMESPACE = 'common';

export const resources = {
  en: {
    common: enCommon,
    auth: enAuth,
    legal: enLegal,
    composer: enComposer,
    accounts: enAccounts,
    account: enAccount,
    media: enMedia,
    overview: enOverview,
    platforms: enPlatforms,
    publications: enPublications,
  },
  ru: {
    common: ruCommon,
    auth: ruAuth,
    legal: ruLegal,
    composer: ruComposer,
    accounts: ruAccounts,
    account: ruAccount,
    media: ruMedia,
    overview: ruOverview,
    platforms: ruPlatforms,
    publications: ruPublications,
  },
} as const;
