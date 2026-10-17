import {
  useLayoutEffect,
  useEffect,
  useRef,
  useState,
  type MouseEvent,
  type ReactNode,
} from 'react';
import {
  Avatar,
  Button,
  buttonVariants,
  Chip,
  Spinner,
} from '@heroui/react';
import { FolderOpen, LogOut } from 'lucide-react';
import { useReducedMotion } from 'motion/react';
import { useTranslation } from 'react-i18next';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useLocation, useNavigate } from 'react-router';
import {
  AUTO_DELETE_DAYS,
  useGetProfilePreferencesQuery,
  useGetSessionQuery,
  useUpdateProfilePreferencesMutation,
  type AutoDeleteDays,
  type ProfilePreferences,
} from '../../api';
import { LANGUAGES, type Language } from '../../app/i18n';
import type { AppDispatch, RootState } from '../../app/store';
import { SettingSelect } from '../../components/SettingSelect';
import { SettingSwitch } from '../../components/SettingSwitch';
import { useSignOut } from '../auth';
import { StorageMeter } from '../media';
import { changeLanguage, changeTheme, type ThemePreference } from '../settings';
import { ACCOUNT_SECTIONS, type AccountSection } from './sections';
import { useActiveSection } from './useActiveSection';

const THEMES: ThemePreference[] = ['system', 'light', 'dark'];

const TIME_ZONES = [
  'Europe/Moscow',
  'Europe/Berlin',
  'Europe/London',
  'America/New_York',
  'America/Los_Angeles',
  'Asia/Tokyo',
];

type Save = (changes: Partial<ProfilePreferences>) => void;

function sectionFromHash(hash: string): AccountSection | undefined {
  return ACCOUNT_SECTIONS.find((section) => `#${section}` === hash);
}

function timeZoneLabel(timeZone: string, language: string): string {
  const name = (style: 'longGeneric' | 'shortOffset') =>
    new Intl.DateTimeFormat(language, { timeZone, timeZoneName: style })
      .formatToParts()
      .find((part) => part.type === 'timeZoneName')?.value ?? timeZone;
  return `${name('longGeneric')} (${name('shortOffset')})`;
}

