# Авторизация платформ на async API — как это работает в теории

Эскиз того, как сценарии подключения аккаунта, обновления токена и отключения
используют async-интерфейс `AuthorizationInteractor` из `platforms2/core/auth/authorization_interactor.py`
(на примере `YouTubeAuthorizationInteractor`). Кода, кроме самой платформы, ещё нет — ниже
предполагаемая форма.

## 1. Слои

```
async view / задача очереди
  └► сценарий (ConnectFlow, TokenService, AccountService)      platforms2/core
       ├► AuthorizationInteractor (create_auth_request / create_auth_token / refresh_auth_token / fetch_auth_profile / revoke_auth_token)
       │     └► GoogleHttp └► aiohttp.ClientSession └► платформа
       └► async-порты (OAuthSessions, Accounts, Clock)
             └► Django-репозитории (async ORM, sync_to_async для транзакций)
```

Правила остаются прежними:

- `platforms2` не импортирует Django; сценарии видят только порты.
- Сетевой вызов никогда не выполняется внутри транзакции БД:
  прочитать → закрыть → `await` платформу → открыть → записать.
- Состояние, которое нельзя выполнить дважды, забирается условным UPDATE (claim).

## 2. Жизненный цикл `ClientSession`

`aiohttp.ClientSession` привязана к event loop, в котором создана, поэтому платформу
нельзя собрать один раз при импорте, как `config.wiring.container()` сейчас.

```python
class PlatformCatalog:
    def __init__(self, configs: PlatformConfigs, session: aiohttp.ClientSession):
        self._platforms = {
            PlatformType.YouTube: YouTubePlatform(configs.youtube, session),
        }

    def get(self, platform: PlatformType) -> Platform:
        return self._platforms[platform]
```

Где создаётся сессия:

| Процесс | Время жизни сессии |
| --- | --- |
| uvicorn (ASGI) | lifespan приложения: открыть на `startup`, закрыть на `shutdown` |
| воркер очереди | на время жизни воркера (taskiq/arq) или на одну задачу (`asyncio.run` в Celery) |
| тесты | на тест, с подменой ответов через `aioresponses` или тестовый сервер aiohttp |

Django из коробки не даёт ASGI lifespan-хуков, поэтому для uvicorn нужна тонкая
обёртка над `get_asgi_application()`, которая обрабатывает `lifespan`-сообщения и
кладёт каталог в место, откуда его берут views.

## 3. Порты

Порты становятся async. Django-адаптеры реализуют их через `aget` / `aupdate` /
`acreate`; то, что требует `transaction.atomic`, оборачивается целиком в
`sync_to_async`.

```python
class OAuthSessions(Protocol):
    async def create(self, owner_id: int, platform: PlatformType, state: str, code_verifier: str) -> OAuthSessionRecord: ...
    async def claim(self, platform: PlatformType, state: str, created_after: datetime) -> OAuthSessionRecord | None: ...
    async def finish(self, session_id: int, status: OAuthSessionStatus) -> None: ...


class Accounts(Protocol):
    async def save(self, owner_id: int, platform: PlatformType, token: AuthToken, profile: AuthProfile) -> None: ...
    async def tokens_of(self, account_id: int) -> AccountTokens: ...
    async def claim_refresh_lease(self, account_id: int, now: datetime, until: datetime) -> bool: ...
    async def store_refreshed(self, account_id: int, token: AuthToken, now: datetime) -> None: ...
    async def release_refresh_lease(self, account_id: int, until: datetime) -> None: ...
    async def mark_needs_reauth(self, account_id: int, reason: str) -> None: ...
    async def mark_revoked(self, account_id: int) -> None: ...
```

## 4. Подключение аккаунта

### 4.1 Старт — `POST /api/social/<platform>/connect`

```python
class ConnectFlow:
    async def start(self, owner_id: int, platform: PlatformType) -> str:
        state = secrets.token_urlsafe(32)
        request = self._catalog.get(platform).get_authorization_interactor().create_auth_request(state)
        await self._sessions.create(owner_id, platform, request.state, request.code_verifier)
        return request.url
```

- `create_auth_request` синхронный: он ничего не отправляет, только собирает URL и PKCE.
- `code_verifier` сохраняется в `OAuthSession` и в ответ браузеру не попадает.

### 4.2 Callback — `GET /api/social/<platform>/callback?code&state`

