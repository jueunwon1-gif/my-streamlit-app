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
            size = "w500" if "w500" in sizes else (
