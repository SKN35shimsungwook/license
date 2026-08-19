# -*- coding: utf-8 -*-
"""표 데이터가 뒤섞인 문제(<테이블명> 마커가 있거나, 숫자가 줄줄이 붙어있는 패턴) 스캔."""
import csv
import re
import json

with open(r"C:\Users\playdata2\Desktop\skn35 report\license_quiz\data\cbt_questions.csv", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

hits = []
for r in rows:
    text = r["question"]
    # <표이름> 마커가 있으면 원본이 표였을 가능성이 높음
    has_table_marker = bool(re.search(r"<[가-힣A-Za-z]+>", text))
    # 숫자가 6자리 이상 연속으로 붙어있는 경우(값이 이어붙은 정황)
    has_long_digit_run = bool(re.search(r"\d{6,}", text))
    # 선택지 끝에 어색한 " -" 트레일링
    trailing_dash = any(r[c].rstrip().endswith("-") and not r[c].rstrip().endswith("--") for c in ["choice1", "choice2", "choice3", "choice4"])
    if has_table_marker or has_long_digit_run or trailing_dash:
        hits.append({
            "id": r["id"], "round": r["round"], "source": r["source"],
            "question": text, "c1": r["choice1"], "c2": r["choice2"],
            "c3": r["choice3"], "c4": r["choice4"],
        })

out_path = r"C:\Users\PLAYDA~1\AppData\Local\Temp\claude\C--Users-playdata2-Desktop-skn35-report\3de228d4-0842-49d7-9719-300b97c01a4f\scratchpad\table_noise_hits.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(hits, f, ensure_ascii=False, indent=1)
print(len(hits))
