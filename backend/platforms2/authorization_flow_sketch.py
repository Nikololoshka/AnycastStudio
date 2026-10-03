import secrets
from collections.abc import Awaitable, Callable

from platforms2.core import AuthorizationError, Platform


# Тестовый эскиз: весь жизненный цикл аккаунта одной функцией, чтобы видеть
# порядок вызовов AuthorizationInteractor. В реальном коде шаги разнесены
# по разным HTTP-запросам и задачам, а `storage` — это БД.
async def authorization_flow_sketch(
    platform: Platform,
    owner_id: int,
    storage: dict,
    open_in_browser_and_wait_callback: Callable[[str], Awaitable[dict]],
) -> None:
    authorization = platform.get_authorization_interactor()

    # ── 1. POST /api/social/<platform>/connect ───────────────────────────
    # Генерируем state — одноразовый ключ, связывающий старт и callback.
    state = secrets.token_urlsafe(32)

    # create_auth_request() синхронный: в сеть не ходит, только собирает URL и PKCE.
    request = authorization.create_auth_request(state)

    # Сохраняем OAuthSession: кто начал, state и code_verifier.
    # verifier НЕ уходит в браузер — он нужен только на шаге 3.
    storage["oauth_session"] = {
        "owner_id": owner_id,
        "state": request.state,
        "code_verifier": request.code_verifier,
        "status": "pending",
    }

    # ── 2. Браузер ───────────────────────────────────────────────────────
    # SPA получает request.url и уводит пользователя на страницу согласия
    # платформы. Платформа возвращает его на redirect_uri с ?code&state
    # (или ?error, если пользователь отказался).
    callback = await open_in_browser_and_wait_callback(request.url)

    # ── 3. GET /api/social/<platform>/callback ───────────────────────────
    session = storage["oauth_session"]

    # Проверка 1: state выдан нами и ещё не использован.
    # В БД это условный UPDATE pending → used (claim), чтобы повторный
    # callback не прошёл.
    if callback.get("state") != session["state"] or session["status"] != "pending":
        raise AuthorizationError("Unknown or used state")
    session["status"] = "used"

    # Проверка 2: callback пришёл от того же пользователя, что начал подключение
    # (сравнение с пользователем из session cookie).
    if callback.get("requester_id") != session["owner_id"]:
        raise AuthorizationError("State belongs to another user")

    # Пользователь отказался на странице согласия.
    if callback.get("error") or not callback.get("code"):
        raise AuthorizationError("User cancelled")

    # Сеть №1: меняем одноразовый code на токены. Не повторять при ошибке —
    # повторный обмен того же code получит invalid_grant.
    token = await authorization.create_auth_token(callback["code"], session["code_verifier"])

    # Сеть №2: узнаём, чей это аккаунт (id канала, имя, аватар).
    # Можно повторять — запрос идемпотентный.
    profile = await authorization.fetch_auth_profile(token.access_token)

    # Сохраняем SocialAccount. В реальности токены шифруются EncryptedTextField,
    # и запись идёт короткой транзакцией ПОСЛЕ сетевых вызовов, не вокруг них.
    storage["account"] = {
        "owner_id": owner_id,
        "external_id": profile.external_id,
        "display_name": profile.display_name,
        "avatar_url": profile.avatar_url,
        "access_token": token.access_token,
        "refresh_token": token.refresh_token,
        "expires_in": token.expires_in,
        "scopes": token.scopes,
        "status": "active",
    }
    session["status"] = "done"

    # ── 4. Позже: перед публикацией токен истёк ──────────────────────────
    # В реальности сначала берётся lease (условный UPDATE), чтобы web и воркер
    # не обновляли один аккаунт одновременно.
    account = storage["account"]
    try:
        refreshed = await authorization.refresh_auth_token(account["refresh_token"])
    except AuthorizationError as error:
        if error.transient:
            # Сеть или 5xx: аккаунт в порядке, попробуем позже.
            raise
        # invalid_grant и т.п.: пользователь отозвал доступ — нужен reconnect.
        account["status"] = "needs_reauth"
        raise

    # Google при refresh не присылает новый refresh_token — старый сохраняем.
    account["access_token"] = refreshed.access_token
    account["refresh_token"] = refreshed.refresh_token or account["refresh_token"]
    account["expires_in"] = refreshed.expires_in

    # ── 5. DELETE /api/social/accounts/<id> ──────────────────────────────
    # Отзываем доступ у платформы. Отзыв refresh_token отзывает и access_token.
    try:
        await authorization.revoke_auth_token(account["refresh_token"] or account["access_token"])
    except AuthorizationError:
        # Отказ платформы не мешает отключить аккаунт у нас.
        pass
    account["status"] = "revoked"
