import json
import random
import re
from html import unescape

import requests
import streamlit as st

st.set_page_config(page_title="나와 어울리는 책은?", page_icon="📚", layout="centered")

# =========================
# 사이드바: API Key 입력
# =========================
st.sidebar.header("🔑 API 설정")

nl_api_key = st.sidebar.text_input(
    "국립중앙도서관(ISBN 서지정보) API Key (cert_key)",
    type="password",
    help="국립중앙도서관 ISBN 서지정보 API cert_key 값을 입력하세요.",
)

openai_api_key = st.sidebar.text_input(
    "OpenAI API Key (선택)",
    type="password",
    help="AI 추천을 실제로 돌리려면 OpenAI API Key가 필요해요. 없으면 '규칙 기반(대체)' 추천이 동작합니다.",
)

openai_model = st.sidebar.text_input("OpenAI 모델", value="gpt-4o-mini")


# =========================
# 질문 데이터
# =========================
st.title("📚 나와 어울리는 책은?")
st.write(
    "7문항 심리테스트 결과를 바탕으로 AI가 당신의 성향을 분석하고, "
    "국립중앙도서관 API로 실제 도서 정보를 찾아 **표지/ISBN/줄거리**까지 보여드릴게요."
)

questions = [
    "1) 새로운 주제를 배울 때 내가 가장 흥미를 느끼는 방식은?",
    "2) 시간이 생겼을 때 내가 가장 자주 선택하는 활동은?",
    "3) 친구가 “요즘 좀 힘들다”고 말하면 나는 보통…",
    "4) 내가 책을 읽는 가장 큰 목적은?",
    "5) 다음 중 가장 끌리는 콘텐츠는?",
    "6) 어떤 책이 “좋은 책”이라고 느껴지는가?",
    "7) 내가 가장 궁금해하는 질문은 어떤 유형인가?",
]

question_choices = [
    [
        "A. 실생활에 적용할 수 있는 방법을 찾는다",
        "B. 그 주제가 삶에 어떤 의미가 있는지 생각한다",
        "C. 원리나 구조를 분석하며 이해한다",
        "D. 사회나 시대적 배경 속에서 바라본다",
        "E. 이야기나 사례를 통해 자연스럽게 몰입한다",
    ],
    [
        "A. 목표를 세우거나 자기관리 루틴을 만든다",
        "B. 깊이 있는 질문을 던지는 글을 읽는다",
        "C. 새로운 기술이나 최신 정보를 찾아본다",
        "D. 사회 이슈나 역사적 사건을 탐구한다",
        "E. 재미있는 스토리 콘텐츠를 즐긴다",
    ],
    [
        "A. 현실적인 해결책과 조언을 정리해준다",
        "B. 감정과 상황의 의미를 함께 고민한다",
        "C. 문제의 원인을 논리적으로 분석한다",
        "D. 비슷한 사회적 사례나 배경을 떠올린다",
        "E. 공감하며 이야기를 들어주는 편이다",
    ],
    [
        "A. 성장하거나 더 나은 사람이 되기 위해",
        "B. 인간과 삶을 깊이 이해하기 위해",
        "C. 새로운 지식과 정보를 얻기 위해",
        "D. 세상과 사회 구조를 이해하기 위해",
        "E. 다른 세계를 경험하고 몰입하기 위해",
    ],
    [
        "A. 성공 습관, 생산성, 동기부여 콘텐츠",
        "B. 철학적 질문이나 인문학적 에세이",
        "C. 과학·기술·미래를 다루는 영상이나 글",
        "D. 사회 문제나 역사적 흐름을 다룬 다큐",
        "E. 감정선이 강한 드라마나 소설 이야기",
    ],
    [
        "A. 읽고 나서 행동이 바뀌는 책",
        "B. 사고의 폭이 넓어지는 책",
        "C. 새로운 사실을 배우게 되는 책",
        "D. 세상을 바라보는 시야가 넓어지는 책",
        "E. 재미있고 몰입감이 뛰어난 책",
    ],
    [
        "A. “어떻게 하면 더 나은 삶을 살 수 있을까?”",
        "B. “인간은 왜 이런 선택을 할까?”",
        "C. “미래에는 어떤 기술이 세상을 바꿀까?”",
        "D. “사회는 왜 이렇게 변화해왔을까?”",
        "E. “만약 다른 삶을 산다면 어떤 이야기가 펼쳐질까?”",
    ],
]

