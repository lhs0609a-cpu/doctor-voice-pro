"""
블로그 지수(A) + 상위노출 가능성 판정(B) 패키지.

원본 로직: D:/developer/blog-index-analyzer/블로그지수_상위노출_로직_전체추출.txt
(상수·임계값·정규식을 그대로 이식한다. 값을 바꾸면 SCORING_VERSION/DIFFICULTY_VERSION 을 올린다.)

모듈 계약 (각 모듈이 반드시 제공하는 공개 함수)
─────────────────────────────────────────────────────────────────
collectors.py   (문서 1장)
  async scrape_blog_stats(blog_id) -> dict
      {success, error_code?, error_message?, canonical_blog_id?, total_posts, neighbor_count,
       total_visitors, naver_level, data_source: "scrape"|None, cumulative_visitors_real: bool}
  async fetch_visitor_series(blog_id) -> dict
      {measured: bool, series:[{date, count}], today, recent_avg}
  async fetch_rss(blog_id) -> dict
      {ok, rss_empty, blog_name, items:[{title, link, description, pub_date, category, post_no}],
       analysis:{total_posts_min, avg_post_length, avg_image_count, avg_word_count, category_count,
                 category_entropy, recent_activity, rss_window_days, rss_truncated, posts_last_90d,
                 posting_interval_days, posting_burstiness}}
  async analyze_post(db, post_url, keyword=None) -> dict   (URL 키 영구 캐시, 1-4 스키마)
  async fullparse_recent(db, blog_id, items, n=15) -> dict
      {fullparse_avg_content_length, fullparse_avg_images, fullparse_avg_headings,
       fullparse_avg_paragraphs, fullparse_avg_likes, fullparse_avg_comments, sample_size}

weights.py      (문서 3장, 13장)
  CATEGORY_KEYWORDS, CATEGORY_WEIGHTS, CATEGORY_TIPS
  detect_keyword_category(keyword) -> str
  resolve_scoring_weights(keyword, learned_weights=None, scoring_version=6) -> dict

scoring.py      (문서 2장, 4장, 6장)
  SCORING_VERSION = 6
  compute_blog_index(stats, analysis, data_sources, weights) -> dict   (2-11 그대로)
  get_blog_level_from_score(score) -> (level, grade)
  get_level_from_percentile(percentile) -> (level, grade)
  level_category(level) -> str
  calculate_post_score(p) -> dict

analyzer.py     (조립: 수집 → 가중치 → 채점 → 레벨 → 스냅샷 저장)
  async analyze_blog(db, blog_id, *, keyword=None, fullparse=True, use_cache=True,
                     verify_index=False, progress=None) -> dict   (14-5 블로그 분석 스키마)
  async score_blog_light(db, blog_id, *, keyword=None, use_cache=True) -> dict | None
      {score, level, grade, recent_activity_days, blog_name, measured_at}  (경쟁자 채점용, 6h 캐시)

serp.py         (문서 1-6)
  async blog_tab_serp(db, keyword, limit=20, use_cache=True) -> dict | None
      {rows:[{rank, blog_id, post_no, post_url, title}], source, parse_mode, measured_at, cached}
      None = 측정 불가(스크래핑 실패). 빈 rows = 결과 없음.
  async blog_tab_true_rank(db, keyword, blog_id, limit=30) -> int | None
  async check_blog_tab_rank(db, query, blog_id, max_results=50) -> int | None
  async check_view_tab_rank(db, query, post_url, max_results=50) -> int | None
  async openapi_blog_rank(query, blog_id, display=30) -> int | None
  def rank_label(rank) -> str  ("노출안됨"/"상위권"/"중위권"/"하위권")

verifier.py     (문서 5장)
  async verify_index(db, blog_id, sample_size=12) -> dict

exposure_ceiling.py (문서 7장)
  async measure_ceiling(db, blog_id, refresh=False, progress=None) -> dict
  def ceiling_from_observations(rows) -> dict

serp_difficulty.py (문서 8장)   async serp_difficulty(db, keyword, top_n=10) -> dict
seo_difficulty.py  (문서 11장)  DIFFICULTY_VERSION=2, compute_difficulty(...), label_for(score)
judge_v1.py        (문서 9장)   judge_keyword(ceiling, target_volume, serp=None) -> dict
keyword_verdict.py (문서 10장)
  async stage1_facts(db, blog_id, keyword) -> dict
  async stage2_verdict(db, blog_id, keyword, facts=None, progress=None, user_id=None) -> dict (14-5 판정 스키마)
  def compute_verdict(*, my, competitors, volume, my_rank, topical, ceiling, serp_reliable=True) -> dict
competition_analyzer.py (문서 12장)
  async analyze_competition(db, keyword, my_blog_id=None) -> dict
post_exposure.py  (1-6, 보조)
  async post_exposure_cards(db, blog_id, sample=10) -> dict
"""

SCORING_VERSION = 6
DIFFICULTY_VERSION = 2
VERDICT_MODEL_VERSION = "v1-heuristic"

DISCLAIMER_INDEX = (
    "네이버는 블로그 지수 API를 외부에 공개하지 않으므로 본 결과는 공개된 측정 신호"
    "(정확매칭 색인률, 30위/72시간 누락, C-Rank/DIA 프록시 등)를 통합한 비공식 추정치입니다. "
    "NSIDE·NVIEW·whereispost·리드뷰 등 타 추적 사이트와 결과가 다를 수 있습니다 — "
    "각 도구의 측정 알고리즘이 모두 다릅니다."
)
DISCLAIMER_CEILING = (
    "노출 천장은 이 블로그가 최근 글 제목의 키워드로 네이버 블로그 검색에서 실제로 상위노출된 "
    "결과만을 근거로 한 실적 기반 추정치입니다. 네이버 알고리즘은 비공개이며 AI 브리핑 등으로 "
    "계속 변하므로 미래 노출을 보장하지 않습니다."
)
DISCLAIMER_VERDICT = (
    "판정은 이 키워드의 실제 네이버 블로그탭 1페이지를 조회해, 그 자리에 앉아 있는 블로그들과 "
    "내 블로그를 같은 기준으로 채점해 낸 추정치입니다. 네이버 알고리즘은 비공개이며 SERP는 "
    "수시로 바뀌므로 노출을 보장하지 않습니다."
)


def normalize_keyword(kw: str) -> str:
    return (kw or "").replace(" ", "").strip().lower()


def normalize_blog_id(v: str) -> str:
    """URL·아이디 어느 쪽을 넣어도 blog_id 만 남긴다."""
    import re
    s = (v or "").strip()
    m = re.search(r"blog\.naver\.com/([A-Za-z0-9_-]+)", s)
    if m:
        return m.group(1)
    m = re.search(r"blogId=([A-Za-z0-9_-]+)", s)
    if m:
        return m.group(1)
    return s.strip("/@ ").split("?")[0]
