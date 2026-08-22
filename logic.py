# -*- coding: utf-8 -*-
"""문항 선택/채점 로직 + 시험별 설정. 여러 시험(exam)을 하나의 앱에서 다루기 위한 설정 테이블."""
import random
import re

EXAM_CONFIG = {
    "ipe_industrial": {
        "label": "정보처리산업기사",
        # 2022년 1회 필기부터 3과목 60문항 체계로 개편됨(2020~2021년까지는 구 5과목 체계였음, 실제 기출 PDF로 확인).
        "subject_label": {
            1: "1과목 정보시스템 기반 기술", 2: "2과목 프로그래밍 언어 활용", 3: "3과목 데이터베이스 활용",
        },
        "exam_subject_counts": {1: 20, 2: 20, 3: 20},
        "exam_min_correct": {1: 8, 2: 8, 3: 8},
        "exam_total_pass": 36,
        "points_per_q": 1,
        "time_limit_min": 90,
    },
    "electrical_industrial": {
        "label": "전기산업기사",
        "subject_label": {},
        "exam_subject_counts": {},
        "exam_min_correct": {},
        "exam_total_pass": 60,
        "points_per_q": 1,
    },
}

EXAM_ORDER = ["ipe_industrial", "electrical_industrial"]


def build_questions_index(rows):
    return {r["id"]: dict(r) for r in rows}


def get_core_groups(questions, subjects):
    groups = {s: {} for s in subjects}
    for qid, q in questions.items():
        if q["source"] != "concept":
            continue
        if q["subject"] not in groups:
            continue
        groups[q["subject"]].setdefault(q["core_id"], []).append(qid)
    return groups


def pick_pool(questions, subjects, limit=None):
    groups = get_core_groups(questions, subjects)
    pool = []
    for s in subjects:
        for variant_ids in groups.get(s, {}).values():
            pool.append(random.choice(variant_ids))
    random.shuffle(pool)
    if limit:
        pool = pool[:limit]
    # 문제 선택은 무작위로 하되, 화면에는 과목 순서대로 묶어서 보여준다(안정정렬이라 과목 내 순서는 그대로 유지).
    pool.sort(key=lambda qid: questions[qid]["subject"])
    return pool


def pick_exam_pool(questions, exam_cfg):
    groups = get_core_groups(questions, list(exam_cfg["exam_subject_counts"].keys()))
    ids = []
    for s, n in exam_cfg["exam_subject_counts"].items():
        core_ids = list(groups.get(s, {}).keys())
        random.shuffle(core_ids)
        subj_ids = [random.choice(groups[s][c]) for c in core_ids[:n]]
        ids.extend(subj_ids)
    return ids


def _dedupe_by_core(questions, ids):
    """같은 문제가 회차마다 반복 출제되면 core_id가 같다(예: 2022_1/2023_3/2025_1에 똑같이 나온
    '에러 검출 및 교정 코드' 문제). 이걸 그대로 두면 무작위 조합에서 우연히 같은 문제가 여러 번
    뽑혀서 한 세트 안에 똑같은 문제가 중복으로 나올 수 있다. source가 다르면 core_id가 우연히
    같아도 완전히 다른 문제일 수 있으므로 (source, core_id)로 묶어서 하나씩만 남긴다."""
    groups = {}
    for qid in ids:
        key = (questions[qid]["source"], questions[qid]["core_id"])
        groups.setdefault(key, []).append(qid)
    return [random.choice(qids) for qids in groups.values()]


def pick_cbt_pool(questions, cbt_ids, subjects, limit=None):
    ids = [qid for qid in cbt_ids if questions[qid]["subject"] in subjects]
    ids = _dedupe_by_core(questions, ids)
    random.shuffle(ids)
    if limit:
        ids = ids[:limit]
    # 문제 선택은 무작위로 하되, 화면에는 과목 순서대로 묶어서 보여준다(안정정렬이라 과목 내 순서는 그대로 유지).
    ids.sort(key=lambda qid: questions[qid]["subject"])
    return ids


def pick_cbt_exam_pool(questions, cbt_ids, exam_cfg):
    ids = []
    for s, n in exam_cfg["exam_subject_counts"].items():
        subj_ids = [qid for qid in cbt_ids if questions[qid]["subject"] == s]
        subj_ids = _dedupe_by_core(questions, subj_ids)
        random.shuffle(subj_ids)
        ids.extend(subj_ids[:n])
    return ids


