# -*- coding: utf-8 -*-
"""표 데이터가 뒤섞인 문제 스캔.
- <표이름> 마커
- 숫자가 6자리 이상 연속으로 붙어있는 경우
- 선택지 끝의 어색한 트레일링 "-"
- 표 헤더 단어(도착시간/실행시간 등)가 공백 없이 붙어있는 경우
- "문자+숫자"(예: A06, P103)가 3번 이상 연속으로 나열된 경우(스케줄링 표 병합 흔적)
"""
import csv
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE, "data", "cbt_questions.csv")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_reports")
os.makedirs(OUT_DIR, exist_ok=True)

with open(PATH, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

TABLE_HEADER_WORDS = [
    "도착시간", "실행시간", "버스트시간", "버스트타임", "완료시간",
    "서비스시간", "대기시간", "우선순위", "반환시간", "처리시간", "요청시간",
]
GLUED_HEADER_RE = re.compile(
    "(?:" + "|".join(TABLE_HEADER_WORDS) + "){2,}"
)
SCHED_ROW_RE = re.compile(r"(?:[A-Za-z가-힣]\s?\d{1,3}\s?){3,}")

hits = []
for r in rows:
    text = r["question"]
    has_table_marker = bool(re.search(r"<[가-힣A-Za-z]+>", text))
    has_long_digit_run = bool(re.search(r"\d{6,}", text))
    trailing_dash = any(
        r[c].rstrip().endswith("-") and not r[c].rstrip().endswith("--")
        for c in ["choice1", "choice2", "choice3", "choice4"]
    )
    has_glued_header = bool(GLUED_HEADER_RE.search(text))
    has_sched_row = bool(SCHED_ROW_RE.search(text))
    if has_table_marker or has_long_digit_run or trailing_dash or has_glued_header or has_sched_row:
        hits.append({
            "id": r["id"], "round": r["round"], "source": r["source"],
            "question": text, "c1": r["choice1"], "c2": r["choice2"],
            "c3": r["choice3"], "c4": r["choice4"],
            "reasons": [name for name, flag in [
                ("table_marker", has_table_marker),
                ("long_digit_run", has_long_digit_run),
                ("trailing_dash", trailing_dash),
                ("glued_header", has_glued_header),
                ("sched_row", has_sched_row),
            ] if flag],
        })

out_path = os.path.join(OUT_DIR, "table_noise_hits.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(hits, f, ensure_ascii=False, indent=1)
print(len(hits))
