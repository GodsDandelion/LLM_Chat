from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_cache_agent
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from app.services.auth_agent import AuthAgent
from app.services.cache_agent import CacheAgent

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_db),
    cache: CacheAgent = Depends(get_cache_agent),
) -> dict[str, str]:
    await AuthAgent(session, cache).register(body)
    return {"status": "created"}


@router.post("/login", response_model=TokenPair)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db),
    cache: CacheAgent = Depends(get_cache_agent),
) -> TokenPair:
    return await AuthAgent(session, cache).login(body)


@router.get("/github")
async def github_start(
    session: AsyncSession = Depends(get_db),
    cache: CacheAgent = Depends(get_cache_agent),
) -> RedirectResponse:
    url = AuthAgent(session, cache).github_authorize_url()
    return RedirectResponse(url)


@router.get("/github/callback", response_model=TokenPair)
async def github_callback(
    code: str,
    session: AsyncSession = Depends(get_db),
    cache: CacheAgent = Depends(get_cache_agent),
) -> TokenPair:
    return await AuthAgent(session, cache).github_callback(code)


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_db),
    cache: CacheAgent = Depends(get_cache_agent),
) -> TokenPair:
    return await AuthAgent(session, cache).refresh(body.refresh_token)
