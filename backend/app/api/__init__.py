from fastapi import APIRouter
from app.api import (
    auth, posts, profiles, admin, naver, websocket, analytics, tags,
    system, export, images, top_posts, subscriptions, payments,
    schedules, reports, sns,
    roi, place, reviews, competitors, rankings, campaigns,
    knowledge, crawl, cafe, viral,
    knowledge_extended, cafe_extended,
    billing, blog_outreach, public_leads
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
# Blog Crawl (블로그 글 가져오기)
api_router.include_router(crawl.router, prefix="/crawl", tags=["crawl"])
# Cafe Viral (카페 바이럴)
api_router.include_router(cafe.router, prefix="/cafe", tags=["cafe"])
# Viral Extended (확장 기능: 다중계정, 알림, 프록시, A/B테스트, 리포트)
api_router.include_router(viral.router, prefix="/viral", tags=["viral"])
# Knowledge Extended (채택추적, 경쟁분석, 질문자분석, 내공우선순위)
api_router.include_router(knowledge_extended.router, prefix="/knowledge-ext", tags=["knowledge-extended"])
# Cafe Extended (대댓글, 게시판타겟팅, 인기글분석, 팔로우/좋아요)
api_router.include_router(cafe_extended.router, prefix="/cafe-ext", tags=["cafe-extended"])
# Billing (정기결제)
api_router.include_router(billing.router)
# Blog Outreach (블로그 영업 자동화)
api_router.include_router(blog_outreach.router, prefix="/outreach", tags=["outreach"])
# Public Data Leads (공공데이터 리드 수집)
api_router.include_router(public_leads.router, tags=["public-leads"])
