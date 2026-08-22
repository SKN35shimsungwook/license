# -*- coding: utf-8 -*-
import datetime
import os
import random
import time

import streamlit as st
import streamlit.components.v1 as components

import ai_coach
import build_db
import db
import logic

# ---------- DB 준비 (CSV가 DB보다 최신이면 재생성, attempts 등 사용자 기록은 보존) ----------
BASE_DIR = os.path.dirname(__file__)
CSV_PATHS = [
    os.path.join(BASE_DIR, "data", "questions.csv"),
    os.path.join(BASE_DIR, "data", "cbt_questions.csv"),
]


def _db_is_stale():
    if not os.path.exists(db.DB_PATH):
        return True
    db_mtime = os.path.getmtime(db.DB_PATH)
    for p in CSV_PATHS:
        if os.path.exists(p) and os.path.getmtime(p) > db_mtime:
            return True
    return False


if _db_is_stale():
    build_db.main()

con = db.get_connection()

st.set_page_config(page_title="자격증 퀴즈", page_icon="📘", layout="centered")

st.markdown("""
<style>
.pill { display:inline-block; padding:3px 9px; border-radius:999px; background:#3E5C9A; color:#fff;
        font-size:12px; font-weight:600; margin-right:4px; }
.pill-sub { background:#9CA3AF; }
.result-ok { background:#16A34A; color:#fff; padding:10px; border-radius:8px; font-weight:600; }
.result-bad { background:#DC2626; color:#fff; padding:10px; border-radius:8px; font-weight:600; }
.card-box { background:#F5F7FB; border-radius:12px; padding:16px; margin-bottom:10px; }
.group-title { font-weight:700; margin-top:14px; margin-bottom:4px; }
</style>
""", unsafe_allow_html=True)

# ---------- 로그인 게이트 (배포 후 무단 접근으로 인한 API 비용 방지) ----------
# Streamlit Cloud의 Secrets에 APP_PASSWORD 또는 APP_PATTERN을 설정하면 활성화된다.
# 로컬에서 secrets.toml에 둘 다 값이 없으면(=미설정) 게이트 없이 그냥 통과한다.
# APP_PATTERN은 PATTERN_GRID_SIZE x PATTERN_GRID_SIZE 표(1번~칸수 번)를 순서대로
# 누르는 방식으로, "1,5,9" 처럼 콤마로 구분된 칸 번호 순서로 지정한다.
PATTERN_GRID_SIZE = 3
ss = st.session_state
ss.setdefault("authed", False)
try:
    _app_password = st.secrets.get("APP_PASSWORD", "")
except Exception:
    _app_password = ""
try:
    _app_pattern_raw = st.secrets.get("APP_PATTERN", "")
except Exception:
    _app_pattern_raw = ""
try:
    _app_pattern = [int(x.strip()) for x in _app_pattern_raw.split(",") if x.strip()]
except ValueError:
    _app_pattern = []

if (_app_password or _app_pattern) and not ss.authed:
    st.title("📘 자격증 퀴즈")
    ss.setdefault("pattern_seq", [])

    if _app_password and _app_pattern:
        method = st.radio("입장 방법", ["비밀번호", "패턴"], horizontal=True, key="login_method")
    elif _app_password:
        method = "비밀번호"
    else:
        method = "패턴"

    if method == "비밀번호":
        pw = st.text_input("비밀번호", type="password", key="login_pw")
        if st.button("입장", key="login_submit"):
            if pw == _app_password:
                ss.authed = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸어요.")
    else:
        st.caption("표의 칸을 정해진 순서대로 눌러주세요.")
        clicked = None
        for r in range(PATTERN_GRID_SIZE):
            row_cols = st.columns(PATTERN_GRID_SIZE)
            for c in range(PATTERN_GRID_SIZE):
                cell_no = r * PATTERN_GRID_SIZE + c + 1
                if cell_no in ss.pattern_seq:
                    label = str(ss.pattern_seq.index(cell_no) + 1)
                else:
                    label = "・"
                if row_cols[c].button(label, key=f"pattern_cell_{cell_no}"):
                    clicked = cell_no
        if clicked is not None:
            if clicked not in ss.pattern_seq:
                ss.pattern_seq.append(clicked)
            st.rerun()

        col_a, col_b = st.columns(2)
        if col_a.button("다시 그리기", key="pattern_reset"):
            ss.pattern_seq = []
            st.rerun()
        if col_b.button("확인", key="pattern_submit"):
            if ss.pattern_seq == _app_pattern:
                ss.authed = True
                st.rerun()
            else:
                st.error("패턴이 틀렸어요.")
                ss.pattern_seq = []
    st.stop()

ss.setdefault("user", "")
ss.setdefault("exam", logic.EXAM_ORDER[0])
ss.setdefault("nav", "홈")

ss.setdefault("quiz_pool", [])
ss.setdefault("quiz_idx", 0)
ss.setdefault("quiz_answered", False)
ss.setdefault("quiz_correct", 0)
ss.setdefault("quiz_seen", 0)
ss.setdefault("quiz_subject", "전체")
ss.setdefault("quiz_return_nav", "퀴즈")
ss.setdefault("quiz_start_at", None)

ss.setdefault("cbt_mode", "연습")
ss.setdefault("cbt_subject", "전체")
ss.setdefault("cbt_pool", [])
ss.setdefault("cbt_submitted", False)
ss.setdefault("cbt_answers_store", {})
ss.setdefault("cbtp_choice_store", {})
ss.setdefault("cbt_view_mode", "전체 풀기")
ss.setdefault("cbt_page", 0)
ss.setdefault("cbt_batch_size", 4)
ss.setdefault("cbt_start_at", None)
ss.setdefault("cbtp_start_at", None)

ss.setdefault("concept_view", "카드")
ss.setdefault("concept_subject", "전체")
ss.setdefault("card_mode", "뒤집기")
ss.setdefault("card_pool", [])
ss.setdefault("card_idx", 0)
ss.setdefault("card_flipped", False)
ss.setdefault("card_results", {})

ss.setdefault("ox_pool", [])
ss.setdefault("ox_idx", 0)

ss.setdefault("coach_active_qid", None)
ss.setdefault("coach_messages", [])
ss.setdefault("coach_context", "")
ss.setdefault("coach_plan_text", "")
ss.setdefault("coach_variant_qid", None)
ss.setdefault("coach_variant", None)
ss.setdefault("coach_variant_result", None)
ss.setdefault("coach_variant_wrong_counts", {})
ss.setdefault("coach_batch_variants", {})
ss.setdefault("coach_batch_results", {})
ss.setdefault("coach_strategy", "")

ss.setdefault("input_mode", "마우스")

ss.setdefault("wrong_subject_filter", None)
ss.setdefault("tagstats_subject_filter", None)
ss.setdefault("bm_subject_filter", None)
ss.setdefault("wrong_source_filter", None)
ss.setdefault("tagstats_source_filter", None)
ss.setdefault("bm_source_filter", None)
ss.setdefault("coach_repeat_subject_filter", None)

if "_pending_nav" in ss:
    ss["nav"] = ss.pop("_pending_nav")
if "_pending_exam" in ss:
    ss["exam"] = ss.pop("_pending_exam")


def goto(nav_target):
    ss["_pending_nav"] = nav_target
    st.rerun()


NAV_ITEMS = ["홈", "퀴즈", "CBT 모드", "개념노트", "오답노트", "자주 틀리는 개념", "즐겨찾기",
             "AI 학습 코치", "나만의 마인드맵"]

with st.sidebar:
    st.title("📘 자격증 퀴즈")
    exam_options = logic.EXAM_ORDER
    exam_labels = {k: logic.EXAM_CONFIG[k]["label"] for k in exam_options}
    picked_exam = st.selectbox(
        "시험 선택", exam_options, format_func=lambda k: exam_labels[k],
        index=exam_options.index(ss.exam),
    )
    if picked_exam != ss.exam:
        ss.exam = picked_exam
        ss.quiz_pool = []
        ss.cbt_pool = []
        ss.card_pool = []
        ss.ox_pool = []
        st.rerun()

    ss.user = st.text_input("닉네임 (풀이 기록 저장용)", value=ss.user or "guest")
    st.radio("메뉴", NAV_ITEMS, key="nav")
    st.radio(
        "입력 방식", ["마우스", "키보드"], key="input_mode", horizontal=True,
        help="키보드 모드: 숫자 1~4로 보기 선택, ←/→로 이전·다음 문제 이동. "
             "스마트폰 등 터치 기기와 충돌하지 않도록 기본값은 마우스 모드예요.",
    )

exam_cfg = logic.EXAM_CONFIG[ss.exam]
QUESTIONS = logic.build_questions_index(db.get_all_questions(con, ss.exam))
CBT_IDS = [qid for qid, q in QUESTIONS.items() if q["source"] == "cbt"]
ALL_IDS = list(QUESTIONS.keys())  # 무작위 조합(연습/실전)에는 기출 + AI 신규문제를 함께 섞는다
ALL_SUBJECTS = sorted(exam_cfg["subject_label"].keys())

if not QUESTIONS:
    st.warning(f"'{exam_cfg['label']}' 문항 데이터가 아직 없어요. PDF/자료를 추가하면 여기에 채워집니다.")
    st.stop()


def subject_choices():
    return ["전체"] + [str(s) for s in ALL_SUBJECTS]


def subject_label(s):
    return exam_cfg["subject_label"].get(s, f"{s}과목")


def source_badge_text(q):
    if q["source"] == "cbt":
        parts = q["tag"].split("_")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            base = f"📄 {parts[0]}년 {parts[1]}회 기출"
        else:
            base = f"📄 {q['tag']} 기출" if q["tag"] else "📄 기출문제"
        if q.get("ai_corrected"):
            return base + " · 🛠️ AI보정"
        return base
    return "✏️ AI 신규문제"


def _render_tree_svg(spec):
    if "|labels:" in spec:
        edge_part, label_part = spec.split("|labels:", 1)
    else:
        edge_part, label_part = spec, ""
    labels = {}
    for kv in label_part.split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            labels[k] = v
    edges = [tuple(e.split(">")) for e in edge_part.split(",") if e]
    children, all_nodes, child_set = {}, [], set()
    for p, c in edges:
        children.setdefault(p, []).append(c)
        if p not in all_nodes:
            all_nodes.append(p)
        if c not in all_nodes:
            all_nodes.append(c)
        child_set.add(c)
    root = next(n for n in all_nodes if n not in child_set)

    positions = {}
    counter = [0]

    def layout(node, depth):
        kids = children.get(node, [])
        if not kids:
            x = counter[0]
            counter[0] += 1
            positions[node] = (x, depth)
            return x
        xs = [layout(k, depth + 1) for k in kids]
        x = sum(xs) / len(xs)
        positions[node] = (x, depth)
        return x

    layout(root, 0)
    n_leaves = max(1, counter[0])
    max_depth = max(d for _, d in positions.values())
    unit, r = 64, 17
    width = n_leaves * unit
    height = (max_depth + 1) * unit + 10

    def px(pos):
        x, y = pos
        return (x * unit + unit / 2, y * unit + unit / 2 + 5)

    parts = []
    for p, kids in children.items():
        x1, y1 = px(positions[p])
        for c in kids:
            x2, y2 = px(positions[c])
            parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#3E5C9A" stroke-width="2"/>')
    for node, pos in positions.items():
        x, y = px(pos)
        label = labels.get(node, node)
        parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="white" stroke="#3E5C9A" stroke-width="2"/>')
        parts.append(
            f'<text x="{x}" y="{y + 5}" text-anchor="middle" font-size="14" '
            f'font-family="sans-serif" fill="#1C2333">{label}</text>'
        )
    return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">{"".join(parts)}</svg>'


def _grid_parts(spec, unit, font_size=13):
    cells = []
    max_x = max_y = 0.0
    for part in spec.split(";"):
        if not part:
            continue
        vals = part.split(",")
        x, y, w, h = (float(v) for v in vals[:4])
        label = vals[4] if len(vals) > 4 else ""
        cells.append((x, y, w, h, label))
        max_x, max_y = max(max_x, x + w), max(max_y, y + h)
    parts = []
    for x, y, w, h, label in cells:
        px_x, px_y, px_w, px_h = x * unit, y * unit, w * unit, h * unit
        parts.append(
            f'<rect x="{px_x}" y="{px_y}" width="{px_w}" height="{px_h}" '
            f'fill="white" stroke="#3E5C9A" stroke-width="2"/>'
        )
        if label:
            parts.append(
                f'<text x="{px_x + px_w / 2}" y="{px_y + px_h / 2 + 5}" text-anchor="middle" '
                f'font-size="{font_size}" font-family="sans-serif" fill="#1C2333">{label}</text>'
            )
    return parts, max_x * unit, max_y * unit


def _render_grid_svg(spec):
    parts, width, height = _grid_parts(spec, 90)
    return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">{"".join(parts)}</svg>'


def _render_grids_grid_svg(spec):
    """선택지 여러 개가 각각 다른 레이아웃 그림인 문제용. spec은 '|'로 구분된 grid-spec 목록."""
    specs = spec.split("|")
    unit = 45
    label_h = 22
    panel_w = 2 * unit + 20
    panel_h = 2 * unit + label_h + 10
    cols = min(4, len(specs))
    rows = (len(specs) + cols - 1) // cols
    groups = []
    for i, s in enumerate(specs):
        col, row = i % cols, i // cols
        tx, ty = col * panel_w, row * panel_h
        parts, _, _ = _grid_parts(s, unit, font_size=10)
        label = "①②③④⑤⑥"[i] if i < 6 else str(i + 1)
        groups.append(
            f'<g transform="translate({tx},{ty})">'
            f'<text x="0" y="16" font-size="15" font-family="sans-serif" fill="#1C2333" font-weight="bold">{label}</text>'
            f'<g transform="translate(24,{label_h})">{"".join(parts)}</g></g>'
        )
    width, height = panel_w * cols, panel_h * rows
    return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">{"".join(groups)}</svg>'


def _digraph_parts(spec, cx, cy, radius, r, marker_id, loop_r=None):
    import math
    if loop_r is None:
        loop_r = max(8, r * 0.6)
    edges = [tuple(e.split(">")) for e in spec.split(",") if e]
    nodes = []
    for a, b in edges:
        if a not in nodes:
            nodes.append(a)
        if b not in nodes:
            nodes.append(b)
    n = max(1, len(nodes))
    pos = {}
    for i, node in enumerate(nodes):
        angle = -math.pi / 2 + 2 * math.pi * i / n
        pos[node] = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))

    parts = [
        f'<defs><marker id="{marker_id}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
        f'<path d="M0,0 L8,4 L0,8 Z" fill="#3E5C9A"/></marker></defs>'
    ]
    for a, b in edges:
        if a == b:
            # 노드 원둘레에 딱 붙어서 시작/끝나는 작은 루프(원 밖으로 살짝 튀어나온 손잡이 모양).
            # 자기 자신을 가리키는 화살표라는 게 한눈에 보이도록 노드에서 떨어뜨리지 않는다.
            x, y = pos[a]
            dx, dy = x - cx, y - cy
            dist = (dx ** 2 + dy ** 2) ** 0.5 or 1
            ox, oy = dx / dist, dy / dist  # 패널 중심에서 바깥쪽(노드 쪽) 방향
            tx_, ty_ = -oy, ox  # 접선 방향
            p1x, p1y = x + tx_ * r * 0.55 + ox * r * 0.7, y + ty_ * r * 0.55 + oy * r * 0.7
            p2x, p2y = x - tx_ * r * 0.55 + ox * r * 0.7, y - ty_ * r * 0.55 + oy * r * 0.7
            reach = r + loop_r * 2.3
            c1x, c1y = x + tx_ * loop_r * 1.4 + ox * reach, y + ty_ * loop_r * 1.4 + oy * reach
            c2x, c2y = x - tx_ * loop_r * 1.4 + ox * reach, y - ty_ * loop_r * 1.4 + oy * reach
            parts.append(
                f'<path d="M{p1x},{p1y} C{c1x},{c1y} {c2x},{c2y} {p2x},{p2y}" fill="none" '
                f'stroke="#3E5C9A" stroke-width="2" marker-end="url(#{marker_id})"/>'
            )
            continue
        x1, y1 = pos[a]
        x2, y2 = pos[b]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ddx, ddy = x2 - x1, y2 - y1
        dist = (ddx ** 2 + ddy ** 2) ** 0.5 or 1
        px, py = -ddy / dist, ddx / dist
        bulge = 16
        cxp, cyp = mx + px * bulge, my + py * bulge
        ang1 = math.atan2(cyp - y1, cxp - x1)
        sx1, sy1 = x1 + r * math.cos(ang1), y1 + r * math.sin(ang1)
        ang2 = math.atan2(cyp - y2, cxp - x2)
        sx2, sy2 = x2 + r * math.cos(ang2), y2 + r * math.sin(ang2)
        parts.append(
            f'<path d="M{sx1},{sy1} Q{cxp},{cyp} {sx2},{sy2}" fill="none" '
            f'stroke="#3E5C9A" stroke-width="2" marker-end="url(#{marker_id})"/>'
        )
    for node, (x, y) in pos.items():
        parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="white" stroke="#3E5C9A" stroke-width="2"/>')
        parts.append(
            f'<text x="{x}" y="{y + 5}" text-anchor="middle" font-size="14" '
            f'font-family="sans-serif" fill="#1C2333">{node}</text>'
        )
    return parts


