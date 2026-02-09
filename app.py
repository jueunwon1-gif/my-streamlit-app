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

# =====================================================
# Streamlit Setup
# =====================================================
st.set_page_config(page_title="나와 어울리는 책은?", page_icon="📚", layout="centered")


# =====================================================
# Sidebar
# =====================================================
st.sidebar.header("🔑 API 설정")

nl_api_key = st.sidebar.text_input(
    "국립중앙도서관(ISBN 서지정보) API Key (cert_key)",
    type="password",
    help="국립중앙도서관 ISBN 서지정보 API의 cert_key",
)

openai_api_key = st.sidebar.text_input(
    "OpenAI API Key (선택)",
    type="password",
    help="입력하면 '후보 리스트 중에서' AI가 3권을 선택합니다. 없으면 규칙 기반으로 고릅니다.",
)
openai_model = st.sidebar.text_input("OpenAI 모델", value="gpt-4o-mini")

st.sidebar.subheader("⚡ 속도 옵션")
pool_size = st.sidebar.slider("후보 풀(가져올 책 개수)", 20, 120, 60, 10)
nl_timeout = st.sidebar.slider("국립중앙도서관 API 타임아웃(초)", 5, 30, 10, 1)
nl_retries = st.sidebar.slider("국립중앙도서관 API 재시도 횟수", 0, 2, 1, 1)

fetch_summary_default = st.sidebar.checkbox(
    "줄거리/책소개도 바로 가져오기(느림)",
    value=False,
    help="OFF 권장: 기본은 표지/ISBN만 빠르게 표시. 줄거리는 버튼으로 지연 로딩.",
)

st.sidebar.subheader("🧪 디버그")
debug_show_raw = st.sidebar.checkbox("후보 1개 raw JSON 보기", value=False)

# =====================================================
# Header
# =====================================================
st.title("📚 나와 어울리는 책은?")
st.write("성향(장르) + 상황(지금 필요한 것)을 분석하고, **국립중앙도서관 후보 리스트 중에서** 3권을 골라 추천합니다.")


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

genre_flavors = {
    "자기계발": ["실행", "루틴", "동기부여", "습관", "자기관리"],
    "인문/철학": ["성찰", "관점", "자기이해", "가치", "질문"],
    "과학/IT": ["원리", "호기심", "미래", "문제해결", "구조"],
    "역사/사회": ["맥락", "흐름", "구조", "사례", "시야"],
    "소설": ["위로", "몰입", "여운", "관계", "회복"],
}

# 상황 태그(Q5~Q7)
situation_tag_map_q5_to_q7 = {
    5: {"A": ["동기"], "B": ["위로"], "C": ["탐구"], "D": ["탐구"], "E": ["위로", "휴식"]},
    6: {"A": ["동기"], "B": ["위로"], "C": ["탐구"], "D": ["탐구"], "E": ["휴식", "위로"]},
    7: {"A": ["동기"], "B": ["위로"], "C": ["탐구"], "D": ["탐구"], "E": ["휴식", "위로"]},
}
tag_display = {"동기": "방향/동기부여", "위로": "감정 정리/위로", "휴식": "휴식/회복", "탐구": "호기심/탐구"}

# 장르/상황 → 국립중앙도서관 검색용 키워드(제목 검색에 사용)
genre_seed_keywords = {
    "자기계발": ["습관", "공부", "시간관리", "목표", "자기계발", "루틴"],
    "인문/철학": ["철학", "사유", "인간", "관계", "삶", "의미"],
    "과학/IT": ["AI", "데이터", "과학", "프로그래밍", "코딩", "기술"],
    "역사/사회": ["사회", "역사", "정치", "경제", "문화", "세계"],
    "소설": ["소설", "장편", "성장", "힐링", "관계", "청춘"],
}
situation_seed_keywords = {
    "위로": ["위로", "마음", "불안", "상처", "치유"],
    "휴식": ["힐링", "휴식", "쉼", "여유"],
    "동기": ["동기", "열정", "성장", "목표", "공부"],
    "탐구": ["호기심", "질문", "탐구", "미래", "사고"],
}


