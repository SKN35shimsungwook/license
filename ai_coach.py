# -*- coding: utf-8 -*-
"""Gemini API 기반 AI 학습 코치. 사용자가 명시적으로 버튼을 눌렀을 때만 호출된다(자동 호출 없음)."""
import json
import os

import streamlit as st
from google import genai
from google.genai import types

_SECRETS_PATH = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")


def save_key_locally(key_name, value):
    """로컬 .streamlit/secrets.toml에 키=값을 저장(기존 값 있으면 갱신).
    Streamlit Cloud 등 소스 폴더가 읽기 전용인 배포 환경에서는 쓰기가 실패할 수 있으므로,
    그런 경우 조용히 실패하고 False를 반환한다(호출부는 세션 상태로 계속 동작시킨다)."""
    try:
        lines = []
        found = False
        if os.path.exists(_SECRETS_PATH):
            with open(_SECRETS_PATH, encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith(f"{key_name} ") or stripped.startswith(f"{key_name}="):
                        lines.append(f'{key_name} = "{value}"\n')
                        found = True
                    else:
                        lines.append(line)
        if not found:
            lines.append(f'{key_name} = "{value}"\n')
        os.makedirs(os.path.dirname(_SECRETS_PATH), exist_ok=True)
        with open(_SECRETS_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True
    except OSError:
        return False

# 정확도가 중요한 작업(변형 문제 생성)은 Flash, 비용이 더 중요한 작업(대화/학습계획)은 Flash-Lite.
# 같은 API 키로 모델 이름만 바꿔서 호출하면 되므로 키를 추가로 발급받을 필요는 없다.
MODEL_ACCURATE = "gemini-3.6-flash"
MODEL_CHEAP = "gemini-3.5-flash-lite"

TUTOR_SYSTEM_PROMPT = """당신은 정보처리산업기사 등 IT 자격증 시험을 준비하는, 완전 초보자(노베이스) 학습자의
1:1 전담 과외 선생님이자, 이 학습자의 "합격 전략"을 총괄하는 컨트롤타워입니다. 이 학습자는 같은 개념/문제를
반복해서 틀리고 있습니다.

당신은 단순히 개념 하나를 설명하는 게 아니라, 아래에 함께 주어지는 "학습 전략 컨텍스트"(과목별 합격 여유,
시험까지 남은 기간 등)를 항상 참고해서, 이 순간 이 학습자에게 가장 도움이 되는 방향으로 판단하고 이끄세요.
예를 들어 지금 다루는 개념이 속한 과목이 과락 위험군이라면, 왜 이 개념이 합격에 특히 중요한지도 짚어주세요.

목표는 정답을 그냥 알려주는 게 아니라, 학습자가 "왜 그렇게 생각했는지" 스스로 설명하게 만들고,
그 답변을 근거로 정말 이해했는지 확인한 뒤, 아직 헷갈리는 부분이 있다면 다른 예시나 비유를 들어
"이렇게 생각하면 이해가 될 거예요"라고 방향을 잡아주며 이해시키는 것입니다.

규칙:
- 학습자의 답변이 정답과 완전히 무관하더라도 개념을 설명할 때는 절대 비난하지 말고, 어느 지점에서
  개념이 꼬였는지 짚어주세요. 설명은 쉬운 말로, 실생활 비유나 다른 예시를 곁들이세요.
- 한 번에 너무 많은 내용을 쏟아내지 말고, 대화하듯 짧게(3~5문장 이내) 여러 번 주고받으세요.
- 학습자가 정말 이해했는지는 그냥 넘어가지 말고 짧은 확인 질문이나 변형 예시로 검증한 뒤 다음으로 넘어가세요.

톤은 무조건 다정하기만 하면 안 됩니다. 상황에 따라 솔직하고 다양하게 반응하세요:
- 같은 개념을 정말 여러 번(3회 이상) 반복해서 틀렸거나, 이 개념이 속한 과목이 과락 위험군인데
  시험이 며칠 안 남았다면, 부드럽게만 돌려 말하지 말고 "이 상태로 시험 보면 이 과목 과락 나올 수 있어요",
  "이거 지금 안 잡으면 시험장에서 또 틀려요"처럼 현실적인 결과를 솔직하게, 따끔하게 짚어주세요.
  단, 인신공격이나 비난이 아니라 "지금 잡아야 할 문제"라는 관점으로 말하세요.
- 반대로 학습자가 스스로 잘 설명했거나 이해가 빠르게 진전됐다면, 형식적인 칭찬 말고 구체적으로
  무엇을 잘했는지 짚어서 진심으로 칭찬하세요.
- 매번 같은 어조(항상 격려만, 항상 걱정만)로 반복하지 말고, 실제 상황(오답 횟수, 과목 위험도, 방금
  학습자가 보인 이해도)에 따라 칭찬/중립/경고 사이를 오가며 솔직하게 반응하세요.
- 반드시 한국어로 답하세요."""


def subject_status_text(exam_cfg, subject, stat):
    """subject 하나에 대한 (정답률, 과락기준, 상태문구) — 여러 기능이 공유."""
    count = exam_cfg.get("exam_subject_counts", {}).get(subject)
    min_correct = exam_cfg.get("exam_min_correct", {}).get(subject, 0)
    if not count:
        return None
    min_rate = round(min_correct / count * 100)
    if not stat or not stat.get("seen"):
        return f"현재 정답률 데이터 부족 (과락 기준 {min_rate}% 이상)"
    acc = round((stat["seen"] - stat["wrong"]) / stat["seen"] * 100)
    gap = acc - min_rate
    if gap < 5:
        status = "과락 위험(합격 기준에 매우 근접하거나 미달)"
    elif gap < 20:
        status = "보통(기준은 넘지만 여유가 적음)"
    else:
        status = "안전"
    return f"현재 정답률 {acc}% (과락 기준 {min_rate}% 이상) → {status}"


def build_strategy_block(exam_cfg, subject_label_map, subject_stats, d_day):
    """과목별 합격 여유(과락 위험/보통/안전)와 남은 기간을 요약한, 여러 기능이 공유하는 전략 컨텍스트."""
    stats_by_subject = {s["subject"]: s for s in subject_stats}
    lines = []
    for subj in sorted(exam_cfg.get("exam_subject_counts", {}).keys()):
        label = subject_label_map.get(subj, f"{subj}과목")
        text = subject_status_text(exam_cfg, subj, stats_by_subject.get(subj))
        lines.append(f"- {label}: {text}")
    d_day_text = f"{d_day}일" if d_day is not None else "미설정"
    return f"[시험까지 남은 기간: {d_day_text}]\n[과목별 합격 여유]\n" + "\n".join(lines)

VARIANT_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "choices": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
        "answer": {"type": "integer", "minimum": 1, "maximum": 4},
        "explanation": {"type": "string"},
    },
    "required": ["question", "choices", "answer", "explanation"],
}


