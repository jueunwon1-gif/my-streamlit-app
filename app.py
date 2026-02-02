import math
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
# 페이지 설정
# =========================
st.set_page_config(page_title="🎬 나와 어울리는 영화는?", page_icon="🎬", layout="wide")

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
# 질문 (이전 대화에서 만든 질문)
# 선택지 4개는 각각:
# - 로맨스/드라마
# - 액션/어드벤처(=액션으로 수렴)
# - SF/판타지
# - 코미디
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

# 선택지 인덱스 -> 장르 점수 매핑
# 고도화: 액션/코미디는 강하게(+2), 로맨스/드라마 & SF/판타지는 2장르로 분배(+1씩)
CHOICE_SCORE = {
    0: {"로맨스": 1, "드라마": 1},
    1: {"액션": 2},
    2: {"SF": 1, "판타지": 1},
    3: {"코미디": 2},
}

# 동점 처리 우선순위(원하면 조정)
PRIORITY = ["로맨스", "드라마", "코미디", "액션", "판타지", "SF"]


# =========================
# HTTP 세션 (리트라이 포함)
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
# TMDB 공통 호출
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


@st.cache_data(ttl=60 * 20, show_spinner=False)
def discover_requests(api_key: str, params: dict) -> list:
    session = get_http_session()
    url = "https://api.themoviedb.org/3/discover/movie"
    base_params = {
        "api_key": api_key,
        "include_adult": "false",
        "page": 1,
    }
    base_params.update(params)
    r = session.get(url, params=base_params, timeout=15)
    r.raise_for_status()
    data = r.json() or {}
    return data.get("results", []) or []


@st.cache_data(ttl=60 * 20, show_spinner=False)
def discover_tmdbsimple(api_key: str, params: dict) -> list:
    tmdb.API_KEY = api_key
    d = tmdb.Discover()
    # tmdbsimple은 파라미터를 그대로 넘겨도 됨 (bool은 bool로)
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


# =========================
# 분석: 답변 -> 점수 -> 상위 장르 + 혼합 비율
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

    # 점수 정렬 (동점은 PRIORITY로 해결)
    def pri(g: str) -> int:
        return PRIORITY.index(g) if g in PRIORITY else 999

    sorted_items = sorted(scores.items(), key=lambda kv: (kv[1], -1000 + (-pri(kv[0]))), reverse=True)
    top1, s1 = sorted_items[0]
    top2, s2 = sorted_items[1]

    # 혼합 전략:
    # - top2가 0점이면 단독
    # - top1과 top2의 점수 차이가 1 이하이면 섞기(70/30 또는 60/40)
    # - 차이가 2 이상이면 top1 위주(80/20 정도) or 단독
    mix = []
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

    return {
        "scores": scores,
        "top1": top1,
        "top2": top2,
        "mix": mix,  # [(genre, weight), ...]
    }


def with_genres_from_mix(mix: list[tuple[str, float]]) -> str:
    # OR 검색: "10749|18"처럼 파이프(|) 사용
    ids = [str(GENRES[g]) for g, w in mix if w > 0]
    return "|".join(ids)


def clamp(text: str, n: int = 240) -> str:
    if not text:
        return ""
    return text if len(text) <= n else text[:n].rstrip() + "…"


def pick_best_overview(api_key: str, movie: dict, prefer_lang: str = "ko-KR") -> str:
    """
    고도화: ko-KR overview가 비면 en-US로 보조 조회(추가 호출 최소화: 필요할 때만)
    """
    overview = (movie.get("overview") or "").strip()
    if overview:
        return overview

    mid = movie.get("id")
    if not mid:
        return ""

    # 보조 조회
    try:
        detail_en = movie_details(api_key, int(mid), "en-US")
        return (detail_en.get("overview") or "").strip()
    except Exception:
        return ""


