import { useState, type FormEvent } from 'react';
import { Button, Card, Input, Label, TextField } from '@heroui/react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { useLoginMutation } from '../../api';
import { messageOf, statusOf } from '../../api/errors';
import { AppMark } from '../../components/AppShell';

export function LoginScreen() {
  const { t } = useTranslation('auth');
  const navigate = useNavigate();
  const [login, { isLoading }] = useLoginMutation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  function describe(cause: unknown): string {
    switch (statusOf(cause)) {
      case 'unauthorized':
        return t('error.credentials');
      case 'rate_limited':
        return t('error.rateLimited');
      case 'invalid':
        return t('error.credentials');
      default:
        return messageOf(cause) ?? t('error.unknown');
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      await login({ email, password }).unwrap();
      void navigate('/compose', { replace: true });
    } catch (cause) {
      setError(describe(cause));
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-window-backdrop px-4 text-foreground">
      <Card className="w-full max-w-sm">
        <Card.Header className="flex flex-col items-center gap-3">
          <AppMark />
          <Card.Title className="font-display text-xl font-semibold tracking-tight">
            {t('title')}
          </Card.Title>
          <Card.Description className="text-center">{t('subtitle')}</Card.Description>
        </Card.Header>

        <Card.Content>
          <form className="flex flex-col gap-4" onSubmit={submit}>
            <TextField
              type="email"
              name="email"
              autoComplete="username"
              isRequired
              value={email}
              onChange={setEmail}
              fullWidth
            >
              <Label>{t('email')}</Label>
              <Input />
            </TextField>

            <TextField
              type="password"
              name="password"
              autoComplete="current-password"
              isRequired
              value={password}
              onChange={setPassword}
              fullWidth
            >
              <Label>{t('password')}</Label>
              <Input />
            </TextField>

            {error && (
              <p role="alert" className="text-sm text-danger">
                {error}
              </p>
            )}

            <Button type="submit" variant="primary" isDisabled={isLoading} fullWidth>
              {t('submit')}
            </Button>
          </form>
        </Card.Content>

        <Card.Footer className="justify-center">
          <p className="text-center text-xs text-muted">{t('noSignUp')}</p>
        </Card.Footer>
      </Card>
    </main>
  );
}
