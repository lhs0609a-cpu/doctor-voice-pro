from fastapi import APIRouter
from app.api import (
    auth, posts, profiles, admin, naver, websocket, analytics, tags,
    system, export, images, top_posts, subscriptions, payments,
    schedules, reports, sns,
    roi, place, reviews, competitors, rankings, campaigns,
    knowledge
)

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
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(images.router, prefix="/images", tags=["images"])
api_router.include_router(top_posts.router, prefix="/top-posts", tags=["top-posts"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(schedules.router, prefix="/schedules", tags=["schedules"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(sns.router, prefix="/sns", tags=["sns"])
# ROI & Place Management
api_router.include_router(roi.router, prefix="/roi", tags=["roi"])
api_router.include_router(place.router, prefix="/place", tags=["place"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
api_router.include_router(competitors.router, prefix="/competitors", tags=["competitors"])
api_router.include_router(rankings.router, prefix="/rankings", tags=["rankings"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
# Knowledge (지식인)
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
