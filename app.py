import json
import random
import re
from html import unescape

import requests
import streamlit as st

st.set_page_config(page_title="나와 어울리는 책은?", page_icon="📚", layout="centered")

# =====================================================
# Sidebar: API Keys / Options
# =====================================================
st.sidebar.header("🔑 API 설정")

nl_api_key = st.sidebar.text_input(
    "국립중앙도서관(ISBN 서지정보) API Key (cert_key)",
    type="password",
    help="국립중앙도서관 ISBN 서지정보 API cert_key 값을 입력하세요.",
)

openai_api_key = st.sidebar.text_input(
    "OpenAI API Key (선택)",
    type="password",
    help="AI가 도서 후보(도서명/저자)를 더 다양하게 추천하도록 하려면 필요합니다. 없으면 데모 추천 목록으로 동작합니다.",
)
openai_model = st.sidebar.text_input("OpenAI 모델", value="gpt-4o-mini")

demo_mode = st.sidebar.checkbox(
    "데모 모드(국립중앙도서관 API 없이도 결과 보기)",
    value=True,
    help="API Key가 없어도 장르 분석 + 추천 3권 + 개인화 이유(설문 근거)를 확인할 수 있습니다.",
)

st.title("📚 나와 어울리는 책은?")
st.write(
    "7문항 심리테스트로 **성향(장르 취향)**과 **현재 상황(무엇이 필요한지)**을 함께 파악해 "
    "당신에게 맞는 책 3권을 추천해드립니다.\n\n"
    "- 국립중앙도서관 API 키가 있으면: **표지/ISBN/소개**까지 실제 데이터로 표시\n"
    "- 없으면(데모 모드): 추천/이유 중심으로 먼저 확인 가능"
)

# =====================================================
# New Questionnaire (성향 + 상황)
#   - Q1~Q4: 성향 중심
#   - Q5~Q7: 상황 중심
# =====================================================
questions = [
    "1) 새로운 책을 고를 때 가장 끌리는 요소는?",
    "2) 친구가 책 추천을 부탁하면 나는 보통…",
    "3) 내가 책을 읽을 때 가장 만족스러운 순간은?",
    "4) 평소 내가 가장 자주 관심을 갖는 주제는?",
    "5) 요즘 나에게 가장 필요한 것은?",
    "6) 최근 내가 책을 찾게 되는 이유는?",
    "7) 지금 당장 책이 내게 해줬으면 하는 역할은?",
]

question_choices = [
    [
        "A. 읽고 나서 바로 실천할 수 있는 조언",
        "B. 삶에 대한 깊은 질문과 통찰",
        "C. 새로운 지식과 기술을 배우는 재미",
        "D. 사회와 시대를 이해하는 관점",
        "E. 감정적으로 몰입할 수 있는 이야기",
    ],
    [
        "A. 도움이 될 만한 현실적인 책을 추천한다",
        "B. 생각을 넓혀줄 책을 추천한다",
        "C. 신기한 정보를 주는 책을 추천한다",
        "D. 세상을 이해하게 해주는 책을 추천한다",
        "E. 재미있게 읽히는 책을 추천한다",
    ],
    [
        "A. “이건 내 삶에 바로 적용할 수 있겠다” 느낄 때",
        "B. “세상을 보는 시야가 넓어졌다” 느낄 때",
        "C. “새로운 사실을 배웠다” 느낄 때",
        "D. “사회나 역사를 이해하게 됐다” 느낄 때",
        "E. “완전히 몰입해서 감정이 움직였다” 느낄 때",
    ],
    [
        "A. 성장, 목표, 자기관리",
        "B. 인간관계, 삶의 의미",
        "C. 미래기술, 과학, 데이터",
        "D. 사회문제, 역사적 사건",
        "E. 감정, 이야기, 상상 속 세계",
    ],
    [
        "A. 다시 동기부여하고 방향을 잡는 것",
        "B. 내 마음을 정리할 수 있는 통찰",
        "C. 머리를 자극하는 새로운 호기심",
        "D. 현실을 이해하고 시야를 넓히는 관점",
        "E. 위로받고 감정을 쉬게 하는 이야기",
    ],
    [
        "A. 미래 준비나 자기계발이 필요해서",
        "B. 복잡한 감정을 정리하고 싶어서",
        "C. 새로운 분야를 배우고 싶어서",
        "D. 사회와 세상 흐름이 궁금해서",
        "E. 지치고 쉬고 싶어서",
    ],
    [
        "A. “앞으로 뭘 해야 할지 알려주는 나침반”",
        "B. “생각을 정리해주는 대화 상대”",
        "C. “새로운 세상을 보여주는 창문”",
        "D. “현실을 이해하게 해주는 지도”",
        "E. “마음을 쉬게 해주는 휴식처”",
    ],
]