# =====================================================
# Session State
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
# Scoring Helpers
# =====================================================
def letter_of(ans: str) -> str:
    return ans.strip()[0]


def compute_genre_scores(answers: List[str]) -> Dict[str, int]:
    scores = {g: 0 for g in set(genre_map.values())}
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


def top_two(scores: Dict[str, int]) -> List[str]:
    r = ranked(scores)
    if not r:
        return []
    top = [k for k, v in r if v == r[0][1]]
    if len(top) >= 2:
        return top[:2]
    # second best 1개 붙이기
    second = None
    for k, v in r:
        if v < r[0][1]:
            second = k
            break
    if second:
        return top + [second]
    return top


def top_list(scores: Dict[str, int]) -> List[str]:
    r = ranked(scores)
    if not r:
        return []
    topv = r[0][1]
    return [k for k, v in r if v == topv]


# =====================================================
# Networking (retry)
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
def nl_search_raw(cert_key: str, title_query: str, page_no: int, page_size: int, timeout: int, retries: int) -> dict:
    url = "https://www.nl.go.kr/seoji/SearchApi.do"
    params = {
        "cert_key": cert_key,
        "result_style": "json",
        "page_no": page_no,
        "page_size": page_size,
        "title": title_query,
    }
    r = requests_get(url, params=params, timeout=timeout, retries=retries)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return json.loads(r.text)


def _extract_items(nl_json: dict) -> List[dict]:
    """API 응답 구조가 케이스별로 달라서, list 형태를 최대한 찾아냄."""
    if not isinstance(nl_json, dict):
        return []

    # 흔한 키 후보
    for k in ["docs", "data", "items", "result"]:
        if k in nl_json and isinstance(nl_json[k], list):
            return nl_json[k]

    # value 중 list[dict] 찾기
    for v in nl_json.values():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v

    return []


def _normalize_item(it: dict) -> dict:
    """여러 키 케이스를 감안해서 표준 필드로 정규화."""
    title = (it.get("TITLE") or it.get("title") or "").strip()
    author = (it.get("AUTHOR") or it.get("author") or "").strip()
    publisher = (it.get("PUBLISHER") or it.get("publisher") or "").strip()

    isbn = (it.get("EA_ISBN") or it.get("ISBN") or it.get("isbn") or "").strip()
    cover_url = (it.get("TITLE_URL") or it.get("cover") or it.get("image") or "").strip()

    intro_url = (it.get("BOOK_INTRODUCTION_URL") or it.get("book_introduction_url") or "").strip()
    summary_url = (it.get("BOOK_SUMMARY_URL") or it.get("book_summary_url") or "").strip()

    # 발행연도/일자 추정
    pub_year = (it.get("PUBLISH_PREDATE") or it.get("PUBLISH_DATE") or it.get("publish_date") or "").strip()
    pub_year = pub_year[:4] if pub_year else ""

    # 분류 관련(있으면)
    kdc_name = (it.get("KDC_NAME") or it.get("kdc_name") or "").strip()

    return {
        "title": title,
        "author": author,
        "publisher": publisher,
        "isbn": isbn,
        "cover_url": cover_url,
        "intro_url": intro_url,
        "summary_url": summary_url,
        "pub_year": pub_year,
        "kdc_name": kdc_name,
        "raw": it,
    }


def _dedup_items(items: List[dict]) -> List[dict]:
    seen = set()
    out = []
    for it in items:
        key = it.get("isbn") or (it.get("title", "") + "|" + it.get("author", ""))
        key = key.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def build_nl_queries(focus_genres: List[str], top_situations: List[str]) -> List[str]:
    """
    국립중앙도서관 SearchApi는 'title' 파라미터가 가장 안전해서,
    장르/상황에 따라 제목 검색 키워드를 몇 개 만든다.
    """
    queries = []
    for g in focus_genres[:2]:
        g_words = genre_seed_keywords.get(g, [])
        # 상황 태그가 있으면 섞기(너무 길게 만들지 말고 1~2단어 수준)
        if top_situations:
            s = top_situations[0]
            s_words = situation_seed_keywords.get(s, [])
            if g_words and s_words:
                queries.append(f"{random.choice(s_words)} {random.choice(g_words)}")
            elif g_words:
                queries.append(random.choice(g_words))
        else:
            if g_words:
                queries.append(random.choice(g_words))

    # 여분 쿼리 1개(상황 중심)
    if top_situations:
        s_words = situation_seed_keywords.get(top_situations[0], [])
        if s_words:
            queries.append(random.choice(s_words))

    # 중복 제거
    uniq = []
    for q in queries:
        q = q.strip()
        if q and q not in uniq:
            uniq.append(q)
    return uniq[:3]  # 최대 3개만 (속도/부하 제한)


