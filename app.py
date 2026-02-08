import json
import random
import re
from html import unescape

import requests
import streamlit as st

st.set_page_config(page_title="나와 어울리는 책은?", page_icon="📚", layout="centered")


# =====================================================
# Sidebar: API Keys
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
    help="AI가 '책 후보(도서명)'를 더 다양하게 고르도록 하려면 필요합니다. 없으면 데모 추천 목록으로 동작합니다.",
)
openai_model = st.sidebar.text_input("OpenAI 모델", value="gpt-4o-mini")

demo_mode = st.sidebar.checkbox(
    "데모 모드(국립중앙도서관 API 없이도 결과 보기)",
    value=True,
    help="API Key가 없어도 장르 분석 + 추천 3권 + 개인화 이유를 확인할 수 있습니다.",
)


# =====================================================
# Questions
# =====================================================
st.title("📚 나와 어울리는 책은?")
st.write(
    "7문항 심리테스트 결과를 바탕으로 **장르 성향**을 분석하고, "
    "추천 도서 3권과 **설문 답변에 근거한 개인화 추천 이유**를 보여드립니다.\n\n"
    "- 국립중앙도서관 API 키가 있으면: 표지/ISBN/소개까지 실제 데이터로 표시\n"
    "- 없으면(데모 모드): 추천/이유만 먼저 확인 가능"
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

genre_map = {"A": "자기계발", "B": "인문/철학", "C": "과학/IT", "D": "역사/사회", "E": "소설"}

genre_persona = {
    "자기계발": "실행·루틴·성과를 중시하는 성장형",
    "인문/철학": "의미·가치·자기이해를 깊게 파고드는 성찰형",
    "과학/IT": "원리·구조·정보를 분석하는 탐구형",
    "역사/사회": "사회 구조·맥락·흐름을 이해하려는 관찰형",
    "소설": "감정·분위기·서사 몰입을 통해 회복하는 감성형",
}

genre_book_point = {
    "자기계발": "바로 적용 가능한 습관·행동 변화 포인트",
    "인문/철학": "생각의 폭을 넓히는 질문과 통찰",
    "과학/IT": "원리·구조를 명확하게 이해시키는 설명",
    "역사/사회": "사회·역사의 큰 흐름을 읽게 해주는 관점",
    "소설": "감정선에 몰입하며 위로와 여운을 주는 서사",
}


# =====================================================
# Demo fallback pool (when OpenAI key 없음)
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
# Session state init
# =====================================================
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "result" not in st.session_state:
    st.session_state.result = None

for i in range(7):
    k = f"q{i+1}"
    if k not in st.session_state:
        st.session_state[k] = None


def reset_test():
    for i in range(7):
        st.session_state[f"q{i+1}"] = None
    st.session_state.submitted = False
    st.session_state.result = None


# =====================================================
# Scoring / genre decision
# =====================================================
def compute_scores(answers):
    scores = {g: 0 for g in genre_map.values()}
    for ans in answers:
        letter = ans.strip()[0]
        scores[genre_map[letter]] += 1
    return scores


def get_top_genres(scores):
    # 내림차순 정렬, 동점 포함
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    max_score = sorted_items[0][1]
    top = [g for g, s in sorted_items if s == max_score]
    # 2등도 함께 반환(복합 성향 추천용)
    second_score = None
    for g, s in sorted_items:
        if s < max_score:
            second_score = s
            break
    second = [g for g, s in sorted_items if second_score is not None and s == second_score]
    return top, second, sorted_items


def pick_3_books_for_profile(primary_genres, secondary_genres):
    """
    - 1등 단일: 해당 장르에서 3권
    - 1등 동점(복합): 1등들에서 섞어서 3권 (균등 분배)
    - 2등이 있으면: (1등 2권 + 2등 1권) 형태도 가능
    """
    books = []

    # 복합(동점)일 때: 1등 장르들에서 섞기
    if len(primary_genres) >= 2:
        pool = []
        for g in primary_genres:
            pool += [{"genre": g, **b} for b in fallback_pool[g]]
        random.shuffle(pool)
        # 중복 제목 방지
        seen = set()
        for item in pool:
            if item["title"] in seen:
                continue
            books.append(item)
            seen.add(item["title"])
            if len(books) == 3:
                break
        return books

    # 단일 1등 + 2등 존재: 1등 2권 + 2등 1권(체감 좋음)
    primary = primary_genres[0]
    if secondary_genres:
        secondary = secondary_genres[0]
        p = random.sample(fallback_pool[primary], k=min(2, len(fallback_pool[primary])))
        s = random.sample(fallback_pool[secondary], k=1)
        books = [{"genre": primary, **b} for b in p] + [{"genre": secondary, **b} for b in s]
        random.shuffle(books)
        return books[:3]

    # 단일 1등: 3권
    books = [{"genre": primary, **b} for b in random.sample(fallback_pool[primary], k=3)]
    return books


# =====================================================
# Evidence-based personal reason
# =====================================================
def letter_of(answer: str) -> str:
    return answer.strip()[0]


def evidence_sentences(answers, target_genre, max_evidence=2):
    # target_genre -> target letter
    target_letter = None
    for letter, g in genre_map.items():
        if g == target_genre:
            target_letter = letter
            break

    matched = [a for a in answers if letter_of(a) == target_letter]
    # 사용자의 문장을 그대로 쓰면 신뢰도가 올라감
    if not matched:
        return []

    # 너무 길면 앞부분만 살짝 줄이기(‘A. ’ 제거)
    cleaned = [m[3:].strip() if len(m) > 3 else m.strip() for m in matched]

    # 다양성 위해 섞어서 2개 선택
    random.shuffle(cleaned)
    return cleaned[:max_evidence]


def build_personal_reason(answers, book_title, book_genre):
    ev = evidence_sentences(answers, book_genre, max_evidence=2)

    persona = genre_persona.get(book_genre, "")
    point = genre_book_point.get(book_genre, "")

    # 근거 1~2개를 문장에 자연스럽게 연결
    if len(ev) >= 2:
        reason = (
            f"당신은 설문에서 “{ev[0]}”, “{ev[1]}”를 선택했어요. "
            f"그래서 {persona}인 당신에게 {point}가 강한 **{book_title}**을(를) 추천합니다."
        )
    elif len(ev) == 1:
        reason = (
            f"당신은 설문에서 “{ev[0]}”를 선택했어요. "
            f"그래서 {persona}인 당신에게 {point}가 강한 **{book_title}**을(를) 추천합니다."
        )
    else:
        # 혹시 근거가 없으면(거의 없음) 일반 템플릿
        reason = (
            f"{persona} 성향을 바탕으로, {point}를 얻기 좋은 **{book_title}**을(를) 추천합니다."
        )

    return reason


# =====================================================
# OpenAI: get 3 book candidates (titles) by genre
# - NOTE: 이유는 우리가 '응답 근거 기반'으로 다시 생성해서 사용
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
    content = r.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def ai_pick_books(answers, primary_genres, secondary_genres):
    """
    OpenAI 키가 있을 때:
    - 장르/성향을 바탕으로 실제 존재 도서 3권 '제목/저자'만 추천 받음
    - 추천 이유는 반드시 설문 근거 기반으로 우리가 생성
    """
    # 우선 추천의 중심 장르(복합이면 두 개 정도 반영)
    focus = primary_genres[:2] if len(primary_genres) >= 2 else primary_genres + secondary_genres[:1]
    focus = [g for g in focus if g] or primary_genres

    system = (
        "너는 한국어 독서 큐레이터다. 사용자의 설문 응답과 성향 장르를 바탕으로 "
        "실제로 존재하는 책 3권을 추천하되, 아래 JSON 형식으로만 응답하라.\n\n"
        "{\n"
        '  "recommendations": [\n'
        '    {"title":"도서명", "author":"저자(모르면 빈 문자열)", "genre":"자기계발|인문/철학|과학/IT|역사/사회|소설"}\n'
        "  ]\n"
        "}\n\n"
        "규칙:\n"
        "- 가능한 한 focus 장르에 맞춰 추천\n"
        "- 대학생이 읽기 무난한 난이도 우선\n"
        "- 도서명은 실제 서점/도서관에 있는 책으로\n"
        "- genre는 반드시 5개 중 하나로\n"
    )

    user = (
        f"focus_genres: {focus}\n"
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
            # 장르 값이 이상하면 focus 첫 장르로 보정
            genre = focus[0]
        if title:
            cleaned.append({"title": title, "author": author, "genre": genre})

    # 혹시 3개 미만이면 fallback으로 채움
    if len(cleaned) < 3:
        fill = pick_3_books_for_profile(primary_genres, secondary_genres)
        for f in fill:
            if len(cleaned) >= 3:
                break
            cleaned.append({"title": f["title"], "author": f.get("author", ""), "genre": f["genre"]})

    return cleaned[:3]


# =====================================================
# National Library of Korea (ISBN 서지정보) API helpers
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
# Main flow: analyze -> recommend -> (optionally) fetch real book info
# =====================================================
if clicked:
    answers = [st.session_state[f"q{i+1}"] for i in range(7)]
    if any(a is None for a in answers):
        # 어떤 문항이 비었는지 알려주면 UX 좋음
        missing = [str(i + 1) for i, a in enumerate(answers) if a is None]
        st.warning(f"모든 질문에 답변해 주세요! (미응답: {', '.join(missing)}번)")
    else:
        with st.spinner("분석 중..."):
            scores = compute_scores(answers)
            top, second, sorted_items = get_top_genres(scores)

            # 추천 후보 3권 생성 (OpenAI 있으면 AI로 후보 고르고, 없으면 fallback)
            if openai_api_key:
                candidates = ai_pick_books(answers, top, second)
            else:
                candidates = pick_3_books_for_profile(top, second)
                # candidates 형태 통일
                candidates = [{"title": b["title"], "author": b.get("author", ""), "genre": b["genre"]} for b in candidates]

            # 각 책에 대해 "응답 근거 기반 개인화 이유" 생성
            enriched = []
            for c in candidates:
                why = build_personal_reason(answers, c["title"], c["genre"])
                enriched.append({**c, "why": why})

            # 국립중앙도서관 API 키가 있고(또는 데모 모드 OFF) 실제 정보 조회
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

                    # 문서에서 TITLE_URL이 표지로 쓰이는 경우가 많아 우선 사용
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
                # 데모: 추천/이유만 보여주고, 실제 서지정보는 비워둠
                for c in enriched:
                    books_final.append({**c, "isbn": "", "cover_url": "", "summary": "", "note": ""})

            st.session_state.submitted = True
            st.session_state.result = {
                "scores": scores,
                "top_genres": top,
                "second_genres": second,
                "sorted": sorted_items,
                "books": books_final,
                "used_openai": bool(openai_api_key),
                "used_nl": can_fetch_nl,
            }


# =====================================================
# Render result
# =====================================================
if st.session_state.submitted and st.session_state.result:
    r = st.session_state.result

    st.subheader("📌 분석 결과")
    if len(r["top_genres"]) >= 2:
        st.success(f"당신은 **복합 성향**이에요: {', '.join(r['top_genres'])}")
    else:
        st.success(f"당신의 주요 성향은 **{r['top_genres'][0]}** 입니다!")

    st.caption("점수: " + ", ".join([f"{k} {v}" for k, v in r["scores"].items()]))

    if not r["used_openai"]:
        st.info("현재는 OpenAI 키가 없어 **데모 추천 목록**으로 추천합니다. (추천 이유는 설문 답변 기반으로 개인화됩니다)")
    if not r["used_nl"]:
        if demo_mode:
            st.warning("국립중앙도서관 API 키가 없어 **표지/ISBN/줄거리**는 표시되지 않습니다. (데모 모드)")
        else:
            st.error("국립중앙도서관 API 키가 필요합니다. 사이드바에 입력해 주세요.")

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
            st.write("**이 책을 추천하는 이유(설문 근거 기반)**")
            st.write(f"- {b.get('why','')}")

            st.write("**줄거리/책소개**")
            if b.get("summary"):
                st.write(b["summary"])
            else:
                st.info("줄거리/책소개 정보를 아직 가져오지 못했어요. (API 키 필요 또는 제공 URL 없음)")

            if b.get("note"):
                st.warning(b["note"])

        st.divider()
