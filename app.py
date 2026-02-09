import json
import random
import re
import time
from html import unescape
from typing import Dict, List, Tuple, Optional

import requests
import streamlit as st
from requests.exceptions import ReadTimeout, ConnectionError, HTTPError, RequestException
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="나와 어울리는 책은?", page_icon="📚", layout="centered")

# =====================================================
# Sidebar
# =====================================================
st.sidebar.header("🔑 API 설정")

nl_api_key = st.sidebar.text_input(
    "국립중앙도서관(ISBN 서지정보) API Key (cert_key)",
    type="password",
)

demo_mode = st.sidebar.checkbox(
    "데모 모드(서지정보 실패해도 결과 보기)",
    value=True,
)

st.sidebar.subheader("⚡ 속도 옵션(추천)")
fetch_summary_default = st.sidebar.checkbox(
    "줄거리/책소개도 바로 가져오기(느림)",
    value=False,
    help="OFF 권장: 기본은 표지/ISBN만 조회해서 빠르게 보여줍니다. 줄거리는 버튼으로 지연 로딩 가능.",
)

nl_timeout = st.sidebar.slider("API 타임아웃(초)", 5, 30, 10, 1)
nl_retries = st.sidebar.slider("재시도 횟수", 0, 2, 1, 1)
max_workers = st.sidebar.slider("동시 요청 수(병렬 처리)", 1, 6, 3, 1)

# =====================================================
# Header
# =====================================================
st.title("📚 나와 어울리는 책은?")
st.write("성향(장르) + 상황(지금 필요한 것)을 함께 분석해 책 3권을 추천합니다.")

# =====================================================
# Questions
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
    ["A. 읽고 나서 바로 실천할 수 있는 조언","B. 삶에 대한 깊은 질문과 통찰","C. 새로운 지식과 기술을 배우는 재미","D. 사회와 시대를 이해하는 관점","E. 감정적으로 몰입할 수 있는 이야기"],
    ["A. 도움이 될 만한 현실적인 책을 추천한다","B. 생각을 넓혀줄 책을 추천한다","C. 신기한 정보를 주는 책을 추천한다","D. 세상을 이해하게 해주는 책을 추천한다","E. 재미있게 읽히는 책을 추천한다"],
    ["A. “이건 내 삶에 바로 적용할 수 있겠다” 느낄 때","B. “세상을 보는 시야가 넓어졌다” 느낄 때","C. “새로운 사실을 배웠다” 느낄 때","D. “사회나 역사를 이해하게 됐다” 느낄 때","E. “완전히 몰입해서 감정이 움직였다” 느낄 때"],
    ["A. 성장, 목표, 자기관리","B. 인간관계, 삶의 의미","C. 미래기술, 과학, 데이터","D. 사회문제, 역사적 사건","E. 감정, 이야기, 상상 속 세계"],
    ["A. 다시 동기부여하고 방향을 잡는 것","B. 내 마음을 정리할 수 있는 통찰","C. 머리를 자극하는 새로운 호기심","D. 현실을 이해하고 시야를 넓히는 관점","E. 위로받고 감정을 쉬게 하는 이야기"],
    ["A. 미래 준비나 자기계발이 필요해서","B. 복잡한 감정을 정리하고 싶어서","C. 새로운 분야를 배우고 싶어서","D. 사회와 세상 흐름이 궁금해서","E. 지치고 쉬고 싶어서"],
    ["A. “앞으로 뭘 해야 할지 알려주는 나침반”","B. “생각을 정리해주는 대화 상대”","C. “새로운 세상을 보여주는 창문”","D. “현실을 이해하게 해주는 지도”","E. “마음을 쉬게 해주는 휴식처”"],
]

# =====================================================
# Mappings
# =====================================================
genre_map = {"A": "자기계발", "B": "인문/철학", "C": "과학/IT", "D": "역사/사회", "E": "소설"}

genre_persona = {
    "자기계발": "실행·루틴·성과를 중시하는 성장형",
    "인문/철학": "의미·가치·자기이해를 깊게 파고드는 성찰형",
    "과학/IT": "원리·구조·정보를 분석하는 탐구형",
    "역사/사회": "사회 구조·맥락·흐름을 이해하려는 관찰형",
    "소설": "감정·분위기·서사 몰입을 통해 회복하는 감성형",
}