# =====================================================
# Genre mapping (A~E)
# =====================================================
genre_map = {"A": "자기계발", "B": "인문/철학", "C": "과학/IT", "D": "역사/사회", "E": "소설"}

genre_persona = {
    "자기계발": "실행·루틴·성과를 중시하는 성장형",
    "인문/철학": "의미·가치·자기이해를 깊게 파고드는 성찰형",
    "과학/IT": "원리·구조·정보를 분석하는 탐구형",
    "역사/사회": "사회 구조·맥락·흐름을 이해하려는 관찰형",
    "소설": "감정·분위기·서사 몰입을 통해 회복하는 감성형",
}

# 상황 태그(위로/휴식/동기/탐구) 점수화: Q5~Q7 기준
# - 위로: 감정 위로/정서적 안정
# - 휴식: 쉬고 싶음/회복
# - 동기: 방향/동기부여/실행
# - 탐구: 호기심/지식 탐색/세상 이해
situation_tag_map_q5_to_q7 = {
    # Q5
    5: {
        "A": ["동기"],
        "B": ["위로"],
        "C": ["탐구"],
        "D": ["탐구"],
        "E": ["위로", "휴식"],
    },
    # Q6
    6: {
        "A": ["동기"],
        "B": ["위로"],
        "C": ["탐구"],
        "D": ["탐구"],
        "E": ["휴식", "위로"],
    },
    # Q7
    7: {
        "A": ["동기"],
        "B": ["위로"],
        "C": ["탐구"],
        "D": ["탐구"],
        "E": ["휴식", "위로"],
    },
}

tag_display = {
    "동기": "방향/동기부여",
    "위로": "감정 정리/위로",
    "휴식": "휴식/회복",
    "탐구": "호기심/탐구",
}

# =====================================================
# Demo fallback pool
# =====================================================
fallback_pool = {
    "자기계발": [
        {"title": "아주 작은 습관의 힘", "author": "제임스 클리어"},
        {"title": "그릿", "author": "앤절라 더크워스"},
        {"title": "딥 워크", "author": "칼 뉴포트"},
        {"title": "원씽", "author": "게리 켈러"},
        {"title": "미라클 모닝", "author": "할 엘로드"},
    ],
    "인문/철학": [
        {"title": "정의란 무엇인가", "author": "마이클 샌델"},
        {"title": "죽음의 수용소에서", "author": "빅터 프랭클"},
        {"title": "소크라테스 익스프레스", "author": "에릭 와이너"},
        {"title": "철학은 어떻게 삶의 무기가 되는가", "author": "야마구치 슈"},
        {"title": "사피엔스", "author": "유발 하라리"},
    ],
    "과학/IT": [
        {"title": "코스모스", "author": "칼 세이건"},
        {"title": "팩트풀니스", "author": "한스 로슬링"},
        {"title": "클린 코드", "author": "로버트 C. 마틴"},
        {"title": "AI 2041", "author": "카이푸 리, 천치우판"},
        {"title": "이기적 유전자", "author": "리처드 도킨스"},
    ],
    "역사/사회": [
        {"title": "총, 균, 쇠", "author": "재레드 다이아몬드"},
        {"title": "넛지", "author": "리처드 탈러, 캐스 선스타인"},
        {"title": "역사의 쓸모", "author": "최태성"},
        {"title": "21세기 자본", "author": "토마 피케티"},
        {"title": "정치의 심리학", "author": "드루 웨스턴"},
    ],
    "소설": [
        {"title": "나미야 잡화점의 기적", "author": "히가시노 게이고"},
        {"title": "불편한 편의점", "author": "김호연"},
        {"title": "1984", "author": "조지 오웰"},
        {"title": "달러구트 꿈 백화점", "author": "이미예"},
        {"title": "데미안", "author": "헤르만 헤세"},
    ],
}

