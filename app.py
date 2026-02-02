import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# (선택) TMDB 파이썬 래퍼: tmdbsimple
# - Wrappers & Libraries 문서에 Python 래퍼로 소개됨 (tmdbsimple 등) :contentReference[oaicite:5]{index=5}
try:
    import tmdbsimple as tmdb  # pip install tmdbsimple
    TMDBSIMPLE_AVAILABLE = True
except Exception:
    TMDBSIMPLE_AVAILABLE = False


# =========================
# 페이지 설정
# =========================
st.set_page_config(page_title="🎬 나와 어울리는 영화는?", page_icon="🎬", layout="wide")

st.title("🎬 나와 어울리는 영화는?")
st.write("5개의 질문에 답하면, 당신의 취향을 분석해 **TMDB 인기 영화 5개**를 추천해드려요! 🍿")
st.caption("※ TMDB API Key는 사이드바에 입력하세요.")

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
# 각 질문의 4개 선택지는 각각:
# - 로맨스/드라마
# - 액션/어드벤처
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

# 선택지 인덱스 -> 장르 점수 매핑(고도화: 묶인 장르에 가중치 분배)
# 0: 로맨스/드라마, 1: 액션, 2: SF/판타지, 3: 코미디
CHOICE_SCORE = {
    0: {"로맨스": 1, "드라마": 1},
    1: {"액션": 2},
    2: {"SF": 1, "판타지": 1},
    3: {"코미디": 2},
}

# =========================
# HTTP 세션 (리트라이 포함)
# =========================
@st.cache_resource
def get_http_session():
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


# =========================
# TMDB configuration 가져오기(이미지 URL 견고화)
# 이미지 URL은 base_url + size + file_path 조합이 원칙 :contentReference[oaicite:6]{index=6}
# =========================
@st.cache_data(ttl=60 * 60, show_spinner=False)
def fetch_tmdb_configuration(api_key: str):
    session = get_http_session()
    url = "https://api.themoviedb.org/3/configuration"
    r = session.get(url, params={"api_key": api_key}, timeout=15)
    r.raise_for_status()
    return r.json()