function Section({
  id,
  title,
  action,
  className = 'bg-surface shadow-surface',
  children,
}: {
  id: AccountSection;
  title: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      className={`flex scroll-mt-22 flex-col gap-5 rounded-[14px] p-6 ${className}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={`${id}-heading`} className="text-lg font-semibold">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function ProfileSection({ preferences, save }: { preferences: ProfilePreferences; save: Save }) {
  const { t, i18n } = useTranslation('account');
  const dispatch = useDispatch<AppDispatch>();
  const { data: user } = useGetSessionQuery();
  const language = useSelector((state: RootState) => state.settings.language);
  const theme = useSelector((state: RootState) => state.settings.theme);
  const timeZones = [...new Set([preferences.timeZone, ...TIME_ZONES])];

  return (
    <Section id="profile" title={t('sections.profile')}>
      <div className="flex items-center gap-4">
        <Avatar size="lg" color="accent" variant="soft" className="shrink-0">
          <Avatar.Fallback>{user?.name.charAt(0).toUpperCase()}</Avatar.Fallback>
        </Avatar>
        <div className="min-w-0">
          <p className="truncate text-[15px] font-semibold">{user?.name}</p>
          <p className="truncate text-sm text-muted">{user?.email}</p>
        </div>
      </div>
      <p className="rounded-xl bg-surface-secondary px-4 py-3 text-sm text-muted">
        {t('profile.managed')}
      </p>
      <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        <SettingSelect<Language>
          label={t('profile.language')}
          value={language}
          options={LANGUAGES.map((value) => ({ value, label: t(`languages.${value}`) }))}
          onChange={(value) => dispatch(changeLanguage(value))}
        />
        <SettingSelect<ThemePreference>
          label={t('profile.theme')}
          value={theme}
          options={THEMES.map((value) => ({ value, label: t(`themes.${value}`) }))}
          onChange={(value) => dispatch(changeTheme(value))}
        />
        <SettingSelect
          label={t('profile.timeZone')}
          description={t('profile.timeZoneHint')}
          value={preferences.timeZone}
          options={timeZones.map((value) => ({
            value,
            label: timeZoneLabel(value, i18n.language),
          }))}
          onChange={(timeZone) => save({ timeZone })}
        />
      </div>
    </Section>
  );
}

function StorageSection({ preferences, save }: { preferences: ProfilePreferences; save: Save }) {
  const { t } = useTranslation('account');
  const { autoDeleteSources } = preferences;

  return (
    <Section id="storage" title={t('sections.storage')}>
      <StorageMeter />
      <div className="flex flex-col gap-2 border-t border-border pt-4">
        <SettingSwitch
          label={t('storage.autoDelete')}
          description={t('storage.autoDeleteHint')}
          isSelected={autoDeleteSources.enabled}
          onChange={(enabled) => save({ autoDeleteSources: { ...autoDeleteSources, enabled } })}
        />
        {autoDeleteSources.enabled && (
          <div className="sm:max-w-60">
            <SettingSelect
              label={t('storage.afterDays')}
              value={String(autoDeleteSources.afterDays)}
              options={AUTO_DELETE_DAYS.map((days) => ({
                value: String(days),
                label: t('storage.days', { count: days }),
              }))}
              onChange={(value) =>
                save({
                  autoDeleteSources: {
                    ...autoDeleteSources,
                    afterDays: Number(value) as AutoDeleteDays,
                  },
                })
              }
            />
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/library" className={buttonVariants({ variant: 'tertiary' })}>
          <FolderOpen className="size-4" />
          {t('storage.openLibrary')}
        </Link>
        <Button variant="primary" isDisabled>
          {t('storage.upgrade')}
        </Button>
        <Chip size="sm" variant="soft">
          {t('storage.upgradeSoon')}
        </Chip>
      </div>
    </Section>
  );
}

function AccountSections({ preferences }: { preferences: ProfilePreferences }) {
  const { t } = useTranslation('account');
  const [update] = useUpdateProfilePreferencesMutation();
  const navigate = useNavigate();
  const { hash } = useLocation();
  const reduceMotion = useReducedMotion();
  const endRef = useRef<HTMLDivElement>(null);
  const [initial] = useState(() => sectionFromHash(window.location.hash));
  const active = useActiveSection(ACCOUNT_SECTIONS, initial ?? ACCOUNT_SECTIONS[0], endRef);

  const save: Save = (changes) => void update({ ...preferences, ...changes });

  useLayoutEffect(() => {
    if (initial) document.getElementById(initial)?.scrollIntoView({ block: 'start' });
  }, [initial]);

  useEffect(() => {
    if (hash !== `#${active}`) {
      void navigate({ hash: active }, { replace: true, preventScrollReset: true });
    }
  }, [active, hash, navigate]);

  function jump(event: MouseEvent, section: AccountSection) {
    event.preventDefault();
    document
      .getElementById(section)
      ?.scrollIntoView({ behavior: reduceMotion ? 'instant' : 'smooth', block: 'start' });
  }

  return (
    <div className="flex items-start gap-8">
      <nav
        aria-label={t('toc.label')}
        className="sticky top-22 hidden w-48 shrink-0 flex-col border-l border-border lg:flex"
      >
        {ACCOUNT_SECTIONS.map((section) => (
          <a
            key={section}
            href={`#${section}`}
            aria-current={section === active ? 'location' : undefined}
            onClick={(event) => jump(event, section)}
            className={[
              '-ml-px border-l-2 py-2 pl-4 text-sm transition-colors motion-reduce:transition-none',
              section === active
                ? 'border-accent font-medium text-foreground'
                : 'border-transparent text-muted hover:text-foreground',
            ].join(' ')}
          >
            {t(`sections.${section}`)}
          </a>
        ))}
      </nav>

      <div className="flex min-w-0 flex-1 flex-col gap-6">
        <ProfileSection preferences={preferences} save={save} />
        <StorageSection preferences={preferences} save={save} />
        <div ref={endRef} />
      </div>
    </div>
  );
}

export function AccountScreen() {
  const { t } = useTranslation('account');
  const { data: preferences } = useGetProfilePreferencesQuery();
  const signOut = useSignOut();

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('screen.title')}</h1>
          <p className="mt-1 text-[15px] text-muted">{t('screen.subtitle')}</p>
        </div>
        <Button variant="tertiary" onPress={() => void signOut()}>
          <LogOut className="size-4" />
          {t('screen.signOut')}
        </Button>
      </header>

      {preferences ? (
        <AccountSections preferences={preferences} />
      ) : (
        <div className="grid place-items-center py-16">
          <Spinner />
        </div>
      )}
    </div>
  );
}