# =====================================================
# Session State init
# =====================================================
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "result" not in st.session_state:
    st.session_state.result = None

for i in range(7):
    key = f"q{i+1}"
    if key not in st.session_state:
        st.session_state[key] = None


def reset_test():
    for i in range(7):
        st.session_state[f"q{i+1}"] = None
    st.session_state.submitted = False
    st.session_state.result = None


# =====================================================
# Helpers: scoring
# =====================================================
def letter_of(answer: str) -> str:
    return answer.strip()[0]


def compute_genre_scores(answers):
    scores = {g: 0 for g in genre_map.values()}
    for ans in answers:
        scores[genre_map[letter_of(ans)]] += 1
    return scores


def compute_situation_scores(answers):
    """
    Q5~Q7만 상황 태그 점수화.
    answers 인덱스: 0~6 (Q1~Q7)
    """
    tags = {"위로": 0, "휴식": 0, "동기": 0, "탐구": 0}
    for qno in [5, 6, 7]:
        ans = answers[qno - 1]
        letter = letter_of(ans)
        for t in situation_tag_map_q5_to_q7[qno].get(letter, []):
            tags[t] += 1
    return tags


def get_ranked(scores: dict):
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def top_keys(scores: dict):
    ranked = get_ranked(scores)
    max_score = ranked[0][1]
    top = [k for k, v in ranked if v == max_score]
    # second tier
    second_score = None
    for k, v in ranked:
        if v < max_score:
            second_score = v
            break
    second = [k for k, v in ranked if second_score is not None and v == second_score]
    return top, second, ranked


# =====================================================
# Recommend 3 books: (demo) mix by top genre(s)
# =====================================================
def pick_3_books(primary_genres, secondary_genres):
    """
    - 1등 동점(복합): 1등 장르들에서 섞어서 3권
    - 단일 1등 + 2등 존재: 1등 2권 + 2등 1권
    - 단일 1등: 3권
    """
    books = []

    if len(primary_genres) >= 2:
        pool = []
        for g in primary_genres:
            pool += [{"genre": g, **b} for b in fallback_pool[g]]
        random.shuffle(pool)
        seen = set()
        for item in pool:
            if item["title"] in seen:
                continue
            books.append(item)
            seen.add(item["title"])
            if len(books) == 3:
                break
        return books

    primary = primary_genres[0]
    if secondary_genres:
        secondary = secondary_genres[0]
        p = random.sample(fallback_pool[primary], k=min(2, len(fallback_pool[primary])))
        s = random.sample(fallback_pool[secondary], k=1)
        books = [{"genre": primary, **b} for b in p] + [{"genre": secondary, **b} for b in s]
        random.shuffle(books)
        return books[:3]

    return [{"genre": primary, **b} for b in random.sample(fallback_pool[primary], k=3)]


# =====================================================
# Evidence-based 이유 생성 (성향 + 상황 반영)
# =====================================================
def evidence_by_genre(answers, target_genre, max_evidence=2):
    target_letter = None
    for letter, g in genre_map.items():
        if g == target_genre:
            target_letter = letter
            break

    matched = [a for a in answers if letter_of(a) == target_letter]
    cleaned = [m[3:].strip() if len(m) > 3 else m.strip() for m in matched]
    random.shuffle(cleaned)
    return cleaned[:max_evidence]


def evidence_by_situation(answers, top_situation_tags, max_evidence=2):
    """
    top_situation_tags: 예) ["휴식"] 또는 ["위로","휴식"]
    Q5~Q7 답변에서 해당 상황 태그를 만들어낸 문항만 근거로 뽑음
    """
    evidences = []
    for qno in [5, 6, 7]:
        ans = answers[qno - 1]
        letter = letter_of(ans)
        tags = situation_tag_map_q5_to_q7[qno].get(letter, [])
        if any(t in top_situation_tags for t in tags):
            evidences.append(ans[3:].strip() if len(ans) > 3 else ans.strip())

    # 중복/길이 방지
    random.shuffle(evidences)
    return evidences[:max_evidence]


