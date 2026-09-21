import { Button } from '@heroui/react';
import { useTranslation } from 'react-i18next';
import { Copy, Minus, Square, X } from 'lucide-react';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { useWindowMaximized } from './useWindowMaximized';

export function WindowControls() {
  const { t } = useTranslation();
  const isMaximized = useWindowMaximized();
  const appWindow = getCurrentWindow();
  const RestoreIcon = isMaximized ? Copy : Square;

  return (
    <div className="flex items-center gap-1">
      <Button
        isIconOnly
        size="sm"
        variant="ghost"
        aria-label={t('window.minimize')}
        onPress={() => appWindow.minimize()}
      >
        <Minus className="size-4" />
      </Button>
      <Button
        isIconOnly
        size="sm"
        variant="ghost"
        aria-label={isMaximized ? t('window.restore') : t('window.maximize')}
        onPress={() => appWindow.toggleMaximize()}
      >
        <RestoreIcon className="size-3.5" />
      </Button>
      <Button
        isIconOnly
        size="sm"
        variant="ghost"
        aria-label={t('window.close')}
        className="hover:bg-danger hover:text-white"
        onPress={() => appWindow.close()}
      >
        <X className="size-4" />
      </Button>
    </div>
  );
}
