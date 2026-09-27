import { Trans, useTranslation } from 'react-i18next';
import { useSelector } from 'react-redux';
import type { RootState } from '../../app/store';
import { tiktokSettingsOf } from './settings';

const MUSIC_USAGE_URL = 'https://www.tiktok.com/legal/page/global/music-usage-confirmation/en';
const BRANDED_CONTENT_URL = 'https://www.tiktok.com/legal/page/global/bc-policy/en';

function PolicyLink({ href, children }: { href: string; children?: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="text-accent hover:underline">
      {children}
    </a>
  );
}

export function TikTokConsent() {
  const { t } = useTranslation('platforms');
  const settings = tiktokSettingsOf(
    useSelector((state: RootState) => state.composer.platformSettings.tiktok),
  );
  const isBranded = settings.discloseContent && settings.brandContent;

  return (
    <p className="text-center text-xs text-muted">
      <Trans
        t={t}
        i18nKey={isBranded ? 'tiktok.consent.withBrandedContent' : 'tiktok.consent.music'}
        components={{
          music: <PolicyLink href={MUSIC_USAGE_URL} />,
          branded: <PolicyLink href={BRANDED_CONTENT_URL} />,
        }}
      />
    </p>
  );
}
