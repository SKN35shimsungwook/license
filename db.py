# -*- coding: utf-8 -*-
"""SQLite 데이터 접근 계층. app.py는 이 모듈을 통해서만 DB에 접근한다.
여러 시험(exam)을 한 DB에서 다루므로, 사용자 기록 조회는 대부분 exam으로 스코프한다."""
import datetime
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "quiz.db")


def get_connection():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def get_all_questions(con, exam):
    return con.execute("SELECT * FROM questions WHERE exam=? ORDER BY id", (exam,)).fetchall()


def get_cbt_rounds(con, exam):
    rows = con.execute(
        "SELECT DISTINCT round FROM questions WHERE exam=? AND source='cbt' AND round<>'' ORDER BY round",
        (exam,),
    ).fetchall()
    return [r["round"] for r in rows]


def get_question(con, qid):
    return con.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()


def record_attempt(con, user, question_id, chosen, is_correct):
    con.execute(
        "INSERT INTO attempts(user, question_id, chosen, is_correct, ts) VALUES (?,?,?,?,?)",
        (user, question_id, chosen, int(is_correct), datetime.datetime.now().isoformat()),
    )
    con.commit()


def get_overall_stats(con, user, exam):
    row = con.execute(
        """SELECT COUNT(*) AS seen, SUM(a.is_correct) AS correct
           FROM attempts a JOIN questions q ON a.question_id = q.id
           WHERE a.user=? AND q.exam=?""",
        (user, exam),
    ).fetchone()
    seen = row["seen"] or 0
    correct = row["correct"] or 0
    rate = round(correct / seen * 100) if seen else 0
    return {"seen": seen, "correct": correct, "rate": rate}


def get_per_question_stats(con, user, exam):
    """qid -> {seen, correct, wrong, last_result, last_chosen, last_ts}"""
    rows = con.execute(
        """SELECT a.question_id AS question_id, a.chosen AS chosen, a.is_correct AS is_correct, a.ts AS ts
           FROM attempts a JOIN questions q ON a.question_id = q.id
           WHERE a.user=? AND q.exam=? ORDER BY a.ts ASC""",
        (user, exam),
    ).fetchall()
    stats = {}
    for r in rows:
        qid = r["question_id"]
        s = stats.setdefault(
            qid,
            {"seen": 0, "correct": 0, "wrong": 0, "last_result": None, "last_chosen": None, "last_ts": None},
        )
        s["seen"] += 1
        if r["is_correct"]:
            s["correct"] += 1
            s["last_result"] = "O"
        else:
            s["wrong"] += 1
            s["last_result"] = "X"
        s["last_chosen"] = r["chosen"]
        s["last_ts"] = r["ts"]
    return stats


def get_wrong_attempt_history(con, user, qid):
    """이 문제에서 틀렸을 때 고른 보기 번호(1~4) 목록, 시간순."""
    rows = con.execute(
        "SELECT chosen FROM attempts WHERE user=? AND question_id=? AND is_correct=0 ORDER BY ts ASC",
        (user, qid),
    ).fetchall()
    return [r["chosen"] for r in rows]


def get_wrong_question_ids(con, user, exam):
    stats = get_per_question_stats(con, user, exam)
    hidden = get_hidden_note_ids(con, user)
    need, done = [], []
    for qid, s in stats.items():
        if s["wrong"] == 0 or qid in hidden:
            continue
        (need if s["last_result"] == "X" else done).append(qid)
    need.sort(key=lambda qid: stats[qid]["last_ts"], reverse=True)
    done.sort(key=lambda qid: stats[qid]["last_ts"], reverse=True)
    return need, done, stats


def get_tag_stats(con, user, exam):
    rows = con.execute(
        """
        SELECT q.subject AS subject, q.tag AS tag, a.question_id AS qid, a.is_correct AS is_correct
        FROM attempts a JOIN questions q ON a.question_id = q.id
        WHERE a.user = ? AND q.exam = ?
        """,
        (user, exam),
    ).fetchall()
    agg = {}
    for r in rows:
        key = (r["subject"], r["tag"])
        d = agg.setdefault(key, {"subject": r["subject"], "tag": r["tag"], "seen": 0, "wrong": 0, "qids": set()})
        d["seen"] += 1
        if not r["is_correct"]:
            d["wrong"] += 1
        d["qids"].add(r["qid"])
    result = [v for v in agg.values() if v["wrong"] > 0]
    result.sort(key=lambda v: (-v["wrong"], -(v["wrong"] / v["seen"])))
    return result


def get_subject_stats(con, user, exam):
    """취약과목 자동 우선순위: subject별 오답률."""
    rows = con.execute(
        """
        SELECT q.subject AS subject, a.is_correct AS is_correct
        FROM attempts a JOIN questions q ON a.question_id = q.id
        WHERE a.user = ? AND q.exam = ?
        """,
        (user, exam),
    ).fetchall()
    agg = {}
    for r in rows:
        d = agg.setdefault(r["subject"], {"subject": r["subject"], "seen": 0, "wrong": 0})
        d["seen"] += 1
        if not r["is_correct"]:
            d["wrong"] += 1
    result = list(agg.values())
    result.sort(key=lambda v: -(v["wrong"] / v["seen"]) if v["seen"] else 0)
    return result


def reset_user(con, user, exam):
    con.execute(
        "DELETE FROM attempts WHERE user=? AND question_id IN (SELECT id FROM questions WHERE exam=?)",
        (user, exam),
    )
    con.commit()