@st.cache_resource(show_spinner=False)
def _client_for_key(api_key):
    return genai.Client(api_key=api_key)


def get_client(explicit_key=None):
    api_key = explicit_key
    if not api_key:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            api_key = ""
    if not api_key:
        return None
    try:
        return _client_for_key(api_key)
    except Exception:
        return None


def build_context_block(question, choices, correct_text, wrong_history_texts):
    labels = "①②③④"
    choice_lines = "\n".join(f"{labels[i]} {c}" for i, c in enumerate(choices))
    if wrong_history_texts:
        hist_lines = "\n".join(f"- {i + 1}번째 시도: '{c}' 선택 (오답)" for i, c in enumerate(wrong_history_texts))
    else:
        hist_lines = "(기록 없음)"
    return (
        f"[문제]\n{question}\n\n[보기]\n{choice_lines}\n\n[정답]\n{correct_text}\n\n"
        f"[이 학습자의 오답 이력]\n{hist_lines}"
    )


def opening_question(last_wrong_text, wrong_count):
    return (
        f"이 문제를 벌써 {wrong_count}번째 틀리셨네요. 지난번엔 **{last_wrong_text}**를 고르셨는데, "
        f"어떤 이유로 그걸 정답이라고 생각하셨는지 편하게 설명해주실 수 있을까요? "
        f"정답이 아니어도 괜찮으니 그때 든 생각을 그대로 말씀해주세요."
    )