def fetch_candidate_pool_from_nl(
    cert_key: str,
    focus_genres: List[str],
    top_situations: List[str],
    target_pool_size: int,
    timeout: int,
    retries: int,
) -> Tuple[List[dict], List[str]]:
    """
    여러 쿼리로 검색해 후보를 모아 pool_size만큼 만들기.
    반환: (candidates, used_queries)
    """
    if not cert_key:
        return [], []

    used_queries = build_nl_queries(focus_genres, top_situations)
    all_items: List[dict] = []

    # 쿼리별로 1페이지씩만 우선 가져와도 pool은 충분히 채워지는 경우가 많음
    per_query_page_size = max(10, min(50, target_pool_size // max(1, len(used_queries))))
    per_query_page_size = min(per_query_page_size, 50)

    for q in used_queries:
        try:
            raw = nl_search_raw(cert_key, title_query=q, page_no=1, page_size=per_query_page_size, timeout=timeout, retries=retries)
            items = [_normalize_item(it) for it in _extract_items(raw)]
            all_items.extend(items)
        except Exception:
            continue

    all_items = _dedup_items(all_items)

    # pool_size 맞추기
    if len(all_items) > target_pool_size:
        all_items = all_items[:target_pool_size]

    return all_items, used_queries


# =====================================================
# Summary fetch (optional lazy)
# =====================================================
@st.cache_data(show_spinner=False)
def fetch_text_from_url(url: str, max_chars: int = 700, timeout: int = 10, retries: int = 0) -> str:
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

        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "…"
        return text
    except RequestException:
        return ""


def get_summary_for_book(book: dict) -> str:
    # summary_url 우선, 없으면 intro_url
    s = ""
    if book.get("summary_url"):
        s = fetch_text_from_url(book["summary_url"], timeout=nl_timeout, retries=0)
    if not s and book.get("intro_url"):
        s = fetch_text_from_url(book["intro_url"], timeout=nl_timeout, retries=0)
    return s.strip()


# =====================================================
# OpenAI: choose 3 from candidate list (Korean books in list)
# =====================================================
@st.cache_data(show_spinner=False)
def call_openai_json(api_key: str, model: str, system: str, user: str) -> dict:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])


def ai_choose_from_pool(
    answers: List[str],
    focus_genres: List[str],
    top_situations: List[str],
    pool: List[dict],
) -> List[dict]:
    """
    pool(후보 리스트) 중에서 AI가 3개를 고르고,
    각 책에 대해 book_hook(책별로 다른 포인트)을 생성하게 한다.
    """
    # 너무 많은 후보를 보내면 토큰/지연 증가 → 최대 40개만
    pool_trim = pool[:40]
    brief = []
    for i, b in enumerate(pool_trim):
        brief.append({
            "id": i,
            "title": b.get("title", ""),
            "author": b.get("author", ""),
            "publisher": b.get("publisher", ""),
            "pub_year": b.get("pub_year", ""),
            "isbn": b.get("isbn", ""),
            "kdc_name": b.get("kdc_name", ""),
        })

    system = (
        "너는 한국어 독서 큐레이터다.\n"
        "사용자의 설문(성향+상황)을 반영해, 제공된 '후보 도서 리스트' 안에서만 3권을 골라라.\n"
        "반드시 서로 다른 책 3권이어야 한다.\n"
        "각 책에 대해 '왜 이 책이 특히 맞는지'를 1문장 book_hook으로 작성하되, 3권이 서로 비슷하지 않게 포인트를 달리해라.\n"
        "출력은 아래 JSON 형식만:\n\n"
        "{\n"
        '  "picks": [\n'
        '    {"id": 0, "book_hook": "한 문장 이유(책마다 다르게)"},\n'
        '    {"id": 1, "book_hook": "..."},\n'
        '    {"id": 2, "book_hook": "..."}\n'
        "  ]\n"
        "}\n"
    )
    user = (
        f"focus_genres: {focus_genres}\n"
        f"top_situations: {top_situations}\n"
        "사용자 답변:\n" + "\n".join([f"- {a}" for a in answers]) + "\n\n"
        "후보 도서 리스트(JSON):\n" + json.dumps({"candidates": brief}, ensure_ascii=False)
    )

    obj = call_openai_json(openai_api_key, openai_model, system, user)
    picks = obj.get("picks", [])

    picked = []
    used = set()
    for p in picks:
        try:
            idx = int(p.get("id"))
        except Exception:
            continue
        if idx < 0 or idx >= len(pool_trim) or idx in used:
            continue
        used.add(idx)
        b = dict(pool_trim[idx])
        b["book_hook"] = str(p.get("book_hook", "")).strip()
        picked.append(b)
        if len(picked) == 3:
            break

    return picked


