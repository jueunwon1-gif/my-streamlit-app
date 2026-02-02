import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# (선택) TMDB 파이썬 래퍼: tmdbsimple 사용 가능하면 사용
try:
    import tmdbsimple as tmdb  # pip install tmdbsimple
    TMDBSIMPLE_AVAILABLE = True
except Exception:
    TMDBSIMPLE_AVAILABLE = False


# =========================
# 페이지 설정 + 간단 CSS
# =========================
st.set_page_config(page_title="🎬 나와 어울리는 영화는?", page_icon="🎬", layout="wide")

st.markdown(
    """
<style>
.block-container {max-width: 1100px; padding-top: 1.2rem; padding-bottom: 3rem;}
h1 {margin-bottom: 0.2rem;}
div[role="radiogroup"] {gap: 0.25rem;}
hr {margin: 1.0rem 0 1.0rem 0;}
.badge{
  display:inline-block; padding:6px 10px; border-radius:999px;
  background: #f1f5f9; border:1px solid #e2e8f0; font-weight:700; font-size:12px;
  margin-right: 6px; margin-bottom: 6px;
}
.badge-strong{ background:#ecfeff; border-color:#a5f3fc; }
.badge-warn{ background:#fff7ed; border-color:#fed7aa; }
.small-muted{ color:#64748b; font-size: 0.92rem; }
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# 장르 ID (요구사항)
# =========================
GENRES = {
    "액션": 28,
    "코미디": 35,
    "드라마": 18,
    "SF": 878,
    "로맨스": 10749,
    "판타지": 14,
}

# =========================
# 질문 데이터
# =========================
questions = [
    {
        "q": "Q1. 시험 끝난 날, 내가 가장 하고 싶은 일은?",
        "options": [
            "❤️ 조용한 카페에서 친구랑 깊은 얘기하며 힐링하기",
            "🔥 당장 어디론가 떠나서 새로운 경험하기",
            "🌌 게임이나 영화로 현실을 벗어나 다른 세계로 가기",
            "😂 친구들이랑 웃긴 영상 보면서 스트레스 날리기",
        ],
    },
    {
        "q": "Q2. 친구들이 말하는 나의 분위기는?",
        "options": [
            "❤️ 감성적이고 공감 잘하는 편",
            "🔥 에너지 넘치고 도전적인 편",
            "🌌 상상력이 풍부하고 독특한 편",
            "😂 항상 분위기 메이커인 편",
        ],
    },
    {
        "q": "Q3. 내가 좋아하는 여행 스타일은?",
        "options": [
            "❤️ 예쁜 풍경 보면서 여유롭게 산책하는 여행",
            "🔥 액티비티 가득한 모험 여행",
            "🌌 신비로운 장소나 테마파크 같은 판타지 여행",
            "😂 친구들과 사건(?)이 끊이지 않는 우당탕 여행",
        ],
    },
    {
        "q": "Q4. 새 학기 첫날, 내가 가장 신경 쓰는 건?",
        "options": [
            "❤️ 새로운 사람들과의 관계와 분위기",
            "🔥 새로운 활동이나 동아리 도전",
            "🌌 내가 좋아할 만한 새로운 세계(취미)를 찾기",
            "😂 재밌는 친구들 만나서 웃길 기대",
        ],
    },
    {
        "q": "Q5. 영화 속 주인공이 된다면 나는?",
        "options": [
            "❤️ 사랑과 성장 속에서 감동을 주는 주인공",
            "🔥 세상을 구하거나 미션을 수행하는 히어로",
            "🌌 마법이나 미래 세계를 탐험하는 특별한 존재",
            "😂 사건을 터뜨리지만 결국 웃음을 주는 캐릭터",
        ],
    },
]

# 선택지 인덱스 -> 장르 점수 (로맨스/드라마, SF/판타지는 1점씩 분배)
CHOICE_SCORE = {
    0: {"로맨스": 1, "드라마": 1},
    1: {"액션": 2},
    2: {"SF": 1, "판타지": 1},
    3: {"코미디": 2},
}
PRIORITY = ["로맨스", "드라마", "코미디", "액션", "판타지", "SF"]


# =========================
# HTTP 세션 (리트라이)
# =========================
@st.cache_resource
def get_http_session():
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.4,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


# =========================
# TMDB: configuration -> 이미지 URL
# =========================
@st.cache_data(ttl=60 * 60, show_spinner=False)
def tmdb_configuration(api_key: str):
    session = get_http_session()
    url = "https://api.themoviedb.org/3/configuration"
    r = session.get(url, params={"api_key": api_key}, timeout=15)
    r.raise_for_status()
    return r.json()


def poster_base_url(api_key: str, preferred_size="w500") -> str:
    fallback = "https://image.tmdb.org/t/p/w500"
    try:
        cfg = tmdb_configuration(api_key)
        images = cfg.get("images", {}) or {}
        base = images.get("secure_base_url") or images.get("base_url")
        sizes = images.get("poster_sizes", []) or []
        if not base:
            return fallback
        if preferred_size in sizes:
            size = preferred_size
        elif "w500" in sizes:
            size = "w500"
        else:
            size = sizes[len(sizes) // 2] if sizes else "w500"
        return f"{base}{size}"
    except Exception:
        return fallback


# =========================
# TMDB: discover/movie + movie detail (ko 비면 en 보조)
# =========================
@st.cache_data(ttl=60 * 15, show_spinner=False)
def discover_requests(api_key: str, params: dict) -> list:
    session = get_http_session()
    url = "https://api.themoviedb.org/3/discover/movie"
    base_params = {"api_key": api_key, "include_adult": "false"}
    base_params.update(params)
    r = session.get(url, params=base_params, timeout=15)
    r.raise_for_status()
    return (r.json() or {}).get("results", []) or []


@st.cache_data(ttl=60 * 15, show_spinner=False)
def discover_tmdbsimple(api_key: str, params: dict) -> list:
    tmdb.API_KEY = api_key
    d = tmdb.Discover()
    data = d.movie(**params)
    return data.get("results", []) or []


def discover(api_key: str, params: dict) -> list:
    if TMDBSIMPLE_AVAILABLE:
        return discover_tmdbsimple(api_key, params)
    return discover_requests(api_key, params)


@st.cache_data(ttl=60 * 60, show_spinner=False)
def movie_details_requests(api_key: str, movie_id: int, language: str) -> dict:
    session = get_http_session()
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    r = session.get(url, params={"api_key": api_key, "language": language}, timeout=15)
    r.raise_for_status()
    return r.json() or {}


@st.cache_data(ttl=60 * 60, show_spinner=False)
def movie_details_tmdbsimple(api_key: str, movie_id: int, language: str) -> dict:
    tmdb.API_KEY = api_key
    m = tmdb.Movies(movie_id)
    return m.info(language=language) or {}


def movie_details(api_key: str, movie_id: int, language: str) -> dict:
    if TMDBSIMPLE_AVAILABLE:
        return movie_details_tmdbsimple(api_key, movie_id, language)
    return movie_details_requests(api_key, movie_id, language)


def pick_best_overview(api_key: str, movie: dict) -> str:
    overview = (movie.get("overview") or "").strip()
    if overview:
        return overview
    mid = movie.get("id")
    if not mid:
        return ""
    try:
        detail_en = movie_details(api_key, int(mid), "en-US")
        return (detail_en.get("overview") or "").strip()
    except Exception:
        return ""


# =========================
# 분석: 점수 -> 상위 2개 + 혼합 비율 + with_genres OR
# =========================
def analyze_answers(answers: dict) -> dict:
    scores = {g: 0 for g in GENRES.keys()}

    for i, q in enumerate(questions, start=1):
        k = f"q{i}"
        selected = answers.get(k)
        if not selected:
            continue
        idx = q["options"].index(selected)
        for g, v in CHOICE_SCORE.get(idx, {}).items():
            scores[g] += v

    def pri(g: str) -> int:
        return PRIORITY.index(g) if g in PRIORITY else 999

    sorted_items = sorted(scores.items(), key=lambda kv: (kv[1], -pri(kv[0])), reverse=True)
    top1, s1 = sorted_items[0]
    top2, s2 = sorted_items[1]

    if s2 <= 0:
        mix = [(top1, 1.0)]
    else:
        diff = s1 - s2
        if diff <= 0:
            mix = [(top1, 0.5), (top2, 0.5)]
        elif diff == 1:
            mix = [(top1, 0.6), (top2, 0.4)]
        elif diff == 2:
            mix = [(top1, 0.7), (top2, 0.3)]
        else:
            mix = [(top1, 0.8), (top2, 0.2)]

    return {"scores": scores, "mix": mix}


def with_genres_from_mix(mix: list[tuple[str, float]]) -> str:
    ids = [str(GENRES[g]) for g, w in mix if w > 0]
    return "|".join(ids)


def clamp(text: str, n: int = 260) -> str:
    if not text:
        return "줄거리 정보가 없습니다."
    return text if len(text) <= n else text[:n].rstrip() + "…"


def build_reason(mix: list[tuple[str, float]], scores: dict, movie: dict) -> str:
    parts = [f"{g} {int(round(w*100))}%" for g, w in mix if w > 0]
    mix_str = " + ".join(parts) if parts else "취향 믹스"

    rating = float(movie.get("vote_average") or 0.0)
    vote_count = int(movie.get("vote_count") or 0)

    if rating >= 7.6 and vote_count >= 500:
        tone = "평점도 높고 반응도 탄탄해서"
    elif vote_count >= 2000:
        tone = "요즘 많이들 보는 대중픽이라"
    elif rating >= 7.0:
        tone = "평점이 안정적이라"
    else:
        tone = "가볍게 즐기기 좋은 인기작이라"

    strength = ", ".join([f"{g}:{scores.get(g,0)}" for g, _ in mix])
    return f"당신의 취향({mix_str}, 점수 {strength})에 잘 맞고, {tone} 과제/시험 끝나고 보기 딱 좋아요."


# =========================
# 세션 상태
# =========================
if "answers" not in st.session_state:
    st.session_state.answers = {}

if "submitted" not in st.session_state:
    st.session_state.submitted = False

if "analysis" not in st.session_state:
    st.session_state.analysis = None

if "rec_popular" not in st.session_state:
    st.session_state.rec_popular = []

if "rec_toprated" not in st.session_state:
    st.session_state.rec_toprated = []

if "error" not in st.session_state:
    st.session_state.error = ""


def reset_test():
    st.session_state.answers = {}
    st.session_state.submitted = False
    st.session_state.analysis = None
    st.session_state.rec_popular = []
    st.session_state.rec_toprated = []
    st.session_state.error = ""
    for i in range(1, len(questions) + 1):
        k = f"q{i}"
        if k in st.session_state:
            del st.session_state[k]


# =========================
# Sidebar: 설정
# =========================
with st.sidebar:
    st.header("🔑 TMDB 설정")
    api_key = st.text_input("TMDB API Key", type="password", placeholder="API Key를 입력하세요")
    st.caption("Key는 저장되지 않고 현재 세션에서만 사용됩니다.")
    st.divider()

    with st.expander("고급 옵션", expanded=False):
        language = st.selectbox("기본 언어", ["ko-KR", "en-US"], index=0)
        region = st.selectbox("지역(region)", ["(미사용)", "KR", "US", "JP"], index=1)
        region_val = None if region == "(미사용)" else region

        vote_count_min = st.slider(
            "호평작 최소 투표수(vote_count.gte)",
            min_value=0,
            max_value=5000,
            value=500,
            step=50,
        )

        show_year_filter = st.checkbox("특정 연도만 추천", value=False)
        year_val = None
        if show_year_filter:
            year_val = st.number_input("개봉 연도", min_value=1960, max_value=2030, value=2020, step=1)

    st.divider()
    if TMDBSIMPLE_AVAILABLE:
        st.success("tmdbsimple 사용 중")
    else:
        st.info("tmdbsimple 미설치 → requests로 호출 중 (선택) `pip install tmdbsimple`")

    st.button("다시 테스트하기", on_click=reset_test)


# =========================
# 메인 인트로
# =========================
st.markdown("## 🎬 나와 어울리는 영화는?")
st.markdown(
    '<div class="small-muted">5문항 · 1분 컷! 지금 기분에 딱 맞는 영화 5개를 추천해줄게요 🍿</div>',
    unsafe_allow_html=True,
)
st.divider()

# =========================
# 질문 화면(2열)
# =========================
left, right = st.columns(2, gap="large")

for idx, q in enumerate(questions, start=1):
    key = f"q{idx}"
    if key not in st.session_state.answers:
        st.session_state.answers[key] = q["options"][0]

    target_col = left if idx in (1, 3, 5) else right
    with target_col:
        try:
            box = st.container(border=True)
        except TypeError:
            box = st.container()
        with box:
            st.markdown(f"**{q['q']}**")
            selected = st.radio(
                label=key,
                options=q["options"],
                key=key,
                label_visibility="collapsed",
            )
            st.session_state.answers[key] = selected

st.divider()

b1, b2, b3 = st.columns([1.2, 1.2, 2.6])
with b1:
    submit = st.button("결과 보기", type="primary", use_container_width=True)
with b2:
    st.button("다시 테스트하기", on_click=reset_test, use_container_width=True)
with b3:
    st.markdown('<div class="small-muted">결과 보기 클릭 시 TMDB에서 데이터를 가져옵니다.</div>', unsafe_allow_html=True)


# =========================
# 핵심 수정: vote_count 필터가 "확실히" 적용되도록
# - 여러 페이지에서 후보를 더 가져온 뒤
# - 클라이언트에서 vote_count로 한 번 더 필터링해서 5개를 채움
# =========================
def fetch_enough_movies(api_key: str, base_params: dict, need: int, *, vote_count_floor: int | None = None, max_pages: int = 5):
    collected = []
    seen = set()

    for page in range(1, max_pages + 1):
        params = dict(base_params)
        params["page"] = page

        items = discover(api_key, params)
        if not items:
            break

        for m in items:
            mid = m.get("id")
            title = (m.get("title") or m.get("original_title") or "").strip()
            if not mid or not title:
                continue
            if mid in seen:
                continue

            # ✅ 여기서 확실히 필터 적용
            if vote_count_floor is not None:
                vc = int(m.get("vote_count") or 0)
                if vc < vote_count_floor:
                    continue

            seen.add(mid)
            collected.append(m)
            if len(collected) >= need:
                return collected

    return collected


def enrich_movies(api_key: str, items: list, pbase: str, mix, scores):
    out = []
    for m in items:
        overview = pick_best_overview(api_key, m)
        m2 = dict(m)
        m2["_poster_base"] = pbase
        m2["_overview_final"] = overview
        m2["_reason"] = build_reason(mix, scores, m2)
        out.append(m2)
    return out


# =========================
# 추천 실행
# =========================
if submit:
    st.session_state.error = ""
    st.session_state.submitted = True
    st.session_state.rec_popular = []
    st.session_state.rec_toprated = []
    st.session_state.analysis = None

    if not api_key.strip():
        st.session_state.error = "TMDB API Key를 사이드바에 입력해 주세요."
    else:
        analysis = analyze_answers(st.session_state.answers)
        st.session_state.analysis = analysis

        mix = analysis["mix"]
        scores = analysis["scores"]
        with_genres = with_genres_from_mix(mix)

        pbase = poster_base_url(api_key.strip(), "w500")

        popular_params = {
            "with_genres": with_genres,
            "language": language,
            "sort_by": "popularity.desc",
            "include_adult": False,
        }
        if region_val:
            popular_params["region"] = region_val
        if year_val:
            popular_params["year"] = year_val

        # 호평작: 평점순 + 투표수 필터
        # vote_count.gte 자체도 넣되(서버 필터), 클라이언트에서 한 번 더 걸러서 “확실히”
        toprated_params = {
            "with_genres": with_genres,
            "language": language,
            "sort_by": "vote_average.desc",
            "vote_count.gte": vote_count_min,  # 공식 discover 파라미터 :contentReference[oaicite:1]{index=1}
            "include_adult": False,
        }
        if region_val:
            toprated_params["region"] = region_val
        if year_val:
            toprated_params["year"] = year_val

        with st.spinner("분석 중... (TMDB에서 추천을 불러오는 중)"):
            try:
                # 대중픽은 5개만 확보
                pop5 = fetch_enough_movies(api_key.strip(), popular_params, need=5, vote_count_floor=None, max_pages=3)

                # ✅ 호평작은 vote_count_min을 “확실히” 만족하는 5개를 확보 (여러 페이지 탐색)
                top5 = fetch_enough_movies(
                    api_key.strip(),
                    toprated_params,
                    need=5,
                    vote_count_floor=vote_count_min,  # ✅ 클라이언트 재필터
                    max_pages=8,
                )

                st.session_state.rec_popular = enrich_movies(api_key.strip(), pop5, pbase, mix, scores)
                st.session_state.rec_toprated = enrich_movies(api_key.strip(), top5, pbase, mix, scores)

                # 사용자가 “너무 높게” 잡아서 후보가 부족하면 안내
                if vote_count_min > 0 and len(top5) < 5:
                    st.warning(
                        f"호평작 조건(vote_count ≥ {vote_count_min})을 만족하는 영화가 충분하지 않아 "
                        f"{len(top5)}개만 표시했어요. 투표수 기준을 낮추면 더 많이 나와요."
                    )

            except requests.HTTPError as e:
                st.session_state.error = f"TMDB 요청 실패(HTTPError): {e}"
            except Exception as e:
                st.session_state.error = f"영화 정보를 가져오지 못했어요: {e}"


# =========================
# 결과 출력
# =========================
if st.session_state.submitted:
    st.write("")
    if st.session_state.error:
        st.error(st.session_state.error)
    else:
        analysis = st.session_state.analysis or {}
        mix = analysis.get("mix", [])
        scores = analysis.get("scores", {})

        try:
            summary = st.container(border=True)
        except TypeError:
            summary = st.container()

        with summary:
            st.markdown("### ✅ 내 취향 요약")
            chips = []
            for g, w in mix:
                chips.append(f'<span class="badge badge-strong">{g} {int(round(w*100))}%</span>')
            st.markdown("".join(chips) if chips else '<span class="badge">분석 결과 없음</span>', unsafe_allow_html=True)
            st.markdown(
                '<div class="small-muted">대학생 무드로 요약하면: <b>과제/시험 끝나고 뇌 비우거나 몰입하기 좋은 타입</b> 😎</div>',
                unsafe_allow_html=True,
            )

        st.write("")
        tab1, tab2 = st.tabs(["🔥 대중픽(인기순)", "🏆 호평작(평점순)"])

        def render_movies(items: list):
            if not items:
                st.info("추천 결과가 비어있어요. (옵션을 바꿔 다시 시도해보세요.)")
                return

            for m in items:
                title = (m.get("title") or m.get("original_title") or "제목 없음").strip()
                rating = float(m.get("vote_average") or 0.0)
                vote_count = int(m.get("vote_count") or 0)

                overview = (m.get("_overview_final") or "").strip()
                poster_path = m.get("poster_path")
                pbase = m.get("_poster_base") or "https://image.tmdb.org/t/p/w500"
                poster_url = f"{pbase}{poster_path}" if poster_path else None

                try:
                    card = st.container(border=True)
                except TypeError:
                    card = st.container()

                with card:
                    c1, c2 = st.columns([1, 2], gap="large")
                    with c1:
                        if poster_url:
                            st.image(poster_url, use_container_width=True)
                        else:
                            st.caption("포스터 없음")
                    with c2:
                        st.markdown(f"#### {title}")
                        st.markdown(f"**평점:** {rating:.1f} / 10  ·  **투표수:** {vote_count:,}")
                        st.write(clamp(overview, 260))
                        st.info("💡 이 영화를 추천하는 이유: " + (m.get("_reason") or ""))

        with tab1:
            render_movies(st.session_state.rec_popular)

        with tab2:
            render_movies(st.session_state.rec_toprated)