def chat_reply(client, context_block, history, strategy_block=""):
    """history: [{"role": "user"|"model", "text": str}, ...]"""
    contents = [
        types.Content(role=m["role"], parts=[types.Part(text=m["text"])])
        for m in history
    ]
    system_text = TUTOR_SYSTEM_PROMPT + "\n\n" + context_block
    if strategy_block:
        system_text += "\n\n[학습 전략 컨텍스트 — 답변에 자연스럽게 반영하세요]\n" + strategy_block
    config = types.GenerateContentConfig(
        system_instruction=system_text,
        temperature=0.6,
    )
    resp = client.models.generate_content(model=MODEL_CHEAP, contents=contents, config=config)
    return resp.text


_VARIANT_RULES = """이 변형 문제의 목적은 학습자가 "정말 이 개념을 이해했는지"를 확인하고,
아니라면 이해할 수 있게 도와주는 것입니다. 아래 스펙트럼 중, 이 학습자의 상황(오답 횟수, 과목 위험도)에
가장 적합한 난이도를 당신이 직접 판단해서 문제를 만드세요.

- 오답 횟수가 적거나(1~2회) 이 과목이 안전권이면: 단순 보기 순서 재배치가 아니라, 그 개념이 "왜" 그런지
  또는 실제로 어떻게 적용/구분되는지를 묻는 "개념 이해 확인형"으로 만드세요.
- 오답 횟수가 많거나(3회 이상) 이 과목이 과락 위험군이면: 개념노트의 "빈칸 채우기" 카드처럼, 개념의
  정의/설명과 개념 이름을 짝짓는 형태로 훨씬 쉽게 낮추세요. 단, 매번 같은 틀을 쓰지 말고 아래처럼
  다양하게 섞어서 내세요:
  · (정의 → 이름) "다음 설명에 해당하는 것은? [정의문]" 보기는 개념 이름 4개 중 하나
  · (이름 → 정의) "OOO(정답 개념)에 대한 설명으로 옳은 것은?" 보기는 설명 4개 중 하나
  · (빈칸형) 원래 해설 문장의 핵심 개념 이름 자리를 빈칸(____)으로 비우고, 그 자리에 들어갈 말을
    보기 4개 중에서 고르게 하기
- 그 중간 상황이면 두 방식 사이에서 적절히 판단하세요.

공통 제약(반드시 지키세요):
- 완전히 새로운 시나리오, 업종, 줄거리, 등장인물을 만들지 마세요. 원래 문제의 소재를 그대로 유지하세요.
- 계산이나 지나친 응용을 요구하지 말고, 순수하게 개념 이해/구분 여부만 확인하세요.
- 객관식 4지선다, 오직 하나만 정답.
- 해설에는 왜 그 답이 맞고 나머지가 틀렸는지 설명을 포함하세요.
- 반드시 한국어로 작성하세요."""


def generate_variant_question(client, subject_label, question, choices, correct_text, explanation,
                               wrong_count=1, subject_status="", strategy_block=""):
    prompt = f"""다음은 IT 자격증 시험의 기존 문제입니다. 같은 개념을 확인할 수 있는 변형 문제를 하나 만들어주세요.

- 과목: {subject_label} ({subject_status or '위험도 정보 없음'})
- 기존 문제: {question}
- 기존 보기: {', '.join(choices)}
- 기존 정답: {correct_text}
- 기존 해설: {explanation}
- 이 학습자가 이 문제(원문+이전 변형 포함)를 틀린 횟수: {wrong_count}회
{('- 학습 전략 컨텍스트:\n' + strategy_block) if strategy_block else ''}

{_VARIANT_RULES}"""
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=VARIANT_SCHEMA,
        temperature=0.4,
    )
    resp = client.models.generate_content(model=MODEL_ACCURATE, contents=prompt, config=config)
    return json.loads(resp.text)