def _render_digraph_svg(spec):
    radius, r, loop_r = 90, 20, 14
    loop_reach = r + loop_r * 2.3
    top_margin = radius + loop_reach + 15
    cx, cy = 150, top_margin
    parts = _digraph_parts(spec, cx, cy, radius, r, "arrow", loop_r)
    width, height = cx * 2, cy + radius + loop_reach + 15
    return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">{"".join(parts)}</svg>'


def _render_digraphs_grid_svg(spec):
    """선택지 여러 개가 각각 다른 방향그래프인 문제용. spec은 '|'로 구분된 edge-list 목록."""
    specs = spec.split("|")
    radius, r, loop_r = 42, 16, 11
    loop_reach = r + loop_r * 2.3
    label_h = 24
    panel_w = 190
    panel_h = int(label_h + radius + loop_reach + radius + loop_reach + 10)
    cols = min(4, len(specs))
    rows = (len(specs) + cols - 1) // cols
    cx, cy = panel_w / 2, label_h + radius + loop_reach
    groups = []
    for i, s in enumerate(specs):
        col, row = i % cols, i // cols
        tx, ty = col * panel_w, row * panel_h
        parts = _digraph_parts(s, cx, cy, radius, r, f"arrow{i}", loop_r)
        label = "①②③④⑤⑥"[i] if i < 6 else str(i + 1)
        groups.append(
            f'<g transform="translate({tx},{ty})">'
            f'<text x="10" y="20" font-size="15" font-family="sans-serif" fill="#1C2333" font-weight="bold">{label}</text>'
            f'{"".join(parts)}</g>'
        )
    width, height = panel_w * cols, panel_h * rows
    return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">{"".join(groups)}</svg>'


def _render_mindmap_interactive(categories, concepts, edges, weak_ids=None, expanded_ids=None,
                                 bridge_label="__mindmap_bridge__", height=560, show_weak=True):
    """옵시디언 그래프 뷰처럼 확대/이동/드래그가 되는 실제 인터랙티브 마인드맵.
    카테고리(상위 분류) -> 1차 개념 -> (펼치면 나오는) 세부 개념의 3단계 구조. parent_concept가
    있는 세부 개념은 그 부모가 expanded_ids에 있을 때만 그려서, 처음엔 안 복잡하다가 클릭한
    개념만 펼쳐지게 한다. vis-network를 CDN에서 불러와 렌더링하고, 노드를 클릭하면 그 id를
    숨은 텍스트 입력창(bridge_label)에 써 넣어서 파이썬 쪽에서 st.rerun 없이도 다음 rerun 때
    읽을 수 있게 한다.

    show_weak: AI 코치의 약점 지도에서만 True. 개념노트(전체 개념 지도)는 오답 여부와 무관한
    구조 정리가 목적이라, False로 넘어오면 자주 틀리는 개념 빨간 표시/범례를 아예 안 보여준다."""
    import json
    weak_ids = (weak_ids or set()) if show_weak else set()
    expanded_ids = expanded_ids or set()
    category_ids = {c["id"] for c in categories}
    children_by_parent = {}
    for c in concepts:
        parent = c.get("parent_concept") or ""
        if parent:
            children_by_parent.setdefault(parent, []).append(c["id"])

    visible_concepts = [c for c in concepts if not c.get("parent_concept")
                         or c["parent_concept"] in expanded_ids]
    visible_ids = {c["id"] for c in visible_concepts}

    vis_nodes = []
    for cat in categories:
        vis_nodes.append({
            "id": cat["id"],
            "label": cat["label"],
            "title": cat["label"],
            "shape": "ellipse",
            "color": {"background": "#3E5C9A", "border": "#2C4374",
                      "highlight": {"background": "#4A6BB0", "border": "#2C4374"}},
            "font": {"color": "white", "size": 16, "face": "sans-serif", "bold": True},
            "borderWidth": 2,
            "mass": 3,
        })
    for c in visible_concepts:
        is_weak = c["id"] in weak_ids
        n_children = len(children_by_parent.get(c["id"], []))
        is_expanded = c["id"] in expanded_ids
        label = c["label"]
        if n_children and not is_expanded:
            label += f" (+{n_children})"
        tip = c.get("summary", c["label"])
        if is_weak:
            tip += " · 자주 틀리는 개념"
        if n_children:
            tip += " · 클릭하면 세부 개념이 펼쳐져요" if not is_expanded else " · 클릭하면 접혀요"
        else:
            tip += " · 클릭하면 이론 설명이 아래에 떠요"
        is_child = bool(c.get("parent_concept"))
        vis_nodes.append({
            "id": c["id"],
            "label": label,
            "title": tip,
            "shape": "box",
            "margin": 8,
            "color": {"background": "#FDECEC" if is_weak else ("#EFF3FB" if is_child else "#F5F7FC"),
                      "border": "#D9534F" if is_weak else ("#9DACD1" if is_child else "#7C8BB5"),
                      "highlight": {"background": "#FDECEC" if is_weak else "#E8EEFC",
                                    "border": "#D9534F" if is_weak else "#3E5C9A"}},
            "font": {"color": "#1C2333", "size": 12 if is_child else 13, "face": "sans-serif"},
            "borderWidth": (2.5 if is_weak else 1.5) + (n_children and not is_expanded and 1 or 0),
        })

    vis_edges = []
    for c in visible_concepts:
        if c.get("parent_concept") in visible_ids:
            vis_edges.append({
                "from": c["parent_concept"], "to": c["id"], "hierarchical": True,
                "color": {"color": "#B7A6D9", "opacity": 0.9}, "width": 1.3,
                "length": 90, "smooth": False, "dashes": [2, 3],
            })
        elif c.get("category") in category_ids:
            vis_edges.append({
                "from": c["category"], "to": c["id"], "hierarchical": True,
                "color": {"color": "#C6CEE2", "opacity": 0.9}, "width": 1.5,
                "length": 130, "smooth": False,
            })
    for e in edges:
        if e["from"] not in visible_ids or e["to"] not in visible_ids:
            continue
        reason = e.get("reason", "")
        vis_edges.append({
            "from": e["from"], "to": e["to"], "hierarchical": False,
            "label": reason, "title": reason,
            "color": {"color": "#8A93A6", "opacity": 0.7}, "width": 1.3,
            "dashes": True, "length": 220,
            "font": {"size": 10, "color": "#5B6B8C", "strokeWidth": 4, "strokeColor": "#ffffff", "align": "middle"},
            "smooth": {"type": "curvedCW", "roundness": 0.15},
        })

    payload = json.dumps({"nodes": vis_nodes, "edges": vis_edges}, ensure_ascii=False)
    bridge_label_js = json.dumps(bridge_label)
    legend_items = ['<span>🔵 카테고리</span>', '<span>⬜ 1차 개념</span>',
                    '<span style="opacity:.85">⬜ 세부 개념</span>']
    if show_weak:
        legend_items.append('<span>🔴 자주 틀리는 개념</span>')
    legend_items.append('<span>(+N) = 클릭하면 세부 개념 펼치기</span>')
    legend = (
        '<div style="display:flex; gap:14px; font-size:12px; color:#5B6B8C; margin-bottom:6px; flex-wrap:wrap;">'
        + "".join(legend_items) + '</div>'
    )
    html = f"""
    {legend}
    <div id="mindmap-net" style="width:100%; height:{height}px; border:1px solid #E2E6F0; border-radius:10px; background:#FBFCFE;"></div>
    <script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
    <script>
        (function() {{
            const container = document.getElementById('mindmap-net');
            const payload = {payload};
            const nodes = new vis.DataSet(payload.nodes);
            const edges = new vis.DataSet(payload.edges);
            const data = {{ nodes: nodes, edges: edges }};
            const options = {{
                physics: {{
                    solver: 'forceAtlas2Based',
                    forceAtlas2Based: {{ gravitationalConstant: -80, springLength: 140, springConstant: 0.05, avoidOverlap: 0.6 }},
                    stabilization: {{ iterations: 200 }},
                }},
                interaction: {{ hover: true, zoomView: true, dragView: true, dragNodes: true, tooltipDelay: 150 }},
                edges: {{ selectionWidth: 2 }},
            }};
            const network = new vis.Network(container, data, options);
            network.once('stabilizationIterationsDone', function() {{ network.fit({{ animation: true }}); }});
            network.on('click', function(params) {{
                if (params.nodes.length === 0) return;
                var nodeId = params.nodes[0];
                try {{
                    var bridge = window.parent.document.querySelector('input[aria-label=' + JSON.stringify({bridge_label_js}) + ']');
                    if (!bridge) return;
                    var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(bridge, nodeId);
                    bridge.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }} catch (err) {{ /* 클릭 브리지 실패해도 그래프 자체는 정상 동작 */ }}
            }});
        }})();
    </script>
    """
    components.html(html, height=height + 40, scrolling=False)


