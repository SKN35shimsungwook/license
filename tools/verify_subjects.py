# -*- coding: utf-8 -*-
"""raw_cbt 원본(회차별 60문항, subject 필드 포함)과 cbt_questions.csv를 대조해서
과목(subject) 라벨이 원본과 다르게 들어간 문제가 있는지 전수 검사한다."""
import csv
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE, "data", "raw_cbt")
CSV_PATH = os.path.join(BASE, "data", "cbt_questions.csv")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_reports")
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, "subject_mismatches.json")

VALID_ROUNDS = {"2022_1", "2022_2", "2022_3", "2023_1", "2023_2", "2023_3",
                "2024_1", "2024_2", "2024_3", "2025_1", "2025_2", "2025_3", "2026_1"}


def norm(s):
    return re.sub(r"\s+", "", s)[:20]


with open(CSV_PATH, encoding="utf-8-sig") as f:
    csv_rows = list(csv.DictReader(f))

csv_by_round = {}
for r in csv_rows:
    if r["source"] != "cbt" or not r["round"]:
        continue
    csv_by_round.setdefault(r["round"], []).append(r)

mismatches = []
unmatched = []
for fn in sorted(os.listdir(RAW_DIR)):
    if not (fn.endswith(".json") and fn[:4].isdigit()):
        continue
    with open(os.path.join(RAW_DIR, fn), encoding="utf-8") as f:
        data = json.load(f)
    rnd = data.get("round")
    if rnd not in VALID_ROUNDS:
        continue
    candidates = csv_by_round.get(rnd, [])
    for q in data["questions"]:
        stem_prefix = norm(q["stem"])[:12]
        matches = [r for r in candidates if norm(r["question"])[:12] == stem_prefix]
        if not matches:
            continue  # 이미 다른 스크립트에서 별도로 다룬 결측 항목
        for r in matches:
            if int(r["subject"]) != q["subject"]:
                mismatches.append({
                    "round": rnd, "num": q["num"], "raw_subject": q["subject"],
                    "csv_id": r["id"], "csv_subject": r["subject"],
                    "stem": q["stem"][:50],
                })

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(mismatches, f, ensure_ascii=False, indent=1)
print(len(mismatches))