# =====================================================
# Fallback chooser (no OpenAI): deterministic-ish selection from pool
# =====================================================
def fallback_choose_from_pool(pool: List[dict], focus_genres: List[str]) -> List[dict]:
    """
    OpenAI가 없으면:
    - 표지/ISBN 존재하는 후보를 우선
    - 제목/저자 중복 최소화
    - 3권 선택
    """
    def score(b):
        s = 0
        if b.get("isbn"):
            s += 3
        if b.get("cover_url"):
            s += 2
        if b.get("pub_year"):
            s += 1
        if b.get("kdc_name"):
            s += 1
        # 랜덤 소금(동점 분산)
        s += random.random() * 0.1
        return s

    sorted_pool = sorted(pool, key=score, reverse=True)
    out = []
    seen = set()
    for b in sorted_pool:
        key = b.get("isbn") or (b.get("title","") + "|" + b.get("author",""))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({**b, "book_hook": ""})
        if len(out) == 3:
            break
    return out


# =====================================================
# Diversified 이유 생성 (설문 근거 + AI의 book_hook까지 섞어서 책마다 다르게)
# =====================================================
def evidence_by_genre(answers: List[str], target_genre_letter: str) -> List[str]:
    return [a[3:].strip() for a in answers if letter_of(a) == target_genre_letter]


def situation_evidence_candidates(answers: List[str], focus_tags: List[str]) -> List[str]:
    ev = []
    for qno in [5, 6, 7]:
        ans = answers[qno - 1]
        l = letter_of(ans)
        tags = situation_tag_map_q5_to_q7[qno].get(l, [])
        if any(t in focus_tags for t in tags):
            ev.append(ans[3:].strip())
    return ev


def rotate_pick(items: List[str], used: set, fallback: str = "") -> str:
    for it in items:
        if it and it not in used:
            used.add(it)
            return it
    return fallback if fallback else (items[0] if items else "")


def pick_focus_tag(top_situations: List[str], idx: int) -> List[str]:
    if not top_situations:
        return []
    if len(top_situations) == 1:
        return top_situations
    if idx == 0:
        return [top_situations[0]]
    if idx == 1:
        return [top_situations[1 % len(top_situations)]]
    return top_situations[:2]


reason_templates = [
    "최근 “{s_ev}”라고 답한 걸 보면 지금은 **{sit}**이(가) 필요해 보여요. “{g_ev}” 선택도 있어서 {persona} 성향과 잘 맞고, **{title}**은(는) {flavor} 관점에서 도움을 줄 수 있어요. {hook}",
    "당신이 고른 답 중 “{g_ev}”가 눈에 띄어요. {persona}인 당신에게 **{sit}**을(를) 채워줄 책이 필요해서, {flavor} 포인트가 강한 **{title}**을(를) 골랐어요. {hook}",
    "지금은 **{sit}**이(가) 우선일 것 같아요(“{s_ev}”). 동시에 “{g_ev}”를 택한 걸 보면 {persona}답게 읽을 책이 필요하죠. 그래서 **{title}**을(를) 추천합니다. {hook}",
    "설문에서 “{s_ev}”라고 했던 점을 반영했어요. {persona} 성향의 당신에게 **{title}**은(는) {flavor}을 통해 **{sit}**에 도움을 줄 확률이 높아요. {hook}",
]