genre_map = {
    "A": "자기계발",
    "B": "인문/철학",
    "C": "과학/IT",
    "D": "역사/사회",
    "E": "소설",
}


# =========================
# session_state 초기화
# =========================
if "submitted" not in st.session_state:
    st.session_state.submitted = False

for i in range(7):
    k = f"q{i+1}"
    if k not in st.session_state:
        st.session_state[k] = None


def reset_test():
    for i in range(7):
        st.session_state[f"q{i+1}"] = None
    st.session_state.submitted = False


# =========================
# 점수 계산 / 장르 결정
# =========================
def compute_scores(answers):
    scores = {g: 0 for g in genre_map.values()}
    for ans in answers:
        letter = ans[0]  # "A. ..."
        scores[genre_map[letter]] += 1
    return scores


def pick_top_genre(scores):
    # 1등 장르(동점이면 랜덤으로 하나 선택)
    max_score = max(scores.values())
    top = [g for g, s in scores.items() if s == max_score]
    return random.choice(top), top


# =========================
# AI 추천: OpenAI (없으면 규칙 기반 대체)
# =========================
@st.cache_data(show_spinner=False)
def call_openai_chat(api_key: str, model: str, system: str, user: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]


def safe_parse_json_object(text: str):
    """
    OpenAI가 json_object로 주면 보통 바로 파싱되지만,
    혹시 섞여 나오는 경우를 대비해 JSON 블록만 추출 시도.
    """
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not m:
            raise ValueError("JSON을 찾지 못했습니다.")
        return json.loads(m.group(0))


def recommend_by_ai_or_fallback(answers, top_genre, openai_api_key, openai_model):
    """
    반환: [{"title":..., "author":..., "why":...}, ...] 3개
    """
    # 1) OpenAI 키가 있으면: AI 추천
    if openai_api_key:
        system = (
            "너는 독서 큐레이터야. 사용자의 심리테스트 응답과 장르 성향을 바탕으로 "
            "한국어로 책 3권을 추천해. "
            "반드시 아래 JSON 형식으로만 답해.\n\n"
            "{\n"
            '  "recommendations": [\n'
            '    {"title": "도서명", "author": "저자(모르면 빈 문자열)", "why": "추천 이유 한줄(20~40자)"}\n'
            "  ]\n"
            "}\n\n"
            "주의:\n"
            "- 실제 존재하는 한국/번역 도서로 추천\n"
            "- 장르 성향(top_genre)에 맞추되, 대학생에게 무난한 난이도/흥미를 우선\n"
            "- why는 간단하고 구체적으로\n"
        )

        user = (
            f"top_genre: {top_genre}\n"
            "아래는 사용자의 7개 답변이야(원문 그대로):\n"
            + "\n".join([f"- {a}" for a in answers])
            + "\n\n"
            "위 정보를 바탕으로 추천 JSON을 만들어줘."
        )

        content = call_openai_chat(openai_api_key, openai_model, system, user)
        obj = safe_parse_json_object(content)
        recs = obj.get("recommendations", [])
        # 형태 보정
        cleaned = []
        for r in recs[:3]:
            cleaned.append(
                {
                    "title": str(r.get("title", "")).strip(),
                    "author": str(r.get("author", "")).strip(),
                    "why": str(r.get("why", "")).strip(),
                }
            )
        # 혹시 3개 미만이면 fallback로 채움
        if len(cleaned) < 3:
            cleaned += fallback_recommendations(top_genre)[: (3 - len(cleaned))]
        return cleaned[:3]

    # 2) OpenAI 키가 없으면: 규칙 기반 대체 추천
    return fallback_recommendations(top_genre)[:3]


