import { buttonVariants, Card } from '@heroui/react';
import { Trans, useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { AppMark } from '../../components/AppShell';
import type legalTexts from '../../locales/en/legal.json';

export type LegalDocument = 'privacy' | 'terms';

const CONTACT_EMAIL = 'nikololoshka@gmail.com';

function RichText({ text }: { text: string }) {
  return (
    <Trans
      defaults={text}
      components={{
        mail: (
          <a href={`mailto:${CONTACT_EMAIL}`} className="text-accent hover:underline">
            {CONTACT_EMAIL}
          </a>
        ),
        privacy: <Link to="/privacy" className="text-accent hover:underline" />,
      }}
    />
  );
}

export function LegalScreen({ document }: { document: LegalDocument }) {
  const { i18n } = useTranslation();
  const texts = i18n.getResourceBundle(i18n.resolvedLanguage ?? 'en', 'legal') as typeof legalTexts;
  const { title, intro, sections } = texts[document];

  return (
    <main className="min-h-screen bg-window-backdrop px-4 py-10 text-foreground">
      <Card className="mx-auto w-full max-w-2xl">
        <Card.Header className="flex flex-col items-start gap-3">
          <AppMark />
          <Card.Title className="font-display text-2xl font-semibold tracking-tight">
            {title}
          </Card.Title>
          <Card.Description className="flex flex-col gap-1">
            <span>{texts.updated}</span>
            <span>
              <RichText text={texts.contact} />
            </span>
          </Card.Description>
        </Card.Header>

        <Card.Content className="flex flex-col gap-6 text-sm">
          <p>{intro}</p>
          {sections.map((section) => (
            <section key={section.title} className="flex flex-col gap-2">
              <h2 className="font-display text-lg font-semibold">{section.title}</h2>
              {section.text.map((paragraph) => (
                <p key={paragraph}>
                  <RichText text={paragraph} />
                </p>
              ))}
              {section.items.length > 0 && (
                <ul className="flex list-disc flex-col gap-1 pl-5">
                  {section.items.map((item) => (
                    <li key={item}>
                      <RichText text={item} />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
          <p className="text-xs text-muted">{texts.metaNote}</p>
        </Card.Content>

        <Card.Footer>
          <Link to="/login" className={buttonVariants({ variant: 'tertiary' })}>
            {texts.back}
          </Link>
        </Card.Footer>
      </Card>
    </main>
  );
}
