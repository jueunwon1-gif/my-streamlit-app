import json
import random
from typing import Dict, List

import requests
import streamlit as st

st.set_page_config(page_title="나와 어울리는 책은?", page_icon="📚", layout="centered")

# =====================================================
# Global UI Style (깔끔 카드 UI)
# =====================================================
st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 860px; }
      .small-muted { color: rgba(0,0,0,.55); font-size: 0.9rem; margin-top: .2rem; }
      .result-card {
        border: 1px solid rgba(0,0,0,.08);
        border-radius: 18px;
        padding: 18px 18px;
        background: rgba(255,255,255,.65);
        box-shadow: 0 8px 22px rgba(0,0,0,.06);
        margin: 14px 0 18px 0;
      }
      .pill {
        display:inline-block;
        padding: 6px 10px;
        border-radius: 999px;
        border: 1px solid rgba(0,0,0,.08);
        background: rgba(0,0,0,.03);
        font-size: 0.82rem;
        margin-right: 6px;
        margin-bottom: 6px;
      }
      .title-row { display:flex; gap:10px; align-items: baseline; flex-wrap: wrap; }
      .book-title { font-size: 1.15rem; font-weight: 800; margin: 0; }
      .book-meta { color: rgba(0,0,0,.62); font-size: 0.92rem; margin: 0.2rem 0 0 0; }
      .why-box {
        border-radius: 14px;
        padding: 12px 14px;
        border: 1px solid rgba(0,0,0,.08);
        background: rgba(255,255,255,.75);
        margin-top: 10px;
      }
      .why-label { font-weight: 700; margin-bottom: 6px; }
      .divider-soft { height: 1px; background: rgba(0,0,0,.06); margin: 14px 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =====================================================
# Sidebar
# =====================================================
st.sidebar.header("🔑 API 설정")

openai_api_key = st.sidebar.text_input(
    "OpenAI API Key (선택)",
    type="password",
    help="입력하면 AI가 '한국어로 출간/유통되는 책' 3권을 추천합니다. 없으면 데모 추천 목록으로 동작합니다.",
)

openai_model = st.sidebar.text_input("OpenAI 모델", value="gpt-4o-mini")

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

genre_flavors = {
    "자기계발": ["실행", "루틴", "동기부여", "습관", "자기관리"],
    "인문/철학": ["성찰", "관점", "자기이해", "가치", "질문"],
    "과학/IT": ["원리", "호기심", "미래", "문제해결", "구조"],
    "역사/사회": ["맥락", "흐름", "구조", "사례", "시야"],
    "소설": ["위로", "몰입", "여운", "관계", "회복"],
}

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
# Scoring
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
    second = [k for k, v in r if v == (r[1][1] if len(r) > 1 else -1)]
    return top, second, r

def pick_3_books(top_genres: List[str], second_genres: List[str]):
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

    primary = top_genres[0]
    out = [{"genre": primary, **b} for b in random.sample(fallback_pool[primary], k=2)]
    if second_genres and second_genres[0] != primary:
        out.append({"genre": second_genres[0], **random.choice(fallback_pool[second_genres[0]])})
        random.shuffle(out)
        return out[:3]
    return [{"genre": primary, **b} for b in random.sample(fallback_pool[primary], k=3)]

# =====================================================
# Evidence + diversified reason generation
# =====================================================
def evidence_by_genre(answers: List[str], target_genre: str) -> List[str]:
    target_letter = next((l for l, g in genre_map.items() if g == target_genre), None)
    return [a[3:].strip() for a in answers if target_letter and letter_of(a) == target_letter]

def situation_evidence_candidates(answers: List[str], situation_tags: List[str]) -> List[str]:
    ev = []
    for qno in [5, 6, 7]:
        ans = answers[qno - 1]
        l = letter_of(ans)
        tags = situation_tag_map_q5_to_q7[qno].get(l, [])
        if any(t in situation_tags for t in tags):
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
    focus_tags = pick_focus_tag(top_situations, idx)
    sit_label = ", ".join([tag_display.get(t, t) for t in focus_tags]) if focus_tags else "지금 필요한 것"

    g_candidates = evidence_by_genre(answers, genre)
    s_candidates = situation_evidence_candidates(answers, focus_tags) if focus_tags else []

    g_ev = rotate_pick(g_candidates, used_genre_ev, fallback=(g_candidates[0] if g_candidates else "책에서 얻고 싶은 게 있다"))
    s_ev = rotate_pick(s_candidates, used_sit_ev, fallback="요즘 책이 필요하다")

    if s_ev == "요즘 책이 필요하다":
        q5to7 = [answers[i][3:].strip() for i in [4, 5, 6] if answers[i]]
        if q5to7:
            s_ev = rotate_pick(q5to7, used_sit_ev, fallback=q5to7[0])
    if g_ev == "책에서 얻고 싶은 게 있다":
        q1to4 = [answers[i][3:].strip() for i in [0, 1, 2, 3] if answers[i]]
        if q1to4:
            g_ev = rotate_pick(q1to4, used_genre_ev, fallback=q1to4[0])

    flavor_candidates = genre_flavors.get(genre, [])
    flavor = rotate_pick(flavor_candidates, used_flavor, fallback=(flavor_candidates[0] if flavor_candidates else "핵심"))

    template = rotate_pick(reason_templates, used_template, fallback=reason_templates[idx % len(reason_templates)])
    persona = genre_persona.get(genre, "이런 성향")

    return template.format(s_ev=s_ev, g_ev=g_ev, sit=sit_label, persona=persona, title=title, flavor=flavor)

# =====================================================
# OpenAI (선택)
# =====================================================
@st.cache_data(show_spinner=False)
def call_openai_json(api_key: str, model: str, system: str, user: str) -> dict:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "temperature": 0.6,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])

