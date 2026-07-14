from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.card_reports import router as card_reports_router
from app.api.collection import router as collection_router
from app.api.filters import router as filters_router
from app.api.master_sets import router as master_sets_router
from app.api.news import router as news_router
from app.api.products import router as products_router
from app.api.routes import router as api_router
from app.api.scan import router as scan_router
from app.api.sealed_collection import router as sealed_collection_router
from app.api.series import router as series_router
from app.api.set_reports import router as set_reports_router
from app.api.sharing import router as sharing_router
from app.api.visits import router as visits_router
from app.api.wishlist import router as wishlist_router
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="PullList API",
    description="Pokémon TCG catalog + real-time stock tracker",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(filters_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(collection_router, prefix="/api/v1")
app.include_router(master_sets_router, prefix="/api/v1")
app.include_router(wishlist_router, prefix="/api/v1")
app.include_router(scan_router, prefix="/api/v1")
app.include_router(sharing_router, prefix="/api/v1")
app.include_router(news_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(sealed_collection_router, prefix="/api/v1")
app.include_router(series_router, prefix="/api/v1")
app.include_router(card_reports_router, prefix="/api/v1")
app.include_router(set_reports_router, prefix="/api/v1")
app.include_router(visits_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "PullList API",
        "version": "0.1.0",
        "docs": "/docs",
    }