genre_book_point = {
    "자기계발": "바로 적용 가능한 습관·실행 포인트",
    "인문/철학": "감정과 생각을 정리해주는 통찰",
    "과학/IT": "새로운 지식과 원리를 이해하는 재미",
    "역사/사회": "세상 흐름을 읽고 관점을 넓히는 내용",
    "소설": "감정적으로 몰입하며 위로와 여운을 주는 서사",
}

# 장르별 "미세 포커스 키워드" (책마다 다르게 강조)
genre_flavors = {
    "자기계발": ["실행", "루틴", "동기부여", "습관", "자기관리"],
    "인문/철학": ["성찰", "관점", "자기이해", "가치", "질문"],
    "과학/IT": ["원리", "호기심", "미래", "문제해결", "구조"],
    "역사/사회": ["맥락", "흐름", "구조", "사례", "시야"],
    "소설": ["위로", "몰입", "여운", "관계", "회복"],
}

# 상황 태그 점수화(Q5~Q7)
situation_tag_map_q5_to_q7 = {
    5: {"A": ["동기"], "B": ["위로"], "C": ["탐구"], "D": ["탐구"], "E": ["위로", "휴식"]},
    6: {"A": ["동기"], "B": ["위로"], "C": ["탐구"], "D": ["탐구"], "E": ["휴식", "위로"]},
    7: {"A": ["동기"], "B": ["위로"], "C": ["탐구"], "D": ["탐구"], "E": ["휴식", "위로"]},
}

tag_display = {"동기": "방향/동기부여", "위로": "감정 정리/위로", "휴식": "휴식/회복", "탐구": "호기심/탐구"}

# =====================================================
# Demo fallback pool
# =====================================================
fallback_pool = {
    "자기계발": [{"title": "아주 작은 습관의 힘", "author": "제임스 클리어"},{"title": "그릿", "author": "앤절라 더크워스"},{"title": "딥 워크", "author": "칼 뉴포트"},{"title": "원씽", "author": "게리 켈러"},{"title": "미라클 모닝", "author": "할 엘로드"}],
    "인문/철학": [{"title": "정의란 무엇인가", "author": "마이클 샌델"},{"title": "죽음의 수용소에서", "author": "빅터 프랭클"},{"title": "소크라테스 익스프레스", "author": "에릭 와이너"},{"title": "철학은 어떻게 삶의 무기가 되는가", "author": "야마구치 슈"},{"title": "사피엔스", "author": "유발 하라리"}],
    "과학/IT": [{"title": "코스모스", "author": "칼 세이건"},{"title": "팩트풀니스", "author": "한스 로슬링"},{"title": "클린 코드", "author": "로버트 C. 마틴"},{"title": "AI 2041", "author": "카이푸 리, 천치우판"},{"title": "이기적 유전자", "author": "리처드 도킨스"}],
    "역사/사회": [{"title": "총, 균, 쇠", "author": "재레드 다이아몬드"},{"title": "넛지", "author": "리처드 탈러, 캐스 선스타인"},{"title": "역사의 쓸모", "author": "최태성"},{"title": "21세기 자본", "author": "토마 피케티"},{"title": "정치의 심리학", "author": "드루 웨스턴"}],
    "소설": [{"title": "나미야 잡화점의 기적", "author": "히가시노 게이고"},{"title": "불편한 편의점", "author": "김호연"},{"title": "1984", "author": "조지 오웰"},{"title": "달러구트 꿈 백화점", "author": "이미예"},{"title": "데미안", "author": "헤르만 헤세"}],
}

# =====================================================
# Session state
# =====================================================
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "result" not in st.session_state:
    st.session_state.result = None
if "summary_loaded" not in st.session_state:
    st.session_state.summary_loaded = False

for i in range(7):
    k = f"q{i+1}"
    if k not in st.session_state:
        st.session_state[k] = None

def reset_test():
    for i in range(7):
        st.session_state[f"q{i+1}"] = None
    st.session_state.submitted = False
    st.session_state.result = None
    st.session_state.summary_loaded = False

# =====================================================
# Utility (scoring)
# =====================================================
def letter_of(ans: str) -> str:
    return ans.strip()[0]

def compute_genre_scores(answers: List[str]) -> Dict[str, int]:
    scores = {g: 0 for g in genre_map.values()}
    for a in answers:
        scores[genre_map[letter_of(a)]] += 1
    return scores

def compute_situation_scores(answers: List[str]) -> Dict[str, int]:
    tags = {"위로": 0, "휴식": 0, "동기": 0, "탐구": 0}
    for qno in [5, 6, 7]:
        l = letter_of(answers[qno - 1])
        for t in situation_tag_map_q5_to_q7[qno].get(l, []):
            tags[t] += 1
    return tags