def ai_pick_books_korean_only(answers: List[str], focus_genres: List[str], top_situations: List[str]) -> List[dict]:
    system = (
        "너는 한국의 독서 큐레이터다.\n"
        "반드시 '한국어로 출간/유통되는 책(국내 도서 또는 한국어 번역서)'만 추천해라.\n"
        "사용자의 설문(성향+상황)을 반영해 3권을 추천하되, 아래 JSON 형식만 출력해라.\n\n"
        "{\n"
        '  "recommendations": [\n'
        '    {"title":"도서명", "author":"저자(모르면 빈 문자열)", "genre":"자기계발|인문/철학|과학/IT|역사/사회|소설"}\n'
        "  ]\n"
        "}\n\n"
        "규칙:\n"
        "- 반드시 실제로 존재하는 책\n"
        "- genre는 지정된 5개 중 하나\n"
        "- focus_genres를 우선 반영하되, 상황(top_situations)도 고려\n"
        "- 대학생이 읽기 무난한 난이도 우선\n"
        "- 시/만화/웹툰은 제외\n"
    )
    user = (
        f"focus_genres: {focus_genres}\n"
        f"top_situations: {top_situations}\n"
        "사용자 답변:\n" + "\n".join([f"- {a}" for a in answers])
    )
    obj = call_openai_json(api_key=openai_api_key, model=openai_model, system=system, user=user)
    recs = obj.get("recommendations", [])

    cleaned = []
    for r in recs[:5]:
        title = str(r.get("title", "")).strip()
        author = str(r.get("author", "")).strip()
        genre = str(r.get("genre", "")).strip()
        if genre not in genre_map.values():
            genre = focus_genres[0] if focus_genres else "소설"
        if title:
            cleaned.append({"title": title, "author": author, "genre": genre})

    uniq, seen = [], set()
    for c in cleaned:
        if c["title"] in seen:
            continue
        seen.add(c["title"])
        uniq.append(c)
        if len(uniq) == 3:
            break
    return uniq

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
c1, c2 = st.columns([1, 1])
with c1:
    clicked = st.button("결과 보기", type="primary")
with c2:
    st.button("다시 테스트하기", on_click=reset_test)

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
            top_genres, second_genres, _ = top_keys(genre_scores)

            situation_scores = compute_situation_scores(answers)
            top_situations, _, _ = top_keys(situation_scores)

            focus_genres = top_genres[:2] if len(top_genres) >= 2 else (top_genres + second_genres[:1])

            candidates: List[dict] = []
            used_ai = False

            if openai_api_key:
                try:
                    ai_recs = ai_pick_books_korean_only(
                        answers=answers,
                        focus_genres=focus_genres,
                        top_situations=top_situations
                    )
                    if len(ai_recs) == 3:
                        candidates = ai_recs
                        used_ai = True
                except Exception:
                    candidates = []
                    used_ai = False

            if len(candidates) < 3:
                fb = pick_3_books(top_genres, second_genres)
                candidates = [{"title": b["title"], "author": b.get("author", ""), "genre": b["genre"]} for b in fb]
                used_ai = False

            used_genre_ev, used_sit_ev, used_flavor, used_template = set(), set(), set(), set()
            books_final = []
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
                books_final.append({**c, "why": why})

            st.session_state.submitted = True
            st.session_state.result = {
                "genre_scores": genre_scores,
                "genre_top": top_genres,
                "situation_scores": situation_scores,
                "situation_top": top_situations,
                "books": books_final,
                "answers": answers,
                "used_ai": used_ai,
            }

# =====================================================
# Render (예쁜 카드 UI)
# =====================================================
if st.session_state.submitted and st.session_state.result:
    r = st.session_state.result

    st.subheader("📌 분석 결과")

    sit_text = ", ".join([tag_display.get(t, t) for t in r["situation_top"]])
    genre_text = ", ".join(r["genre_top"])

    st.markdown(
        f"""
        <div class="result-card">
          <div class="title-row">
            <div class="pill">📚 성향</div>
            <div style="font-size:1.05rem; font-weight:800;">{genre_text}</div>
          </div>
          <div style="margin-top:10px;" class="title-row">
            <div class="pill">🎯 지금 필요한 것</div>
            <div style="font-size:1.02rem; font-weight:750;">{sit_text}</div>
          </div>
          <div class="divider-soft"></div>
          <div class="small-muted">
            {("✅ OpenAI 기반 추천" if r.get("used_ai") else "ℹ️ 데모 추천 목록 기반")}
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.subheader("📚 추천 도서 3권")

    for idx, b in enumerate(r["books"], start=1):
        title = b.get("title", "").strip()
        author = b.get("author", "").strip()
        why = b.get("why", "").strip()
        genre = b.get("genre", "").strip()

        st.markdown('<div class="result-card">', unsafe_allow_html=True)

        st.markdown(
            f"""
            <div class="title-row">
              <span class="pill">#{idx}</span>
              {f'<span class="pill">🏷️ {genre}</span>' if genre else ''}
            </div>
            <div class="book-title">{title}</div>
            <div class="book-meta">
              {("저자: " + author) if author else ""}
            </div>
            """,
            unsafe_allow_html=True
        )

        if why:
            st.markdown(
                f"""
                <div class="why-box">
                  <div class="why-label">✨ 추천 이유</div>
                  <div>{why}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown("</div>", unsafe_allow_html=True)