def build_reason(mix: list[tuple[str, float]], scores: dict, movie: dict, user_context_hint: str) -> str:
    """
    고도화:
    - 혼합 비율(장르 mix)을 문장에 반영
    - 평점/투표수 기반으로 "호평작/대중픽" 느낌 반영
    - 대학생 컨텍스트(시험/새학기/친구/힐링) 힌트를 가볍게 섞음
    """
    parts = []
    for g, w in mix:
        if w <= 0:
            continue
        pct = int(round(w * 100))
        parts.append(f"{g} {pct}%")
    mix_str = " + ".join(parts)

    rating = float(movie.get("vote_average") or 0.0)
    vote_count = int(movie.get("vote_count") or 0)

    tone = ""
    if rating >= 7.6 and vote_count >= 500:
        tone = "평점도 높고(호평), 어느 정도 검증된 작품이라"
    elif vote_count >= 2000:
        tone = "요즘 많이들 보는 대중픽 라인이라"
    elif rating >= 7.0:
        tone = "기본 평점이 안정적이라"
    else:
        tone = "가볍게 보기 좋은 인기작 중에서"

    strength = ", ".join([f"{g}:{scores.get(g,0)}" for g, _ in mix])
    context = user_context_hint.strip()
    if context:
        context = f" {context}"

    return f"당신의 취향 믹스({mix_str}, 점수 {strength})에 맞고, {tone}{context} 추천해요."


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
# UI: Sidebar
# =========================
with st.sidebar:
    st.header("🔑 TMDB 설정")
    api_key = st.text_input("TMDB API Key", type="password", placeholder="여기에 API Key 입력")
    st.caption("API Key는 저장되지 않고 현재 세션에서만 사용됩니다.")
    st.divider()

    st.subheader("⚙️ 추천 고도화 옵션")
    language = st.selectbox("기본 언어", ["ko-KR", "en-US"], index=0)
    region = st.selectbox("지역(region)", ["(미사용)", "KR", "US", "JP"], index=1)
    region_val = None if region == "(미사용)" else region

    # 결과 다양화 옵션
    vote_count_min = st.slider("호평작 최소 투표수(vote_count.gte)", min_value=0, max_value=5000, value=500, step=50)
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
# UI: Main
# =========================
st.title("🎬 나와 어울리는 영화는?")
st.write("질문 5개에 답하면, 답변을 분석해 **장르를 혼합**해서 더 정확하게 추천해드려요! 🍿")
st.caption("고도화: 상위 장르 2개 혼합, 대중픽/호평작 탭 분리, 줄거리 한국어가 없으면 영어로 보조 조회")

st.divider()

# 질문 표시
for i, q in enumerate(questions, start=1):
    key = f"q{i}"
    if key not in st.session_state.answers:
        st.session_state.answers[key] = q["options"][0]

    st.subheader(q["q"])
    selected = st.radio(
        label=key,
        options=q["options"],
        key=key,
        label_visibility="collapsed",
    )
    st.session_state.answers[key] = selected
    st.write("")

st.divider()

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    submit = st.button("결과 보기", type="primary")
with c2:
    st.button("다시 테스트하기", on_click=reset_test)
with c3:
    st.caption("결과 보기 클릭 시 TMDB에서 데이터를 가져옵니다.")