def ranked(scores: Dict[str, int]):
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def top_keys(scores: Dict[str, int]):
    r = ranked(scores)
    maxv = r[0][1]
    top = [k for k, v in r if v == maxv]
    return top, r

def pick_3_books(top_genres: List[str]):
    # 복합 성향이면 섞고, 아니면 한 장르 3권
    if len(top_genres) >= 2:
        pool = []
        for g in top_genres[:2]:
            pool += [{"genre": g, **b} for b in fallback_pool[g]]
        random.shuffle(pool)
        out, seen = [], set()
        for item in pool:
            if item["title"] in seen:
                continue
            out.append(item)
            seen.add(item["title"])
            if len(out) == 3:
                break
        return out
    g = top_genres[0]
    return [{"genre": g, **b} for b in random.sample(fallback_pool[g], k=3)]

# =====================================================
# Evidence + diversified reason generation
#   ✅ 책마다 이유가 다르게 나오도록 "분산/템플릿/포커스" 적용
# =====================================================
def evidence_by_genre(answers: List[str], target_genre: str) -> List[str]:
    target_letter = next((l for l, g in genre_map.items() if g == target_genre), None)
    matched = [a[3:].strip() for a in answers if target_letter and letter_of(a) == target_letter]
    return matched  # 전체 후보를 반환(나중에 분산해서 씀)

def situation_evidence_candidates(answers: List[str], situation_tags: List[str]) -> List[str]:
    ev = []
    for qno in [5, 6, 7]:
        ans = answers[qno - 1]
        l = letter_of(ans)
        tags = situation_tag_map_q5_to_q7[qno].get(l, [])
        if any(t in situation_tags for t in tags):
            ev.append(ans[3:].strip())
    return ev  # 전체 후보

def rotate_pick(items: List[str], used: set, fallback: str = "") -> str:
    for it in items:
        if it not in used:
            used.add(it)
            return it
    return fallback if fallback else (items[0] if items else "")

def pick_focus_tag(top_situations: List[str], idx: int) -> List[str]:
    # 책 3권에 대해 상황 태그를 분산 강조
    if not top_situations:
        return []
    if len(top_situations) == 1:
        return top_situations
    # 2개 이상이면 idx에 따라 하나씩 돌아가며 강조 (+ 3번째는 둘 다)
    if idx == 0:
        return [top_situations[0]]
    if idx == 1:
        return [top_situations[1 % len(top_situations)]]
    return top_situations[:2]

reason_templates = [
    # (situation_first, genre_first) 느낌이 다르게
    "최근 “{s_ev}”라고 답한 걸 보면 지금은 **{sit}**이(가) 필요해 보여요. 그리고 “{g_ev}” 선택이 많아 {persona} 성향도 강하네요. 그래서 **{title}**을(를) 추천합니다. ({flavor} 포인트에 특히 잘 맞아요.)",
    "당신이 고른 답변 중 “{g_ev}”가 눈에 띄어요. {persona} 성향인 당신에게 **{sit}**을(를) 채워줄 책이 필요해서, {flavor}에 강한 **{title}**을(를) 골랐어요.",
    "지금은 **{sit}**을(를) 얻는 게 우선일 것 같아요(“{s_ev}”). 동시에 “{g_ev}”를 선택한 걸 보면 {persona}답게 읽을 만한 책이 필요하죠. 그래서 **{title}**을(를) 추천합니다.",
    "설문에서 “{s_ev}”라고 했던 점을 반영했어요. {persona} 성향의 당신에게 **{title}**은(는) {flavor}을 통해 **{sit}**에 도움을 줄 확률이 높아요.",
    "현재 상태(“{s_ev}”)를 보면 **{sit}**을(를) 챙겨야 해요. 그리고 “{g_ev}” 선택은 {persona} 성향을 보여줘요. 그래서 {flavor}이(가) 강한 **{title}**을(를) 추천합니다.",
]

