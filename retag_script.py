# -*- coding: utf-8 -*-
"""quiz_app(정보처리산업기사, 3과목 구조) 225문항을 공식 5과목 구조로 재태깅해
license_quiz/data/questions.csv 를 생성한다(1차 초안). PDF 기출/요약자료 확보 후
교차검증하여 오류 수정·중복 제거·부족 부분 보강 후 다시 업데이트할 예정."""
import csv
import os

SRC = os.path.join(os.path.dirname(__file__), "..", "quiz_app", "data", "questions.csv")
OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
OUT = os.path.join(OUT_DIR, "questions.csv")

TAG_TO_SUBJECT = {
    "운영체제 개요": 5, "프로세스": 5, "스케줄링": 5, "교착상태": 5, "기억장치 관리": 5,
    "가상기억장치": 5, "디스크 관리": 5, "파일 시스템": 5, "UNIX": 5, "데이터 통신": 5, "OSI·TCP/IP": 5,
    "SW공학 기초": 1, "개발 방법론": 1, "UML": 1, "구조적 분석": 1, "아키텍처 패턴": 1,
    "객체지향 기본": 1, "럼바우 분석기법": 1, "디자인 패턴": 1, "사용자 인터페이스": 1,
    "테스트": 2, "형상관리·빌드": 2,
    "C언어 기초": 4, "연산자": 4, "표준 입출력": 4, "제어문": 4, "배열과 포인터": 4,
    "함수": 4, "Python": 4, "웹 프로그래밍": 4, "객체지향 언어": 4,
    "결합도·응집도": 2, "프레임워크": 2, "재사용": 2,
    "스택과 큐": 2, "트리와 그래프": 2, "수식 표기법": 2, "정렬": 2, "해싱": 2,
    "DB 개념": 3, "키와 무결성": 3, "관계대수": 3, "정규화": 3, "시스템카탈로그·뷰": 3,
    "트랜잭션": 3, "SQL-DDL": 3, "SQL-DML": 3, "SQL-DCL": 3, "DB 기타": 3,
}
ROW_OVERRIDE = {225: 2}  # "디버깅"(DB 기타 태그) -> 소프트웨어개발
SUBJECT_LABEL = {
    1: "1과목 소프트웨어 설계", 2: "2과목 소프트웨어 개발", 3: "3과목 데이터베이스 구축",
    4: "4과목 프로그래밍 언어 활용", 5: "5과목 정보시스템 구축관리",
}


def main():
    with open(SRC, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    unmapped = set()
    for r in rows:
        old_id = int(r["id"])
        tag = r["tag"]
        subj = ROW_OVERRIDE.get(old_id) or TAG_TO_SUBJECT.get(tag)
        if subj is None:
            unmapped.add(tag)
            continue
        out_rows.append({
            "id": old_id, "exam": "ipe_industrial", "subject": subj, "tag": tag,
            "question": r["question"], "choice1": r["choice1"], "choice2": r["choice2"],
            "choice3": r["choice3"], "choice4": r["choice4"], "answer": int(r["answer"]),
            "explanation": r["explanation"], "core_id": old_id, "source": "concept",
        })

    if unmapped:
        raise SystemExit(f"매핑 안 된 태그 발견: {unmapped}")

    os.makedirs(OUT_DIR, exist_ok=True)
    fieldnames = ["id", "exam", "subject", "tag", "question", "choice1", "choice2",
                  "choice3", "choice4", "answer", "explanation", "core_id", "source"]
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    by_subj = {}
    for row in out_rows:
        by_subj.setdefault(row["subject"], 0)
        by_subj[row["subject"]] += 1
    print("총", len(out_rows), "문항 ->", OUT)
    for s in sorted(by_subj):
        print(f"  {SUBJECT_LABEL[s]}: {by_subj[s]}문항")


if __name__ == "__main__":
    main()