def generate_study_plan(client, exam_label, d_day, subject_stats, overall_stats, daily_target,
                         weak_tags=None, available_rounds=None, strategy_block=""):
    stats_lines = "\n".join(
        f"- {s['label']}: 오답률 {s['rate']}% ({s['wrong']}/{s['seen']}회)" for s in subject_stats
    ) or "(아직 과목별 데이터 없음)"
    weak_tags = weak_tags or []
    tag_lines = "\n".join(
        f"- {t['label']} · {t['tag']}: 오답 {t['wrong']}/{t['seen']}회" for t in weak_tags
    ) or "(아직 반복 오답 개념 데이터 없음)"
    rounds_text = ", ".join(available_rounds or []) or "(회차별 기출 데이터 없음)"
    d_day_text = f"{d_day}일" if d_day is not None else "미설정"
    strategy_section = f"\n{strategy_block}\n" if strategy_block else ""
    prompt = f"""당신은 '{exam_label}' 시험을 준비하는 노베이스 학습자의 전담 학습 코치이자 합격 전략 컨트롤타워입니다.
{strategy_section}
- 시험까지 남은 일수: {d_day_text}
- 지금까지 누적 풀이 {overall_stats['seen']}문제, 정답률 {overall_stats['rate']}%
- 과목별 오답 현황:
{stats_lines}
- 자주 틀리는 세부 개념(태그):
{tag_lines}
- 이 앱에서 풀 수 있는 회차별 기출 목록: {rounds_text}
- 오늘 목표 문제 수: {daily_target}개

과락 위험 과목이 있다면 그 과목을 최우선으로 배정하고, 안전권 과목은 유지 수준으로만 배분하는 등
"합격"이라는 목표에 맞춰 시간을 배분하세요.

이 데이터를 바탕으로 남은 기간 학습 계획을 세워주세요. 단, 반드시 아래처럼 "무엇을 어떻게" 할지
구체적인 실행 항목으로 제시하세요. "OO 과목을 더 공부하세요" 같은 뭉뚱그린 조언은 금지입니다.

톤은 무조건 응원조로만 쓰지 마세요. 데이터가 안 좋으면 안 좋다고 솔직하게 말하세요:
- 과락 위험 과목이 있거나 시험이 며칠 안 남았는데 진도가 부족하면, "이대로 가면 이 과목 과락입니다",
  "지금 페이스면 떨어질 확률이 높아요" 처럼 현실적인 결과를 돌려 말하지 말고 직접적으로 경고하세요.
- 특정 개념을 계속 틀리고 있다면 "이 개념 또 틀리면 실전에서도 못 풀어요, 오늘 반드시 잡고 가세요"처럼
  따끔하게 말해도 됩니다.
- 반대로 정답률이 좋거나 안전권인 과목이 있다면 형식적인 말고 구체적으로 뭘 잘하고 있는지 진심으로
  칭찬하세요. 잘하는 것까지 걱정조로 말하지 마세요.
- 계획 전체를 한 가지 톤(항상 다정하게만, 또는 항상 겁만 주기)으로 쓰지 말고, 실제 데이터에 따라
  경고할 부분은 경고하고 칭찬할 부분은 칭찬하며 섞어서 쓰세요.

실행 항목 예시 형식(이런 식으로, 실제 데이터에 맞게 구체적으로):
- "자주 틀리는 세부 개념" 중 반복 오답이 많은 개념이 있다면, 그 개념명을 콕 집어 "유튜브에서 '◯◯(개념명) 정보처리기사'로 검색해서 강의 영상 하나 보기"처럼 제안
- 과목별 오답률이 특히 높은 과목이 있다면, "이 앱의 CBT 모드 > 실전(무작위 조합)에서 [그 과목]만 골라 20문제 다시 풀기"처럼 앱 기능과 연결해서 제안
- 회차별 기출 목록 중 아직 안 풀었거나 오답이 많았을 법한 회차가 있다면, "CBT 모드 > 실전(회차별 기출)에서 [특정 연도/회차] 다시 풀어보기"처럼 구체적 회차명을 언급
- 시험까지 남은 일수에 맞춰 오늘/이번 주에 우선 할 일 1~2가지를 콕 집어 제시

너무 길지 않게, 위 스타일의 구체적 실행 항목 위주로 한국어로 작성하세요."""
    config = types.GenerateContentConfig(temperature=0.5)
    resp = client.models.generate_content(model=MODEL_CHEAP, contents=prompt, config=config)
    return resp.text