# =========================
# 추천 실행
# =========================
def run_recommendation():
    st.session_state.error = ""
    st.session_state.submitted = True
    st.session_state.rec_popular = []
    st.session_state.rec_toprated = []
    st.session_state.analysis = None

    if not api_key.strip():
        st.session_state.error = "TMDB API Key를 사이드바에 입력해 주세요."
        return

    analysis = analyze_answers(st.session_state.answers)
    st.session_state.analysis = analysis

    mix = analysis["mix"]
    scores = analysis["scores"]
    with_genres = with_genres_from_mix(mix)

    # 대학생 컨텍스트 힌트(가볍게)
    # (답변 내용에 따라 조금 바꿀 수 있지만, 일단 공통 문구를 짧게)
    user_context_hint = "시험/과제 후 리프레시용으로 딱!"

    # 포스터 base
    pbase = poster_base_url(api_key.strip(), "w500")

    # 1) 대중픽: popularity.desc
    popular_params = {
        "with_genres": with_genres,
        "language": language,
        "sort_by": "popularity.desc",
        "include_adult": False,
        "page": 1,
    }
    # 2) 호평작: vote_average.desc + vote_count.gte
    toprated_params = {
        "with_genres": with_genres,
        "language": language,
        "sort_by": "vote_average.desc",
        "vote_count.gte": vote_count_min,
        "include_adult": False,
        "page": 1,
    }

    if region_val:
        popular_params["region"] = region_val
        toprated_params["region"] = region_val
    if year_val:
        popular_params["year"] = year_val
        toprated_params["year"] = year_val

    with st.spinner("분석 중... (TMDB에서 추천을 불러오는 중)"):
        try:
            pop = discover(api_key.strip(), popular_params)[:12]   # 후보를 넉넉히 받아 중복/빈 줄거리 보정
            top = discover(api_key.strip(), toprated_params)[:12]

            # 후보에서 5개 뽑기: 포스터/제목 존재 우선, 중복 제거
            def pick5(items: list) -> list:
                seen = set()
                picked = []
                for m in items:
                    mid = m.get("id")
                    title = (m.get("title") or m.get("original_title") or "").strip()
                    if not mid or not title or mid in seen:
                        continue
                    seen.add(mid)
                    picked.append(m)
                    if len(picked) >= 5:
                        break
                return picked

            pop5 = pick5(pop)
            top5 = pick5(top)

            # 줄거리 보조 조회(ko-KR 비어있으면 en-US)
            def enrich(items: list) -> list:
                out = []
                for m in items:
                    overview = pick_best_overview(api_key.strip(), m, prefer_lang=language)
                    m2 = dict(m)
                    m2["_overview_final"] = overview
                    m2["_poster_base"] = pbase
                    m2["_reason"] = build_reason(mix, scores, m2, user_context_hint)
                    out.append(m2)
                return out

            st.session_state.rec_popular = enrich(pop5)
            st.session_state.rec_toprated = enrich(top5)

        except requests.HTTPError as e:
            st.session_state.error = f"TMDB 요청 실패(HTTPError): {e}"
        except Exception as e:
            st.session_state.error = f"영화 정보를 가져오지 못했어요: {e}"


if submit:
    run_recommendation()

# =========================
# 결과 출력
# =========================
if st.session_state.submitted:
    if st.session_state.error:
        st.error(st.session_state.error)
    else:
        analysis = st.session_state.analysis or {}
        mix = analysis.get("mix", [])
        scores = analysis.get("scores", {})

        # 헤더: 취향 믹스 보여주기
        st.subheader("✅ 분석 결과: 취향 믹스")
        if mix:
            chips = []
            for g, w in mix:
                chips.append(f"{g} {int(round(w*100))}%")
            st.success(" + ".join(chips))
        else:
            st.info("분석 결과가 비어있어요. 다시 시도해 주세요.")

        # 디버그/설명
        with st.expander("🧾 내 답변 + 점수 자세히 보기"):
            st.write("### 내 답변")
            for i, q in enumerate(questions, start=1):
                k = f"q{i}"
                st.write(f"**{q['q']}**")
                st.write(f"- {st.session_state.answers.get(k, '미선택')}")
            st.write("### 장르 점수")
            st.json(scores)

        st.divider()

        tab1, tab2 = st.tabs(["🔥 대중픽(인기순)", "🏆 호평작(평점순)"])

        def render_movies(items: list):
            if not items:
                st.info("추천 결과가 비어있어요. 옵션(지역/연도/투표수)을 바꿔 다시 시도해보세요.")
                return

            for m in items:
                title = (m.get("title") or m.get("original_title") or "제목 없음").strip()
                rating = float(m.get("vote_average") or 0)
                vote_count = int(m.get("vote_count") or 0)
                overview = (m.get("_overview_final") or "").strip()
                if not overview:
                    overview = "줄거리 정보가 없습니다."
                overview = clamp(overview, 260)

                poster_path = m.get("poster_path")
                pbase = m.get("_poster_base") or "https://image.tmdb.org/t/p/w500"
                poster_url = f"{pbase}{poster_path}" if poster_path else None

                c1, c2 = st.columns([1, 2])
                with c1:
                    if poster_url:
                        st.image(poster_url, use_container_width=True)
                    else:
                        st.caption("포스터 없음")

                with c2:
                    st.markdown(f"### {title}")
                    st.markdown(f"**평점:** {rating:.1f} / 10  ·  **투표수:** {vote_count:,}")
                    st.write(overview)
                    st.info("💡 이 영화를 추천하는 이유: " + (m.get("_reason") or ""))

                st.divider()

        with tab1:
            render_movies(st.session_state.rec_popular)

        with tab2:
            render_movies(st.session_state.rec_toprated)
