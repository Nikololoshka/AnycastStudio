import { Avatar } from '@heroui/react';
import { useTranslation } from 'react-i18next';
import { Link, NavLink } from 'react-router';
import { useGetSessionQuery } from '../../api';
import { StorageMeter } from '../../features/media';
import { AppMark } from './AppMark';
import { NAV_ITEMS } from './navItems';

function navClass({ isActive }: { isActive: boolean }): string {
  return [
    'flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-colors',
    isActive
      ? 'bg-accent-soft text-accent-soft-foreground'
      : 'text-muted-strong hover:bg-surface-secondary hover:text-foreground',
  ].join(' ');
}

export function AppSidebar() {
  const { t } = useTranslation();
  const { data: user } = useGetSessionQuery();

  return (
    <aside className="flex flex-col gap-6 border-b border-border bg-surface px-3 py-5 min-[900px]:sticky min-[900px]:top-0 min-[900px]:h-dvh min-[900px]:w-62 min-[900px]:shrink-0 min-[900px]:overflow-y-auto min-[900px]:border-r min-[900px]:border-b-0">
      <div className="flex items-center gap-2.5 px-2">
        <AppMark />
        <span className="text-lg font-bold tracking-tight">{t('app.name')}</span>
      </div>

      <nav aria-label={t('nav.label')} className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ to, key, icon: Icon }) => (
          <NavLink key={to} to={to} className={navClass}>
            <Icon className="size-5 shrink-0" strokeWidth={1.8} />
            {t(key)}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-3">
        <Link
          to="/library"
          className="rounded-xl bg-surface-secondary p-3 transition-colors hover:bg-surface-tertiary"
        >
          <StorageMeter />
        </Link>

        {user && (
          <NavLink
            to="/account"
            className={({ isActive }) =>
              [
                'flex items-center gap-2.5 rounded-xl p-2 transition-colors',
                isActive ? 'bg-accent-soft' : 'hover:bg-surface-secondary',
              ].join(' ')
            }
          >
            <Avatar color="accent" variant="soft" className="shrink-0">
              <Avatar.Fallback>{user.name.charAt(0).toUpperCase()}</Avatar.Fallback>
            </Avatar>
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{user.name}</span>
              <span className="block truncate text-xs text-muted">{user.email}</span>
            </span>
          </NavLink>
        )}
      </div>
    </aside>
  );
}
