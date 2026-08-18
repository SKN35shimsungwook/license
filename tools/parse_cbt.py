# -*- coding: utf-8 -*-
"""2022~2026년 정보처리산업기사 기출 PDF를 컬럼 인식 재구성 후 파싱해
문항(과목/번호/보기4개/정답)과 해설(가능한 경우)을 추출한다.
결과를 라운드별 JSON으로 저장해 검수 후 최종 CSV로 합친다."""
import json
import os
import re

import pdfplumber

FILES = {
    "2021_1": r"C:\Users\playdata2\Downloads\2021년_산업기사필기기출문제\2021년1회_산업기사필기기출문제.pdf",
    "2021_2": r"C:\Users\playdata2\Downloads\2021년_산업기사필기기출문제\2021년2회_산업기사필기기출문제.pdf",
    "2022_1": r"C:\Users\playdata2\Downloads\22년_정보처리산업기사_필기_기출문제\2022년1회_산업기사 필기 기출문제.pdf",
    "2022_2": r"C:\Users\playdata2\Downloads\22년_정보처리산업기사_필기_기출문제\2022년2회_산업기사 필기 기출문제.pdf",
    "2022_3": r"C:\Users\playdata2\Downloads\22년_정보처리산업기사_필기_기출문제\2022년3회_산업기사 필기 기출문제.pdf",
    "2023_1": r"C:\Users\playdata2\Downloads\2023 정보처리산업기사필기 기출문제\2023년 1회_정보처리산업기사필기 기출문제.pdf",
    "2023_2": r"C:\Users\playdata2\Downloads\2023 정보처리산업기사필기 기출문제\2023년 2회_정보처리산업기사필기 기출문제.pdf",
    "2023_3": r"C:\Users\playdata2\Downloads\2023 정보처리산업기사필기 기출문제\2023년 3회_정보처리산업기사필기 기출문제.pdf",
    "2024_1": r"C:\Users\playdata2\Downloads\정보처리산업기사 필기 기출문제\1. 2024년1회_정보처리산업기사필기 기출문제.pdf",
    "2024_2": r"C:\Users\playdata2\Downloads\정보처리산업기사 필기 기출문제\2. 2024년2회_정보처리산업기사필기 기출문제.pdf",
    "2024_3": r"C:\Users\playdata2\Downloads\정보처리산업기사 필기 기출문제\3. 2024년3회_정보처리산업기사필기기출문제.pdf",
    "2025_1": r"C:\Users\playdata2\Downloads\2025년 정보처리산업기사 기출문제\2025년1회_정보처리산업기사필기 기출문제.pdf",
    "2025_2": r"C:\Users\playdata2\Downloads\2025년 정보처리산업기사 기출문제\2025년2회_정보처리산업기사필기 기출문제.pdf",
    "2025_3": r"C:\Users\playdata2\Downloads\2025년 정보처리산업기사 기출문제\2025년3회_정보처리산업기사 필기_기출문제.pdf",
    "2026_1": r"C:\Users\playdata2\Downloads\2026년1회_산업기사필기_기출문제.pdf",
}

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw_cbt")

SUBJECT_MAP = {
    "정보시스템": 1,
    "프로그래밍": 2,
    "데이터베이스": 3,
}

CIRCLE = "①②③④"
CTRL_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")
NOISE_RE = re.compile(r"^(정보처리산업기사.*|기출문제\s*&?\s*정답.*|저작권 안내|이 자료는.*|다른 매체.*|-\s*\d+\s*-?$|\d+회$|\d{4}년\s*\d+회.*|※.*|답란.*)")
# 페이지 경계에서 잘려 line 중간 위치에 섞여 들어오기도 하는 저작권 안내 문구 조각들
NOISE_SUBSTRINGS = [
    "허락 없이 복제", "용도로만 사용할 수 있습니다", "옮겨 실을 수 없으며",
    "상업적 용도로 사용할 수 없습니다", "저작권 안내", "시나공 카페",
    "기출문제 & 정답", "기출문제&정답",
]


def is_noise(line):
    if NOISE_RE.match(line):
        return True
    return any(s in line for s in NOISE_SUBSTRINGS)


def reconstruct_page(page, line_tol=3):
    chars = [c for c in page.chars if not CTRL_RE.search(c.get("text", ""))]
    if not chars:
        return []
    mid = page.width / 2
    left = [c for c in chars if c["x0"] < mid]
    right = [c for c in chars if c["x0"] >= mid]

    def lines_from(chs):
        chs = sorted(chs, key=lambda c: (round(c["top"] / line_tol), c["x0"]))
        lines = []
        cur_key, cur = None, []
        for c in chs:
            key = round(c["top"] / line_tol)
            if cur_key is None or key == cur_key:
                cur.append(c)
                cur_key = key
            else:
                lines.append("".join(x["text"] for x in sorted(cur, key=lambda x: x["x0"])))
                cur, cur_key = [c], key
        if cur:
            lines.append("".join(x["text"] for x in sorted(cur, key=lambda x: x["x0"])))
        return lines

    return lines_from(left) + lines_from(right)