def build_reason_diversified(
    answers: List[str],
    title: str,
    genre: str,
    top_situations: List[str],
    idx: int,
    used_genre_ev: set,
    used_sit_ev: set,
    used_flavor: set,
    used_template: set,
) -> str:
    # 1) 상황 포커스(책마다 다르게)
    focus_tags = pick_focus_tag(top_situations, idx)
    sit_label = ", ".join([tag_display.get(t, t) for t in focus_tags]) if focus_tags else "지금 필요한 것"

    # 2) 근거 후보 수집
    g_candidates = evidence_by_genre(answers, genre)
    s_candidates = situation_evidence_candidates(answers, focus_tags) if focus_tags else []

    g_ev = rotate_pick(g_candidates, used_genre_ev, fallback=(g_candidates[0] if g_candidates else ""))
    s_ev = rotate_pick(s_candidates, used_sit_ev, fallback=(s_candidates[0] if s_candidates else ""))

    # 근거가 비면 최소 문장 유지
    if not s_ev:
        # Q5~Q7 중 아무거나라도 하나 가져와서 분위기 살리기
        q5to7 = [answers[i][3:].strip() for i in [4, 5, 6] if answers[i]]
        s_ev = rotate_pick(q5to7, used_sit_ev, fallback=(q5to7[0] if q5to7 else "요즘 책이 필요하다"))
    if not g_ev:
        # Q1~Q4 중 아무거나
        q1to4 = [answers[i][3:].strip() for i in [0, 1, 2, 3] if answers[i]]
        g_ev = rotate_pick(q1to4, used_genre_ev, fallback=(q1to4[0] if q1to4 else "책을 통해 얻고 싶은 게 있다"))

    # 3) flavor 분산
    flavor_candidates = genre_flavors.get(genre, [])
    flavor = rotate_pick(flavor_candidates, used_flavor, fallback=(flavor_candidates[0] if flavor_candidates else ""))

    # 4) 템플릿 분산
    template = rotate_pick(reason_templates, used_template, fallback=reason_templates[idx % len(reason_templates)])

    persona = genre_persona.get(genre, "이런 성향")

    return template.format(
        s_ev=s_ev,
        g_ev=g_ev,
        sit=sit_label,
        persona=persona,
        title=title,
        flavor=flavor,
    )

# =====================================================
# Networking (fast)
# =====================================================
def requests_get(url, params=None, timeout=10, retries=1):
    last = None
    for i in range(retries + 1):
        try:
            return requests.get(url, params=params, timeout=timeout)
        except (ReadTimeout, ConnectionError) as e:
            last = e
            if i == retries:
                raise
            time.sleep(0.4 * (2**i))
    raise last

@st.cache_data(show_spinner=False)
def nl_isbn_search(cert_key: str, title: str, author: str = "", page_size: int = 5, timeout: int = 10, retries: int = 1):
    url = "https://www.nl.go.kr/seoji/SearchApi.do"
    params = {"cert_key": cert_key, "result_style": "json", "page_no": 1, "page_size": page_size, "title": title}
    if author:
        params["author"] = author
    r = requests_get(url, params=params, timeout=timeout, retries=retries)
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

    def score(it):
        t = str(it.get("TITLE", "") or it.get("title", "")).replace(" ", "").lower()
        if not t:
            return 0
        if t == wt:
            return 100
        if wt in t or t in wt:
            return 60
        return 1

    return sorted(items, key=score, reverse=True)[0]