def build_reason_diversified(
    answers: List[str],
    genre: str,
    top_situations: List[str],
    idx: int,
    book: dict,
    used_genre_ev: set,
    used_sit_ev: set,
    used_flavor: set,
    used_template: set,
) -> str:
    # 장르 → 설문 선택지 문자 매핑(A/B/C/D/E)
    genre_to_letter = {v: k for k, v in genre_map.items()}
    target_letter = genre_to_letter.get(genre, "")

    focus_tags = pick_focus_tag(top_situations, idx)
    sit_label = ", ".join([tag_display.get(t, t) for t in focus_tags]) if focus_tags else "지금 필요한 것"

    g_candidates = evidence_by_genre(answers, target_letter) if target_letter else []
    s_candidates = situation_evidence_candidates(answers, focus_tags) if focus_tags else []

    g_ev = rotate_pick(g_candidates, used_genre_ev, fallback="")
    s_ev = rotate_pick(s_candidates, used_sit_ev, fallback="요즘 책이 필요하다")

    if not g_ev:
        q1to4 = [answers[i][3:].strip() for i in [0, 1, 2, 3] if answers[i]]
        g_ev = rotate_pick(q1to4, used_genre_ev, fallback=(q1to4[0] if q1to4 else "책에서 얻고 싶은 게 있다"))

    flavor = rotate_pick(genre_flavors.get(genre, []), used_flavor, fallback="핵심")
    template = rotate_pick(reason_templates, used_template, fallback=reason_templates[idx % len(reason_templates)])
    persona = genre_persona.get(genre, "이런 성향")

    hook = book.get("book_hook", "").strip()
    hook = f"({hook})" if hook else ""

    return template.format(
        s_ev=s_ev,
        g_ev=g_ev,
        sit=sit_label,
        persona=persona,
        title=book.get("title", ""),
        flavor=flavor,
        hook=hook,
    ).strip()


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
# Main Flow
# =====================================================
if clicked:
    answers = [st.session_state[f"q{i+1}"] for i in range(7)]
    if any(a is None for a in answers):
        missing = [str(i + 1) for i, a in enumerate(answers) if a is None]
        st.warning(f"모든 질문에 답변해 주세요! (미응답: {', '.join(missing)}번)")
    else:
        if not nl_api_key:
            st.error("국립중앙도서관 API 키(cert_key)가 필요합니다. 사이드바에 입력해 주세요.")
        else:
            with st.spinner("분석 + 후보 리스트 가져오는 중..."):
                genre_scores = compute_genre_scores(answers)
                situation_scores = compute_situation_scores(answers)

                focus_genres = top_two(genre_scores)  # 최대 2개 장르
                top_situations = top_list(situation_scores)

                # 1) 후보 풀: NL에서 먼저 가져오기
                pool, used_queries = fetch_candidate_pool_from_nl(
                    cert_key=nl_api_key,
                    focus_genres=focus_genres,
                    top_situations=top_situations,
                    target_pool_size=pool_size,
                    timeout=nl_timeout,
                    retries=nl_retries,
                )

                if not pool:
                    st.error("국립중앙도서관 API에서 후보를 가져오지 못했어요. (키/네트워크/쿼리 문제 가능)")
                else:
                    # 2) 후보 중에서 3권 선택: AI(가능하면) / 없으면 fallback
                    used_ai = False
                    if openai_api_key:
                        try:
                            picked = ai_choose_from_pool(
                                answers=answers,
                                focus_genres=focus_genres,
                                top_situations=top_situations,
                                pool=pool,
                            )
                            if len(picked) == 3:
                                used_ai = True
                            else:
                                picked = fallback_choose_from_pool(pool, focus_genres)
                        except Exception:
                            picked = fallback_choose_from_pool(pool, focus_genres)
                            used_ai = False
                    else:
                        picked = fallback_choose_from_pool(pool, focus_genres)
                        used_ai = False

                    # 3) (옵션) 줄거리 지연 로딩
                    if fetch_summary_default or st.session_state.summary_loaded:
                        for b in picked:
                            b["summary"] = get_summary_for_book(b)
                    else:
                        for b in picked:
                            b["summary"] = ""

                    # 4) 추천 이유: 책마다 다르게 생성(설문 근거 + book_hook 섞기)
                    used_genre_ev, used_sit_ev, used_flavor, used_template = set(), set(), set(), set()
                    # 책별 장르는 “현재 앱의 성향 장르”로 붙여도 되지만,
                    # 후보 리스트에는 장르 정보가 확실치 않아서, 여기서는
                    # "주된 성향 장르"를 기본 장르로 사용(안정적인 UX)
                    primary_genre = focus_genres[0] if focus_genres else "소설"

                    for idx, b in enumerate(picked):
                        b["genre"] = primary_genre
                        b["why"] = build_reason_diversified(
                            answers=answers,
                            genre=primary_genre,
                            top_situations=top_situations,
                            idx=idx,
                            book=b,
                            used_genre_ev=used_genre_ev,
                            used_sit_ev=used_sit_ev,
                            used_flavor=used_flavor,
                            used_template=used_template,
                        )

                    st.session_state.submitted = True
                    st.session_state.result = {
                        "answers": answers,
                        "genre_scores": genre_scores,
                        "situation_scores": situation_scores,
                        "focus_genres": focus_genres,
                        "top_situations": top_situations,
                        "used_queries": used_queries,
                        "pool_count": len(pool),
                        "used_ai": used_ai,
                        "picked": picked,
                        "raw_first_pool_item": pool[0].get("raw") if pool else None,
                    }