def get_poster_base(api_key: str, preferred_size: str = "w500") -> str:
    """
    configuration에서 base_url + size를 구성.
    실패하면 요구사항의 기본 URL로 fallback.
    """
    fallback = "https://image.tmdb.org/t/p/w500"
    try:
        config = fetch_tmdb_configuration(api_key)
        images = config.get("images", {})
        base_url = images.get("secure_base_url") or images.get("base_url")
        sizes = images.get("poster_sizes", []) or []
        if not base_url:
            return fallback

        # preferred_size가 없으면 가장 가까운/무난한 크기 선택
        if preferred_size in sizes:
            size = preferred_size
        else:
            # w500이 없을 때를 대비해 중간값에 가까운 사이즈 선택
            size = "w500" if "w500" in sizes else (sizes[len(sizes)//2] if sizes else "w500")

        return f"{base_url}{size}"
    except Exception:
        return fallback


# =========================
# TMDB discover/movie 호출 (상위 장르 1~2개 OR 검색)
# with_genres는 여러 값을 받을 수 있고, 파이프(|)는 OR 개념으로 사용됨 :contentReference[oaicite:7]{index=7}
# =========================
@st.cache_data(ttl=60 * 30, show_spinner=False)
def discover_movies_requests(api_key: str, with_genres: str, language: str, region: str | None, year: int | None):
    session = get_http_session()
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": api_key,
        "with_genres": with_genres,
        "language": language,
        "sort_by": "popularity.desc",
        "include_adult": "false",
        "page": 1,
    }
    if region:
        params["region"] = region
    if year:
        params["year"] = year

    r = session.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    return (data.get("results") or [])[:5]


@st.cache_data(ttl=60 * 30, show_spinner=False)
def discover_movies_tmdbsimple(api_key: str, with_genres: str, language: str, region: str | None, year: int | None):
    # tmdbsimple은 v3 래퍼로, 엔드포인트와 1:1로 매핑하는 형태 :contentReference[oaicite:8]{index=8}
    tmdb.API_KEY = api_key
    d = tmdb.Discover()
    kwargs = {
        "with_genres": with_genres,
        "language": language,
        "sort_by": "popularity.desc",
        "include_adult": False,
        "page": 1,
    }
    if region:
        kwargs["region"] = region
    if year:
        kwargs["year"] = year

    data = d.movie(**kwargs)
    results = (data.get("results") or [])[:5]
    return results


def discover_top5(api_key: str, with_genres: str, language: str, region: str | None, year: int | None):
    if TMDBSIMPLE_AVAILABLE:
        return discover_movies_tmdbsimple(api_key, with_genres, language, region, year)
    return discover_movies_requests(api_key, with_genres, language, region, year)


# =========================
# 분석: 답변 -> 장르 점수 -> 상위 2개 선택(고도화)
# =========================
def analyze_answers(answers: dict) -> dict:
    scores = {g: 0 for g in GENRES.keys()}

    for i, q in enumerate(questions, start=1):
        key = f"q{i}"
        selected = answers.get(key)
        if not selected:
            continue
        idx = q["options"].index(selected)
        for g, v in CHOICE_SCORE.get(idx, {}).items():
            scores[g] += v

    # 상위 2개(동점이면 우선순위로 정리)
    priority = ["로맨스", "드라마", "코미디", "액션", "판타지", "SF"]

    sorted_genres = sorted(
        scores.items(),
        key=lambda kv: (kv[1], -priority.index(kv[0]) if kv[0] in priority else -999),
        reverse=True,
    )

    top1, top2 = sorted_genres[0][0], sorted_genres[1][0]
    # top2가 0점이면 굳이 섞지 않음
    top = [top1] if scores[top2] == 0 else [top1, top2]

    return {"scores": scores, "top_genres": top}


def build_reason(top_genres: list[str], scores: dict, movie: dict) -> str:
    """
    '이 영화를 추천하는 이유'를 간단히:
    - 상위 장르(들) + 영화 평점 기반
    """
    labels = ", ".join(top_genres)
    strength = "/".join([f"{g} {scores.get(g,0)}점" for g in top_genres])
    rating = float(movie.get("vote_average") or 0)

    if rating >= 7.5:
        return f"당신의 선호 장르({labels}) 성향({strength})과 잘 맞고, 평점도 높아 만족도가 높을 확률이 커요."
    if rating >= 6.5:
        return f"당신의 선호 장르({labels}) 분위기({strength})에 잘 맞는 인기작이라 가볍게 시작하기 좋아요."
    return f"당신의 선호 장르({labels}) 성향({strength})을 반영해, 요즘 많이 보는 인기 영화 중에서 골랐어요."


def clamp(text: str, n: int = 220) -> str:
    if not text:
        return "줄거리 정보가 없습니다."
    return text if len(text) <= n else text[:n].rstrip() + "…"


# =========================
# 세션 상태
# =========================
if "answers" not in st.session_state:
    st.session_state.answers = {}

if "submitted" not in st.session_state:
    st.session_state.submitted = False

if "movies" not in st.session_state:
    st.session_state.movies = []

if "analysis" not in st.session_state:
    st.session_state.analysis = {"scores": {g: 0 for g in GENRES}, "top_genres": []}

if "error" not in st.session_state:
    st.session_state.error = ""


def reset_test():
    st.session_state.answers = {}
    st.session_state.submitted = False
    st.session_state.movies = []
    st.session_state.analysis = {"scores": {g: 0 for g in GENRES}, "top_genres": []}
    st.session_state.error = ""

    for i in range(1, len(questions) + 1):
        k = f"q{i}"
        if k in st.session_state:
            del st.session_state[k]


# =========================
# Sidebar: API Key + 옵션
# =========================
with st.sidebar:
    st.header("🔑 TMDB 설정")

    api_key = st.text_input("TMDB API Key", type="password", placeholder="사이드바에 API Key 입력")
    st.caption("Key는 앱에 저장되지 않고 현재 세션에서만 사용됩니다.")

    st.divider()
    st.subheader("⚙️ 추천 옵션 (고도화)")
    language = st.selectbox("언어(language)", ["ko-KR", "en-US"], index=0)
    region = st.selectbox("지역(region)", ["(미사용)", "KR", "US", "JP"], index=1)
    region_val = None if region == "(미사용)" else region

    use_year = st.checkbox("특정 연도만 보기(선택)", value=False)
    year_val = None
    if use_year:
        year_val = st.number_input("개봉 연도", min_value=1960, max_value=2030, value=2020, step=1)

    st.divider()
    if not TMDBSIMPLE_AVAILABLE:
        st.info("참고: tmdbsimple 미설치로 requests 방식으로 호출 중입니다. (선택) `pip install tmdbsimple`")
    else:
        st.success("tmdbsimple 래퍼를 사용 중입니다. (코드가 더 단순/견고해짐)")

    st.button("다시 테스트하기", on_click=reset_test)


st.divider()

# =========================
# 질문 화면
# =========================
for i, q in enumerate(questions, start=1):
    key = f"q{i}"

    # 초기값: 첫 옵션
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

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    submit = st.button("결과 보기", type="primary")
with col2:
    st.button("다시 테스트하기", on_click=reset_test)
with col3:
    st.caption("결과 보기 클릭 시 TMDB에서 인기 영화 데이터를 가져옵니다.")

# =========================
# 결과 처리
# =========================
if submit:
    st.session_state.error = ""
    st.session_state.submitted = True
    st.session_state.movies = []
    st.session_state.analysis = {"scores": {g: 0 for g in GENRES}, "top_genres": []}

    if not api_key.strip():
        st.session_state.error = "TMDB API Key를 사이드바에 입력해 주세요."
    else:
        analysis = analyze_answers(st.session_state.answers)
        st.session_state.analysis = analysis

        # 상위 1~2개 장르로 OR 검색: 예) "10749|18"
        top_genres = analysis["top_genres"]
        with_genres = "|".join(str(GENRES[g]) for g in top_genres)

        # 포스터 base_url 구성 (configuration 기반) :contentReference[oaicite:9]{index=9}
        poster_base = get_poster_base(api_key.strip(), preferred_size="w500")

        with st.spinner("분석 중... (TMDB에서 인기 영화를 불러오는 중)"):
            try:
                movies = discover_top5(
                    api_key=api_key.strip(),
                    with_genres=with_genres,
                    language=language,
                    region=region_val,
                    year=year_val,
                )
                # poster_base를 각 영화 표시에서 사용하기 위해 세션에 저장해도 되지만,
                # 여기서는 아래 출력에서 local 변수로 사용
                st.session_state.movies = [{"_poster_base": poster_base, **m} for m in movies]

            except requests.HTTPError as e:
                st.session_state.error = f"TMDB 요청 실패(HTTPError): {e}"
            except Exception as e:
                st.session_state.error = f"영화 정보를 가져오지 못했어요: {e}"

# =========================
# 결과 출력
# =========================
if st.session_state.submitted:
    if st.session_state.error:
        st.error(st.session_state.error)
    else:
        top_genres = st.session_state.analysis.get("top_genres", [])
        scores = st.session_state.analysis.get("scores", {})

        st.subheader("✅ 분석 결과")
        if top_genres:
            st.success(f"당신의 선호 장르는 **{', '.join(top_genres)}** 쪽이에요!")
        else:
            st.info("분석 결과가 비어있어요. 다시 시도해 주세요.")

        with st.expander("🧾 답변/점수 보기"):
            st.write("### 내 답변")
            for i, q in enumerate(questions, start=1):
                k = f"q{i}"
                st.write(f"**{q['q']}**")
                st.write(f"- {st.session_state.answers.get(k, '미선택')}")
            st.write("### 장르 점수")
            st.json(scores)

        st.divider()
        st.subheader("🎥 추천 영화 TOP 5")

        movies = st.session_state.movies
        if not movies:
            st.info("추천 결과가 아직 없어요. API Key가 올바른지 확인하고 다시 눌러주세요.")
        else:
            for m in movies:
                poster_base = m.get("_poster_base") or "https://image.tmdb.org/t/p/w500"
                title = m.get("title") or m.get("original_title") or "제목 없음"
                rating = float(m.get("vote_average") or 0)
                overview = clamp(m.get("overview") or "", 240)

                poster_path = m.get("poster_path")
                poster_url = f"{poster_base}{poster_path}" if poster_path else None

                c1, c2 = st.columns([1, 2])
                with c1:
                    if poster_url:
                        st.image(poster_url, use_container_width=True)
                    else:
                        st.caption("포스터 없음")

                with c2:
                    st.markdown(f"### {title}")
                    st.markdown(f"**평점:** {rating:.1f} / 10")
                    st.write(overview)
                    st.info("💡 이 영화를 추천하는 이유: " + build_reason(top_genres, scores, m))

                st.divider()