def pick_cbt_round_pool(questions, cbt_ids, round_name):
    """회차별 기출 모의고사: 무작위 조합이 아니라 실제 그 회차에 출제된 문제 그대로, 원래 순서로 반환.
    과목 블록(1~20/21~40/41~60)이 원본과 같도록 과목 우선으로 정렬한다(과목 내부는 id 순).
    단, 나중에 복구되어 id가 훨씬 큰 문제(qnum에 실제 원본 문제 번호가 기록된 경우)는
    id 순서 대신 그 qnum이 가리키는 원래 위치에 끼워 넣는다."""
    ids = [qid for qid in cbt_ids if questions[qid].get("round") == round_name]
    by_subject = {}
    for qid in ids:
        by_subject.setdefault(questions[qid]["subject"], []).append(qid)

    result = []
    for subject in sorted(by_subject):
        group = by_subject[subject]
        known, unknown = [], []
        for qid in group:
            qnum = (questions[qid].get("qnum") or "").strip()
            if qnum.isdigit():
                known.append((int(qnum), qid))
            else:
                unknown.append(qid)
        unknown.sort(key=lambda qid: questions[qid]["id"])
        known.sort()
        subject_base = (subject - 1) * 20
        for qnum, qid in known:
            pos = max(0, min(qnum - subject_base - 1, len(unknown)))
            unknown.insert(pos, qid)
        result.extend(unknown)
    return result


_TRAILING_PUNCT_RE = re.compile(r"[.,!?~;:。，！？]+$")


def _normalize_answer(s):
    s = _TRAILING_PUNCT_RE.sub("", s.strip())
    return re.sub(r"\s+", "", s.lower())


def _answer_keyword_variants(correct_text):
    """정답 문자열에서 비교 후보(키워드) 집합을 뽑는다.
    "프록시(Proxy) 패턴"처럼 괄호가 문장 끝이 아니라 중간에 있어도 괄호 안/밖을 각각 후보로 잡고,
    "핵심어 + 범주어(패턴/기법/방식/구조 등)" 형태면 핵심어 하나만 입력해도 인정되도록 첫 단어도 후보에 넣는다."""
    variants = {correct_text}
    paren_stripped = re.sub(r"\s*\([^)]*\)", "", correct_text).strip()
    if paren_stripped:
        variants.add(paren_stripped)
    for m in re.finditer(r"\(([^)]+)\)", correct_text):
        inner = m.group(1).strip()
        if inner:
            variants.add(inner)
    words = paren_stripped.split()
    if len(words) >= 2:
        variants.add(words[0])
        variants.add("".join(words[:-1]))
    return {v for v in variants if v}


def answer_matches(user_input, correct_text):
    if not user_input or not user_input.strip():
        return False
    u = _normalize_answer(user_input)
    if not u:
        return False
    norm_variants = {_normalize_answer(v) for v in _answer_keyword_variants(correct_text)}
    norm_variants.discard("")
    if u in norm_variants:
        return True
    # 키워드 포함 매칭: 완전히 같지 않아도 핵심 키워드를 포함하면(또는 그 반대면) 정답으로 인정한다.
    # 너무 짧은 키워드(1자)로 우연히 맞는 걸 막기 위해 최소 길이를 둔다.
    return any(len(v) >= 2 and (v in u or u in v) for v in norm_variants)


def make_blank_sentence(explanation, answer_text):
    candidates = [answer_text]
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", answer_text)
    if m:
        candidates = [answer_text, m.group(1).strip()]
    for cand in candidates:
        if cand and cand in explanation:
            return explanation.replace(cand, "〔　　　　〕", 1)
    return None


def group_ids_by_tag(questions, ids):
    groups = {}
    for qid in ids:
        q = questions.get(qid)
        if q is None:
            continue
        key = (q["subject"], q["tag"])
        groups.setdefault(key, []).append(qid)
    return dict(sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])))


def build_ox_pool(concepts):
    pool = []
    for c in concepts:
        choices = [c["choice1"], c["choice2"], c["choice3"], c["choice4"]]
        correct_idx = c["answer"] - 1
        is_true = random.random() < 0.5
        if is_true:
            statement = choices[correct_idx]
        else:
            wrong_idx = random.choice([i for i in range(4) if i != correct_idx])
            statement = choices[wrong_idx]
        pool.append({
            "qid": c["id"], "subject": c["subject"], "tag": c["tag"], "source": c["source"], "stem": c["question"],
            "statement": statement, "truth": is_true, "explanation": c["explanation"],
        })
    random.shuffle(pool)
    return pool