def clear_question_history(con, user, qid):
    con.execute("DELETE FROM attempts WHERE user=? AND question_id=?", (user, qid))
    con.commit()


def hide_note(con, user, qid):
    con.execute(
        "INSERT OR IGNORE INTO note_hidden(user, question_id, ts) VALUES (?,?,?)",
        (user, qid, datetime.datetime.now().isoformat()),
    )
    con.commit()


def hide_notes(con, user, qids):
    now = datetime.datetime.now().isoformat()
    con.executemany(
        "INSERT OR IGNORE INTO note_hidden(user, question_id, ts) VALUES (?,?,?)",
        [(user, qid, now) for qid in qids],
    )
    con.commit()


def get_hidden_note_ids(con, user):
    rows = con.execute("SELECT question_id FROM note_hidden WHERE user=?", (user,)).fetchall()
    return {r["question_id"] for r in rows}


def save_coach_message(con, user, qid, role, text):
    con.execute(
        "INSERT INTO coach_chat(user, question_id, role, text, ts) VALUES (?,?,?,?,?)",
        (user, qid, role, text, datetime.datetime.now().isoformat()),
    )
    con.commit()


def get_coach_messages(con, user, qid):
    rows = con.execute(
        "SELECT role, text FROM coach_chat WHERE user=? AND question_id=? ORDER BY ts ASC",
        (user, qid),
    ).fetchall()
    return [{"role": r["role"], "text": r["text"]} for r in rows]


def add_flag(con, user, qid):
    con.execute(
        "INSERT OR IGNORE INTO flags(user, question_id, ts) VALUES (?,?,?)",
        (user, qid, datetime.datetime.now().isoformat()),
    )
    con.commit()


def remove_flag(con, user, qid):
    con.execute("DELETE FROM flags WHERE user=? AND question_id=?", (user, qid))
    con.commit()


def is_flagged(con, user, qid):
    row = con.execute("SELECT 1 FROM flags WHERE user=? AND question_id=?", (user, qid)).fetchone()
    return row is not None


def get_flagged_ids(con, user, exam):
    rows = con.execute(
        """SELECT f.question_id AS question_id FROM flags f JOIN questions q ON f.question_id=q.id
           WHERE f.user=? AND q.exam=? ORDER BY f.ts DESC""",
        (user, exam),
    ).fetchall()
    return [r["question_id"] for r in rows]


def add_ox_wrong(con, user, concept_qid):
    con.execute(
        "INSERT OR REPLACE INTO ox_wrong(user, concept_qid, ts) VALUES (?,?,?)",
        (user, concept_qid, datetime.datetime.now().isoformat()),
    )
    con.commit()


def get_ox_wrong_ids(con, user, exam):
    rows = con.execute(
        """SELECT o.concept_qid AS concept_qid FROM ox_wrong o JOIN questions q ON o.concept_qid=q.id
           WHERE o.user=? AND q.exam=? ORDER BY o.ts DESC""",
        (user, exam),
    ).fetchall()
    return [r["concept_qid"] for r in rows]


def clear_ox_wrong(con, user, concept_qid=None):
    if concept_qid is None:
        con.execute("DELETE FROM ox_wrong WHERE user=?", (user,))
    else:
        con.execute("DELETE FROM ox_wrong WHERE user=? AND concept_qid=?", (user, concept_qid))
    con.commit()


def add_card_wrong(con, user, concept_qid):
    con.execute(
        "INSERT OR REPLACE INTO card_wrong(user, concept_qid, ts) VALUES (?,?,?)",
        (user, concept_qid, datetime.datetime.now().isoformat()),
    )
    con.commit()


def get_card_wrong_ids(con, user, exam):
    rows = con.execute(
        """SELECT c.concept_qid AS concept_qid FROM card_wrong c JOIN questions q ON c.concept_qid=q.id
           WHERE c.user=? AND q.exam=? ORDER BY c.ts DESC""",
        (user, exam),
    ).fetchall()
    return [r["concept_qid"] for r in rows]


def clear_card_wrong(con, user, concept_qid=None):
    if concept_qid is None:
        con.execute("DELETE FROM card_wrong WHERE user=?", (user,))
    else:
        con.execute("DELETE FROM card_wrong WHERE user=? AND concept_qid=?", (user, concept_qid))
    con.commit()


def get_study_goal(con, user, exam):
    row = con.execute(
        "SELECT exam_date, daily_target FROM study_goal WHERE user=? AND exam=?", (user, exam)
    ).fetchone()
    if row is None:
        return {"exam_date": None, "daily_target": 20}
    return {"exam_date": row["exam_date"], "daily_target": row["daily_target"]}


def set_study_goal(con, user, exam, exam_date, daily_target):
    con.execute(
        """INSERT INTO study_goal(user, exam, exam_date, daily_target) VALUES (?,?,?,?)
           ON CONFLICT(user, exam) DO UPDATE SET exam_date=excluded.exam_date, daily_target=excluded.daily_target""",
        (user, exam, exam_date, daily_target),
    )
    con.commit()


def get_today_solved_count(con, user, exam):
    today = datetime.date.today().isoformat()
    row = con.execute(
        """SELECT COUNT(*) AS c FROM attempts a JOIN questions q ON a.question_id=q.id
           WHERE a.user=? AND q.exam=? AND substr(a.ts,1,10)=?""",
        (user, exam, today),
    ).fetchone()
    return row["c"] or 0
