# -*- coding: utf-8 -*-
"""2024년 회차(실제 해설 보유)에서 해설 텍스트를 문항에 매칭한다.
정답 보기 텍스트를 '앵커'로 해설 블롭에서 위치를 찾고, 앵커 위치 순서대로
텍스트를 잘라 각 문항의 해설 후보로 삼는다(순서 기반 추정이 아니라 내용 기반).
사람이 검수할 수 있도록 신뢰도(anchor_found)를 같이 남긴다."""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from parse_cbt import FILES, extract_lines, parse_answer_key, parse_questions  # noqa: E402

ROUNDS_WITH_EXPLANATION = ["2024_1", "2024_2", "2024_3"]
OUT_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "raw_cbt", "explanation_review.csv")


def anchor_text(q):
    if not q["answer"]:
        return None
    c = q["choices"][q["answer"] - 1].strip()
    return c if len(c) >= 2 else None


def find_anchor_pos(blob, anchor):
    pos = blob.find(anchor)
    if pos != -1:
        return pos, anchor
    for cut in (14, 10, 8, 6, 4):
        if len(anchor) > cut:
            pos = blob.find(anchor[:cut])
            if pos != -1:
                return pos, anchor[:cut]
    return -1, None


def process_round(name):
    lines = extract_lines(FILES[name])
    idx = next(i for i, l in enumerate(lines) if l.strip().startswith("정답 및 해설") or l.strip() == "정답")
    q_lines, tail_lines = lines[:idx], lines[idx:]
    questions = parse_questions(q_lines)
    answers = parse_answer_key(tail_lines)
    for q in questions:
        q["answer"] = answers.get(q["num"])

    blob_lines = [l for l in tail_lines if not re.match(r"^(\d{1,2}[.．][①②③④]){2,}", l.strip())]
    blob = re.sub(r"\s+", " ", " ".join(blob_lines))

    hits = []
    for q in questions:
        a = anchor_text(q)
        if not a:
            continue
        pos, matched = find_anchor_pos(blob, a)
        if pos != -1:
            hits.append((pos, q["num"], matched))
    hits.sort()

    explanations = {}
    for i, (pos, num, matched) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else min(pos + 400, len(blob))
        snippet = blob[pos:end].strip()
        explanations[num] = snippet

    rows = []
    for q in questions:
        rows.append({
            "round": name, "num": q["num"], "subject": q["subject"], "stem": q["stem"],
            "c1": q["choices"][0], "c2": q["choices"][1], "c3": q["choices"][2], "c4": q["choices"][3],
            "answer": q["answer"],
            "explanation": explanations.get(q["num"], ""),
            "anchor_found": q["num"] in explanations,
        })
    return rows


def main():
    all_rows = []
    for name in ROUNDS_WITH_EXPLANATION:
        all_rows.extend(process_round(name))

    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["round", "num", "subject", "stem", "c1", "c2", "c3", "c4", "answer", "explanation", "anchor_found"])
        writer.writeheader()
        writer.writerows(all_rows)

    found = sum(1 for r in all_rows if r["anchor_found"])
    print(f"total {len(all_rows)}, matched {found}, missing {len(all_rows) - found}")
    print("saved:", OUT_CSV)


if __name__ == "__main__":
    main()
