from fastapi import APIRouter
from app.api import auth, posts, profiles, admin, naver, websocket, analytics, tags, system

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(naver.router, prefix="/naver", tags=["naver"])
api_router.include_router(websocket.router, tags=["websocket"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(tags.router, prefix="/tags", tags=["tags"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