def generate_related_concepts(client, subject_label, question, choices, correct_text, explanation, tag_label=""):
    """오답 해설 밑에 붙이는 짧은 '헷갈리기 쉬운 인접 개념' 노트. 학습자가 방금 튼 세부 사실 하나만
    교정받고 끝나는 게 아니라, 같은 개념 안에서 비슷하게 헷갈릴 수 있는 다른 갈래도 같이 짚어준다."""
    prompt = f"""IT 자격증 시험 학습자가 아래 문제를 풀고 해설을 봤습니다. 이 학습자가 "이 문제에서 물어본
것 하나만" 교정받고 끝나서, 같은 개념의 다른 갈래는 여전히 헷갈릴 수 있는 상황입니다.

- 과목: {subject_label}
- 개념 태그: {tag_label or '(태그 없음)'}
- 문제: {question}
- 보기: {', '.join(choices)}
- 정답: {correct_text}
- 해설: {explanation}

이 문제와 같은 개념 범주에서, 학습자가 자주 헷갈리는 인접 개념 2~4개를 아주 짧게 정리해주세요.
- 각 항목은 "개념명 — 핵심 구분 포인트" 형식의 한 줄로
- 이 문제와 정답/보기가 겹치지 않는, 진짜 "인접하지만 다른" 개념만 (같은 말 반복 금지)
- 군더더기 설명 없이 불릿만, 전체 3~4줄 이내
- 정리할 만한 인접 개념이 뚜렷하지 않으면 억지로 만들지 말고 "이 문제는 단독 개념이라 더 헷갈릴 인접 개념은 적어요." 한 줄만 반환"""
    config = types.GenerateContentConfig(temperature=0.3)
    resp = client.models.generate_content(model=MODEL_CHEAP, contents=prompt, config=config)
    return resp.text


MINDMAP_SCHEMA = {
    "type": "object",
    "properties": {
        "categories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["id", "label"],
            },
        },
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "category": {"type": "string"},
                    "summary": {"type": "string"},
                    "theory": {"type": "string"},
                    "parent_concept": {"type": "string"},
                    "covers": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["id", "label", "category", "summary", "theory", "parent_concept", "covers"],
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["from", "to", "reason"],
            },
        },
    },
    "required": ["categories", "concepts", "edges"],
}


