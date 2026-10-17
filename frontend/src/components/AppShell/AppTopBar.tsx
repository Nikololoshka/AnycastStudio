import { Button, Popover, SearchField } from '@heroui/react';
import { Bell } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router';
import { ACCOUNT_SECTIONS } from '../../features/account';
import { NAV_ITEMS } from './navItems';
import { useScrolled } from './useScrolled';

export function AppTopBar() {
  const { t } = useTranslation();
  const { t: tAccount } = useTranslation('account');
  const { pathname, hash } = useLocation();
  const scrolled = useScrolled(4);
  const page = NAV_ITEMS.find((item) => pathname.startsWith(item.to));
  const accountSection =
    pathname === '/account'
      ? ACCOUNT_SECTIONS.find((section) => `#${section}` === hash)
      : undefined;

  const notificationsLabel = t('topBar.notifications');

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
        {page ? t(page.key) : pathname === '/account' && t('nav.account')}
        {accountSection && ` · ${tAccount(`sections.${accountSection}`)}`}
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

    </header>
  );
}
