from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import hashlib

import bcrypt
import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair
from app.services.cache_agent import CacheAgent
from app.services.user_agent import UserAgent


def _password_digest(password: str) -> bytes:
    """Fixed-length input for bcrypt (avoids 72-byte password limit issues)."""
    return hashlib.sha256(password.encode("utf-8")).digest()


class AuthAgent:
    def __init__(self, session: AsyncSession, cache: CacheAgent, settings: Settings | None = None) -> None:
        self._session = session
        self._cache = cache
        self._settings = settings or get_settings()
        self._users = UserAgent(session)

    def hash_password(self, password: str) -> str:
        digest = _password_digest(password)
        return bcrypt.hashpw(digest, bcrypt.gensalt(rounds=12)).decode("ascii")

    def verify_password(self, plain: str, hashed: str | None) -> bool:
        if not hashed:
            return False
        digest = _password_digest(plain)
        try:
            return bcrypt.checkpw(digest, hashed.encode("ascii"))
        except (ValueError, TypeError):
            return False

    def create_access_token(self, user_id: int) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self._settings.access_token_expire_minutes)
        payload = {"sub": str(user_id), "exp": expire}
        return jwt.encode(
            payload,
            self._settings.jwt_secret,
            algorithm=self._settings.jwt_algorithm,
        )

    @staticmethod
    def decode_access_token(token: str, settings: Settings | None = None) -> int:
        s = settings or get_settings()
        try:
            payload = jwt.decode(
                token,
                s.jwt_secret,
                algorithms=[s.jwt_algorithm],
            )
            sub = payload.get("sub")
            if sub is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
            return int(sub)
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            ) from exc

    async def _issue_token_pair(self, user_id: int) -> TokenPair:
        access = self.create_access_token(user_id)
        refresh = str(uuid4())
        await self._cache.store_refresh(refresh, user_id)
        return TokenPair(access_token=access, refresh_token=refresh)

    async def register(self, body: RegisterRequest) -> None:
        existing = await self._users.get_by_login(body.login)
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login already taken")
        try:
            hashed = self.hash_password(body.password)
            await self._users.create_user(body.login, hashed)
        except IntegrityError:
            await self._session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Login already taken",
            ) from None

    async def login(self, body: LoginRequest) -> TokenPair:
        user = await self._users.get_by_login(body.login)
        if not user or not self.verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        return await self._issue_token_pair(user.id)

    async def refresh(self, refresh_token: str) -> TokenPair:
        user_id = await self._cache.get_refresh_user_id(refresh_token)
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        user = await self._users.get_by_id(user_id)
        if not user:
            await self._cache.delete_refresh(refresh_token)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        await self._cache.delete_refresh(refresh_token)
        return await self._issue_token_pair(user.id)

    def github_authorize_url(self) -> str:
        if not self._settings.github_client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GitHub OAuth is not configured",
            )
        from urllib.parse import urlencode

        params = {
            "client_id": self._settings.github_client_id,
            "redirect_uri": self._settings.github_redirect_uri,
            "scope": "read:user user:email",
        }
        return f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    async def github_callback(self, code: str) -> TokenPair:
        if not self._settings.github_client_id or not self._settings.github_client_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GitHub OAuth is not configured",
            )
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": self._settings.github_client_id,
                    "client_secret": self._settings.github_client_secret,
                    "code": code,
                    "redirect_uri": self._settings.github_redirect_uri,
                },
                timeout=30.0,
            )
            token_resp.raise_for_status()
            token_json = token_resp.json()
            access = token_json.get("access_token")
            if not access:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=token_json.get("error_description") or "GitHub token exchange failed",
                )
            user_resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            user_resp.raise_for_status()
            gh_user = user_resp.json()

        github_id = str(gh_user["id"])
        gh_login = str(gh_user.get("login") or f"user_{github_id}")

        user = await self._users.get_by_github_id(github_id)
        if user:
            return await self._issue_token_pair(user.id)

        login = gh_login
        if await self._users.get_by_login(login):
            login = f"{gh_login}_{github_id}"

        user = await self._users.create_oauth_user(login=login, github_id=github_id)
        return await self._issue_token_pair(user.id)