@st.cache_data(show_spinner=False)
def fetch_text_from_url(url: str, max_chars: int = 650, timeout: int = 10, retries: int = 0) -> str:
    if not url:
        return ""
    try:
        r = requests_get(url, params=None, timeout=timeout, retries=retries)
        r.raise_for_status()
        text = r.text
        text = re.sub(r"<script.*?>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return (text[:max_chars].rstrip() + "…") if len(text) > max_chars else text
    except RequestException:
        return ""

def fetch_one_book_nl(c: dict) -> dict:
    if not nl_api_key:
        return {**c, "isbn": "", "cover_url": "", "summary": "", "note": ""}

    try:
        nl_json = nl_isbn_search(
            nl_api_key,
            title=c["title"],
            author=c.get("author", ""),
            page_size=5,
            timeout=nl_timeout,
            retries=nl_retries,
        )
        item = pick_best_item(nl_json, c["title"])
        if not item:
            return {**c, "isbn": "", "cover_url": "", "summary": "", "note": "검색 결과가 없어 서지정보를 가져오지 못했어요."}

        isbn = item.get("EA_ISBN") or item.get("ISBN") or item.get("isbn") or ""
        cover_url = item.get("TITLE_URL") or item.get("cover") or item.get("image") or ""

        summary = ""
        if fetch_summary_default or st.session_state.summary_loaded:
            intro_url = item.get("BOOK_INTRODUCTION_URL") or ""
            summary_url = item.get("BOOK_SUMMARY_URL") or ""
            summary = fetch_text_from_url(summary_url, timeout=nl_timeout, retries=0)
            if not summary:
                summary = fetch_text_from_url(intro_url, timeout=nl_timeout, retries=0)

        return {
            **c,
            "title": (item.get("TITLE") or c["title"]).strip(),
            "author": (item.get("AUTHOR") or c.get("author", "")).strip(),
            "isbn": str(isbn).strip(),
            "cover_url": str(cover_url).strip(),
            "summary": summary.strip(),
            "note": "",
        }

    except (ReadTimeout, ConnectionError, HTTPError, RequestException):
        if demo_mode:
            return {**c, "isbn": "", "cover_url": "", "summary": "", "note": "API 응답이 느려서(Timeout/오류) 서지정보를 생략했어요."}
        raise

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
c1, c2, c3 = st.columns([1, 1, 1.4])
with c1:
    clicked = st.button("결과 보기", type="primary")
with c2:
    st.button("다시 테스트하기", on_click=reset_test)
with c3:
    load_summary_clicked = st.button("줄거리 불러오기(느림)", help="결과가 나온 뒤 눌러주세요. (지연 로딩)")

if load_summary_clicked:
    st.session_state.summary_loaded = True

# =====================================================
# Flow
# =====================================================
if clicked:
    answers = [st.session_state[f"q{i+1}"] for i in range(7)]
    if any(a is None for a in answers):
        missing = [str(i + 1) for i, a in enumerate(answers) if a is None]
        st.warning(f"모든 질문에 답변해 주세요! (미응답: {', '.join(missing)}번)")
    else:
        with st.spinner("분석 중..."):
            genre_scores = compute_genre_scores(answers)
            top_genres, _ = top_keys(genre_scores)

            situation_scores = compute_situation_scores(answers)
            top_situations, _ = top_keys(situation_scores)

            candidates = pick_3_books(top_genres)

            # ✅ 책마다 이유가 달라지도록 "used set"을 공유
            used_genre_ev, used_sit_ev, used_flavor, used_template = set(), set(), set(), set()

            enriched = []
            for idx, c in enumerate(candidates[:3]):
                why = build_reason_diversified(
                    answers=answers,
                    title=c["title"],
                    genre=c["genre"],
                    top_situations=top_situations,
                    idx=idx,
                    used_genre_ev=used_genre_ev,
                    used_sit_ev=used_sit_ev,
                    used_flavor=used_flavor,
                    used_template=used_template,
                )
                enriched.append({**c, "why": why})

            # ✅ 병렬로 3권 조회 (표지/ISBN 우선)
            books_final = []
            if nl_api_key:
                with ThreadPoolExecutor(max_workers=max_workers) as ex:
                    futures = [ex.submit(fetch_one_book_nl, c) for c in enriched]
                    for f in as_completed(futures):
                        books_final.append(f.result())
                # 추천 순서 유지(원래 리스트 기준)
                order = {b["title"]: i for i, b in enumerate(enriched)}
                books_final.sort(key=lambda x: order.get(x["title"], 999))
            else:
                books_final = [{**c, "isbn": "", "cover_url": "", "summary": "", "note": ""} for c in enriched]

            st.session_state.submitted = True
            st.session_state.result = {
                "genre_scores": genre_scores,
                "genre_top": top_genres,
                "situation_scores": situation_scores,
                "situation_top": top_situations,
                "books": books_final,
                "answers": answers,
            }

# =====================================================
# Render
# =====================================================
if st.session_state.submitted and st.session_state.result:
    r = st.session_state.result
    st.subheader("📌 분석 결과")

    st.success(f"독서 성향: {', '.join(r['genre_top'])}")
    sit_text = ", ".join([tag_display.get(t, t) for t in r["situation_top"]])
    st.info(f"현재 필요한 것: **{sit_text}**")

    if nl_api_key:
        st.caption("※ 속도 개선: 기본은 표지/ISBN만 조회합니다. 줄거리는 ‘줄거리 불러오기’ 버튼으로 지연 로딩하세요.")
    else:
        st.warning("국립중앙도서관 API 키가 없어서 표지/ISBN/줄거리는 표시되지 않습니다.")

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
                st.info("표지 없음/조회 실패")

        with cols[1]:
            st.write("**추천 이유(책마다 다르게 생성됨)**")
            st.write(f"- {b.get('why', '')}")

            st.write("**줄거리/책소개**")
            if b.get("summary"):
                st.write(b["summary"])
            else:
                st.info("줄거리 미로딩(버튼으로 불러올 수 있어요) 또는 제공 URL 없음/실패")

            if b.get("note"):
                st.warning(b["note"])

        st.divider()