def _render_dialog_svg(spec):
    """브라우저 alert/prompt 대화상자 목업. spec 형식: '메시지|기본값' (기본값 없으면 alert 스타일).
    사용 예: dialog:title|default"""
    parts = spec.split("|")
    message = parts[0] if len(parts) > 0 else ""
    default = parts[1] if len(parts) > 1 else None
    width = 320
    height = 150 if default is not None else 120
    input_box = ""
    if default is not None:
        input_box = (
            f'<rect x="14" y="58" width="{width - 28}" height="26" rx="3" fill="#F5F7FC" stroke="#9DACD1"/>'
            f'<text x="22" y="76" font-size="13" font-family="sans-serif" fill="#1C2333">{default}</text>'
        )
    return f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
        <rect x="0" y="0" width="{width}" height="{height}" rx="6" fill="white" stroke="#9DACD1" stroke-width="1.5"/>
        <text x="14" y="26" font-size="13" font-family="sans-serif" fill="#1C2333">이 페이지 내용:</text>
        <text x="14" y="46" font-size="13" font-family="sans-serif" fill="#1C2333">{message}</text>
        {input_box}
        <rect x="{width - 172}" y="{height - 42}" width="70" height="28" rx="3" fill="#3E5C9A"/>
        <text x="{width - 137}" y="{height - 23}" text-anchor="middle" font-size="12" font-family="sans-serif" fill="white">확인</text>
        <rect x="{width - 96}" y="{height - 42}" width="70" height="28" rx="3" fill="#EFF3FB" stroke="#9DACD1"/>
        <text x="{width - 61}" y="{height - 23}" text-anchor="middle" font-size="12" font-family="sans-serif" fill="#1C2333">취소</text>
    </svg>'''


def render_diagram(q):
    spec = (q.get("diagram") or "").strip()
    if not spec:
        return
    try:
        if spec.startswith("tree:"):
            svg = _render_tree_svg(spec[len("tree:"):])
        elif spec.startswith("grid:"):
            svg = _render_grid_svg(spec[len("grid:"):])
        elif spec.startswith("digraph:"):
            svg = _render_digraph_svg(spec[len("digraph:"):])
        elif spec.startswith("digraphs:"):
            svg = _render_digraphs_grid_svg(spec[len("digraphs:"):])
        elif spec.startswith("grids:"):
            svg = _render_grids_grid_svg(spec[len("grids:"):])
        elif spec.startswith("dialog:"):
            svg = _render_dialog_svg(spec[len("dialog:"):])
        else:
            return
        st.markdown(f'<div style="margin:6px 0 12px;">{svg}</div>', unsafe_allow_html=True)
    except Exception:
        pass


def tag_display(tag):
    parts = tag.split("_")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"📄 {parts[0]}년 {parts[1]}회 기출"
    if tag == "신규작성":
        return "✏️ AI 신규문제"
    return tag


def predicted_exam_result(exam_cfg, subj_stats_raw):
    """지금까지의 과목별 정답률을 실전 배점(과목당 문항수)에 대입한, 정직한 '현재 페이스' 예상 점수."""
    stats_by_subject = {s["subject"]: s for s in subj_stats_raw}
    per_subject = {}
    total_correct = 0
    total_q = 0
    fail_subjects = []
    has_any_data = False
    for subj, count in sorted(exam_cfg["exam_subject_counts"].items()):
        min_correct = exam_cfg["exam_min_correct"].get(subj, 0)
        s = stats_by_subject.get(subj)
        if s and s["seen"]:
            has_any_data = True
            acc = (s["seen"] - s["wrong"]) / s["seen"]
            predicted_correct = round(acc * count)
        else:
            predicted_correct = None
        per_subject[subj] = {"count": count, "min_correct": min_correct, "predicted_correct": predicted_correct}
        if predicted_correct is not None:
            total_correct += predicted_correct
            total_q += count
            if predicted_correct < min_correct:
                fail_subjects.append(subj)
    overall_pass = has_any_data and total_correct >= exam_cfg["exam_total_pass"] and not fail_subjects
    return {
        "has_any_data": has_any_data,
        "per_subject": per_subject,
        "total_correct": total_correct,
        "total_q": total_q,
        "fail_subjects": fail_subjects,
        "overall_pass": overall_pass,
    }


def subject_picker_gate(state_key, counts_by_subject):
    """과목별 개수를 큰 버튼으로 보여주고 하나를 고르게 하는 공통 게이트.
    아직 과목이 선택되지 않았으면 버튼 화면을 그리고 None을 반환한다(호출부는 그대로 return해야 함).
    선택된 과목이 있으면 '◀ 과목 다시 선택' 버튼을 그리고 그 과목(int)을 반환한다."""
    picked = ss.get(state_key)
    if picked is None:
        st.caption("과목을 선택하면 그 과목 문제만 모아서 볼 수 있어요.")
        for subj in ALL_SUBJECTS:
            n = counts_by_subject.get(subj, 0)
            if st.button(f"{subject_label(subj)} — {n}개", key=f"{state_key}_pick_{subj}",
                         disabled=(n == 0), width="stretch"):
                ss[state_key] = subj
                st.rerun()
        return None
    if st.button("◀ 과목 다시 선택", key=f"{state_key}_back"):
        ss[state_key] = None
        st.rerun()
    return picked


SOURCE_FILTER_LABELS = {"concept": "퀴즈 (개념 문제)", "cbt": "CBT 문제 (기출)"}


def source_picker_gate(state_key, counts_by_source):
    """오답노트/자주 틀리는 개념/즐겨찾기에서 퀴즈(개념) 문제와 CBT 기출 문제가 뒤섞여
    보이는 걸 막기 위한 게이트. subject_picker_gate와 같은 패턴(과목 선택보다 먼저 거친다)."""
    picked = ss.get(state_key)
    if picked is None:
        st.caption("퀴즈 문제인지, CBT 모드 문제인지 먼저 골라주세요.")
        for src in ("concept", "cbt"):
            n = counts_by_source.get(src, 0)
            if st.button(f"{SOURCE_FILTER_LABELS[src]} — {n}개", key=f"{state_key}_pick_{src}",
                         disabled=(n == 0), width="stretch"):
                ss[state_key] = src
                st.rerun()
        return None
    if st.button("◀ 유형 다시 선택", key=f"{state_key}_back"):
        ss[state_key] = None
        st.rerun()
    return picked


# =====================================================================
# 홈 (D-day/학습목표 + 취약과목 자동 우선순위)
# =====================================================================
def view_home():
    st.header(f"{exam_cfg['label']} 학습 현황")
    overall = db.get_overall_stats(con, ss.user, ss.exam)
    c1, c2, c3 = st.columns(3)
    c1.metric("누적 풀이", overall["seen"])
    c2.metric("정답률", f"{overall['rate']}%")
    need, _done, _stats = db.get_wrong_question_ids(con, ss.user, ss.exam)
    c3.metric("복습 필요", len(need))

    st.divider()
    st.subheader("🎯 D-day & 오늘의 목표")
    goal = db.get_study_goal(con, ss.user, ss.exam)
    with st.expander("목표 설정", expanded=goal["exam_date"] is None):
        d_val = datetime.date.fromisoformat(goal["exam_date"]) if goal["exam_date"] else datetime.date.today()
        new_date = st.date_input("시험일", value=d_val)
        new_target = st.number_input("오늘 풀 목표 문제 수", min_value=1, max_value=200, value=goal["daily_target"])
        if st.button("저장", key="save_goal"):
            db.set_study_goal(con, ss.user, ss.exam, new_date.isoformat(), int(new_target))
            st.rerun()

    if goal["exam_date"]:
        d_day = (datetime.date.fromisoformat(goal["exam_date"]) - datetime.date.today()).days
        if d_day > 0:
            st.info(f"시험까지 **D-{d_day}**일 남았어요.")
        elif d_day == 0:
            st.info("오늘이 시험일이에요. 화이팅!")
        else:
            st.info("설정한 시험일이 지났어요. 새 시험일을 등록해보세요.")

    today_n = db.get_today_solved_count(con, ss.user, ss.exam)
    target = goal["daily_target"]
    pct = min(100, round(today_n / target * 100)) if target else 0
    st.write(f"오늘 {today_n}/{target}문제 ({pct}%)")
    st.progress(pct / 100)

    st.divider()
    st.subheader("⚠️ 취약과목 우선순위")
    subj_stats = db.get_subject_stats(con, ss.user, ss.exam)
    if not subj_stats:
        st.caption("아직 데이터가 없어요. 문제를 풀면 여기에 취약 과목이 표시됩니다.")
    else:
        for d in subj_stats[:5]:
            rate = round(d["wrong"] / d["seen"] * 100) if d["seen"] else 0
            cols = st.columns([3, 1])
            cols[0].write(f"**{subject_label(d['subject'])}** — 오답률 {rate}% ({d['wrong']}/{d['seen']})")
            if cols[1].button("바로 풀기", key=f"home_weak_{d['subject']}"):
                subjects = [d["subject"]]
                ss.quiz_pool = logic.pick_pool(QUESTIONS, subjects)
                ss.quiz_idx = 0
                ss.quiz_answered = False
                ss.quiz_subject = str(d["subject"])
                ss.quiz_return_nav = "홈"
                goto("퀴즈")


# =====================================================================
# 퀴즈 연습모드
# =====================================================================
def elapsed_str(start_ts):
    if not start_ts:
        return "0:00"
    sec = int(time.time() - start_ts)
    m, s = divmod(max(0, sec), 60)
    return f"{m}:{s:02d}"


def bookmark_toggle(qid):
    flagged = db.is_flagged(con, ss.user, qid)
    label = "★ 즐겨찾기 해제" if flagged else "☆ 즐겨찾기"
    if st.button(label, key=f"flag_{qid}"):
        if flagged:
            db.remove_flag(con, ss.user, qid)
        else:
            db.add_flag(con, ss.user, qid)
        st.rerun()


def start_quiz_pool(subject_key):
    ss.quiz_subject = subject_key
    subjects = ALL_SUBJECTS if subject_key == "전체" else [int(subject_key)]
    ss.quiz_pool = logic.pick_pool(QUESTIONS, subjects)
    ss.quiz_idx = 0
    ss.quiz_answered = False
    ss.quiz_start_at = time.time()


def start_focus_session(qids, return_nav):
    ss.quiz_pool = list(qids)
    ss.quiz_idx = 0
    ss.quiz_answered = False
    ss.quiz_return_nav = return_nav


def view_quiz():
    st.header("퀴즈 연습모드")
    if not ss.quiz_pool:
        picked = st.radio("과목", subject_choices(),
                           format_func=lambda s: "전체" if s == "전체" else subject_label(int(s)),
                           horizontal=True, key="quiz_subject_radio")
        if st.button("시작", key="quiz_start"):
            start_quiz_pool(picked)
            st.rerun()
        return

    if ss.quiz_idx >= len(ss.quiz_pool):
        rate = round(ss.quiz_correct / ss.quiz_seen * 100) if ss.quiz_seen else 0
        st.success(f"연습 완료! 이번 세션 정답률: {ss.quiz_correct}/{ss.quiz_seen} ({rate}%)")
        c1, c2 = st.columns(2)
        if c1.button("다시 풀기"):
            start_quiz_pool(ss.quiz_subject)
            st.rerun()
        if c2.button("메뉴로"):
            ss.quiz_pool = []
            target = ss.quiz_return_nav
            ss.quiz_return_nav = "퀴즈"
            goto(target)
        return

    qid = ss.quiz_pool[ss.quiz_idx]
    q = QUESTIONS[qid]
    choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]

    st.markdown(
        f'<span class="pill">{subject_label(q["subject"])}</span>'
        f'<span class="pill pill-sub">{source_badge_text(q)}</span>',
        unsafe_allow_html=True,
    )
    c_prog, c_time = st.columns([3, 1])
    c_prog.caption(f"{ss.quiz_idx + 1} / {len(ss.quiz_pool)}")
    c_time.caption(f"⏱ {elapsed_str(ss.quiz_start_at)}")
    st.subheader(q["question"])
    render_diagram(q)

    bookmark_toggle(qid)

    choice_labels = [f"{'①②③④'[i]} {c}" for i, c in enumerate(choices)]
    picked = st.radio("보기", choice_labels, key=f"quiz_radio_{qid}", index=None,
                       label_visibility="collapsed", disabled=ss.quiz_answered)

    if not ss.quiz_answered:
        if st.button("확인", key=f"quiz_check_{qid}", disabled=picked is None):
            chosen = choice_labels.index(picked)
            ss["_quiz_chosen"] = chosen
            ss.quiz_answered = True
            ss.quiz_seen += 1
            is_correct = (chosen + 1) == q["answer"]
            if is_correct:
                ss.quiz_correct += 1
            db.record_attempt(con, ss.user, qid, chosen + 1, is_correct)
            st.rerun()
    else:
        chosen = ss["_quiz_chosen"]
        is_correct = (chosen + 1) == q["answer"]
        if is_correct:
            st.markdown('<div class="result-ok">정답이에요!</div>', unsafe_allow_html=True)
        else:
            ans_text = choices[q["answer"] - 1]
            st.markdown(f'<div class="result-bad">오답이에요. 정답: {"①②③④"[q["answer"]-1]} {ans_text}</div>',
                        unsafe_allow_html=True)
        st.write(q["explanation"])
        if not is_correct:
            _render_related_concepts_box(qid, q, choices)
        if st.button("다음 문제 ▶", key=f"quiz_next_{qid}"):
            ss.quiz_idx += 1
            ss.quiz_answered = False
            st.rerun()

    st.divider()
    if st.button("세션 그만두기"):
        ss.quiz_pool = []
        target = ss.quiz_return_nav
        ss.quiz_return_nav = "퀴즈"
        goto(target)


# =====================================================================
# CBT 모드 (연습 / 실전-무작위 / 실전-회차별기출)
# =====================================================================
def view_cbt():
    st.header("CBT 모드")
    if not CBT_IDS:
        st.info("아직 이 시험의 기출문제(CBT) 데이터가 없어요. PDF 자료가 추가되면 여기서 풀 수 있어요.")
        return

    mode = st.radio(
        "모드", ["연습", "실전(무작위 조합)", "실전(회차별 기출)", "확장 학습 모드(기출+AI 신규 혼합)"],
        key="cbt_mode_radio", horizontal=True,
    )
    if mode != ss.cbt_mode:
        ss.cbt_mode = mode
        ss.cbt_pool = []
        ss.cbt_submitted = False

    if mode == "연습":
        _cbt_practice()
    elif mode == "실전(무작위 조합)":
        _cbt_exam_random()
    elif mode == "실전(회차별 기출)":
        _cbt_exam_round()
    else:
        _cbt_exam_mixed()


def _practice_is_done(qid):
    return f"cbtp_result_{qid}" in ss


def _practice_render_number_grid(indices, flags, grid_key):
    mode = ss.cbt_view_mode
    if mode == "전체 풀기":
        html = []
        for i in indices:
            done = flags[i]
            bg = "#16A34A" if done else "#E5E7EB"
            color = "#fff" if done else "#111"
            html.append(
                f'<a href="#cbtpq_{i}" style="display:inline-block;width:32px;height:32px;line-height:32px;'
                f'text-align:center;margin:2px;border-radius:6px;background:{bg};color:{color};'
                f'text-decoration:none;font-size:12px;">{i + 1}</a>'
            )
        st.markdown("".join(html), unsafe_allow_html=True)
    else:
        cols = st.columns(10)
        for j, i in enumerate(indices):
            label = ("✅" if flags[i] else "⬜") + f" {i + 1}"
            if cols[j % 10].button(label, key=f"pnavjump_{grid_key}_{i}"):
                step = 1 if mode == "1문제씩" else ss.cbt_batch_size
                ss.cbt_page = i // step
                st.rerun()


def _practice_render_navigator(pool):
    total = len(pool)
    flags = [_practice_is_done(qid) for qid in pool]
    done_n = sum(flags)
    st.markdown(f"**풀이 현황 · 푼 문제 {done_n} / 안 푼 문제 {total - done_n} (전체 {total}문항)**")
    st.progress(done_n / total if total else 0)

    with st.expander("🗂 문제 번호로 이동 / 안 푼 문제 목록 보기"):
        tab_all, tab_unsolved = st.tabs(["전체 번호", f"안 푼 문제만 ({total - done_n})"])
        with tab_all:
            _practice_render_number_grid(list(range(total)), flags, "all")
        with tab_unsolved:
            unsolved = [i for i, f in enumerate(flags) if not f]
            if unsolved:
                _practice_render_number_grid(unsolved, flags, "unsolved")
            else:
                st.success("모든 문제를 풀었어요!")


def _cbt_practice_pool_builder(variant, picked_subject, picked_round, picked_year, picked_count):
    if variant == "회차별 기출":
        pool = logic.pick_cbt_round_pool(QUESTIONS, CBT_IDS, picked_round)
        if picked_subject != "전체":
            pool = [qid for qid in pool if QUESTIONS[qid]["subject"] == int(picked_subject)]
        return pool
    subjects = ALL_SUBJECTS if picked_subject == "전체" else [int(picked_subject)]
    ids = CBT_IDS
    if picked_year != "전체":
        ids = [qid for qid in ids if QUESTIONS[qid]["tag"].split("_")[0] == picked_year]
    limit = None if picked_count == "전체" else int(picked_count)
    return logic.pick_cbt_pool(QUESTIONS, ids, subjects, limit=limit)


def _clear_cbt_practice_results():
    """연습모드 채점 상태(cbtp_result_*, cbtp_radio_*)는 qid별로 세션 전체에 걸쳐 남아있어서,
    새 문제 세트를 뽑았을 때 예전에 다른 세트에서 풀었던 문항과 같은 qid가 무작위로 다시 뽑히면
    이번엔 안 풀었는데도 '이미 푼 문제'로 잘못 표시된다. 새 세트를 시작할 때마다 통째로 지워서
    이전 세트의 결과가 절대 새 세트로 새어 들어오지 않게 한다."""
    for key in [k for k in ss.keys() if k.startswith("cbtp_result_") or k.startswith("cbtp_radio_")]:
        del ss[key]
    ss.cbtp_choice_store = {}


def _cbt_practice():
    if not ss.cbt_pool:
        variant = st.radio("방식", ["무작위 조합", "회차별 기출"], key="cbt_practice_variant", horizontal=True)
        picked_subject, picked_round, picked_year, picked_count = "전체", None, "전체", "10"
        if variant == "회차별 기출":
            rounds = db.get_cbt_rounds(con, ss.exam)
            if not rounds:
                st.info("회차별 기출 데이터가 아직 없어요.")
                return
            picked_round = st.selectbox("회차 선택", rounds, key="cbt_practice_round_pick")
            picked_subject = st.radio("과목", subject_choices(),
                                       format_func=lambda s: "전체" if s == "전체" else subject_label(int(s)),
                                       horizontal=True, key="cbt_practice_round_subject")
        else:
            picked_subject = st.radio("과목", subject_choices(),
                                       format_func=lambda s: "전체" if s == "전체" else subject_label(int(s)),
                                       horizontal=True, key="cbt_subject_radio")
            rounds = db.get_cbt_rounds(con, ss.exam)
            years = ["전체"] + sorted({r.split("_")[0] for r in rounds if r.split("_")[0].isdigit()})
            cy, cc = st.columns(2)
            picked_year = cy.selectbox("연도", years, key="cbt_practice_year")
            picked_count = cc.selectbox("문제 수", ["10", "20", "30", "전체"], index=1, key="cbt_practice_count")
        view_mode = st.radio(
            "보기 방식", ["전체 풀기", "1문제씩", "3~4문제씩"],
            key="cbt_viewmode_practice", horizontal=True,
        )
        if st.button("연습 시작", key="cbt_practice_start"):
            ss.cbt_pool = _cbt_practice_pool_builder(variant, picked_subject, picked_round, picked_year, picked_count)
            ss.cbt_view_mode = view_mode
            ss.cbt_page = 0
            ss.cbtp_start_at = time.time()
            _clear_cbt_practice_results()
            st.rerun()
        return

    st.caption(f"⏱ 풀이 시간 {elapsed_str(ss.cbtp_start_at)}")

    pool = ss.cbt_pool
    total = len(pool)
    mode = ss.cbt_view_mode

    if mode == "전체 풀기":
        render_indices = list(range(total))
    elif mode == "1문제씩":
        render_indices = [ss.cbt_page]
    else:
        start = ss.cbt_page * ss.cbt_batch_size
        render_indices = list(range(start, min(start + ss.cbt_batch_size, total)))

    # 방금 이 페이지에서 답을 고른 문제가 있으면 store에 아직 안 옮겨진 상태라 네비게이터가
    # 하나 늦게 표시될 수 있다. 렌더링 전에 미리 동기화해서 즉시 정확한 숫자를 보여준다.
    for i in render_indices:
        _pqid = pool[i]
        _praw = ss.get(f"cbtp_radio_{_pqid}")
        if _praw is not None:
            ss.cbtp_choice_store[_pqid] = _praw

    _practice_render_navigator(pool)

    for i in render_indices:
        qid = pool[i]
        q = QUESTIONS[qid]
        choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]
        if mode == "전체 풀기":
            st.markdown(f'<a id="cbtpq_{i}"></a>', unsafe_allow_html=True)
        st.markdown(
            f'<span class="pill">{subject_label(q["subject"])}</span>'
            f'<span class="pill pill-sub">{source_badge_text(q)}</span> <b>[{i + 1}/{total}]</b>',
            unsafe_allow_html=True,
        )
        st.write(q["question"])
        render_diagram(q)
        bookmark_toggle(qid)
        labels = [f"{'①②③④'[j]} {c}" for j, c in enumerate(choices)]
        already_checked = f"cbtp_result_{qid}" in ss
        # 채점 후에도 라디오를 계속 바꿀 수 있으면, 화면엔 새로 고른 보기가 표시되는데 정답/오답
        # 배너는 처음 "정답 확인"을 눌렀을 때 값 그대로 남아 서로 안 맞는 것처럼 보인다.
        # 한 번 채점되면 그 문제의 라디오는 잠가서 이 불일치가 아예 생기지 않게 한다.
        # 1문제씩/3~4문제씩 모드에서 페이지를 오가면 Streamlit이 화면에 안 그려진 라디오의
        # session_state를 지워버리므로(cbt_answers_store와 같은 문제), 고른 보기를 별도
        # store에도 옮겨 담아서 다시 그 페이지로 돌아와도 체크 표시가 남아있게 한다.
        stored_choice = ss.cbtp_choice_store.get(qid)
        picked = st.radio("보기", labels, key=f"cbtp_radio_{qid}",
                           index=labels.index(stored_choice) if stored_choice in labels else None,
                           label_visibility="collapsed", disabled=already_checked)
        if picked is not None:
            ss.cbtp_choice_store[qid] = picked
        if st.button("정답 확인", key=f"cbtp_check_{qid}", disabled=picked is None):
            chosen = labels.index(picked)
            is_correct = (chosen + 1) == q["answer"]
            db.record_attempt(con, ss.user, qid, chosen + 1, is_correct)
            ss[f"cbtp_result_{qid}"] = is_correct
            ss.cbtp_choice_store[qid] = picked
            st.rerun()
        if f"cbtp_result_{qid}" in ss:
            if ss[f"cbtp_result_{qid}"]:
                st.markdown('<div class="result-ok">정답!</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="result-bad">오답 · 정답: {choices[q["answer"]-1]}</div>', unsafe_allow_html=True)
            st.caption(q["explanation"])
            if not ss[f"cbtp_result_{qid}"]:
                _render_related_concepts_box(qid, q, choices)
        st.divider()

    if mode != "전체 풀기":
        step = 1 if mode == "1문제씩" else ss.cbt_batch_size
        max_page = (total - 1) // step
        c1, c2, c3 = st.columns([1, 2, 1])
        if c1.button("◀ 이전", key="cbtp_prev", disabled=ss.cbt_page <= 0):
            ss.cbt_page = max(0, ss.cbt_page - 1)
            st.rerun()
        c2.write(f"페이지 {ss.cbt_page + 1} / {max_page + 1}")
        if c3.button("다음 ▶", key="cbtp_next", disabled=ss.cbt_page >= max_page):
            ss.cbt_page = min(max_page, ss.cbt_page + 1)
            st.rerun()

    correct_n = sum(1 for qid in pool if ss.get(f"cbtp_result_{qid}") is True)
    checked_n = sum(1 for qid in pool if f"cbtp_result_{qid}" in ss)
    if checked_n:
        st.write(f"채점 결과 {correct_n}/{checked_n}")
    if st.button("새 문제 세트", key="cbtp_new"):
        ss.cbt_pool = []
        st.rerun()


def _exam_choice_labels(qid):
    q = QUESTIONS[qid]
    choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]
    return [f"{'①②③④'[i]} {c}" for i, c in enumerate(choices)]


def _exam_is_answered(qid):
    return ss.cbt_answers_store.get(qid) is not None


def _exam_collect_answers(pool):
    answers = {}
    for qid in pool:
        picked = ss.cbt_answers_store.get(qid)
        if picked is not None:
            answers[qid] = _exam_choice_labels(qid).index(picked)
    return answers


def _exam_render_navigator(pool):
    total = len(pool)
    flags = [_exam_is_answered(qid) for qid in pool]
    answered_n = sum(flags)
    st.markdown(f"**풀이 현황 · 푼 문제 {answered_n} / 안 푼 문제 {total - answered_n} (전체 {total}문항)**")
    st.progress(answered_n / total if total else 0)

    with st.expander("🗂 문제 번호로 이동 / 안 푼 문제 목록 보기"):
        tab_all, tab_unsolved = st.tabs(["전체 번호", f"안 푼 문제만 ({total - answered_n})"])
        with tab_all:
            _exam_render_number_grid(list(range(total)), flags, "all")
        with tab_unsolved:
            unsolved = [i for i, f in enumerate(flags) if not f]
            if unsolved:
                _exam_render_number_grid(unsolved, flags, "unsolved")
            else:
                st.success("모든 문제를 풀었어요!")


def _exam_render_number_grid(indices, flags, grid_key):
    mode = ss.cbt_view_mode
    if mode == "전체 풀기":
        html = []
        for i in indices:
            done = flags[i]
            bg = "#16A34A" if done else "#E5E7EB"
            color = "#fff" if done else "#111"
            html.append(
                f'<a href="#cbtq_{i}" style="display:inline-block;width:32px;height:32px;line-height:32px;'
                f'text-align:center;margin:2px;border-radius:6px;background:{bg};color:{color};'
                f'text-decoration:none;font-size:12px;">{i + 1}</a>'
            )
        st.markdown("".join(html), unsafe_allow_html=True)
    else:
        cols = st.columns(10)
        for j, i in enumerate(indices):
            label = ("✅" if flags[i] else "⬜") + f" {i + 1}"
            if cols[j % 10].button(label, key=f"navjump_{grid_key}_{i}"):
                step = 1 if mode == "1문제씩" else ss.cbt_batch_size
                ss.cbt_page = i // step
                st.rerun()


def _run_cbt_exam(pool_builder, exam_key):
    if not ss.cbt_pool:
        view_mode = st.radio(
            "보기 방식", ["전체 풀기", "1문제씩", "3~4문제씩"],
            key=f"cbt_viewmode_{exam_key}", horizontal=True,
        )
        if st.button("실전 시작", key=f"cbt_exam_start_{exam_key}"):
            ss.cbt_pool = pool_builder()
            ss.cbt_submitted = False
            ss.cbt_view_mode = view_mode
            ss.cbt_page = 0
            ss.cbt_start_at = time.time()
            ss.cbt_answers_store = {}
            st.rerun()
        return

    if ss.cbt_submitted:
        _cbt_exam_result()
        return

    limit_sec = exam_cfg.get("time_limit_min", 90) * 60
    remaining = limit_sec - (time.time() - (ss.cbt_start_at or time.time()))
    mm, sec = divmod(max(0, int(remaining)), 60)
    timer_color = "#DC2626" if remaining < 300 else "#111827"
    st.markdown(
        f'<div style="text-align:right;font-weight:700;color:{timer_color};">'
        f'⏱ 남은 시간 {mm:02d}:{sec:02d}</div>', unsafe_allow_html=True,
    )

    if remaining <= 0:
        answers = _exam_collect_answers(ss.cbt_pool)
        for qid, chosen in answers.items():
            is_correct = (chosen + 1) == QUESTIONS[qid]["answer"]
            db.record_attempt(con, ss.user, qid, chosen + 1, is_correct)
        ss["_cbt_answers"] = answers
        ss.cbt_submitted = True
        st.warning("⏰ 제한 시간이 종료되어 자동 제출되었습니다.")
        st.rerun()
        return

    pool = ss.cbt_pool
    total = len(pool)
    mode = ss.cbt_view_mode

    if mode == "전체 풀기":
        render_indices = list(range(total))
    elif mode == "1문제씩":
        render_indices = [ss.cbt_page]
    else:
        start = ss.cbt_page * ss.cbt_batch_size
        render_indices = list(range(start, min(start + ss.cbt_batch_size, total)))

    # 이번 rerun에서 방금 답을 고른 문제가 있으면(같은 페이지에서 라디오를 막 클릭한 경우),
    # 아직 store에 반영되기 전이라 네비게이터가 답한 문항 수를 하나 늦게 보여줄 수 있다.
    # 렌더링 루프 전에 미리 한 번 동기화해서 네비게이터도 즉시 정확한 숫자를 보여주게 한다.
    for i in render_indices:
        _qid = pool[i]
        _raw = ss.get(f"cbte_radio_{_qid}")
        if _raw is not None:
            ss.cbt_answers_store[_qid] = _raw

    _exam_render_navigator(pool)

    for i in render_indices:
        qid = pool[i]
        q = QUESTIONS[qid]
        choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]
        if mode == "전체 풀기":
            st.markdown(f'<a id="cbtq_{i}"></a>', unsafe_allow_html=True)
        st.markdown(
            f'<span class="pill">{subject_label(q["subject"])}</span>'
            f'<span class="pill pill-sub">{source_badge_text(q)}</span> <b>[{i + 1}/{total}]</b>',
            unsafe_allow_html=True,
        )
        st.write(q["question"])
        render_diagram(q)
        labels = [f"{'①②③④'[j]} {c}" for j, c in enumerate(choices)]
        # 위젯이 렌더링 안 된 페이지(1문제씩/3~4문제씩)로 넘어가면 Streamlit이 그 위젯의
        # session_state를 지워버려서, 매번 렌더링될 때마다 별도 dict(cbt_answers_store)에
        # 값을 옮겨 담아 페이지를 오가도 답이 안 사라지게 한다.
        stored = ss.cbt_answers_store.get(qid)
        picked = st.radio(
            "보기", labels, key=f"cbte_radio_{qid}",
            index=labels.index(stored) if stored in labels else None,
            label_visibility="collapsed",
        )
        ss.cbt_answers_store[qid] = picked
        st.divider()

    if mode != "전체 풀기":
        step = 1 if mode == "1문제씩" else ss.cbt_batch_size
        max_page = (total - 1) // step
        c1, c2, c3 = st.columns([1, 2, 1])
        if c1.button("◀ 이전", key="cbte_prev", disabled=ss.cbt_page <= 0):
            ss.cbt_page = max(0, ss.cbt_page - 1)
            st.rerun()
        c2.write(f"페이지 {ss.cbt_page + 1} / {max_page + 1}")
        if c3.button("다음 ▶", key="cbte_next", disabled=ss.cbt_page >= max_page):
            ss.cbt_page = min(max_page, ss.cbt_page + 1)
            st.rerun()

    answers = _exam_collect_answers(pool)
    st.write(f"{total}문항 중 답한 문항: {len(answers)}")
    if st.button("제출", key="cbt_submit"):
        for qid, chosen in answers.items():
            is_correct = (chosen + 1) == QUESTIONS[qid]["answer"]
            db.record_attempt(con, ss.user, qid, chosen + 1, is_correct)
        ss["_cbt_answers"] = answers
        ss.cbt_submitted = True
        st.rerun()


def _cbt_available_years():
    rounds = db.get_cbt_rounds(con, ss.exam)
    return sorted({r.split("_")[0] for r in rounds if r.split("_")[0].isdigit()})


def _filter_ids_by_year_range(ids, year_range):
    if not year_range:
        return ids
    lo, hi = year_range
    out = []
    for qid in ids:
        year = QUESTIONS[qid]["tag"].split("_")[0]
        if not year.isdigit() or (lo <= year <= hi):
            out.append(qid)
    return out


def _subject_multiselect(key_prefix):
    """실전 모드용 과목 선택: 1개만, 2개만, 3개 다 등 자유롭게 조합할 수 있게 다중 선택으로 받는다.
    과락 판정은 _cbt_exam_result에서 여기 골라진 과목 각각에 대해 그 과목 자신의 과락 기준으로
    채점하므로, 몇 과목을 고르든 상관없이 항상 과락 여부를 보여줄 수 있다."""
    return sorted(st.multiselect(
        "과목 (여러 개 선택 가능)", ALL_SUBJECTS, default=ALL_SUBJECTS,
        format_func=subject_label, key=f"{key_prefix}_subjects",
    ))


def _build_subject_exam_pool(ids, picked_subjects, year_range=None):
    ids = _filter_ids_by_year_range(ids, year_range)
    if set(picked_subjects) == set(exam_cfg["exam_subject_counts"].keys()):
        return logic.pick_cbt_exam_pool(QUESTIONS, ids, exam_cfg)
    pool = []
    for subj in picked_subjects:
        count = exam_cfg["exam_subject_counts"].get(subj, 20)
        pool.extend(logic.pick_cbt_pool(QUESTIONS, ids, [subj], limit=count))
    pool.sort(key=lambda qid: QUESTIONS[qid]["subject"])
    return pool


def _cbt_subject_year_viewmode_picker(key_prefix, with_year=True):
    picked_subjects = _subject_multiselect(key_prefix)
    year_range = None
    if with_year:
        years = _cbt_available_years()
        if years:
            year_range = st.select_slider(
                "연도 범위", options=years, value=(years[0], years[-1]), key=f"{key_prefix}_year_range",
            )
    view_mode = st.radio(
        "보기 방식", ["전체 풀기", "1문제씩", "3~4문제씩"], key=f"{key_prefix}_viewmode", horizontal=True,
    )
    return picked_subjects, year_range, view_mode


def _cbt_exam_random():
    if not ss.cbt_pool:
        picked_subjects, year_range, view_mode = _cbt_subject_year_viewmode_picker("cbt_exam_random")
        if st.button("실전 시작", key="cbt_exam_start_random", disabled=not picked_subjects):
            ss.cbt_pool = _build_subject_exam_pool(CBT_IDS, picked_subjects, year_range)
            ss.cbt_submitted = False
            ss.cbt_view_mode = view_mode
            ss.cbt_page = 0
            ss.cbt_start_at = time.time()
            ss.cbt_answers_store = {}
            st.rerun()
        return
    _run_cbt_exam(lambda: ss.cbt_pool, "random")


def _cbt_exam_mixed():
    st.caption("실제 기출문제와 AI가 만든 신규 문제를 함께 섞어서, 더 폭넓게 연습하는 모드예요. (기존 실전/연습 모드는 기출문제만 그대로 사용해요)")
    if not ss.cbt_pool:
        picked_subjects, year_range, view_mode = _cbt_subject_year_viewmode_picker("cbt_exam_mixed")
        if st.button("실전 시작", key="cbt_exam_start_mixed", disabled=not picked_subjects):
            ss.cbt_pool = _build_subject_exam_pool(ALL_IDS, picked_subjects, year_range)
            ss.cbt_submitted = False
            ss.cbt_view_mode = view_mode
            ss.cbt_page = 0
            ss.cbt_start_at = time.time()
            ss.cbt_answers_store = {}
            st.rerun()
        return
    _run_cbt_exam(lambda: ss.cbt_pool, "mixed")


def _cbt_exam_round():
    rounds = db.get_cbt_rounds(con, ss.exam)
    if not rounds:
        st.info("회차별 기출 데이터가 아직 없어요. PDF 기출문제가 추가되면 회차를 선택해 그대로 풀 수 있어요.")
        return
    if not ss.cbt_pool:
        picked_round = st.selectbox("회차 선택", rounds, key="cbt_round_pick")
        picked_subjects = _subject_multiselect("cbt_round")
        view_mode = st.radio(
            "보기 방식", ["전체 풀기", "1문제씩", "3~4문제씩"],
            key="cbt_viewmode_round", horizontal=True,
        )
        if st.button("이 회차 실전 시작", key="cbt_round_start", disabled=not picked_subjects):
            pool = logic.pick_cbt_round_pool(QUESTIONS, CBT_IDS, picked_round)
            if set(picked_subjects) != set(exam_cfg["exam_subject_counts"].keys()):
                pool = [qid for qid in pool if QUESTIONS[qid]["subject"] in picked_subjects]
            ss.cbt_pool = pool
            ss.cbt_submitted = False
            ss.cbt_view_mode = view_mode
            ss.cbt_page = 0
            ss.cbt_start_at = time.time()
            ss.cbt_answers_store = {}
            st.rerun()
        return
    _run_cbt_exam(lambda: ss.cbt_pool, "round")


def _cbt_exam_result():
    answers = ss.get("_cbt_answers", {})
    per_subject = {}
    correct_n = 0
    for qid in ss.cbt_pool:
        q = QUESTIONS[qid]
        chosen = answers.get(qid)
        is_correct = chosen is not None and (chosen + 1) == q["answer"]
        d = per_subject.setdefault(q["subject"], {"correct": 0, "total": 0})
        d["total"] += 1
        if is_correct:
            d["correct"] += 1
            correct_n += 1

    covers_all_subjects = set(per_subject.keys()) == set(exam_cfg["exam_subject_counts"].keys())
    fail_subjects = [s for s in per_subject if per_subject[s]["correct"] < exam_cfg["exam_min_correct"].get(s, 0)]
    total_score = correct_n * exam_cfg["points_per_q"]

    if covers_all_subjects:
        overall_pass = (correct_n >= exam_cfg["exam_total_pass"]) and not fail_subjects
        if overall_pass:
            st.markdown(
                f'<div class="result-ok">합격 예상 · 총점 {total_score}점 · {correct_n}/{len(ss.cbt_pool)}문항 정답</div>',
                unsafe_allow_html=True,
            )
        else:
            reasons = []
            if correct_n < exam_cfg["exam_total_pass"]:
                reasons.append(f"총점 미달({total_score}점)")
            if fail_subjects:
                reasons.append("과락 과목: " + ", ".join(subject_label(s) for s in fail_subjects))
            st.markdown(f'<div class="result-bad">불합격 예상 · {" / ".join(reasons)}</div>', unsafe_allow_html=True)
    else:
        # 일부 과목만 푼 경우: 전체 합격 판정 대신 그 과목(들)의 과락 여부만 안내
        st.write(f"**{correct_n}/{len(ss.cbt_pool)}문항 정답** (총점 {total_score}점)")
        if fail_subjects:
            st.markdown(
                '<div class="result-bad">과락 기준 미달 과목: ' + ", ".join(subject_label(s) for s in fail_subjects)
                + '</div>', unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="result-ok">선택한 과목은 과락 기준을 넘겼어요.</div>', unsafe_allow_html=True)
        st.caption("전체 3과목을 다 풀지 않아서 종합 합격 판정은 표시하지 않아요.")

    for s in sorted(per_subject.keys()):
        d = per_subject[s]
        st.write(f"{subject_label(s)}: {d['correct']}/{d['total']}문항")

    wrong_qids = [
        qid for qid in ss.cbt_pool
        if answers.get(qid) is None or (answers.get(qid) + 1) != QUESTIONS[qid]["answer"]
    ]

    c1, c2 = st.columns(2)
    with c1:
        if st.button("다시 시작", key="cbt_exam_restart"):
            ss.cbt_pool = []
            ss.cbt_submitted = False
            ss.cbt_answers_store = {}
            st.rerun()
    with c2:
        if st.button(f"🔁 틀린 문제만 다시 풀기 ({len(wrong_qids)}개)", key="cbt_exam_retry_wrong",
                      disabled=not wrong_qids):
            ss.cbt_pool = wrong_qids
            ss.cbt_submitted = False
            ss["_cbt_answers"] = {}
            ss.cbt_answers_store = {}
            ss.cbt_page = 0
            ss.cbt_start_at = time.time()
            st.rerun()

    if wrong_qids:
        with st.expander(f"❌ 틀린 문제 목록 ({len(wrong_qids)}개)"):
            for qid in wrong_qids:
                q = QUESTIONS[qid]
                choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]
                correct_text = choices[q["answer"] - 1]
                chosen = answers.get(qid)
                chosen_text = choices[chosen] if chosen is not None else "(안 풂)"
                st.markdown(
                    f'<span class="pill">{subject_label(q["subject"])}</span>'
                    f'<span class="pill pill-sub">{source_badge_text(q)}</span>', unsafe_allow_html=True,
                )
                st.write(f"**{q['question']}**")
                st.markdown(f'<div class="result-bad">선택: {chosen_text} · 정답: {correct_text}</div>',
                            unsafe_allow_html=True)
                st.caption(q["explanation"])
                st.divider()


# =====================================================================
# 개념노트 (카드 / 노트 / OX)
# =====================================================================
def view_concept():
    st.header("개념노트")
    view = st.radio("보기 방식", ["카드", "노트", "OX 퀴즈", "마인드맵"], key="concept_view", horizontal=True)
    subj_pick = st.radio("과목", subject_choices(),
                          format_func=lambda s: "전체" if s == "전체" else subject_label(int(s)),
                          horizontal=True, key="concept_subject_radio")
    if subj_pick != ss.concept_subject:
        ss.concept_subject = subj_pick
        ss.card_pool = []
        ss.ox_pool = []

    subjects = ALL_SUBJECTS if ss.concept_subject == "전체" else [int(ss.concept_subject)]

    if view == "카드":
        _view_card(subjects)
    elif view == "노트":
        _view_note(subjects)
    elif view == "OX 퀴즈":
        _view_ox(subjects)
    else:
        _view_mindmap(subjects)


def _view_card(subjects):
    card_mode = st.radio("확인 방식", ["뒤집기", "단어 입력형", "빈칸 채우기"], key="card_mode", horizontal=True)
    if not ss.card_pool:
        ss.card_pool = logic.pick_pool(QUESTIONS, subjects)
        ss.card_idx = 0
        ss.card_flipped = False

    if not ss.card_pool:
        st.info("표시할 개념이 없어요.")
        return

    qid = ss.card_pool[ss.card_idx]
    q = QUESTIONS[qid]
    answer_text = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]][q["answer"] - 1]

    st.markdown(
        f'<span class="pill">{subject_label(q["subject"])}</span>'
        f'<span class="pill pill-sub">{source_badge_text(q)}</span>', unsafe_allow_html=True,
    )
    st.caption(f"{ss.card_idx + 1} / {len(ss.card_pool)}")
    st.subheader(q["question"])
    render_diagram(q)

    if card_mode == "뒤집기":
        if not ss.card_flipped:
            if st.button("정답 보기"):
                ss.card_flipped = True
                st.rerun()
        else:
            st.markdown(f'<div class="result-ok">정답: {answer_text}</div>', unsafe_allow_html=True)
            st.caption(q["explanation"])
            if st.button("다시 가리기"):
                ss.card_flipped = False
                st.rerun()
    else:
        blanked = None
        if card_mode == "빈칸 채우기":
            blanked = logic.make_blank_sentence(q["explanation"], answer_text)
            if blanked:
                st.write(blanked)
            choices_hint = "보기: " + "  ".join(
                f"{'①②③④'[i]} {c}" for i, c in enumerate([q["choice1"], q["choice2"], q["choice3"], q["choice4"]])
            )
            st.caption(choices_hint)

        user_input = st.text_input("정답 입력", key=f"card_input_{qid}_{card_mode}",
                                    disabled=qid in ss.card_results)
        c1, c2 = st.columns(2)
        if c1.button("확인", key=f"card_check_{qid}_{card_mode}", disabled=qid in ss.card_results):
            ok = logic.answer_matches(user_input, answer_text)
            ss.card_results[qid] = ok
            if ok:
                db.clear_card_wrong(con, ss.user, qid)
            else:
                db.add_card_wrong(con, ss.user, qid)
            st.rerun()
        if c2.button("모르겠어요", key=f"card_dontknow_{qid}_{card_mode}"):
            ss.card_results[qid] = False
            db.add_card_wrong(con, ss.user, qid)
            st.rerun()
        if qid in ss.card_results:
            if ss.card_results[qid]:
                st.markdown('<div class="result-ok">정답이에요!</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="result-bad">정답: {answer_text}</div>', unsafe_allow_html=True)
            st.caption(q["explanation"])

    st.divider()
    c1, c2, c3 = st.columns(3)
    if c1.button("◀ 이전"):
        ss.card_idx = (ss.card_idx - 1) % len(ss.card_pool)
        ss.card_flipped = False
        st.rerun()
    if c2.button("다음 ▶"):
        ss.card_idx = (ss.card_idx + 1) % len(ss.card_pool)
        ss.card_flipped = False
        st.rerun()
    if c3.button("🔀 순서 섞기"):
        random.shuffle(ss.card_pool)
        ss.card_idx = 0
        ss.card_flipped = False
        st.rerun()

    if card_mode != "뒤집기":
        if st.button("🔄 전체 리셋 (지금까지 푼 카드)"):
            ss.card_results = {}
            st.rerun()

        wrong_ids = db.get_card_wrong_ids(con, ss.user, ss.exam)
        if wrong_ids:
            st.markdown(f'<div class="group-title">📋 카드 오답 · 개념별로 확인 ({len(wrong_ids)}개)</div>',
                        unsafe_allow_html=True)
            groups = logic.group_ids_by_tag(QUESTIONS, wrong_ids)
            for (subject, tag), ids in groups.items():
                st.markdown(f'<div class="group-title">{subject_label(subject)} · {tag_display(tag)}</div>', unsafe_allow_html=True)
                for wqid in ids:
                    wq = QUESTIONS[wqid]
                    wans = [wq["choice1"], wq["choice2"], wq["choice3"], wq["choice4"]][wq["answer"] - 1]
                    st.write(wq["question"])
                    retry_val = st.text_input("정답 입력", key=f"wrong_card_input_{wqid}")
                    cc1, cc2 = st.columns(2)
                    if cc1.button("확인", key=f"wrong_card_check_{wqid}"):
                        if logic.answer_matches(retry_val, wans):
                            db.clear_card_wrong(con, ss.user, wqid)
                            st.rerun()
                        else:
                            st.error(f"오답이에요. 정답: {wans}")
                    if cc2.button("목록서 지우기", key=f"wrong_card_clear_{wqid}"):
                        db.clear_card_wrong(con, ss.user, wqid)
                        st.rerun()


def _view_note(subjects):
    groups = logic.get_core_groups(QUESTIONS, subjects)
    rep_ids = []
    for subj in subjects:
        for core_id, variant_ids in groups.get(subj, {}).items():
            rep_ids.append(min(variant_ids))
    by_tag = logic.group_ids_by_tag(QUESTIONS, rep_ids)
    total = sum(len(v) for v in by_tag.values())
    st.caption(f"{total}개 개념을 과목·태그별로 정리했습니다.")
    for (subject, tag), ids in by_tag.items():
        st.markdown(f'<div class="group-title">{subject_label(subject)} · {tag_display(tag)}</div>', unsafe_allow_html=True)
        for qid in ids:
            q = QUESTIONS[qid]
            answer_text = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]][q["answer"] - 1]
            with st.container(border=True):
                st.write(f"**{q['question']}**")
                st.write(f"정답: {answer_text}")
                st.caption(q["explanation"])


def _view_ox(subjects):
    if not ss.ox_pool:
        if st.button("OX 퀴즈 시작"):
            concepts = [QUESTIONS[qid] for qid in logic.pick_pool(QUESTIONS, subjects)]
            ss.ox_pool = logic.build_ox_pool(concepts)
            ss.ox_idx = 0
            st.rerun()
    elif ss.ox_idx >= len(ss.ox_pool):
        correct_n = sum(1 for it in ss.ox_pool if it.get("_correct"))
        st.success(f"OX 퀴즈 완료! {correct_n}/{len(ss.ox_pool)} 정답")
        if st.button("다시 풀기", key="ox_restart"):
            ss.ox_pool = []
            st.rerun()
    else:
        item = ss.ox_pool[ss.ox_idx]
        st.markdown(
            f'<span class="pill">{subject_label(item["subject"])}</span>'
            f'<span class="pill pill-sub">{source_badge_text(item)}</span>', unsafe_allow_html=True,
        )
        st.caption(item["stem"])
        st.subheader(item["statement"])
        if not item.get("_answered"):
            c1, c2 = st.columns(2)
            if c1.button("⭕ 참", key=f"ox_true_{ss.ox_idx}"):
                item["_answered"] = True
                item["_correct"] = item["truth"] is True
                if item["_correct"]:
                    db.clear_ox_wrong(con, ss.user, item["qid"])
                else:
                    db.add_ox_wrong(con, ss.user, item["qid"])
                st.rerun()
            if c2.button("❌ 거짓", key=f"ox_false_{ss.ox_idx}"):
                item["_answered"] = True
                item["_correct"] = item["truth"] is False
                if item["_correct"]:
                    db.clear_ox_wrong(con, ss.user, item["qid"])
                else:
                    db.add_ox_wrong(con, ss.user, item["qid"])
                st.rerun()
        else:
            if item["_correct"]:
                st.markdown('<div class="result-ok">정답이에요!</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="result-bad">오답이에요. 정답은 {"참" if item["truth"] else "거짓"}입니다.</div>',
                             unsafe_allow_html=True)
            st.caption(item["explanation"])
            if st.button("다음 ▶", key=f"ox_next_{ss.ox_idx}"):
                ss.ox_idx += 1
                st.rerun()

    wrong_ids = db.get_ox_wrong_ids(con, ss.user, ss.exam)
    if wrong_ids:
        st.markdown(f'<div class="group-title">📋 OX 오답 · 개념별로 확인 ({len(wrong_ids)}개)</div>', unsafe_allow_html=True)
        groups = logic.group_ids_by_tag(QUESTIONS, wrong_ids)
        for (subject, tag), ids in groups.items():
            st.markdown(f'<div class="group-title">{subject_label(subject)} · {tag_display(tag)}</div>', unsafe_allow_html=True)
            for wqid in ids:
                key = f"wrong_ox_item_{wqid}"
                if key not in ss:
                    ss[key] = logic.build_ox_pool([QUESTIONS[wqid]])[0]
                item = ss[key]
                st.caption(item["stem"])
                st.write(item["statement"])
                if not item.get("_answered"):
                    cc1, cc2, cc3 = st.columns(3)
                    if cc1.button("⭕ 참", key=f"wrongox_true_{wqid}"):
                        item["_answered"] = True
                        if item["truth"] is True:
                            db.clear_ox_wrong(con, ss.user, wqid)
                            del ss[key]
                            st.rerun()
                        else:
                            item["_correct"] = False
                    if cc2.button("❌ 거짓", key=f"wrongox_false_{wqid}"):
                        item["_answered"] = True
                        if item["truth"] is False:
                            db.clear_ox_wrong(con, ss.user, wqid)
                            del ss[key]
                            st.rerun()
                        else:
                            item["_correct"] = False
                    if cc3.button("목록서 지우기", key=f"wrongox_clear_{wqid}"):
                        db.clear_ox_wrong(con, ss.user, wqid)
                        if key in ss:
                            del ss[key]
                        st.rerun()
                else:
                    st.error(f"오답이에요. 정답은 {'참' if item['truth'] else '거짓'}입니다.")
                    st.caption(item["explanation"])
                    if st.button("다시 시도", key=f"wrongox_retry_{wqid}"):
                        del ss[key]
                        st.rerun()


def _gather_mindmap_items(subject, limit=None, wrong_only=False):
    """마인드맵 재료 수집. 이 앱엔 문제별 세부 개념 태그가 없어서(회차별 CBT는 tag가 회차명일 뿐)
    core_id(같은 문제의 회차별 중복 묶음)당 대표 문제 하나씩을 뽑아 AI에게 넘긴다.

    wrong_only=False (개념노트용): 오답 여부와 상관없이, 개념노트 "카드"와 정확히 같은 모집단
    (source=="concept", logic.pick_pool과 동일한 기준)을 하나도 빠짐없이 넘긴다 — 카드 개수(예:
    1과목 192개)와 마인드맵에 들어가는 개념 수가 어긋나지 않게 하기 위함. limit을 명시로 주지
    않으면 샘플링하지 않는다.
    wrong_only=True (AI 코치용): 소스(개념/CBT 기출) 구분 없이 실제로 틀린 적 있는 문제만 골라서
    "약점 지도"를 만든다."""
    ids_in_subject = [
        qid for qid in ALL_IDS
        if QUESTIONS[qid]["subject"] == subject and (wrong_only or QUESTIONS[qid]["source"] == "concept")
    ]
    by_core = {}
    for qid in ids_in_subject:
        by_core.setdefault(QUESTIONS[qid]["core_id"], []).append(qid)

    per_q = db.get_per_question_stats(con, ss.user, ss.exam)
    reps = []
    for qids in sorted(by_core.values(), key=lambda qids: qids[0]):
        wrong_first = [qid for qid in qids if per_q.get(qid, {}).get("wrong", 0) > 0]
        reps.append(wrong_first[0] if wrong_first else qids[0])

    if wrong_only:
        reps = [qid for qid in reps if per_q.get(qid, {}).get("wrong", 0) > 0]
        reps = reps[:limit] if limit else reps
    elif limit and len(reps) > limit:
        step = len(reps) / limit
        reps = [reps[int(i * step)] for i in range(limit)]

    items, idx_to_qid = [], {}
    for i, qid in enumerate(reps):
        q = QUESTIONS[qid]
        snippet = " ".join(q["question"].split())[:70]
        items.append({"idx": i, "question": snippet, "wrong": per_q.get(qid, {}).get("wrong", 0) > 0})
        idx_to_qid[i] = qid
    return items, idx_to_qid


def _mindmap_new_node_id(concepts):
    n = sum(1 for c in concepts if str(c.get("id", "")).startswith("user_"))
    while True:
        n += 1
        cid = f"user_{n}"
        if not any(c["id"] == cid for c in concepts):
            return cid


def _mindmap_collect_descendants(concepts, node_id):
    """node_id 자신 + 그 아래 모든 하위 개념(세부의 세부까지)의 id 집합. 가지를 지울 때 고아 노드가
    안 남게 통째로 걷어내기 위함."""
    ids = {node_id}
    changed = True
    while changed:
        changed = False
        for c in concepts:
            if c.get("parent_concept") in ids and c["id"] not in ids:
                ids.add(c["id"])
                changed = True
    return ids


def _render_mindmap_board(board_id, data, per_q=None, show_insight=False, subject_lbl=""):
    """DB에 저장된 보드 하나(카테고리/개념/엣지 + 사용자가 추가한 가지)를 그래프로 그리고,
    클릭한 개념의 이론·맨션(댓글)·가지 추가 UI까지 한 화면에서 다룬다. board_id가 있으면
    (AI 생성 보드) 클릭/댓글/가지추가가 전부 DB에 영구 저장된다."""
    categories = data.get("categories", [])
    concepts = data.get("concepts", [])
    edges = data.get("edges", [])
    if not concepts:
        st.info("마인드맵을 만들 만한 개념을 찾지 못했어요.")
        return

    per_q = per_q or {}
    weak_ids = {c["id"] for c in concepts
                if any(per_q.get(qid, {}).get("wrong", 0) > 0 for qid in c.get("covers", []))}

    if show_insight:
        if data.get("insight"):
            st.info(f"🔎 **이 마인드맵으로 보는 취약점 분석**\n\n{data['insight']}")
        elif weak_ids and st.button("🔎 이 마인드맵 취약점 분석 보기", key=f"mm_insight_{board_id}"):
            client = _get_gemini_client()
            if client:
                weak_list = [{"label": c["label"], "summary": c.get("summary", "")}
                             for c in concepts if c["id"] in weak_ids]
                with st.spinner("취약점을 분석하고 있어요..."):
                    try:
                        insight = ai_coach.generate_mindmap_insight(client, subject_lbl, weak_list)
                        data["insight"] = insight
                        db.save_mindmap_board_data(con, board_id, data)
                        st.rerun()
                    except Exception as e:
                        st.error(f"분석을 가져오지 못했어요: {e}")

    ss.setdefault("mindmap_expanded", {})
    expanded = ss.mindmap_expanded.setdefault(board_id, set())
    bridge_label = f"__mmclick_{board_id}__"
    st.markdown(
        f'<style>div[data-testid="stTextInput"]:has(input[aria-label="{bridge_label}"]) {{ display:none; }}</style>',
        unsafe_allow_html=True,
    )
    clicked = st.text_input(bridge_label, key=f"mmbridge_{board_id}", label_visibility="collapsed")

    _render_mindmap_interactive(categories, concepts, edges, weak_ids, expanded, bridge_label,
                                 show_weak=show_insight)
    st.caption("마우스 휠로 확대/축소, 드래그로 이동·노드 재배치가 돼요. 세부 개념이 있는 박스를 클릭하면 펼쳐지고, "
               "그렇지 않은 박스를 클릭하면 아래에 이론 설명이 떠요.")

    by_id = {c["id"]: c for c in concepts}
    ss.setdefault("mindmap_selected", {})
    if clicked and clicked in by_id:
        ss[f"mmbridge_{board_id}"] = ""  # 다음 클릭이 같은 노드여도 다시 반응하도록 리셋
        has_children = any(c.get("parent_concept") == clicked for c in concepts)
        if has_children:
            if clicked in expanded:
                expanded.discard(clicked)
            else:
                expanded.add(clicked)
        ss.mindmap_selected[board_id] = clicked
        st.rerun()

    selected_id = ss.mindmap_selected.get(board_id)
    node_labels = {c["id"]: c["label"] for c in concepts}
    pick_options = ["(선택 안 함)"] + [c["id"] for c in concepts]
    pick_default = pick_options.index(selected_id) if selected_id in pick_options else 0
    picked = st.selectbox(
        "🔍 개념 선택해서 자세히 보기 (그래프 클릭이 안 먹히는 환경이면 여기서 골라도 똑같이 돼요)",
        pick_options, index=pick_default, format_func=lambda cid: node_labels.get(cid, cid),
        key=f"mmpick_{board_id}",
    )
    if picked != "(선택 안 함)":
        selected_id = picked
        ss.mindmap_selected[board_id] = picked

    if selected_id and selected_id in by_id:
        c = by_id[selected_id]
        with st.container(border=True):
            st.markdown(f"**{c['label']}**" + (" 🔴" if show_insight and selected_id in weak_ids else ""))
            if c.get("summary"):
                st.caption(c["summary"])
            if c.get("theory"):
                st.write(c["theory"])
            qids = [qid for qid in c.get("covers", []) if qid in QUESTIONS]
            if qids:
                with st.expander(f"관련 문제 {len(qids)}개"):
                    for qid in qids:
                        mark = "❌" if per_q.get(qid, {}).get("wrong", 0) > 0 else "·"
                        st.caption(f"{mark} {' '.join(QUESTIONS[qid]['question'].split())[:60]}")

            if board_id:
                comments = db.get_mindmap_comments(con, board_id, selected_id)
                if comments:
                    st.markdown("💬 **맨션(내가 남긴 메모)**")
                    for cm in comments:
                        st.caption(f"· {cm['text']}")
                new_comment = st.text_area("맨션 추가하기 (이론 정리, 추가 메모 등)",
                                            key=f"mmcomment_{board_id}_{selected_id}", height=70)
                if st.button("💬 맨션 남기기", key=f"mmcomment_btn_{board_id}_{selected_id}"):
                    if new_comment.strip():
                        db.add_mindmap_comment(con, board_id, selected_id, ss.user, new_comment.strip())
                        st.rerun()

                with st.expander("🗑️ 이 가지 삭제하기"):
                    to_remove = _mindmap_collect_descendants(concepts, selected_id)
                    n_children = len(to_remove) - 1
                    if n_children:
                        st.caption(f"이 개념 아래 하위 개념 {n_children}개도 함께 삭제돼요. 되돌릴 수 없어요.")
                    else:
                        st.caption("삭제하면 되돌릴 수 없어요.")
                    confirm_del = st.checkbox("정말 삭제할게요", key=f"mmdel_confirm_{board_id}_{selected_id}")
                    if st.button("🗑️ 삭제", key=f"mmdel_btn_{board_id}_{selected_id}", disabled=not confirm_del):
                        data["concepts"] = [c for c in concepts if c["id"] not in to_remove]
                        data["edges"] = [e for e in edges
                                          if e["from"] not in to_remove and e["to"] not in to_remove]
                        db.delete_mindmap_comments_for_nodes(con, board_id, list(to_remove))
                        db.save_mindmap_board_data(con, board_id, data)
                        expanded.discard(selected_id)
                        ss.mindmap_selected[board_id] = None
                        st.rerun()

    if board_id:
        with st.expander("➕ 가지 추가하기 (내가 직접 개념 추가)"):
            new_label = st.text_input("개념 이름", key=f"mmnew_label_{board_id}")
            new_summary = st.text_input("한 줄 요약", key=f"mmnew_summary_{board_id}")
            new_theory = st.text_area("이론 설명(선택)", key=f"mmnew_theory_{board_id}", height=70)
            parent_options = ["(카테고리 바로 아래)"] + [c["id"] for c in concepts]
            parent_pick = st.selectbox(
                "어디에 붙일까요?", parent_options,
                format_func=lambda cid: "(카테고리 바로 아래)" if cid == "(카테고리 바로 아래)" else node_labels.get(cid, cid),
                key=f"mmnew_parent_{board_id}",
            )
            cat_options = [cat["id"] for cat in categories]
            if parent_pick == "(카테고리 바로 아래)" and cat_options:
                cat_pick = st.selectbox("카테고리", cat_options,
                                         format_func=lambda cid: next((cc["label"] for cc in categories if cc["id"] == cid), cid),
                                         key=f"mmnew_cat_{board_id}")
            else:
                cat_pick = by_id.get(parent_pick, {}).get("category", cat_options[0] if cat_options else "")
            if st.button("➕ 가지 추가", key=f"mmnew_add_{board_id}", disabled=not new_label.strip()):
                new_id = _mindmap_new_node_id(concepts)
                concepts.append({
                    "id": new_id, "label": new_label.strip(), "category": cat_pick,
                    "summary": new_summary.strip(), "theory": new_theory.strip(),
                    "parent_concept": "" if parent_pick == "(카테고리 바로 아래)" else parent_pick,
                    "covers": [], "source": "user",
                })
                data["concepts"] = concepts
                db.save_mindmap_board_data(con, board_id, data)
                if parent_pick != "(카테고리 바로 아래)":
                    expanded.add(parent_pick)
                ss.mindmap_selected[board_id] = new_id
                st.rerun()


def _render_mindmap_section(subject, wrong_only, cache_ns, empty_caption, spinner_text, empty_data_caption):
    """개념노트(전체 개념 지도)와 AI 코치(오답/약점 지도)가 공유하는 마인드맵 생성 로직.
    cache_ns로 두 용도를 DB에서 분리해서, 같은 과목이어도 서로 다른 그래프를 따로 저장·기억한다."""
    client = _get_gemini_client()
    if client is None:
        st.warning("마인드맵은 AI 학습 코치 기능이라 Gemini API 키가 필요해요.")
        st.caption("'AI 학습 코치' 메뉴에서 키를 먼저 등록하면 여기서도 바로 쓸 수 있어요.")
        return

    board = db.get_mindmap_board(con, ss.user, ss.exam, subject, cache_ns)
    if st.button("🔄 마인드맵 다시 생성" if board else "🧠 마인드맵 생성", key=f"mindmap_gen_{cache_ns}_{subject}"):
        items, idx_to_qid = _gather_mindmap_items(subject, wrong_only=wrong_only)
        if len(items) < 3:
            st.info(empty_data_caption)
        else:
            with st.spinner(spinner_text):
                try:
                    mode = "weak" if wrong_only else "overview"
                    result = ai_coach.generate_concept_mindmap(client, subject_label(subject), items, mode=mode)
                    concepts = result.setdefault("concepts", [])
                    covered = {i for c in concepts for i in c.get("covers", [])}
                    missing = [it["idx"] for it in items if it["idx"] not in covered]
                    if missing:
                        # AI가 누락시킨 카드가 있어도 유실 없이 "기타" 노드로 흡수한다(빠짐없이
                        # 정리해야 한다는 개념노트 마인드맵의 원칙을 코드로 강제).
                        categories = result.setdefault("categories", [])
                        fallback_cat = categories[0]["id"] if categories else "cat_etc"
                        if not categories:
                            categories.append({"id": fallback_cat, "label": "기타"})
                        concepts.append({
                            "id": "_uncovered", "label": "기타(분류 보류)", "category": fallback_cat,
                            "summary": "아직 세부 분류되지 않은 개념", "theory": "",
                            "parent_concept": "", "covers": missing,
                        })
                    for c in concepts:
                        c["covers"] = [idx_to_qid[i] for i in c.get("covers", []) if i in idx_to_qid]
                        c["source"] = "ai"
                    saved = db.save_mindmap_board(con, ss.user, ss.exam, subject, cache_ns, "", result)
                    ss.setdefault("mindmap_expanded", {})[saved["id"]] = set()
                    st.rerun()
                except Exception as e:
                    st.error(f"마인드맵을 만들지 못했어요: {e}")

    if not board:
        st.caption(empty_caption)
        return

    per_q = db.get_per_question_stats(con, ss.user, ss.exam)
    _render_mindmap_board(board["id"], board["data"], per_q, show_insight=wrong_only, subject_lbl=subject_label(subject))


def _view_mindmap(subjects):
    """개념노트의 마인드맵: 오답 여부와 상관없이 그 과목의 개념 전체를 한눈에 정리하는 용도."""
    if len(subjects) != 1:
        st.info("마인드맵은 과목을 하나 골랐을 때 볼 수 있어요. 위에서 과목을 하나 선택해주세요.")
        return
    subject = subjects[0]
    _render_mindmap_section(
        subject, wrong_only=False, cache_ns="concept",
        empty_caption="위 버튼을 누르면 이 과목의 개념 전체를 한눈에 정리한 마인드맵을 만들어줘요.",
        spinner_text="이 과목의 개념을 전체적으로 정리하고 있어요...",
        empty_data_caption="마인드맵을 만들기엔 이 과목 문제가 아직 너무 적어요.",
    )


# =====================================================================
# 나만의 마인드맵 (백지에서 시작, AI가 초안 제안 -> 사용자가 가지/맨션 추가)
# =====================================================================
def view_custom_mindmap():
    st.header("🗺️ 나만의 마인드맵")
    st.caption("주제를 입력하면 AI가 기본 틀을 제안해요. 그 위에 가지(개념)를 추가하고, 각 개념에 맨션(메모)을 남기면서 내 방식대로 정리해보세요.")

    boards = db.list_custom_boards(con, ss.user, ss.exam)
    ss.setdefault("custom_mindmap_active", None)

    with st.expander("➕ 새 마인드맵 만들기", expanded=not boards):
        topic = st.text_input("주제 (예: 프로세스 스케줄링, SQL 정규화, 3과목 전체 등)", key="custom_mm_topic")
        if st.button("🧠 AI 초안으로 시작", key="custom_mm_start", disabled=not topic.strip()):
            if any(b["title"] == topic.strip() for b in boards):
                st.error("같은 이름의 마인드맵이 이미 있어요. 다른 이름을 써주세요.")
            else:
                client = _get_gemini_client()
                if client is None:
                    st.warning("Gemini API 키가 필요해요. 'AI 학습 코치' 메뉴에서 먼저 등록해주세요.")
                else:
                    with st.spinner("초안을 만들고 있어요..."):
                        try:
                            result = ai_coach.generate_custom_mindmap_seed(client, exam_cfg["label"], topic.strip())
                            for c in result.get("concepts", []):
                                c["source"] = "ai"
                            saved = db.save_mindmap_board(con, ss.user, ss.exam, 0, "custom", topic.strip(), result)
                            ss.custom_mindmap_active = saved["id"]
                            st.rerun()
                        except Exception as e:
                            st.error(f"초안을 만들지 못했어요: {e}")

    if not boards:
        st.info("아직 만든 마인드맵이 없어요. 위에서 주제를 입력해 시작해보세요.")
        return

    board_by_id = {b["id"]: b for b in boards}
    if ss.custom_mindmap_active not in board_by_id:
        ss.custom_mindmap_active = boards[0]["id"]

    labels = {b["id"]: b["title"] for b in boards}
    active = st.radio("내 마인드맵 목록", list(labels.keys()), format_func=lambda bid: labels[bid],
                       key="custom_mm_picker", horizontal=True,
                       index=list(labels.keys()).index(ss.custom_mindmap_active))
    ss.custom_mindmap_active = active

    if st.button("🗑️ 이 마인드맵 삭제", key=f"custom_mm_delete_{active}"):
        db.delete_mindmap_board(con, active)
        ss.custom_mindmap_active = None
        st.rerun()

    board = db.get_mindmap_board_by_id(con, active)
    if board is None:
        return
    per_q = db.get_per_question_stats(con, ss.user, ss.exam)
    _render_mindmap_board(active, board["data"], per_q)


# =====================================================================
# 오답노트
# =====================================================================
def view_wrong():
    st.header("오답노트")
    need, done, stats = db.get_wrong_question_ids(con, ss.user, ss.exam)
    overall = db.get_overall_stats(con, ss.user, ss.exam)
    st.caption(f"누적 풀이 {overall['seen']} · 정답률 {overall['rate']}% · 복습 필요 {len(need)}")

    if overall["seen"] == 0:
        st.info("아직 풀이 기록이 없어요.")
        return

    if not need and not done:
        st.success("복습이 필요한 오답이 없어요. 계속 이렇게 풀어보세요!")
        return

    src_counts = {}
    for qid in need + done:
        q = QUESTIONS.get(qid)
        if q:
            src_counts[q["source"]] = src_counts.get(q["source"], 0) + 1
    source = source_picker_gate("wrong_source_filter", src_counts)
    if source is None:
        return
    need = [qid for qid in need if QUESTIONS.get(qid, {}).get("source") == source]
    done = [qid for qid in done if QUESTIONS.get(qid, {}).get("source") == source]

    counts = {}
    for qid in need + done:
        q = QUESTIONS.get(qid)
        if q:
            counts[q["subject"]] = counts.get(q["subject"], 0) + 1
    subj = subject_picker_gate("wrong_subject_filter", counts)
    if subj is None:
        return
    need = [qid for qid in need if QUESTIONS[qid]["subject"] == subj]
    done = [qid for qid in done if QUESTIONS.get(qid, {}).get("subject") == subj]

    if need:
        if st.button(f"복습 필요 {len(need)}개 다시 풀기"):
            start_focus_session(need, "오답노트")
            goto("퀴즈")
        st.caption("개념별로 바로 다시 풀어보세요. 맞히면 목록에서 자동으로 빠집니다. (삭제해도 정답률 통계에는 영향 없어요)")
        groups = logic.group_ids_by_tag(QUESTIONS, need)
        checked_ids = []
        for (subject, tag), ids in groups.items():
            st.markdown(f'<div class="group-title">{tag_display(tag)}</div>', unsafe_allow_html=True)
            for qid in ids:
                q = QUESTIONS[qid]
                choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]
                cchk, cmain = st.columns([1, 15])
                checked = cchk.checkbox("삭제", key=f"wrong_chk_{qid}", label_visibility="collapsed")
                if checked:
                    checked_ids.append(qid)
                with cmain:
                    st.caption(source_badge_text(q))
                    st.write(q["question"])
                    render_diagram(q)
                    labels = [f"{'①②③④'[i]} {c}" for i, c in enumerate(choices)]
                    picked = st.radio("보기", labels, key=f"wrongq_radio_{qid}", index=None, label_visibility="collapsed")
                    if st.button("확인", key=f"wrongq_check_{qid}", disabled=picked is None):
                        chosen = labels.index(picked)
                        is_correct = (chosen + 1) == q["answer"]
                        db.record_attempt(con, ss.user, qid, chosen + 1, is_correct)
                        if is_correct:
                            st.rerun()
                        else:
                            st.error(f"오답이에요. 정답: {choices[q['answer']-1]}")
        cdel1, cdel2 = st.columns(2)
        if cdel1.button(f"선택 삭제 ({len(checked_ids)})", key="wrong_delete_selected", disabled=not checked_ids):
            db.hide_notes(con, ss.user, checked_ids)
            st.rerun()
        if cdel2.button(f"전체 삭제 ({len(need)})", key="wrong_delete_all_need"):
            db.hide_notes(con, ss.user, need)
            st.rerun()
    else:
        st.success("현재 복습이 필요한 문제가 없어요. 잘하고 있어요!")

    if done:
        st.markdown(f'<div class="group-title">✅ 복습 완료 ({len(done)}개)</div>', unsafe_allow_html=True)
        done_checked = []
        for qid in done[:30]:
            q = QUESTIONS.get(qid)
            if q:
                cchk, cmain = st.columns([1, 15])
                checked = cchk.checkbox("삭제", key=f"wrongdone_chk_{qid}", label_visibility="collapsed")
                if checked:
                    done_checked.append(qid)
                snippet = q['question'][:40] + ('...' if len(q['question']) > 40 else '')
                cmain.caption(f"· {snippet} ({source_badge_text(q)})")
        cdel1, cdel2 = st.columns(2)
        if cdel1.button(f"선택 삭제 ({len(done_checked)})", key="wrongdone_delete_selected", disabled=not done_checked):
            db.hide_notes(con, ss.user, done_checked)
            st.rerun()
        if cdel2.button(f"전체 삭제 ({len(done[:30])})", key="wrongdone_delete_all"):
            db.hide_notes(con, ss.user, done[:30])
            st.rerun()


# =====================================================================
# 자주 틀리는 개념
# =====================================================================
def view_tagstats():
    st.header("자주 틀리는 개념")
    all_stats = db.get_tag_stats(con, ss.user, ss.exam)
    if not all_stats:
        st.info("아직 오답 데이터가 없어요.")
        return

    src_counts = {
        "concept": len(db.get_tag_stats(con, ss.user, ss.exam, source="concept")),
        "cbt": len(db.get_tag_stats(con, ss.user, ss.exam, source="cbt")),
    }
    source = source_picker_gate("tagstats_source_filter", src_counts)
    if source is None:
        return
    stats = db.get_tag_stats(con, ss.user, ss.exam, source=source)
    if not stats:
        st.info("이 유형에는 아직 오답 데이터가 없어요.")
        return

    counts = {}
    for d in stats:
        counts[d["subject"]] = counts.get(d["subject"], 0) + 1
    subj = subject_picker_gate("tagstats_subject_filter", counts)
    if subj is None:
        return
    stats = [d for d in stats if d["subject"] == subj]

    per_q = db.get_per_question_stats(con, ss.user, ss.exam)
    hidden = db.get_hidden_note_ids(con, ss.user)
    for d in stats[:20]:
        rate = round(d["wrong"] / d["seen"] * 100) if d["seen"] else 0
        wrong_qids = [qid for qid in sorted(d["qids"])
                      if per_q.get(qid, {}).get("wrong", 0) > 0 and qid not in hidden]
        with st.container(border=True):
            st.write(f"**{tag_display(d['tag'])}**")
            st.caption(f"오답 {d['wrong']}/{d['seen']}회 ({rate}%) · 통계는 삭제해도 유지돼요")
            if st.button("이 개념 집중 풀기", key=f"tagstat_focus_{d['subject']}_{d['tag']}"):
                start_focus_session(sorted(d["qids"]), "자주 틀리는 개념")
                goto("퀴즈")
            if wrong_qids:
                with st.expander(f"개별 문제 보기 ({len(wrong_qids)}개)"):
                    checked_ids = []
                    for qid in wrong_qids:
                        q = QUESTIONS.get(qid)
                        if not q:
                            continue
                        answer_text = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]][q["answer"] - 1]
                        cchk, cmain = st.columns([1, 15])
                        checked = cchk.checkbox("삭제", key=f"tagstat_chk_{qid}", label_visibility="collapsed")
                        if checked:
                            checked_ids.append(qid)
                        with cmain:
                            st.write(q["question"])
                            render_diagram(q)
                            st.caption(f"정답: {answer_text} · {source_badge_text(q)}")
                    cdel1, cdel2 = st.columns(2)
                    if cdel1.button(f"선택 삭제 ({len(checked_ids)})",
                                     key=f"tagstat_delsel_{d['subject']}_{d['tag']}", disabled=not checked_ids):
                        db.hide_notes(con, ss.user, checked_ids)
                        st.rerun()
                    if cdel2.button(f"전체 삭제 ({len(wrong_qids)})",
                                     key=f"tagstat_delall_{d['subject']}_{d['tag']}"):
                        db.hide_notes(con, ss.user, wrong_qids)
                        st.rerun()


# =====================================================================
# 즐겨찾기
# =====================================================================
def view_bookmarks():
    st.header("즐겨찾기")
    ids = db.get_flagged_ids(con, ss.user, ss.exam)
    if not ids:
        st.info("아직 즐겨찾기한 문제가 없어요. 퀴즈 풀이 중 ☆ 즐겨찾기 버튼으로 추가할 수 있어요.")
        return

    src_counts = {}
    for qid in ids:
        q = QUESTIONS.get(qid)
        if q:
            src_counts[q["source"]] = src_counts.get(q["source"], 0) + 1
    source = source_picker_gate("bm_source_filter", src_counts)
    if source is None:
        return
    ids = [qid for qid in ids if QUESTIONS.get(qid, {}).get("source") == source]

    counts = {}
    for qid in ids:
        q = QUESTIONS.get(qid)
        if q:
            counts[q["subject"]] = counts.get(q["subject"], 0) + 1
    subj = subject_picker_gate("bm_subject_filter", counts)
    if subj is None:
        return
    ids = [qid for qid in ids if QUESTIONS.get(qid, {}).get("subject") == subj]

    if st.button(f"즐겨찾기 {len(ids)}개 풀어보기"):
        start_focus_session(ids, "즐겨찾기")
        goto("퀴즈")
    groups = logic.group_ids_by_tag(QUESTIONS, ids)
    checked_ids = []
    for (subject, tag), qids in groups.items():
        st.markdown(f'<div class="group-title">{tag_display(tag)}</div>', unsafe_allow_html=True)
        for qid in qids:
            q = QUESTIONS[qid]
            answer_text = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]][q["answer"] - 1]
            with st.container(border=True):
                cchk, cmain = st.columns([1, 15])
                checked = cchk.checkbox("삭제", key=f"bm_chk_{qid}", label_visibility="collapsed")
                if checked:
                    checked_ids.append(qid)
                with cmain:
                    st.write(f"**{q['question']}**")
                    st.caption(f"정답: {answer_text} · {source_badge_text(q)}")
                    if st.button("★ 해제", key=f"unflag_{qid}"):
                        db.remove_flag(con, ss.user, qid)
                        st.rerun()
    cdel1, cdel2 = st.columns(2)
    if cdel1.button(f"선택 삭제 ({len(checked_ids)})", key="bm_delete_selected", disabled=not checked_ids):
        for qid in checked_ids:
            db.remove_flag(con, ss.user, qid)
        st.rerun()
    if cdel2.button(f"전체 삭제 ({len(ids)})", key="bm_delete_all"):
        for qid in ids:
            db.remove_flag(con, ss.user, qid)
        st.rerun()


# =====================================================================
# AI 학습 코치 (Gemini) — 전부 사용자가 버튼을 눌러야만 호출된다
# =====================================================================
def _get_d_day():
    goal = db.get_study_goal(con, ss.user, ss.exam)
    d_day = None
    if goal["exam_date"]:
        d_day = (datetime.date.fromisoformat(goal["exam_date"]) - datetime.date.today()).days
    return goal, d_day


def _build_strategy_block():
    _, d_day = _get_d_day()
    subj_stats_raw = db.get_subject_stats(con, ss.user, ss.exam)
    return ai_coach.build_strategy_block(exam_cfg, exam_cfg["subject_label"], subj_stats_raw, d_day)


def _coach_start_chat(qid, q, choices, correct_text):
    wrong_chosen = db.get_wrong_attempt_history(con, ss.user, qid)
    wrong_texts = [choices[c - 1] for c in wrong_chosen if 1 <= c <= 4]
    last_wrong = wrong_texts[-1] if wrong_texts else "잘 모르겠음"
    ss.coach_active_qid = qid
    ss.coach_context = ai_coach.build_context_block(q["question"], choices, correct_text, wrong_texts)
    ss.coach_strategy = _build_strategy_block()

    saved = db.get_coach_messages(con, ss.user, qid)
    if saved:
        ss.coach_messages = saved
    else:
        opening = ai_coach.opening_question(last_wrong, max(len(wrong_texts), 1))
        ss.coach_messages = [{"role": "model", "text": opening}]
        db.save_coach_message(con, ss.user, qid, "model", opening)


def _render_coach_chat_page(client):
    qid = ss.coach_active_qid
    q = QUESTIONS.get(qid)
    if q is None:
        ss.coach_active_qid = None
        st.rerun()
        return
    choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]

    if st.button("◀ 목록으로", key="coach_back"):
        ss.coach_active_qid = None
        st.rerun()

    st.markdown(
        f'<span class="pill">{subject_label(q["subject"])}</span>'
        f'<span class="pill pill-sub">{source_badge_text(q)}</span>', unsafe_allow_html=True,
    )
    st.write(f"**{q['question']}**")
    st.caption("정답: " + choices[q["answer"] - 1])
    st.divider()

    for m in ss.coach_messages:
        with st.chat_message("assistant" if m["role"] == "model" else "user"):
            st.write(m["text"])

    prompt = st.chat_input("선생님에게 답해보세요...")
    if prompt:
        ss.coach_messages.append({"role": "user", "text": prompt})
        db.save_coach_message(con, ss.user, qid, "user", prompt)
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("선생님이 생각하고 있어요..."):
                try:
                    reply = ai_coach.chat_reply(
                        client, ss.coach_context, ss.coach_messages, strategy_block=ss.coach_strategy,
                    )
                except Exception as e:
                    st.error(f"응답을 받아오지 못했어요: {e}")
                    reply = None
            if reply:
                st.write(reply)
                ss.coach_messages.append({"role": "model", "text": reply})
                db.save_coach_message(con, ss.user, qid, "model", reply)


def _render_coach_variant(client, qid, q, choices, correct_text):
    if st.button("🔀 변형 문제 만들기", key=f"coach_variant_btn_{qid}"):
        with st.spinner("변형 문제를 만들고 있어요..."):
            try:
                real_wrong_n = len(db.get_wrong_attempt_history(con, ss.user, qid))
                variant_wrong_n = ss.coach_variant_wrong_counts.get(qid, 0)
                subj_stats_raw = db.get_subject_stats(con, ss.user, ss.exam)
                stat = next((s for s in subj_stats_raw if s["subject"] == q["subject"]), None)
                subject_status = ai_coach.subject_status_text(exam_cfg, q["subject"], stat)
                variant = ai_coach.generate_variant_question(
                    client, subject_label(q["subject"]), q["question"], choices, correct_text, q["explanation"],
                    wrong_count=max(real_wrong_n + variant_wrong_n, 1),
                    subject_status=subject_status, strategy_block=_build_strategy_block(),
                )
                ss.coach_variant_qid = qid
                ss.coach_variant = variant
                ss.coach_variant_result = None
            except Exception as e:
                st.error(f"변형 문제를 만들지 못했어요: {e}")

    if ss.coach_variant_qid == qid and ss.coach_variant:
        v = ss.coach_variant
        with st.container(border=True):
            st.caption("✏️ AI가 지금 이 학습자 상황에 맞춰 만든 변형 문제")
            st.write(v["question"])
            v_labels = [f"{'①②③④'[i]} {c}" for i, c in enumerate(v["choices"])]
            picked = st.radio("보기", v_labels, key=f"coach_variant_radio_{qid}", index=None,
                               label_visibility="collapsed", disabled=ss.coach_variant_result is not None)
            if st.button("확인", key=f"coach_variant_check_{qid}", disabled=picked is None):
                ss.coach_variant_result = (v_labels.index(picked) + 1) == v["answer"]
                if not ss.coach_variant_result:
                    ss.coach_variant_wrong_counts[qid] = ss.coach_variant_wrong_counts.get(qid, 0) + 1
            if ss.coach_variant_result is not None:
                if ss.coach_variant_result:
                    st.markdown('<div class="result-ok">정답이에요!</div>', unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div class="result-bad">오답 · 정답: {v["choices"][v["answer"] - 1]}</div>',
                        unsafe_allow_html=True,
                    )
                st.caption(v["explanation"])


def _render_coach_batch_variant(qid):
    """체크박스로 여러 문제를 한 번에 골라 만든 변형 문제 표시. 기존 _render_coach_variant(문제 하나씩
    누르는 버튼)와는 별도의 세션 상태(coach_batch_variants/coach_batch_results)를 써서, 두 방식이 서로
    간섭하지 않고 같이 쓸 수 있게 한다."""
    v = ss.coach_batch_variants.get(qid)
    if not v:
        return
    with st.container(border=True):
        st.caption("✏️ AI가 지금 이 학습자 상황에 맞춰 만든 변형 문제 (일괄 생성)")
        st.write(v["question"])
        v_labels = [f"{'①②③④'[i]} {c}" for i, c in enumerate(v["choices"])]
        picked = st.radio("보기", v_labels, key=f"coach_batch_radio_{qid}", index=None,
                           label_visibility="collapsed", disabled=ss.coach_batch_results.get(qid) is not None)
        if st.button("확인", key=f"coach_batch_check_{qid}", disabled=picked is None):
            ss.coach_batch_results[qid] = (v_labels.index(picked) + 1) == v["answer"]
            if not ss.coach_batch_results[qid]:
                ss.coach_variant_wrong_counts[qid] = ss.coach_variant_wrong_counts.get(qid, 0) + 1
        result = ss.coach_batch_results.get(qid)
        if result is not None:
            if result:
                st.markdown('<div class="result-ok">정답이에요!</div>', unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<div class="result-bad">오답 · 정답: {v["choices"][v["answer"] - 1]}</div>',
                    unsafe_allow_html=True,
                )
            st.caption(v["explanation"])


def _get_gemini_client():
    """AI 학습 코치와 마인드맵/관련개념 기능이 공유하는 Gemini 클라이언트 조회.
    키가 없으면 None(호출부가 알아서 안내 문구를 보여줌)."""
    ss.setdefault("manual_gemini_key", "")
    try:
        secret_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        secret_key = ""
    active_key = secret_key or ss.manual_gemini_key
    return ai_coach.get_client(active_key) if active_key else None


def _render_related_concepts_box(qid, q, choices):
    """오답 해설 밑에 붙는, AI가 그 자리에서 만들어주는 '헷갈리기 쉬운 인접 개념' 노트.
    이 문제 하나만 교정받고 끝나서 같은 개념의 다른 갈래는 여전히 헷갈리는 걸 막기 위함.
    같은 문제에 대해 반복 호출하지 않도록 세션에 캐시한다."""
    ss.setdefault("related_concepts_cache", {})
    cached = ss.related_concepts_cache.get(qid)
    if cached:
        st.info(f"🔗 **헷갈리기 쉬운 관련 개념**\n\n{cached}")
        return
    if st.button("🔗 헷갈리기 쉬운 관련 개념 보기", key=f"related_btn_{qid}"):
        client = _get_gemini_client()
        if client is None:
            st.caption("Gemini API 키가 없어서 관련 개념을 못 불러와요. 'AI 학습 코치' 메뉴에서 키를 등록해보세요.")
            return
        correct_text = choices[q["answer"] - 1]
        with st.spinner("관련 개념을 정리하고 있어요..."):
            try:
                text = ai_coach.generate_related_concepts(
                    client, subject_label(q["subject"]), q["question"], choices, correct_text,
                    q["explanation"], tag_label=tag_display(q.get("tag", "")),
                )
                ss.related_concepts_cache[qid] = text
                st.rerun()
            except Exception as e:
                st.error(f"관련 개념을 가져오지 못했어요: {e}")


def view_coach():
    st.header("🤖 AI 학습 코치")
    client = _get_gemini_client()

    if client is None:
        st.warning("Gemini API 키가 설정되지 않았어요.")
        st.caption("키는 https://aistudio.google.com/apikey 에서 무료로 발급받을 수 있어요.")
        key_input = st.text_input("Gemini API 키 붙여넣기", type="password", key="gemini_key_input")
        save_local = st.checkbox("이 컴퓨터에 저장해서 다음부터 안 물어보기", value=True, key="gemini_key_save_local")
        if st.button("저장하고 시작", key="gemini_key_submit"):
            if key_input:
                ss.manual_gemini_key = key_input
                if save_local:
                    ss.coach_key_save_failed = not ai_coach.save_key_locally("GEMINI_API_KEY", key_input)
                st.rerun()
            else:
                st.error("키를 입력해주세요.")
        return

    if ss.pop("coach_key_save_failed", False):
        st.info("이 환경(예: Streamlit Cloud)은 파일 저장이 안 돼서, 이번 세션 동안만 키가 유지돼요. "
                 "계속 쓰려면 배포 대시보드의 Secrets 설정에 키를 등록해두세요.")

    if ss.coach_active_qid is not None:
        _render_coach_chat_page(client)
        return

    st.subheader("🎯 현재 페이스 기준 합격 예측")
    subj_stats_raw = db.get_subject_stats(con, ss.user, ss.exam)
    pred = predicted_exam_result(exam_cfg, subj_stats_raw)
    if not pred["has_any_data"]:
        st.caption("아직 풀이 데이터가 부족해요. 문제를 몇 개 풀면 여기에 예상 점수가 나와요.")
    else:
        full_total = sum(exam_cfg["exam_subject_counts"].values())
        c1, c2 = st.columns([1, 2])
        c1.metric("예상 총점", f"{pred['total_correct']}/{full_total}점", help=f"합격선 {exam_cfg['exam_total_pass']}점")
        if pred["overall_pass"]:
            c2.success("지금 페이스면 합격 예상이에요! 이 흐름 유지하면서 약한 부분만 다지면 됩니다.")
        else:
            reasons = []
            if pred["total_correct"] < exam_cfg["exam_total_pass"]:
                reasons.append("전체 총점 부족")
            if pred["fail_subjects"]:
                reasons.append("과락 위험 과목: " + ", ".join(subject_label(s) for s in pred["fail_subjects"]))
            c2.warning("지금 페이스면 아직 불합격 예상이에요 — " + " / ".join(reasons) + ". 아래 학습 계획을 참고하세요.")
        st.caption("⚠️ 지금까지 푼 문제의 과목별 정답률을 실전 배점에 대입한 참고용 추정치이며, 실제 시험과 다를 수 있어요.")

    st.divider()
    st.subheader("📅 이번 학습 계획 받기")
    if st.button("AI에게 학습 계획 물어보기", key="coach_plan_btn"):
        goal, d_day = _get_d_day()
        overall = db.get_overall_stats(con, ss.user, ss.exam)
        stats_for_ai = [
            {"label": subject_label(d["subject"]), "wrong": d["wrong"], "seen": d["seen"],
             "rate": round(d["wrong"] / d["seen"] * 100) if d["seen"] else 0}
            for d in subj_stats_raw
        ]
        tag_stats = db.get_tag_stats(con, ss.user, ss.exam)
        weak_tags_for_ai = [
            {"label": subject_label(t["subject"]), "tag": tag_display(t["tag"]),
             "wrong": t["wrong"], "seen": t["seen"]}
            for t in tag_stats[:8]
        ]
        available_rounds = db.get_cbt_rounds(con, ss.exam)
        with st.spinner("학습 계획을 분석하고 있어요..."):
            try:
                ss.coach_plan_text = ai_coach.generate_study_plan(
                    client, exam_cfg["label"], d_day, stats_for_ai, overall, goal["daily_target"],
                    weak_tags=weak_tags_for_ai, available_rounds=available_rounds,
                    strategy_block=_build_strategy_block(),
                )
            except Exception as e:
                st.error(f"학습 계획을 받아오지 못했어요: {e}")
    if ss.coach_plan_text:
        st.info(ss.coach_plan_text)

    st.divider()
    st.subheader("🧠 오답·약점 마인드맵")
    st.caption("오답노트·자주 틀리는 개념 데이터를 개념 단위로 묶어서, 내가 어떤 부분에서 왜 헷갈리는지 한눈에 볼 수 있어요.")
    ss.setdefault("coach_mindmap_subject", ALL_SUBJECTS[0])
    coach_mm_subject = st.radio(
        "과목", ALL_SUBJECTS, format_func=subject_label, horizontal=True, key="coach_mindmap_subject",
    )
    _render_mindmap_section(
        coach_mm_subject, wrong_only=True, cache_ns="weak",
        empty_caption="위 버튼을 누르면 이 과목에서 지금까지 틀린 문제들을 개념 단위로 묶어 약점 지도를 만들어줘요.",
        spinner_text="오답과 자주 틀리는 개념을 분석해서 약점 지도를 만들고 있어요...",
        empty_data_caption="이 과목은 아직 틀린 문제가 3개 미만이라 약점 지도를 만들기엔 데이터가 부족해요.",
    )

    st.divider()
    st.subheader("🔁 반복해서 틀리는 문제")
    st.caption("2번 이상 틀린 문제를 대상으로, 왜 헷갈리는지 AI와 대화하거나 변형 문제로 다시 확인해볼 수 있어요.")
    per_q = db.get_per_question_stats(con, ss.user, ss.exam)
    repeated = sorted(
        [(qid, s) for qid, s in per_q.items() if s["wrong"] >= 2 and qid in QUESTIONS],
        key=lambda kv: -kv[1]["wrong"],
    )
    if not repeated:
        st.caption("아직 2번 이상 반복해서 틀린 문제가 없어요. 문제를 풀다 보면 여기에 나타나요.")
        return

    counts = {}
    for qid, s in repeated:
        counts[QUESTIONS[qid]["subject"]] = counts.get(QUESTIONS[qid]["subject"], 0) + 1
    subj = subject_picker_gate("coach_repeat_subject_filter", counts)
    if subj is None:
        return
    repeated = [(qid, s) for qid, s in repeated if QUESTIONS[qid]["subject"] == subj]
    shown = repeated[:15]

    st.caption("문제마다 '🔀 변형 문제 만들기'를 따로 눌러도 되고, 아래에서 여러 개를 체크한 뒤 "
               "한 번에 만들어도 돼요(API 호출을 아낄 수 있어요).")
    if st.button("🔀 체크한 문제 한 번에 변형 문제 만들기", key="coach_batch_gen_btn"):
        picked_qids = [qid for qid, _ in shown if ss.get(f"coach_batch_pick_{qid}")]
        if not picked_qids:
            st.warning("체크한 문제가 없어요. 아래 목록에서 먼저 체크해주세요.")
        else:
            subj_stats_raw = db.get_subject_stats(con, ss.user, ss.exam)
            strategy_block = _build_strategy_block()
            ok, failed = 0, 0
            with st.spinner(f"{len(picked_qids)}개 문제의 변형 문제를 만들고 있어요..."):
                for qid in picked_qids:
                    q = QUESTIONS[qid]
                    choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]
                    correct_text = choices[q["answer"] - 1]
                    try:
                        real_wrong_n = len(db.get_wrong_attempt_history(con, ss.user, qid))
                        variant_wrong_n = ss.coach_variant_wrong_counts.get(qid, 0)
                        stat = next((st_ for st_ in subj_stats_raw if st_["subject"] == q["subject"]), None)
                        subject_status = ai_coach.subject_status_text(exam_cfg, q["subject"], stat)
                        variant = ai_coach.generate_variant_question(
                            client, subject_label(q["subject"]), q["question"], choices, correct_text,
                            q["explanation"], wrong_count=max(real_wrong_n + variant_wrong_n, 1),
                            subject_status=subject_status, strategy_block=strategy_block,
                        )
                        ss.coach_batch_variants[qid] = variant
                        ss.coach_batch_results[qid] = None
                        ok += 1
                    except Exception:
                        failed += 1
            if failed:
                st.error(f"{ok}개는 만들었고, {failed}개는 실패했어요.")
            st.rerun()

    for qid, s in shown:
        q = QUESTIONS[qid]
        choices = [q["choice1"], q["choice2"], q["choice3"], q["choice4"]]
        correct_text = choices[q["answer"] - 1]
        with st.container(border=True):
            st.markdown(
                f'<span class="pill">{subject_label(q["subject"])}</span>'
                f'<span class="pill pill-sub">{source_badge_text(q)}</span>', unsafe_allow_html=True,
            )
            st.write(f"**{q['question']}**")
            st.caption(f"{s['wrong']}번 틀림 · 정답: {correct_text}")
            st.checkbox("☑️ 한 번에 만들기 대상으로 선택", key=f"coach_batch_pick_{qid}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("💬 AI 선생님에게 질문하기", key=f"coach_ask_{qid}"):
                    _coach_start_chat(qid, q, choices, correct_text)
                    st.rerun()
            with c2:
                _render_coach_variant(client, qid, q, choices, correct_text)
            _render_coach_batch_variant(qid)


# =====================================================================
# 키보드 모드: 숫자 1~4로 보기 선택, ←/→로 이전·다음 문제 이동
# (화면 중앙에 가장 가까운 문제에 적용 — 마우스 모드일 때는 리스너가 아무 동작도 하지 않아
#  스마트폰 등 터치 기기에서 켜져 있어도 충돌하지 않는다)
# =====================================================================
def _inject_keyboard_shortcuts(enabled):
    # A listener attached from inside this component's iframe onto window.parent.document
    # is unreliable in Chrome (cross-realm addEventListener onto a sandboxed parent can
    # silently fail to fire). So instead we inject a real <script> element into the PARENT
    # document's own DOM — appendChild (unlike innerHTML) actually executes it — which makes
    # the handler run natively in the parent's own realm, attached exactly once ever.
    components.html(
        """
        <script>
        (function() {
            var doc = window.parent.document;
            doc.__cbtKbdModeOn = """ + ("true" if enabled else "false") + """;
            if (doc.__cbtKbdScriptInjected) return;
            doc.__cbtKbdScriptInjected = true;
            var s = doc.createElement('script');
            s.textContent = [
                '(function() {',
                '    var choiceKey = {',
                "        '1': 0, '2': 1, '3': 2, '4': 3,",
                "        'Numpad1': 0, 'Numpad2': 1, 'Numpad3': 2, 'Numpad4': 3,",
                '    };',
                '    function findGroups() {',
                '        return Array.from(document.querySelectorAll(\\'div[role="radiogroup"]\\'))',
                "            .filter(function(g) { return g.getAttribute('aria-label') === '보기'; });",
                '    }',
                '    function closestToCenter(groups) {',
                '        if (groups.length === 1) return groups[0];',
                '        var vh = window.innerHeight;',
                '        var best = groups[0], bestDist = Infinity;',
                '        groups.forEach(function(g) {',
                '            var r = g.getBoundingClientRect();',
                '            if (r.bottom < 0 || r.top > vh) return;',
                '            var dist = Math.abs((r.top + r.bottom) / 2 - vh / 2);',
                '            if (dist < bestDist) { bestDist = dist; best = g; }',
                '        });',
                '        return best;',
                '    }',
                '    function findNavButton(word) {',
                "        return Array.from(document.querySelectorAll('button'))",
                '            .find(function(b) { return b.textContent.indexOf(word) !== -1 && !b.disabled; });',
                '    }',
                '    function findConfirmButton() {',
                "        var btns = Array.from(document.querySelectorAll('button')).filter(function(b) {",
                '            var t = b.textContent.trim();',
                "            return (t === '확인' || t === '정답 확인') && !b.disabled;",
                '        });',
                '        if (btns.length === 0) return null;',
                '        if (btns.length === 1) return btns[0];',
                '        var vh = window.innerHeight;',
                '        var best = btns[0], bestDist = Infinity;',
                '        btns.forEach(function(b) {',
                '            var r = b.getBoundingClientRect();',
                '            if (r.bottom < 0 || r.top > vh) return;',
                '            var dist = Math.abs((r.top + r.bottom) / 2 - vh / 2);',
                '            if (dist < bestDist) { bestDist = dist; best = b; }',
                '        });',
                '        return best;',
                '    }',
                "    document.addEventListener('keydown', function(e) {",
                '        if (!document.__cbtKbdModeOn) return;',
                '        var active = document.activeElement;',
                "        if (e.key === 'Enter') {",
                "            var isMultilineField = active && (active.tagName === 'TEXTAREA' || active.isContentEditable);",
                '            if (isMultilineField) return;',
                '            var confirmBtn = findConfirmButton();',
                '            if (confirmBtn) { confirmBtn.click(); e.preventDefault(); e.stopPropagation(); }',
                '            return;',
                '        }',
                '        var isTypingField = active && (',
                "            active.tagName === 'TEXTAREA' ||",
                '            active.isContentEditable ||',
                "            (active.tagName === 'INPUT' && ['radio', 'checkbox', 'button', 'submit'].indexOf((active.type || '').toLowerCase()) === -1)",
                '        );',
                '        if (isTypingField) return;',
                "        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {",
                "            var btn = findNavButton(e.key === 'ArrowRight' ? '다음' : '이전');",
                '            if (btn) { btn.click(); e.preventDefault(); e.stopPropagation(); }',
                '            return;',
                '        }',
                '        var idx = choiceKey[e.key];',
                '        if (idx === undefined) return;',
                '        var groups = findGroups();',
                '        if (groups.length === 0) return;',
                '        var target = closestToCenter(groups);',
                '        var inputs = target.querySelectorAll(\\'input[type="radio"]\\');',
                '        if (inputs[idx]) {',
                '            inputs[idx].click();',
                '            inputs[idx].blur();',
                '            e.preventDefault();',
                '            e.stopPropagation();',
                '        }',
                '    }, true);',
                '})();',
            ].join('\\n');
            doc.body.appendChild(s);
        })();
        </script>
        """,
        height=0,
    )


_inject_keyboard_shortcuts(ss.input_mode == "키보드")

# =====================================================================
# 메인 디스패치
# =====================================================================
if ss.nav == "홈":
    view_home()
elif ss.nav == "퀴즈":
    view_quiz()
elif ss.nav == "CBT 모드":
    view_cbt()
elif ss.nav == "개념노트":
    view_concept()
elif ss.nav == "오답노트":
    view_wrong()
elif ss.nav == "자주 틀리는 개념":
    view_tagstats()
elif ss.nav == "즐겨찾기":
    view_bookmarks()
elif ss.nav == "나만의 마인드맵":
    view_custom_mindmap()
else:
    view_coach()