def fallback_recommendations(top_genre):
    pool = {
        "자기계발": [
            {"title": "아주 작은 습관의 힘", "author": "제임스 클리어", "why": "루틴·실천 성향에 잘 맞아요."},
            {"title": "그릿", "author": "앤절라 더크워스", "why": "목표 지향 성향을 강화해줘요."},
            {"title": "딥 워크", "author": "칼 뉴포트", "why": "집중·성과 중심 사고에 어울려요."},
            {"title": "원씽", "author": "게리 켈러", "why": "우선순위 정리에 강점을 줘요."},
        ],
        "인문/철학": [
            {"title": "정의란 무엇인가", "author": "마이클 샌델", "why": "가치·판단을 깊게 확장해줘요."},
            {"title": "소크라테스 익스프레스", "author": "에릭 와이너", "why": "질문하는 사고를 키워줘요."},
            {"title": "죽음의 수용소에서", "author": "빅터 프랭클", "why": "삶의 의미 탐색에 도움돼요."},
            {"title": "철학은 어떻게 삶의 무기가 되는가", "author": "야마구치 슈", "why": "현실 고민을 철학으로 풀어요."},
        ],
        "과학/IT": [
            {"title": "코스모스", "author": "칼 세이건", "why": "원리·호기심 중심 성향에 좋아요."},
            {"title": "클린 코드", "author": "로버트 C. 마틴", "why": "논리·구조를 중시한다면 추천!"},  # 이유는 짧게
            {"title": "팩트풀니스", "author": "한스 로슬링", "why": "데이터 기반 사고에 잘 맞아요."},
            {"title": "AI 2041", "author": "카이푸 리, 천치우판", "why": "기술의 미래를 흥미롭게 보여줘요."},
        ],
        "역사/사회": [
            {"title": "총, 균, 쇠", "author": "재레드 다이아몬드", "why": "사회 구조를 큰 흐름으로 이해해요."},
            {"title": "넛지", "author": "리처드 탈러, 캐스 선스타인", "why": "사람·사회 선택을 설계로 설명해요."},
            {"title": "역사의 쓸모", "author": "최태성", "why": "역사 관점으로 현재를 읽게 해줘요."},
            {"title": "21세기 자본", "author": "토마 피케티", "why": "불평등·경제 구조에 관심이면 딱!"},  # 이유는 짧게
        ],
        "소설": [
            {"title": "나미야 잡화점의 기적", "author": "히가시노 게이고", "why": "따뜻한 몰입형 이야기 선호에 좋아요."},
            {"title": "불편한 편의점", "author": "김호연", "why": "현실 공감과 서사가 균형 좋아요."},
            {"title": "1984", "author": "조지 오웰", "why": "강한 서사로 사회를 비추는 소설이에요."},
            {"title": "데미안", "author": "헤르만 헤세", "why": "자기 탐색·성장 서사를 원하면 추천!"},  # 이유는 짧게
        ],
    }
    recs = pool.get(top_genre, [])
    random.shuffle(recs)
    return recs


# =========================
# 국립중앙도서관(ISBN 서지정보) 검색
# =========================
@st.cache_data(show_spinner=False)
def nl_isbn_search(cert_key: str, title: str, author: str = "", page_size: int = 10):
    """
    국립중앙도서관 ISBN 서지정보 SearchApi.do (result_style=json)
    - title, author로 조회 (둘 다 가능)
    """
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

    # 응답이 JSON 문자열일 수도 있어서 방어적으로 처리
    try:
        data = r.json()
    except Exception:
        data = json.loads(r.text)

    return data


def pick_best_item(nl_json, wanted_title: str):
    """
    API 응답에서 가장 그럴듯한 1건 선택:
    - 제목이 포함/유사한 것을 우선
    - 없으면 첫 번째
    """
    items = None

    # 응답 구조가 환경/버전에 따라 달라질 수 있어 여러 케이스 대응
    # 흔한 케이스: {"TOTAL_COUNT": "...", "docs": [ ... ]} 혹은 {"data": [ ... ]} 등
    if isinstance(nl_json, dict):
        for k in ["docs", "data", "items", "result", "book"]:
            if k in nl_json and isinstance(nl_json[k], list):
                items = nl_json[k]
                break

        # docs가 바로 없으면, value가 list인 첫 항목을 찾기
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
        # 약한 유사도: 앞 5글자 일치
        return 10 if t[:5] == wt[:5] else 1

    items_sorted = sorted(items, key=score, reverse=True)
    return items_sorted[0]


