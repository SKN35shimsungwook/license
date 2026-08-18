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


def pick_cbt_pool(questions, cbt_ids, subjects, limit=None):
    ids = [qid for qid in cbt_ids if questions[qid]["subject"] in subjects]
    random.shuffle(ids)
    if limit:
        ids = ids[:limit]
    return ids


def pick_cbt_exam_pool(questions, cbt_ids, exam_cfg):
    ids = []
    for s, n in exam_cfg["exam_subject_counts"].items():
        subj_ids = [qid for qid in cbt_ids if questions[qid]["subject"] == s]
        random.shuffle(subj_ids)
        ids.extend(subj_ids[:n])
    return ids


def pick_cbt_round_pool(questions, cbt_ids, round_name):
    """회차별 기출 모의고사: 무작위 조합이 아니라 실제 그 회차에 출제된 문제 그대로, 원래 순서로 반환."""
    ids = [qid for qid in cbt_ids if questions[qid].get("round") == round_name]
    ids.sort(key=lambda qid: questions[qid]["id"])
    return ids


def _normalize_answer(s):
    return re.sub(r"\s+", "", s.strip().lower())


def answer_matches(user_input, correct_text):
    if not user_input or not user_input.strip():
        return False
    variants = {correct_text}
    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", correct_text)
    if m:
        variants.add(m.group(1).strip())
        variants.add(m.group(2).strip())
    u = _normalize_answer(user_input)
    return any(u == _normalize_answer(v) for v in variants if v)


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
