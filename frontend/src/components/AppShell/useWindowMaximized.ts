import { useEffect, useState } from 'react';
import { getCurrentWindow } from '@tauri-apps/api/window';

export function useWindowMaximized() {
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    const appWindow = getCurrentWindow();
    let disposed = false;
    let unlisten: (() => void) | undefined;

    const sync = () => {
      appWindow.isMaximized().then((value) => {
        if (!disposed) setIsMaximized(value);
      });
    };

    sync();
    appWindow.onResized(sync).then((stop) => {
      if (disposed) stop();
      else unlisten = stop;
    });

    return () => {
      disposed = true;
      unlisten?.();
    };
  }, []);

  return isMaximized;
}