def fetch_text_from_url(url: str, max_chars: int = 600):
    """
    BOOK_INTRODUCTION_URL / BOOK_SUMMARY_URL 등 URL 내용을 간단히 텍스트로 가져오기.
    (페이지 형식이 HTML일 가능성이 높아 태그 제거를 간단히 수행)
    """
    if not url:
        return ""

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        text = r.text

        # 아주 단순한 HTML 태그 제거(완벽하진 않지만 데모용으로 충분)
        text = re.sub(r"<script.*?>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) > max_chars:
            text = text[: max_chars].rstrip() + "…"
        return text
    except Exception:
        return ""


# =========================
# UI: 질문
# =========================
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

# =========================
# 결과 보기 클릭 처리
# =========================
if clicked:
    answers = [st.session_state[f"q{i+1}"] for i in range(7)]

    if any(a is None for a in answers):
        st.warning("모든 질문에 답변해 주세요!")
    else:
        if not nl_api_key:
            st.error("국립중앙도서관 API Key(cert_key)를 사이드바에 입력해 주세요.")
        else:
            st.session_state.submitted = True

            with st.spinner("분석 중..."):
                scores = compute_scores(answers)
                top_genre, top_candidates = pick_top_genre(scores)

                # 1) AI에게 추천받기(또는 fallback)
                ai_recs = recommend_by_ai_or_fallback(
                    answers=answers,
                    top_genre=top_genre,
                    openai_api_key=openai_api_key,
                    openai_model=openai_model,
                )

                # 2) 국립중앙도서관 API로 실제 도서 정보 가져오기
                final_books = []
                for rec in ai_recs:
                    title = rec["title"]
                    author = rec.get("author", "")

                    nl_json = nl_isbn_search(nl_api_key, title=title, author=author, page_size=10)
                    item = pick_best_item(nl_json, wanted_title=title)

                    if not item:
                        final_books.append(
                            {
                                "title": title,
                                "author": author,
                                "isbn": "",
                                "cover_url": "",
                                "summary": "",
                                "why": rec.get("why", ""),
                                "note": "국립중앙도서관에서 일치하는 도서를 찾지 못했어요.",
                            }
                        )
                        continue

                    # ISBN 서지정보 API 응답 필드(문서 기준)
                    # - TITLE, AUTHOR, EA_ISBN, TITLE_URL, BOOK_SUMMARY_URL, BOOK_INTRODUCTION_URL 등
                    picked_title = item.get("TITLE") or item.get("title") or title
                    picked_author = item.get("AUTHOR") or item.get("author") or author
                    isbn = item.get("EA_ISBN") or item.get("isbn") or item.get("ISBN") or ""

                    cover_url = item.get("TITLE_URL") or item.get("cover") or item.get("image") or ""
                    intro_url = item.get("BOOK_INTRODUCTION_URL") or ""
                    summary_url = item.get("BOOK_SUMMARY_URL") or ""

                    # 줄거리/책소개 텍스트 가져오기(가능한 쪽 먼저)
                    summary_text = fetch_text_from_url(summary_url)
                    if not summary_text:
                        summary_text = fetch_text_from_url(intro_url)

                    final_books.append(
                        {
                            "title": str(picked_title).strip(),
                            "author": str(picked_author).strip(),
                            "isbn": str(isbn).strip(),
                            "cover_url": str(cover_url).strip(),
                            "summary": summary_text.strip(),
                            "why": rec.get("why", "").strip(),
                            "note": "",
                        }
                    )

                st.session_state["result"] = {
                    "scores": scores,
                    "top_genre": top_genre,
                    "top_candidates": top_candidates,
                    "books": final_books,
                }

# =========================
# 결과 출력
# =========================
if st.session_state.get("submitted") and st.session_state.get("result"):
    result = st.session_state["result"]

    st.subheader("📌 분석 결과")
    st.write(f"**가장 잘 맞는 장르:** {result['top_genre']}")
    st.caption(f"점수: " + ", ".join([f"{k} {v}" for k, v in result["scores"].items()]))

    st.subheader("📚 추천 도서 3권 (실제 도서 정보)")
    for idx, b in enumerate(result["books"], start=1):
        st.markdown(f"### {idx}. {b['title']}")
        meta = []
        if b["author"]:
            meta.append(f"저자: {b['author']}")
        if b["isbn"]:
            meta.append(f"ISBN: {b['isbn']}")
        if meta:
            st.caption(" · ".join(meta))

        cols = st.columns([1, 2])
        with cols[0]:
            if b["cover_url"]:
                st.image(b["cover_url"], use_container_width=True)
            else:
                st.info("표지 이미지 없음")

        with cols[1]:
            if b["summary"]:
                st.write("**줄거리/책소개**")
                st.write(b["summary"])
            else:
                st.write("**줄거리/책소개**")
                st.info("줄거리/책소개 정보를 가져오지 못했어요.")

            if b["why"]:
                st.write("**이 책을 추천하는 이유**")
                st.write(f"- {b['why']}")
            else:
                st.write("**이 책을 추천하는 이유**")
                st.write("- (추천 이유 생성 실패)")

            if b["note"]:
                st.warning(b["note"])

        st.divider()
