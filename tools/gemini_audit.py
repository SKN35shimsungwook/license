# -*- coding: utf-8 -*-
"""Gemini로 전체 문제 은행을 배치 단위로 훑어서, 문제 텍스트가 읽을 수 없거나(표/그림 병합 잔재 등),
선택지가 부적절하거나(중복/모호), 해설이 정답을 실제로 뒷받침하지 않는 경우를 찾아낸다.
결과는 tools/_reports/gemini_audit_hits.json 에 저장되고, 직접 수정은 하지 않는다(사람이 최종 검토 후 수정).
"""
import csv
import json
import os
import time
import tomllib

from google import genai
from google.genai import types

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE, "data", "cbt_questions.csv")
SECRETS_PATH = os.path.join(BASE, ".streamlit", "secrets.toml")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_reports")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, "gemini_audit_hits.json")
PROGRESS_PATH = os.path.join(OUT_DIR, "gemini_audit_progress.txt")

MODEL = "gemini-3.5-flash-lite"
BATCH_SIZE = 8

with open(SECRETS_PATH, "rb") as f:
    secrets = tomllib.load(f)
api_key = secrets["GEMINI_API_KEY"]

client = genai.Client(api_key=api_key)

with open(CSV_PATH, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "readable": {"type": "boolean"},
                    "choices_ok": {"type": "boolean"},
                    "answer_consistent": {"type": "boolean"},
                    "issue": {"type": "string"},
                },
                "required": ["id", "readable", "choices_ok", "answer_consistent", "issue"],
            },
        }
    },
    "required": ["results"],
}

SYSTEM_PROMPT = """당신은 한국 IT 자격증(정보처리산업기사) 4지선다 문제 은행의 데이터 품질 검수자입니다.
각 문제에 대해 아래 3가지를 판정하세요.

1) readable: 문제 지문이 사람이 읽고 이해할 수 있는 정상적인 한국어/코드/표 형식인가?
   (PDF 추출 과정에서 표나 단어가 뭉쳐 붙어 의미를 알 수 없게 된 경우 false)
2) choices_ok: 4개 선택지가 서로 명확히 구분되고(중복 없음), 형식이 정상인가?
3) answer_consistent: 표시된 정답(answer_index)이 해설(explanation) 내용과 실제로 일치하는가?
   (해설이 다른 문제 얘기를 하거나, 해설의 근거가 정답이 아닌 다른 선택지를 가리키면 false)

문제나 해설 자체의 사실관계가 미묘하게 의심스러워도, 확실히 틀렸다고 판단되는 경우에만 false로 표시하고
issue에 한 문장으로 이유를 쓰세요. 애매하면 true로 두고 issue는 비워두세요(과잉 신고 금지).
반드시 입력된 모든 id에 대해 결과를 반환하세요."""


def build_batch_prompt(batch):
    items = []
    for r in batch:
        items.append({
            "id": r["id"],
            "question": r["question"],
            "choice1": r["choice1"], "choice2": r["choice2"],
            "choice3": r["choice3"], "choice4": r["choice4"],
            "answer_index": r["answer"],
            "explanation": r.get("explanation", ""),
        })
    return json.dumps(items, ensure_ascii=False)


def main():
    all_hits = []
    checked = 0
    start_from = 0
    if os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH, encoding="utf-8") as f:
            start_from = int(f.read().strip() or 0)
    if os.path.exists(OUT_PATH) and start_from > 0:
        with open(OUT_PATH, encoding="utf-8") as f:
            all_hits = json.load(f)

    by_id = {r["id"]: r for r in rows}

    for i in range(start_from, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        prompt = build_batch_prompt(batch)
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_json_schema=SCHEMA,
                ),
            )
            data = json.loads(resp.text)
            for item in data.get("results", []):
                if not (item.get("readable") and item.get("choices_ok") and item.get("answer_consistent")):
                    r = by_id.get(item["id"], {})
                    all_hits.append({
                        "id": item["id"], "round": r.get("round", ""), "source": r.get("source", ""),
                        "question": r.get("question", ""),
                        "choices": [r.get("choice1", ""), r.get("choice2", ""), r.get("choice3", ""), r.get("choice4", "")],
                        "answer": r.get("answer", ""), "explanation": r.get("explanation", ""),
                        "readable": item.get("readable"), "choices_ok": item.get("choices_ok"),
                        "answer_consistent": item.get("answer_consistent"), "issue": item.get("issue", ""),
                    })
        except Exception as e:
            with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
                f.write(str(i))
            with open(OUT_PATH, "w", encoding="utf-8") as f:
                json.dump(all_hits, f, ensure_ascii=False, indent=1)
            with open(os.path.join(OUT_DIR, "gemini_audit_error.txt"), "a", encoding="utf-8") as f:
                f.write(f"batch starting at {i}: {e}\n")
            time.sleep(3)
            continue

        checked += len(batch)
        with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
            f.write(str(i + BATCH_SIZE))
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(all_hits, f, ensure_ascii=False, indent=1)
        with open(os.path.join(OUT_DIR, "gemini_audit_status.txt"), "w", encoding="utf-8") as f:
            f.write(f"checked={checked+start_from}/{len(rows)} hits={len(all_hits)}")

    with open(os.path.join(OUT_DIR, "gemini_audit_status.txt"), "w", encoding="utf-8") as f:
        f.write(f"DONE checked={len(rows)}/{len(rows)} hits={len(all_hits)}")


if __name__ == "__main__":
    main()
