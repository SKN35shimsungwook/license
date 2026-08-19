# -*- coding: utf-8 -*-
"""전체 문제 은행 구조적 오타/오염 점검. 결과를 파일로 저장(콘솔 mojibake 회피)."""
import csv
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE, "data", "cbt_questions.csv")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_reports")
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, "audit_report.txt")

with open(PATH, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

issues = []

# 1) 완전히 비었거나 공백뿐인 선택지 (그림/다이어그램 선택지라 텍스트 추출 실패)
for r in rows:
    choices = [r["choice1"], r["choice2"], r["choice3"], r["choice4"]]
    if any(not c.strip() for c in choices) or not r["question"].strip():
        issues.append(("BLANK_CHOICE", r["id"], r["round"], r["source"]))

# 2) 알려진 잡음 패턴(페이지 헤더/저작권 문구 잔재)
NOISE_RE = re.compile(r"\d*회\s*정보처리산업기사\s*필기|(?<!수\s)없습니다\.(?!\s*\()")
for r in rows:
    for field in ["choice1", "choice2", "choice3", "choice4"]:
        text = r[field]
        if re.search(r"\d*회\s*정보처리산업기사\s*필기", text):
            issues.append(("NOISE_HEADER", r["id"], field, text))
        # "없습니다." 가 문장 중간에 끼어있는 패턴(설명 문장이 아니라 선택지 자체인 경우만 의심)
        if "없습니다" in text and len(text) < 80:
            issues.append(("NOISE_SUSPECT", r["id"], field, text))

# 3) 중복 선택지 (같은 문항 내 4개 중 2개 이상 동일 텍스트)
for r in rows:
    choices = [r["choice1"].strip(), r["choice2"].strip(), r["choice3"].strip(), r["choice4"].strip()]
    if len(set(choices)) != 4:
        issues.append(("DUP_CHOICE", r["id"], r["round"], r["source"]))

# 4) answer 필드 범위 이상
for r in rows:
    try:
        a = int(r["answer"])
        if a < 1 or a > 4:
            issues.append(("BAD_ANSWER_RANGE", r["id"], r["answer"]))
    except Exception:
        issues.append(("BAD_ANSWER_TYPE", r["id"], r["answer"]))

# 5) 이상한 이중 띄어쓰기/붙어있는 단어 스플릿 패턴 힌트 (예: "감 소된다") - 단일 한글 사이 공백
SPLIT_RE = re.compile(r"[가-힣] [가-힣](?=[다요임됨함])")

# 6) 선택지가 전부 숫자인 문제: 정답으로 표시된 선택지의 값이 해설에 실제로 등장하는지
#    (다른 문제의 해설이 잘못 복사된 경우 등을 잡아냄)
NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")
for r in rows:
    choices = [r["choice1"].strip(), r["choice2"].strip(), r["choice3"].strip(), r["choice4"].strip()]
    if not all(NUM_RE.match(c) for c in choices):
        continue
    try:
        ans_idx = int(r["answer"]) - 1
    except ValueError:
        continue
    if not (0 <= ans_idx < 4):
        continue
    correct_val = choices[ans_idx]
    explanation = r.get("explanation", "")
    if correct_val not in explanation:
        issues.append(("ANSWER_EXPLANATION_MISMATCH", r["id"], correct_val, explanation[:60]))

# 7) 원본이 그림/도표에 의존하는데(예: "다음 그림에서") 해설도 구체적 근거 없이 얼버무리는 경우
#    -> 텍스트만으로는 풀 수 없는 문제로 의심
IMAGE_DEP_RE = re.compile(r"(다음|아래)\s*(그림|그래프|도표|다이어그램)")
VAGUE_EXP_RE = re.compile(r"그림.{0,6}따라|그림.{0,6}의해|구체적\s*(값|수치)은")
for r in rows:
    text = r["question"]
    if IMAGE_DEP_RE.search(text) and VAGUE_EXP_RE.search(r.get("explanation", "")):
        issues.append(("IMAGE_DEPENDENT_VAGUE_EXPLANATION", r["id"], text[:60]))

with open(OUT, "w", encoding="utf-8") as f:
    f.write(f"total rows: {len(rows)}\n")
    by_type = {}
    for it in issues:
        by_type.setdefault(it[0], []).append(it)
    for t, items in by_type.items():
        f.write(f"\n=== {t} ({len(items)}) ===\n")
        for it in items:
            f.write(str(it) + "\n")

print("done, issues:", len(issues))