def build_reason(answers, book_title, book_genre, top_situation_tags):
    """
    - 장르 근거 1~2개 + 상황 근거 1개를 조합해 개인화 문장 생성
    """
    genre_ev = evidence_by_genre(answers, book_genre, max_evidence=2)
    situa_ev = evidence_by_situation(answers, top_situation_tags, max_evidence=1)

    persona = genre_persona.get(book_genre, "")
    point = genre_book_point.get(book_genre, "")

    situa_phrase = ", ".join([tag_display.get(t, t) for t in top_situation_tags])

    parts = []

    if situa_ev:
        parts.append(f"당신은 최근 “{situa_ev[0]}”라고 답해 **{situa_phrase}**가 필요한 상태로 보여요.")
    else:
        parts.append(f"지금은 **{situa_phrase}**에 도움이 되는 책이 잘 맞는 시점이에요.")

    if genre_ev:
        if len(genre_ev) >= 2:
            parts.append(f"또 “{genre_ev[0]}”, “{genre_ev[1]}”를 고른 걸 보면 {persona} 성향도 강해요.")
        else:
            parts.append(f"또 “{genre_ev[0]}”를 선택한 걸 보면 {persona} 성향도 강해요.")
    else:
        parts.append(f"{persona} 성향을 바탕으로 책을 골랐어요.")

    parts.append(f"그래서 {point}를 주는 **{book_title}**을(를) 추천합니다.")
    return " ".join(parts)


# =====================================================
# OpenAI: optional book candidate generation
#  - 이유는 우리가 (설문 근거 기반) 생성
# =====================================================
@st.cache_data(show_spinner=False)
def call_openai_json(api_key: str, model: str, system: str, user: str) -> dict:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])


def ai_pick_books(answers, focus_genres):
    system = (
        "너는 한국어 독서 큐레이터다. 사용자의 설문 응답(성향+상황)을 바탕으로 "
        "실제로 존재하는 책 3권을 추천하되, 아래 JSON 형식으로만 응답하라.\n\n"
        "{\n"
        '  "recommendations": [\n'
        '    {"title":"도서명", "author":"저자(모르면 빈 문자열)", "genre":"자기계발|인문/철학|과학/IT|역사/사회|소설"}\n'
        "  ]\n"
        "}\n\n"
        "규칙:\n"
        "- focus_genres에 최대한 맞춰 추천\n"
        "- 대학생이 읽기 무난한 난이도 우선\n"
        "- 도서명은 실제 존재 책\n"
        "- genre는 반드시 5개 중 하나\n"
    )
    user = (
        f"focus_genres: {focus_genres}\n"
        "사용자 답변(원문):\n"
        + "\n".join([f"- {a}" for a in answers])
        + "\n\n"
        "추천 JSON을 만들어줘."
    )
    obj = call_openai_json(openai_api_key, openai_model, system, user)
    recs = obj.get("recommendations", [])[:3]

    cleaned = []
    for r in recs:
        title = str(r.get("title", "")).strip()
        author = str(r.get("author", "")).strip()
        genre = str(r.get("genre", "")).strip()
        if genre not in genre_map.values():
            genre = focus_genres[0]
        if title:
            cleaned.append({"title": title, "author": author, "genre": genre})

    return cleaned[:3]


# =====================================================
# National Library (ISBN 서지정보) API helpers
# =====================================================
@st.cache_data(show_spinner=False)
def nl_isbn_search(cert_key: str, title: str, author: str = "", page_size: int = 10):
    url = "https://www.nl.go.kr/seoji/SearchApi.do"
    params = {
        "cert_key": cert_key,
        "result_style": "json",
        "page_no": 1,
        "page_size": page_size,
        "title": title,
    }
    if author:
        params["author"] = author

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return json.loads(r.text)