```python
    async def complete(self, platform, state, code, refused, requester_id) -> ConnectOutcome:
        session = await self._sessions.claim(platform, state, self._clock.now() - self._ttl)
        if session is None:
            return ConnectOutcome.INVALID
        if session.owner_id != requester_id:
            await self._sessions.finish(session.id, OAuthSessionStatus.ERROR)
            return ConnectOutcome.INVALID
        if refused or not code:
            await self._sessions.finish(session.id, OAuthSessionStatus.ERROR)
            return ConnectOutcome.CANCELLED

        authorization = self._catalog.get(platform).get_authorization_interactor()
        try:
            token = await authorization.create_auth_token(code, session.code_verifier)
            profile = await authorization.fetch_auth_profile(token.access_token)
        except AuthorizationError as error:
            await self._sessions.finish(session.id, OAuthSessionStatus.ERROR)
            logger.info("OAuth session %s failed: %s", session.id, error.message)
            return ConnectOutcome.FAILED

        await self._accounts.save(session.owner_id, platform, token, profile)
        await self._sessions.finish(session.id, OAuthSessionStatus.DONE)
        return ConnectOutcome.CONNECTED
```

Порядок:

1. `claim` по `state` — условный UPDATE `pending → used`; повторный callback получает `None`.
2. Проверка, что сессию открыл тот же пользователь, чей cookie на запросе.
3. `create_auth_token` и `fetch_auth_profile` — два сетевых вызова, транзакции в этот момент нет.
4. `save` шифрует токены (`EncryptedTextField`) и пишет `SocialAccount` одной короткой транзакцией.

Код одноразовый, поэтому `create_auth_token` не ретраится: повтор после таймаута
получит `invalid_grant`. `fetch_auth_profile` можно повторить.

### 4.3 View

```python
@require_GET
async def social_callback(request, platform: str):
    user = await request.auser()
    outcome = await connect_flow().complete(
        PlatformType(platform),
        state=request.GET.get("state", ""),
        code=request.GET.get("code"),
        refused=bool(request.GET.get("error")),
        requester_id=user.pk if user.is_authenticated else None,
    )
    return back_to_app(platform, outcome)
```

Декораторы из `common/core/decorators.py` уже умеют строить async-обёртки.

## 5. Токен для вызова платформы

Публикация и `creator_info` просят действующий токен у `TokenService`:

```python
class TokenService:
    async def valid(self, account_id: int) -> str:
        account = await self._accounts.tokens_of(account_id)
        if not account.expires_within(self._clock.now(), self.REFRESH_MARGIN):
            return account.access_token
        return await self.refresh(account_id)

    async def refresh(self, account_id: int) -> str:
        account = await self._accounts.tokens_of(account_id)
        until = self._clock.now() + self.REFRESH_LEASE
        if not await self._accounts.claim_refresh_lease(account_id, self._clock.now(), until):
            return await self._await_other_refresh(account)
        try:
            token = await self._token_of(account)
            await self._accounts.store_refreshed(account_id, token.merged_with(account.token), self._clock.now())
        finally:
            await self._accounts.release_refresh_lease(account_id, until)
        return (await self._accounts.tokens_of(account_id)).access_token

    async def _token_of(self, account: AccountTokens) -> AuthToken:
        authorization = self._catalog.get(account.platform).get_authorization_interactor()
        try:
            return await authorization.refresh_auth_token(account.refresh_token)
        except AuthorizationError as error:
            if error.failure in (AuthFailure.GRANT_REVOKED, AuthFailure.SCOPE_MISSING):
                await self._accounts.mark_needs_reauth(account.id, error.message)
                raise AuthorizationError(error.failure, RECONNECT) from None
            if error.failure is AuthFailure.MISCONFIGURED:
                logger.error("%s client is misconfigured: %s", account.platform, error.message)
            raise
```

- Lease остаётся условным UPDATE в БД: два процесса (web и воркер) могут
  одновременно захотеть обновить один аккаунт.
- Ожидание чужого refresh — `await asyncio.sleep(...)` вместо `time.sleep`, loop не блокируется.
- Google не возвращает новый `refresh_token` при refresh, поэтому `merged_with`
  оставляет старый (нужно перенести из `platforms/core/auth/tokens.py`).
- Реакция зависит от `AuthFailure`:

| `AuthFailure` | Google | TikTok | Реакция |
| --- | --- | --- | --- |
| `NETWORK` | обрыв, 408, 5xx | обрыв, 408, 5xx | повторить с backoff |
| `RATE_LIMITED` | 429, `quotaExceeded`, `rateLimitExceeded` | 429, `rate_limit_exceeded` | ждать; квоту YouTube повтор не вернёт |
| `TOKEN_REJECTED` | 401 на API | `access_token_invalid`, 401 | один раз `refresh_auth_token` и повторить вызов |
| `GRANT_REVOKED` | `invalid_grant` | `invalid_grant` | при refresh — `needs_reauth`; при обмене кода — подключить заново |
| `SCOPE_MISSING` | `insufficientPermissions`, `ACCESS_TOKEN_SCOPE_INSUFFICIENT` | `scope_not_authorized` | `needs_reauth`, refresh не поможет |
| `MISCONFIGURED` | `invalid_client`, `unauthorized_client`, `redirect_uri_mismatch`, `invalid_scope`, `invalid_request` | те же OAuth-коды | лог уровня error; аккаунты **не трогать** |
| `REFUSED` | прочие 4xx, нет канала | прочие коды | показать причину |
| `UNEXPECTED` | ответ не той формы | ответ не той формы | лог, не повторять |

Второй `TOKEN_REJECTED` сразу после refresh — `needs_reauth`.

## 6. Отключение аккаунта

```python
class AccountService:
    async def disconnect(self, account_id: int) -> None:
        account = await self._accounts.tokens_of(account_id)
        try:
            await self._catalog.get(account.platform).get_authorization_interactor().revoke_auth_token(account.token)
        except AuthorizationError as error:
            logger.info("Revocation of account %s failed: %s", account_id, error.message)
        await self._accounts.mark_revoked(account_id)
```

Отказ платформы отозвать токен не мешает отключению у нас.

## 7. Периодический refresh

Задача `social.refresh_expiring_tokens` проходит по аккаунтам, истекающим в
ближайший час. В async её можно распараллелить с ограничением:

```python
    async def refresh_expiring(self) -> int:
        limit = asyncio.Semaphore(4)

        async def one(account_id: int) -> bool:
            async with limit:
                try:
                    await self.valid_within(account_id, self.REFRESH_AHEAD)
                    return True
                except AuthorizationError:
                    return False

        ids = await self._accounts.expiring_before(self._clock.now() + self.REFRESH_AHEAD)
        return sum(await asyncio.gather(*(one(account_id) for account_id in ids)))
```

Параллельные записи в SQLite всё равно встанут в очередь, поэтому лимит маленький.

## 8. Запуск из очереди

| Вариант | Как выглядит | Цена |
| --- | --- | --- |
| Celery + мост | `@shared_task def refresh(): asyncio.run(run_refresh())`, сессия и каталог создаются внутри `run_refresh` | Ничего не меняется в инфраструктуре; каждый запуск — новый loop и новая сессия |
| taskiq (Redis) | `@broker.task async def refresh(): ...`, сессия на время жизни воркера | Новая зависимость, свой планировщик вместо beat, переписать claim/ack-семантику и тесты |

Для авторизации достаточно моста: задач мало, и они короткие. Решение по очереди
стоит принимать, когда до async дойдёт загрузка видео.

## 9. Повторы

`GoogleHttp` только классифицирует отказ (`AuthFailure`); `transient` — производное
свойство (`NETWORK`, `RATE_LIMITED`). Повтор делает async-политика вокруг вызова,
а не сам клиент:

```python
class RetryPolicy:
    async def run(self, action: Callable[[], Awaitable[T]], attempts: int) -> T:
        for attempt in range(attempts):
            try:
                return await action()
            except AuthorizationError as failure:
                if not failure.transient or attempt == attempts - 1:
                    raise
                await asyncio.sleep(self.backoff_seconds(attempt))
```

| Вызов | Повторять |
| --- | --- |
| `create_auth_token` | нет — код одноразовый |
| `refresh_auth_token` | да, 3 попытки |
| `fetch_auth_profile` | да, 3 попытки |
| `revoke_auth_token` | нет — отказ не критичен |

## 10. Безопасность

- `AuthToken`, `AuthRequest.code_verifier`, `YouTubeConfig.client_secret`
  скрыты из `repr`.
- Ошибки сети — только класс исключения: `aiohttp.ClientResponseError` содержит URL,
  а тело запроса к `/token` содержит `client_secret`.
- `state` проверяется дважды: `claim` (выдан нами и ещё `pending`) и сравнение
  владельца с пользователем запроса.

## 11. Открытые вопросы

1. Кто владеет `ClientSession` в ASGI-процессе и как views получают каталог без глобального `container()`.
2. Async-порты поверх Django ORM: где граница `sync_to_async` и как тестировать на фейках (`IsolatedAsyncioTestCase`).
3. Celery-мост или смена очереди — решать вместе с загрузкой видео.
4. Где живут `RetryPolicy` и классификация ответов, общие для всех платформ, когда `GoogleHttp` появится у каждой.