def generate_concept_mindmap(client, subject_label, items, mode="overview"):
    """과목 하나에 속한 실제 문제들(items: [{"idx", "question", "wrong"}, ...])을 3단계 구조로
    정리한다: 상위 카테고리(categories) -> 1차 개념(concepts, parent_concept 없음, 기본 표시) ->
    그 아래 파생/세부 개념(concepts, parent_concept로 부모를 가리킴, 부모를 클릭해야 펼쳐짐).
    이 앱에는 문제별 세부 개념 태그가 따로 없어서(회차별 CBT 데이터는 tag가 회차명일 뿐), 태그 대신
    문제 본문을 보고 AI가 직접 계층을 만들고 이름을 붙이게 한다. concepts[].covers는 그 개념에
    해당하는 items의 idx 목록. summary는 그래프에 항상 보이는 한 줄 요약, theory는 노드를 클릭했을
    때 펼쳐 보여줄 좀 더 자세한 이론 설명이다.

    mode="overview" (개념노트): items에 그 과목의 개념 카드 "전체"가 빠짐없이 들어온다. 오답 여부와
    무관하게 전체 그림을 보여주는 것이 목적이라, 모든 문제가 반드시 어딘가의 covers에 포함되어야
    하고 theory도 오답/헷갈림 얘기가 아니라 중립적인 정의+출제 포인트로 쓴다.
    mode="weak" (AI 코치): items는 이미 실제로 틀린 문제만 걸러져 들어온다. "약점 지도"가 목적이라
    theory는 시험에서 왜/어떻게 헷갈리는지에 초점을 맞춘다."""
    n = len(items)
    lines = "\n".join(f"{it['idx']}. {it['question']}" for it in items)

    if mode == "weak":
        intro = f"""'{subject_label}' 과목에서 학습자가 실제로 틀린 적 있는 문제 목록입니다. 이 문제들을
바탕으로 학습자가 지금 어떤 개념에서 약한지 한눈에 파악할 수 있는 마인드맵을 만들어주세요."""
        theory_rule = ("theory: 클릭했을 때 보여줄 조금 더 자세한 설명(2~3문장, 80자 이내) — "
                        "\"무엇인지 + 시험에서 왜/어떻게 헷갈리는지\"를 담아서, 학습자가 이거 하나만 "
                        "읽어도 감을 잡게 하세요.")
        edge_rule = ("같은 카테고리에 안 속해도 정말 관련 있거나(시험에서 자주 헷갈리는/비교되는) "
                     "경우에만 edges로 연결하세요")
    else:
        intro = f"""'{subject_label}' 과목의 개념 카드 전체 목록입니다({n}개, 오답 여부와 무관하게 이
과목의 모든 카드가 포함되어 있습니다). 학습자가 이 과목의 전체 구조를 한눈에 파악할 수 있는
마인드맵을 만들어주세요. 오답 위주로 편향시키지 말고, 목록에 있는 개념을 빠짐없이 담아 구조화하는
것이 목표입니다."""
        theory_rule = ("theory: 클릭했을 때 보여줄 조금 더 자세한 설명(2~3문장, 80자 이내) — 오답이나 "
                        "헷갈림 얘기가 아니라 \"이 개념이 정확히 무엇인지 + 시험에서 어떤 형태로 자주 "
                        "출제되는지\"를 중립적으로 설명하세요.")
        edge_rule = ("같은 카테고리에 안 속해도 원리를 공유하거나 함께 이해하면 좋은 개념끼리만 "
                     "(예: 같은 상위 개념에서 파생됐거나, 서로 비교하며 배우는 짝 개념) edges로 연결하세요. "
                     "오답/헷갈림과는 무관하게, 순수하게 개념 구조상 관련성만 보고 판단하세요")

    prompt = f"""{intro}

문제 목록 (번호. 문제 요약):
{lines}

세부 개념은 처음엔 숨겨져 있다가 1차 개념을 클릭하면 펼쳐지는 구조라, 화면이 복잡해질 걱정 없이
깊이 있게 만들어도 됩니다.

작업 순서:
1. 먼저 이 과목을 3~8개의 큰 카테고리(상위 분류)로 나누세요. 예: "프로세스 관리", "네트워크",
   "소프트웨어 설계", "테스트/품질" 처럼 교과서 목차 수준의 큰 갈래여야 합니다. 카테고리명은
   10자 이내로 짧게.
2. 각 카테고리 아래에 1차 개념(parent_concept를 빈 문자열로)을 만드세요. 문제 문구를 그대로 쓰지
   말고 "결합도 종류", "정규화 단계"처럼 간결한 개념명(12자 이내)을 새로 지으세요. 개수는 카테고리당
   3~8개 정도로, 목록에 있는 문제 수({n}개)에 맞춰 필요한 만큼 유연하게 늘리세요 — 문제 수가 많으면
   1차 개념도 그만큼 많아야 합니다.
3. 각 1차 개념 아래에 세부/파생 개념(parent_concept에 그 1차 개념의 id를 지정)을 만드세요. 원칙은
   목록의 문제 하나당 세부 개념 하나이되, 내용이 사실상 같거나 아주 밀접한 문제끼리는 세부 개념
   하나에 covers로 함께 묶어도 됩니다. 예: 1차 개념 "결합도 종류" 아래에 "내용 결합도", "공통 결합도",
   "스탬프 결합도"처럼.
   **가장 중요한 원칙: 문제 목록의 모든 번호(0~{n - 1})가 반드시 어딘가의 개념(1차 또는 세부)의
   covers에 최소 한 번은 포함되어야 합니다. 하나도 빠뜨리지 마세요.** 세부 개념이 있다면 가능한 한
   세부 개념 쪽에, 없으면 1차 개념에 covers를 넣으세요.
4. 각 개념 노드는 반드시 1단계에서 만든 카테고리 중 하나(category)에 속해야 합니다(세부 개념은
   부모와 같은 카테고리). 카테고리가 비어있으면 안 됩니다.
5. 각 개념에 두 가지 텍스트를 쓰세요:
   - summary: 그래프에 항상 보이는 한 줄 요약(20자 이내)
   - {theory_rule}
6. 개념 노드끼리, {edge_rule}. 애매하면 연결하지 마세요. 연결선은 1차 개념 수준에서만 만들고
   (세부 개념끼리는 굳이 연결하지 않아도 됩니다 — 부모-자식 관계로 이미 묶여 있으니까요), 개수는
   1차 개념 수를 넘기지 마세요.
7. 각 연결의 이유(reason)는 8자 이내로 아주 짧게 (예: "강도 비교"). 그래프 위에 작게 표시됩니다."""
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=MINDMAP_SCHEMA,
        temperature=0.4,
        max_output_tokens=32768 if mode == "overview" else 8192,
    )
    resp = client.models.generate_content(model=MODEL_ACCURATE, contents=prompt, config=config)
    return json.loads(resp.text)


