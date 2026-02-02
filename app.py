import streamlit as st
import requests

st.set_page_config(page_title="🎬 나와 어울리는 영화는?", page_icon="🎬", layout="wide")

# =========================
# TMDB 설정 / 상수
# =========================
POSTER_BASE = "https://image.tmdb.org/t/p/w500"

GENRES = {
    "액션": 28,
    "코미디": 35,
    "드라마": 18,
    "SF": 878,
    "로맨스": 10749,
    "판타지": 14,
}

# 선택지(4개)는 각각 장르 성향을 나타냄 (요구사항)
# - 로맨스/드라마
# - 액션/어드벤처
# - SF/판타지
# - 코미디
CHOICE_GENRE_MAP = {
    0: ["로맨스", "드라마"],  # ❤️
    1: ["액션"],             # 🔥 (어드벤처는 TMDB 장르 ID에 없으므로 액션으로 수렴)
    2: ["SF", "판타지"],      # 🌌
    3: ["코미디"],            # 😂
}

# =========================
# 질문 데이터 (이전 대화에서 만든 질문)
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

# =========================
# 세션 상태 초기화
# =========================
if "answers" not in st.session_state:
    st.session_state.answers = {}  # {"q1": option_text, ...}

if "submitted" not in st.session_state:
    st.session_state.submitted = False

if "result_genre" not in st.session_state:
    st.session_state.result_genre = None  # "액션"/"코미디"/...

if "movies" not in st.session_state:
    st.session_state.movies = []  # TMDB results (top 5)

if "analysis" not in st.session_state:
    st.session_state.analysis = {}  # scoring details


def reset_test():
    st.session_state.answers = {}
    st.session_state.submitted = False
    st.session_state.result_genre = None
    st.session_state.movies = []
    st.session_state.analysis = {}

    # 라디오 상태 초기화(키 삭제)
    for i in range(1, len(questions) + 1):
        key = f"q{i}"
        if key in st.session_state:
            del st.session_state[key]


# =========================
# 로직: 답변 분석 -> 장르 결정
# =========================
def analyze_answers(answers: dict):
    """
    answers: {"q1": selected_text, ...}
    선택지 인덱스를 기반으로 장르 점수 누적 후, 최종 장르 1개 선택
    """
    scores = {g: 0 for g in GENRES.keys()}  # 액션/코미디/드라마/SF/로맨스/판타지

    # 우선순위(동점 처리)
    # 대학생 대상 무난한 우선순위 예시 (원하면 바꿔도 됨)
    priority = ["로맨스", "드라마", "코미디", "액션", "판타지", "SF"]

    for i, q in enumerate(questions, start=1):
        q_key = f"q{i}"
        selected_text = answers.get(q_key)
        if not selected_text:
            continue

        # 해당 질문 options에서 몇 번째 선택지인지 찾기
        try:
            idx = q["options"].index(selected_text)
        except ValueError:
            continue

        mapped = CHOICE_GENRE_MAP.get(idx, [])
        for g in mapped:
            if g in scores:
                # 로맨스/드라마처럼 2개가 매핑될 수 있으니 가중치를 조금 조정
                # (로맨스/드라마 선택지는 2장르라 각 1점씩)
                scores[g] += 1

    # 최종 장르: 최고 점수
    best = None
    for g in scores.keys():
        if best is None:
            best = g
            continue
        if scores[g] > scores[best]:
            best = g
        elif scores[g] == scores[best]:
            # tie-break: priority 순서가 빠른 장르를 선택
            a = priority.index(g) if g in priority else 999
            b = priority.index(best) if best in priority else 999
            if a < b:
                best = g

    return best, scores


# =========================
# TMDB 호출
# =========================
@st.cache_data(show_spinner=False, ttl=60 * 30)
def fetch_top_movies(api_key: str, genre_id: int):
    """
    TMDB discover/movie로 인기 영화 5개 가져오기
    """
    url = (
        "https://api.themoviedb.org/3/discover/movie"
        f"?api_key={api_key}"
        f"&with_genres={genre_id}"
        f"&language=ko-KR"
        f"&sort_by=popularity.desc"
        f"&include_adult=false"
        f"&page=1"
    )
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    results = data.get("results", []) or []
    return results[:5]


def build_reason(result_genre: str, scores: dict, movie: dict):
    """
    간단 추천 이유(요구사항)
    - 장르 점수 기반 + 영화 평점 기반
    """
    label = result_genre
    g_score = scores.get(result_genre, 0)
    rating = movie.get("vote_average", 0) or 0

    if rating >= 7.5:
        return f"당신의 답변이 '{label}' 성향({g_score}점)과 가장 잘 맞고, 평점도 높아 만족도가 높을 가능성이 커요."
    if rating >= 6.5:
        return f"'{label}' 무드({g_score}점)를 선호하는 편이라, 지금 기분 전환용으로 잘 맞을 것 같아요."
    return f"당신의 선택이 '{label}' 분위기({g_score}점)에 가깝고, 인기 작품 중에서 가볍게 즐기기 좋은 영화예요."


def clamp(text: str, n: int = 170):
    if not text:
        return "줄거리 정보가 없습니다."
    return text if len(text) <= n else text[:n].rstrip() + "…"


# =========================
# UI
# =========================
with st.sidebar:
    st.header("🔑 TMDB 설정")
    api_key = st.text_input("TMDB API Key", type="password", placeholder="여기에 API Key를 입력하세요")
    st.caption("API Key는 저장되지 않아요(현재 세션에서만 사용).")
    st.divider()
    st.button("다시 테스트하기", on_click=reset_test)

st.title("🎬 나와 어울리는 영화는?")
st.write("5개의 질문에 답하면, 당신의 취향에 맞는 장르를 분석해서 **TMDB 인기 영화 5개**를 추천해줘요! 🍿")

st.divider()

# 질문 표시
for i, item in enumerate(questions, start=1):
    q_key = f"q{i}"

    # 초기값 설정: 아직 답이 없으면 첫번째 옵션으로
    if q_key not in st.session_state.answers:
        st.session_state.answers[q_key] = item["options"][0]

    st.subheader(item["q"])
    selected = st.radio(
        label=q_key,
        options=item["options"],
        key=q_key,
        label_visibility="collapsed",
    )

    # 세션에 저장
    st.session_state.answers[q_key] = selected
    st.write("")

st.divider()

col1, col2 = st.columns([1, 1])

with col1:
    result_clicked = st.button("결과 보기", type="primary")

with col2:
    st.caption("※ 결과 보기 클릭 시 TMDB에서 데이터를 가져옵니다.")

# =========================
# 결과 보기 로직
# =========================
if result_clicked:
    st.session_state.submitted = True
    st.session_state.movies = []
    st.session_state.result_genre = None
    st.session_state.analysis = {}

    # 입력 검증
    if not api_key.strip():
        st.error("사이드바에 TMDB API Key를 입력해 주세요.")
    else:
        # 1) 답변 분석 -> 장르 결정
        best_genre, scores = analyze_answers(st.session_state.answers)
        st.session_state.result_genre = best_genre
        st.session_state.analysis = scores

        # 2) TMDB에서 인기 영화 5개 가져오기
        with st.spinner("분석 중... (TMDB에서 영화를 불러오는 중)"):
            try:
                genre_id = GENRES[best_genre]
                movies = fetch_top_movies(api_key.strip(), genre_id)
                st.session_state.movies = movies