# =====================================================
# Render Result
# =====================================================
if st.session_state.submitted and st.session_state.result:
    r = st.session_state.result

    st.subheader("📌 분석 결과")
    st.success(f"독서 성향(상위): {', '.join(r['focus_genres'])}")
    sit_text = ", ".join([tag_display.get(t, t) for t in r["top_situations"]]) if r["top_situations"] else "—"
    st.info(f"현재 필요한 것(상위): **{sit_text}**")

    st.caption(f"국립중앙도서관 검색 키워드: {', '.join(r['used_queries'])} · 후보 {r['pool_count']}권 확보")
    if r["used_ai"]:
        st.caption("✅ AI가 후보 리스트 중에서 3권을 선택했습니다.")
    else:
        st.caption("ℹ️ AI 미사용/실패로 규칙 기반 선택을 사용했습니다.")

    if debug_show_raw and r.get("raw_first_pool_item"):
        with st.expander("🧪 후보 1개 raw JSON"):
            st.json(r["raw_first_pool_item"])

    st.subheader("📚 추천 도서 3권")
    for i, b in enumerate(r["picked"], start=1):
        st.markdown(f"### {i}. {b.get('title','')}")
        meta = []
        if b.get("author"):
            meta.append(f"저자: {b['author']}")
        if b.get("publisher"):
            meta.append(f"출판사: {b['publisher']}")
        if b.get("pub_year"):
            meta.append(f"발행: {b['pub_year']}")
        if b.get("isbn"):
            meta.append(f"ISBN: {b['isbn']}")
        if meta:
            st.caption(" · ".join(meta))

        cols = st.columns([1, 2])
        with cols[0]:
            if b.get("cover_url"):
                st.image(b["cover_url"], use_container_width=True)
            else:
                st.info("표지 이미지 없음(데이터 미제공)")

        with cols[1]:
            st.write("**추천 이유(설문 근거 + 책별 포인트)**")
            st.write(f"- {b.get('why','')}")

            st.write("**줄거리/책소개**")
            if b.get("summary"):
                st.write(b["summary"])
            else:
                st.info("줄거리 미로딩(‘줄거리 불러오기’ 버튼으로 지연 로딩) 또는 제공 URL 없음")

        st.divider()