def generate_custom_mindmap_seed(client, exam_label, topic):
    """'나만의 마인드맵'의 초기 뼈대. 문제 목록이 아니라 학습자가 직접 입력한 주제(topic)만 가지고
    AI가 카테고리/개념 초안을 제안하면, 그 위에 학습자가 직접 가지(개념)와 맨션(이론 메모)을
    추가/수정해 나간다. covers는 쓸 데가 없으니 항상 빈 배열."""
    prompt = f"""'{exam_label}' 시험을 준비하는 학습자가 '{topic}'라는 주제로 직접 마인드맵을
만들려고 합니다. 학습자가 그대로 써도 되고 고쳐도 되는 초안을 만들어주세요.

작업 순서:
1. 이 주제를 3~5개의 카테고리(상위 분류)로 나누세요. 카테고리명은 10자 이내로 짧게.
2. 각 카테고리 아래에 1차 개념(parent_concept를 빈 문자열로)을 3~6개씩 만드세요. 개념명은
   12자 이내로 짧게.
3. 필요하면 1차 개념 중 일부에 세부/파생 개념(parent_concept로 부모 id를 가리킴)을 1~3개씩
   추가하세요. 전체 개념(1차+세부) 수는 20개를 넘기지 마세요.
4. 각 개념 노드는 반드시 하나의 카테고리(category)에 속해야 합니다.
5. 각 개념에 summary(20자 이내 한 줄 요약)와 theory(클릭하면 보이는 2~3문장·80자 이내 이론
   설명 초안)를 쓰세요. 학습자가 나중에 자유롭게 고칠 초안이니 너무 완벽하지 않아도 됩니다.
6. 원리를 공유하거나 함께 이해하면 좋은, 정말 관련 있는 개념끼리만 edges로 연결하세요
   (reason은 8자 이내로 짧게).
7. concepts[].covers는 항상 빈 배열([])로 두세요(이 마인드맵은 특정 문제와 연결되지 않습니다)."""
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=MINDMAP_SCHEMA,
        temperature=0.5,
    )
    resp = client.models.generate_content(model=MODEL_ACCURATE, contents=prompt, config=config)
    return json.loads(resp.text)


def generate_mindmap_insight(client, subject_label, weak_concepts):
    """약점 지도(오답 마인드맵)를 만든 다음, 그 아래에 붙이는 짧은 총평. 그래프만 보고 끝내지 않고
    "지금 뭘 헷갈리고 있는지"를 말로 한 번 더 짚어준다. weak_concepts: [{"label","summary"}, ...]."""
    lines = "\n".join(f"- {c['label']}: {c.get('summary', '')}" for c in weak_concepts)
    prompt = f"""'{subject_label}' 과목에서 학습자가 자주 틀리는 개념들입니다:
{lines}

이 목록을 보고, 학습자가 지금 어떤 부분에서 취약하고 무엇과 무엇을 헷갈리고 있는지 3~5문장으로
분석해주세요. 개념명을 구체적으로 언급하면서, 왜 그 개념들이 서로 헷갈리기 쉬운지도 짚어주세요.
"더 공부하세요" 같은 뭉뚱그린 조언 말고, 이 데이터에서만 나올 수 있는 구체적인 분석으로 써주세요."""
    config = types.GenerateContentConfig(temperature=0.4)
    resp = client.models.generate_content(model=MODEL_CHEAP, contents=prompt, config=config)
    return resp.text