def pick_best_item(nl_json, wanted_title: str):
    items = None
    if isinstance(nl_json, dict):
        for k in ["docs", "data", "items", "result"]:
            if k in nl_json and isinstance(nl_json[k], list):
                items = nl_json[k]
                break
        if items is None:
            for v in nl_json.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    items = v
                    break

    if not items:
        return None

    wt = wanted_title.replace(" ", "").lower()

    def score(item):
        t = str(item.get("TITLE", "") or item.get("title", "")).replace(" ", "").lower()
        if not t:
            return 0
        if t == wt:
            return 100
        if wt in t or t in wt:
            return 60
        return 10 if t[:5] == wt[:5] else 1

    return sorted(items, key=score, reverse=True)[0]


def fetch_text_from_url(url: str, max_chars: int = 700):
    if not url:
        return ""
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        text = r.text

        text = re.sub(r"<script.*?>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "…"
        return text
    except Exception:
        return ""


# =====================================================
# UI: Questionnaire
# =====================================================
st.divider()
st.subheader("📝 질문에 답해주세요")

for i, q in enumerate(questions):
    st.markdown(f"**{q}**")
    st.radio(
        label=f"q{i+1}",
        options=question_choices[i],
        key=f"q{i+1}",
        index=None,
        label_visibility="collapsed",
    )
    st.write("")

st.divider()

c1, c2 = st.columns(2)
with c1:
    clicked = st.button("결과 보기", type="primary")
with c2:
    st.button("다시 테스트하기", on_click=reset_test)

# =====================================================
# Flow: analyze -> recommend -> (optionally) fetch real book info
# =====================================================
if clicked:
    answers = [st.session_state[f"q{i+1}"] for i in range(7)]
    if any(a is None for a in answers):
        missing = [str(i + 1) for i, a in enumerate(answers) if a is None]
        st.warning(f"모든 질문에 답변해 주세요! (미응답: {', '.join(missing)}번)")
    else:
        with st.spinner("분석 중..."):
            # 1) 성향(장르) 점수
            genre_scores = compute_genre_scores(answers)
            top_genres, second_genres, genre_ranked = top_keys(genre_scores)

            # 2) 상황 태그 점수
            situation_scores = compute_situation_scores(answers)
            top_situations, second_situations, situation_ranked = top_keys(situation_scores)

            # focus genres for AI or mixing
            focus_genres = (top_genres[:2] if len(top_genres) >= 2 else top_genres + second_genres[:1]) or top_genres

            # 3) 책 후보 3권 생성
            if openai_api_key:
                candidates = ai_pick_books(answers, focus_genres=focus_genres)
                # 혹시 부족하면 데모로 보충
                if len(candidates) < 3:
                    fill = pick_3_books(top_genres, second_genres)
                    for f in fill:
                        if len(candidates) >= 3:
                            break
                        candidates.append({"title": f["title"], "author": f.get("author", ""), "genre": f["genre"]})
            else:
                fill = pick_3_books(top_genres, second_genres)
                candidates = [{"title": b["title"], "author": b.get("author", ""), "genre": b["genre"]} for b in fill]

            # 4) 개인화 추천 이유(설문 근거 + 상황 태그 기반) 생성
            enriched = []
            for c in candidates[:3]:
                why = build_reason(answers, c["title"], c["genre"], top_situations)
                enriched.append({**c, "why": why})

            # 5) 국립중앙도서관 API로 실제 도서 정보 조회(가능할 때만)
            books_final = []
            can_fetch_nl = bool(nl_api_key)

            if can_fetch_nl:
                for c in enriched:
                    title = c["title"]
                    author = c.get("author", "")

                    nl_json = nl_isbn_search(nl_api_key, title=title, author=author, page_size=10)
                    item = pick_best_item(nl_json, wanted_title=title)

                    if not item:
                        books_final.append(
                            {
                                **c,
                                "isbn": "",
                                "cover_url": "",
                                "summary": "",
                                "note": "국립중앙도서관에서 일치하는 도서를 찾지 못했어요.",
                            }
                        )
                        continue

                    picked_title = item.get("TITLE") or item.get("title") or title
                    picked_author = item.get("AUTHOR") or item.get("author") or author
                    isbn = item.get("EA_ISBN") or item.get("ISBN") or item.get("isbn") or ""

                    cover_url = item.get("TITLE_URL") or item.get("cover") or item.get("image") or ""
                    intro_url = item.get("BOOK_INTRODUCTION_URL") or ""
                    summary_url = item.get("BOOK_SUMMARY_URL") or ""

                    summary_text = fetch_text_from_url(summary_url)
                    if not summary_text:
                        summary_text = fetch_text_from_url(intro_url)

                    books_final.append(
                        {
                            **c,
                            "title": str(picked_title).strip(),
                            "author": str(picked_author).strip(),
                            "isbn": str(isbn).strip(),
                            "cover_url": str(cover_url).strip(),
                            "summary": summary_text.strip(),
                            "note": "",
                        }
                    )
            else:
                # 데모 모드가 켜져 있으면 결과는 보여주되, 표지/소개는 비움
                if demo_mode:
                    for c in enriched:
                        books_final.append({**c, "isbn": "", "cover_url": "", "summary": "", "note": ""})
                else:
                    # 데모 모드 OFF + 키 없음 => 결과를 만들지 않고 안내만
                    st.error("국립중앙도서관 API 키(cert_key)가 필요합니다. 사이드바에 입력해 주세요.")
                    st.stop()

            st.session_state.submitted = True
            st.session_state.result = {
                "genre_scores": genre_scores,
                "genre_top": top_genres,
                "genre_second": second_genres,
                "genre_ranked": genre_ranked,
                "situation_scores": situation_scores,
                "situation_top": top_situations,
                "situation_second": second_situations,
                "situation_ranked": situation_ranked,
                "focus_genres": focus_genres,
                "used_openai": bool(openai_api_key),
                "used_nl": can_fetch_nl,
                "books": books_final,
                "answers": answers,
            }


# =====================================================
# Render result
# =====================================================
if st.session_state.submitted and st.session_state.result:
    r = st.session_state.result

    st.subheader("📌 분석 결과")

    # 성향(장르)
    if len(r["genre_top"]) >= 2:
        st.success(f"당신의 **독서 성향(복합)**: {', '.join(r['genre_top'])}")
    else:
        st.success(f"당신의 **독서 성향**: {r['genre_top'][0]}")

    # 상황(태그)
    top_sit = r["situation_top"]
    sit_text = ", ".join([tag_display.get(t, t) for t in top_sit])
    st.info(f"현재 당신에게 가장 필요한 것: **{sit_text}**")

    # 점수 표시(간단)
    st.caption("장르 점수: " + ", ".join([f"{k} {v}" for k, v in r["genre_scores"].items()]))
    st.caption("상황 점수: " + ", ".join([f"{tag_display.get(k,k)} {v}" for k, v in r["situation_scores"].items()]))

    if not r["used_openai"]:
        st.info("OpenAI 키가 없어 **데모 추천 목록**으로 도서를 골랐습니다. (추천 이유는 설문 답변 근거 기반)")
    if not r["used_nl"]:
        st.warning("국립중앙도서관 API 키가 없어 **표지/ISBN/줄거리**는 표시되지 않습니다. (데모 모드)")

    st.subheader("📚 추천 도서 3권")
    for idx, b in enumerate(r["books"], start=1):
        st.markdown(f"### {idx}. {b['title']}")
        meta = []
        if b.get("author"):
            meta.append(f"저자: {b['author']}")
        if b.get("isbn"):
            meta.append(f"ISBN: {b['isbn']}")
        if meta:
            st.caption(" · ".join(meta))

        cols = st.columns([1, 2])
        with cols[0]:
            if b.get("cover_url"):
                st.image(b["cover_url"], use_container_width=True)
            else:
                st.info("표지 이미지 없음(데모/검색 실패)")

        with cols[1]:
            st.write("**이 책을 추천하는 이유(설문 근거 + 상황 기반)**")
            st.write(f"- {b.get('why','')}")

            st.write("**줄거리/책소개**")
            if b.get("summary"):
                st.write(b["summary"])
            else:
                st.info("줄거리/책소개 정보를 아직 가져오지 못했어요. (API 키 필요 또는 제공 URL 없음)")

            if b.get("note"):
                st.warning(b["note"])

        st.divider()
