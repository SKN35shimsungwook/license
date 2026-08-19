# -*- coding: utf-8 -*-
"""전체 문제 은행 구조적 오타/오염 점검. 결과를 파일로 저장(콘솔 mojibake 회피)."""
import csv
import re

PATH = r"C:\Users\playdata2\Desktop\skn35 report\license_quiz\data\cbt_questions.csv"
OUT = r"C:\Users\PLAYDA~1\AppData\Local\Temp\claude\C--Users-playdata2-Desktop-skn35-report\3de228d4-0842-49d7-9719-300b97c01a4f\scratchpad\audit_report.txt"

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
