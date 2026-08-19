# -*- coding: utf-8 -*-
"""data/questions.csv(개념) + data/cbt_questions.csv(기출, 있으면)를 읽어 SQLite DB를 만든다.
- questions 테이블: exam 컬럼으로 시험(정보처리산업기사/전기산업기사 등)을 구분한다.
- attempts/flags 등 사용자 기록 테이블은 재실행해도 보존된다.
"""
import csv
import os
import sqlite3

BASE_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(BASE_DIR, "data", "questions.csv")
CBT_CSV_PATH = os.path.join(BASE_DIR, "data", "cbt_questions.csv")
DB_PATH = os.path.join(BASE_DIR, "data", "quiz.db")


def _read_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [
            (
                r["exam"], int(r["subject"]), r["tag"], r["question"],
                r["choice1"], r["choice2"], r["choice3"], r["choice4"],
                int(r["answer"]), r["explanation"], int(r["core_id"]), r["source"],
                r.get("round", "") or "",
                1 if (r.get("ai_corrected", "") or "").strip() == "1" else 0,
                r.get("diagram", "") or "",
                r.get("qnum", "") or "",
            )
            for r in reader
        ]


def main():
    if not os.path.exists(CSV_PATH):
        raise SystemExit(f"CSV가 없습니다: {CSV_PATH}")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("DROP TABLE IF EXISTS questions")
    cur.execute("""
        CREATE TABLE questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam TEXT NOT NULL,
            subject INTEGER NOT NULL,
            tag TEXT NOT NULL,
            question TEXT NOT NULL,
            choice1 TEXT NOT NULL,
            choice2 TEXT NOT NULL,
            choice3 TEXT NOT NULL,
            choice4 TEXT NOT NULL,
            answer INTEGER NOT NULL,
            explanation TEXT NOT NULL,
            core_id INTEGER NOT NULL,
            source TEXT NOT NULL DEFAULT 'concept',
            round TEXT NOT NULL DEFAULT '',
            ai_corrected INTEGER NOT NULL DEFAULT 0,
            diagram TEXT NOT NULL DEFAULT '',
            qnum TEXT NOT NULL DEFAULT ''
        )
    """)

    rows = _read_rows(CSV_PATH) + _read_rows(CBT_CSV_PATH)
    cur.executemany(
        "INSERT INTO questions (exam, subject, tag, question, choice1, choice2, choice3, choice4, "
        "answer, explanation, core_id, source, round, ai_corrected, diagram, qnum) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_questions_exam ON questions(exam)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            question_id INTEGER NOT NULL REFERENCES questions(id),
            chosen INTEGER NOT NULL,
            is_correct INTEGER NOT NULL,
            ts TEXT NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_attempts_user ON attempts(user)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_attempts_q ON attempts(question_id)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            question_id INTEGER NOT NULL REFERENCES questions(id),
            ts TEXT NOT NULL,
            UNIQUE(user, question_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ox_wrong (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            concept_qid INTEGER NOT NULL REFERENCES questions(id),
            ts TEXT NOT NULL,
            UNIQUE(user, concept_qid)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS card_wrong (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            concept_qid INTEGER NOT NULL REFERENCES questions(id),
            ts TEXT NOT NULL,
            UNIQUE(user, concept_qid)
        )
    """)

    # 오답노트/자주 틀리는 개념에서 "삭제(숨김)"한 문제 (통계에는 영향 없음, 목록 표시에서만 제외)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS note_hidden (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            question_id INTEGER NOT NULL REFERENCES questions(id),
            ts TEXT NOT NULL,
            UNIQUE(user, question_id)
        )
    """)

    # AI 학습 코치와의 문제별 대화 기록 (다시 들어와도 이어서 볼 수 있게 보존)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS coach_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            question_id INTEGER NOT NULL REFERENCES questions(id),
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            ts TEXT NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_coach_chat_user_q ON coach_chat(user, question_id)")

    # 사용자별 D-day/학습 목표 설정 (시험별로 별도 저장)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS study_goal (
            user TEXT NOT NULL,
            exam TEXT NOT NULL,
            exam_date TEXT,
            daily_target INTEGER NOT NULL DEFAULT 20,
            PRIMARY KEY (user, exam)
        )
    """)

    con.commit()
    n_q = cur.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    n_a = cur.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    con.close()
    print(f"questions: {n_q}행, attempts: 기존 기록 {n_a}행 보존 -> {DB_PATH}")


if __name__ == "__main__":
    main()
