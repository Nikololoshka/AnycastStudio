import { History } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export function HistoryPanel() {
  const { t } = useTranslation();

  return (
    <div className="flex h-full flex-col px-5 pt-7">
      <h2 className="font-display text-xl font-semibold tracking-tight">{t('history.title')}</h2>
      <div className="flex flex-1 flex-col items-center justify-center gap-3 pb-16 text-center">
        <span className="grid size-10 place-items-center rounded-xl border border-border bg-surface text-muted">
          <History className="size-5" />
        </span>
        <p className="max-w-44 text-sm text-muted">{t('history.empty')}</p>
      </div>
    </div>
  );
}