def extract_lines(path):
    lines = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            lines.extend(reconstruct_page(page))
    return [l for l in lines if l.strip() and not is_noise(l.strip())]


def normalize_stem_key(s):
    """중복 판정용 정규화: 공백 제거 + 소문자화 + 특수문자 제거."""
    s = re.sub(r"\s+", "", s).lower()
    return re.sub(r"[^\w가-힣]", "", s)


def split_choices(line):
    """'① A② B' 같은 한 줄에 보기 두 개가 붙어있는 걸 분리."""
    parts = re.split(r"(?=[①②③④])", line)
    return [p.strip() for p in parts if p.strip()]


def parse_questions(lines):
    """질문 블록(과목 헤더 ~ '정답 및 해설' 전)에서 문항을 추출한다.
    문제 번호는 항상 1씩 증가한다는 사실을 이용해, 그 다음 기대되는 번호와
    일치하는 'N. ' 패턴만 새 문제 시작으로 인정한다(보기 안의 우연한 숫자.점 오탐 방지)."""
    questions = []
    subject = None
    cur = None  # {"num":..., "stem":[...], "choices":[]}
    next_expected = 1

    def flush():
        nonlocal cur
        if cur and cur["num"] is not None:
            choices = cur["choices"]
            if len(choices) >= 4:
                questions.append({
                    "num": cur["num"], "subject": subject,
                    "stem": " ".join(cur["stem"]).strip(),
                    "choices": [re.sub(r"^[①②③④]\s*", "", c).strip() for c in choices[:4]],
                })
        cur = None

    for raw in lines:
        line = raw.strip()
        if line.startswith("정답 및 해설") or line == "정답":
            flush()
            break
        m_subj = re.match(r"^제([1-5])과목\s*[:：]?\s*(.*)", line)
        if m_subj:
            flush()
            subject = int(m_subj.group(1))
            continue
        m_q = re.match(r"^(\d{1,3})[.\s]\s*(.*)", line)
        if m_q and int(m_q.group(1)) == next_expected:
            flush()
            cur = {"num": int(m_q.group(1)), "stem": [m_q.group(2)], "choices": []}
            next_expected += 1
            continue
        if cur is None:
            continue
        if "①" in line or "②" in line or "③" in line or "④" in line:
            cur["choices"].extend(split_choices(line))
        elif not cur["choices"]:
            cur["stem"].append(line)
        else:
            # 보기 문장이 다음 줄로 줄바꿈된 경우 마지막 보기에 이어붙인다
            cur["choices"][-1] = cur["choices"][-1] + " " + line
    flush()
    return questions


def parse_answer_key(lines):
    text = " ".join(lines)
    pairs = re.findall(r"(\d{1,3})\s*[.．]\s*([①②③④])", text)
    return {int(num): CIRCLE.index(mark) + 1 for num, mark in pairs}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    summary = []
    for name, path in FILES.items():
        if not os.path.exists(path):
            print("MISSING FILE:", path)
            continue
        lines = extract_lines(path)
        # 정답 및 해설 위치 찾기
        try:
            idx = next(i for i, l in enumerate(lines) if l.strip().startswith("정답 및 해설") or l.strip() == "정답")
        except StopIteration:
            idx = len(lines)
        q_lines = lines[:idx]
        tail_lines = lines[idx:]

        questions = parse_questions(q_lines)
        # 답안 그리드가 좌/우 컬럼으로 쪼개져 재구성되고, 해설이 있는 회차는
        # 그리드 나머지 절반이 해설 사이 더 뒤쪽에 나오기도 해서 전체를 훑는다
        # ('N.①' 패턴은 해설 문장에 우연히 나타나지 않아 안전하다)
        answers = parse_answer_key(tail_lines)

        for q in questions:
            q["answer"] = answers.get(q["num"])

        out_path = os.path.join(OUT_DIR, f"{name}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"round": name, "questions": questions, "n_answers": len(answers)}, f, ensure_ascii=False, indent=1)

        n_ok = sum(1 for q in questions if q["answer"] is not None)
        summary.append((name, len(questions), n_ok))

    print("round | parsed_q | with_answer")
    for s in summary:
        print(s)


if __name__ == "__main__":
    main()
