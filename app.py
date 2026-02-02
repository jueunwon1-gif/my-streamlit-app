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

# 선택지 인덱스 → 장르 성향 매핑
CHOICE_GENRE_MAP = {
    0: ["로맨스", "드라마"],  # ❤️
    1: ["액션"],             # 🔥
    2: ["SF", "판타지"],      # 🌌
    3: ["코미디"],            # 😂
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

# =========================
# 세션 상태 초기화
# =========================
if "answers" not in st.session_state:
    st.session_state.answers = {}

if "submitted" not in st.session_state:
    st.session_state.submitted = False

if "movies" not in st.session_state:
    st.session_state.movies = []

if "result_genre" not in st.session_state:
    st.session_state.result_genre = None

if "scores" not in st.session_state:
    st.session_state.scores = {}


# =========================
# 초기화 함수
# =========================
def reset_test():
    st.session_state.answers = {}
    st.session_state.submitted = False
    st.session_state.movies = []
    st.session_state.result_genre = None
    st.session_state.scores = {}

    for i in range(1, 6):
        key = f"q{i}"
        if key in st.session_state:
            del st.session_state[key]


# =========================
# 답변 분석 함수
# =========================
def analyze_answers():
    scores = {g: 0 for g in GENRES.keys()}

    for i, q in enumerate(questions, start=1):
        q_key = f"q{i}"
        selected = st.session_state.answers.get(q_key)

        if selected:
            idx = q["options"].index(selected)
            mapped_genres = CHOICE_GENRE_MAP[idx]

            for g in mapped_genres:
                scores[g] += 1

    best_genre = max(scores, key=scores.get)
    return best_genre, scores


# =========================
# TMDB 영화 가져오기
# =========================
def fetch_movies(api_key, genre_id):
    url = (
        f"https://api.themoviedb.org/3/discover/movie"
        f"?api_key={api_key}"
        f"&with_genres={genre_id}"
        f"&language=ko-KR"
        f"&sort_by=popularity.desc"
    )

    response = requests.get(url)
    data = response.json()

    return data["results"][:5]


# =========================
# 추천 이유 생성
# =========================
def build_reason(genre):
    return f"당신의 답변이 '{genre}' 성향과 가장 잘 맞아서 추천했어요!"


# =========================
# UI 시작
# =========================

# 사이드바
with st.sidebar:
    st.header("🔑 TMDB API Key 입력")
    api_key = st.text_input("API Key", type="password")

    st.button("다시 테스트하기", on_click=reset_test)

st.title("🎬 나와 어울리는 영화는?")
st.write("질문에 답하면 TMDB에서 인기 영화 5개를 추천해드려요!")

st.divider()

# 질문 출력
for i, q in enumerate(questions, start=1):
    st.subheader(q["q"])

    selected = st.radio(
        label=f"q{i}",
        options=q["options"],
        key=f"q{i}",
        label_visibility="collapsed"
    )

    st.session_state.answers[f"q{i}"] = selected

st.divider()

# 결과 보기 버튼
if st.button("결과 보기", type="primary"):

    if not api_key:
        st.error("TMDB API Key를 입력해주세요!")
    else:
        st.session_state.submitted = True

        # 1) 장르 분석
        best_genre, scores = analyze_answers()
        st.session_state.result_genre = best_genre
        st.session_state.scores = scores

        # 2) TMDB 영화 가져오기
        with st.spinner("분석 중... 영화 추천 불러오는 중..."):
            try:
                genre_id = GENRES[best_genre]
                movies = fetch_movies(api_key, genre_id)
                st.session_state.movies = movies

            except Exception as e:
                st.error("TMDB 영화 데이터를 불러오지 못했습니다.")
                st.write(e)

# =========================
# 결과 출력
# =========================
if st.session_state.submitted:

    st.subheader("✅ 당신에게 어울리는 장르")
    st.success(f"🎭 {st.session_state.result_genre}")

    st.subheader("🎥 추천 영화 TOP 5")

    for movie in st.session_state.movies:

        title = movie.get("title")
        rating = movie.get("vote_average")
        overview = movie.get("overview")
        poster_path = movie.get("poster_path")

        poster_url = POSTER_BASE + poster_path if poster_path else None

        col1, col2 = st.columns([1, 2])

        with col1:
            if poster_url:
                st.image(poster_url, use_container_width=True)

        with col2:
            st.markdown(f"### 🎬 {title}")
            st.write(f"⭐ 평점: {rating}")
            st.write(f"📖 줄거리: {overview[:200]}...")

            st.info("💡 추천 이유: " + build_reason(st.session_state.result_genre))

        st.divider()
