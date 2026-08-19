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


NAV_ITEMS = ["홈", "퀴즈", "CBT 모드", "개념노트", "오답노트", "자주 틀리는 개념", "즐겨찾기", "AI 학습 코치"]

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


def _esc_xml(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _render_mindmap_svg(nodes, edges, weak_ids=None):
    """개념(태그) 마인드맵: 원형 배치 + 곡선 무방향 연결선. 화살표 없음(개념 관계에는 방향이 없으므로),
    각 연결선/노드에 <title>을 넣어 마우스를 올리면 이유/취약 여부가 브라우저 기본 툴팁으로 뜨게 한다."""
    import math
    weak_ids = weak_ids or set()
    n = max(1, len(nodes))
    radius = max(140, 34 * n / (2 * math.pi) + 60)
    cx = cy = radius + 90
    pos = {}
    node_wh = {}
    for i, node in enumerate(nodes):
        angle = -math.pi / 2 + 2 * math.pi * i / n
        pos[node["id"]] = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
        w = max(64, len(node["label"]) * 13 + 20)
        node_wh[node["id"]] = (w, 32)

    parts = []
    for e in edges:
        if e["from"] not in pos or e["to"] not in pos:
            continue
        x1, y1 = pos[e["from"]]
        x2, y2 = pos[e["to"]]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ddx, ddy = x2 - x1, y2 - y1
        dist = (ddx ** 2 + ddy ** 2) ** 0.5 or 1
        px, py = -ddy / dist, ddx / dist
        bulge = 22
        cxp, cyp = mx + px * bulge, my + py * bulge
        reason = _esc_xml(e.get("reason", ""))
        parts.append(
            f'<path d="M{x1},{y1} Q{cxp},{cyp} {x2},{y2}" fill="none" '
            f'stroke="#93A3C7" stroke-width="2"><title>{reason}</title></path>'
        )
        if reason:
            parts.append(
                f'<text x="{cxp}" y="{cyp}" text-anchor="middle" font-size="10" '
                f'font-family="sans-serif" fill="#5B6B8C">{reason}</text>'
            )
    for node in nodes:
        nid = node["id"]
        x, y = pos[nid]
        w, h = node_wh[nid]
        is_weak = nid in weak_ids
        fill = "#FDECEC" if is_weak else "white"
        stroke = "#D9534F" if is_weak else "#3E5C9A"
        label = _esc_xml(node["label"])
        tip = "자주 틀리는 개념" if is_weak else node["label"]
        parts.append(
            f'<g><rect x="{x - w / 2}" y="{y - h / 2}" width="{w}" height="{h}" rx="8" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="2"><title>{_esc_xml(tip)}</title></rect>'
            f'<text x="{x}" y="{y + 5}" text-anchor="middle" font-size="13" '
            f'font-family="sans-serif" fill="#1C2333">{label}</text></g>'
        )
    width = height = cx + radius + 90
    return f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">{"".join(parts)}</svg>'


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
        st.caption("퀴즈에서 틀린 문제인지, CBT 모드에서 틀린 문제인지 먼저 골라주세요.")
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
    picked = st.radio("보기", choice_labels, key=f"quiz_radio_{qid}", index=None, label_visibility="collapsed")

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
            st.rerun()
        return

    st.caption(f"⏱ 풀이 시간 {elapsed_str(ss.cbtp_start_at)}")

    pool = ss.cbt_pool
    total = len(pool)
    mode = ss.cbt_view_mode

    _practice_render_navigator(pool)

    if mode == "전체 풀기":
        render_indices = list(range(total))
    elif mode == "1문제씩":
        render_indices = [ss.cbt_page]
    else:
        start = ss.cbt_page * ss.cbt_batch_size
        render_indices = list(range(start, min(start + ss.cbt_batch_size, total)))

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
        picked = st.radio("보기", labels, key=f"cbtp_radio_{qid}", index=None, label_visibility="collapsed")
        if st.button("정답 확인", key=f"cbtp_check_{qid}", disabled=picked is None):
            chosen = labels.index(picked)
            is_correct = (chosen + 1) == q["answer"]
            db.record_attempt(con, ss.user, qid, chosen + 1, is_correct)
            ss[f"cbtp_result_{qid}"] = is_correct
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
    return ss.get(f"cbte_radio_{qid}") is not None


def _exam_collect_answers(pool):
    answers = {}
    for qid in pool:
        picked = ss.get(f"cbte_radio_{qid}")
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

    _exam_render_navigator(pool)

    if mode == "전체 풀기":
        render_indices = list(range(total))
    elif mode == "1문제씩":
        render_indices = [ss.cbt_page]
    else:
        start = ss.cbt_page * ss.cbt_batch_size
        render_indices = list(range(start, min(start + ss.cbt_batch_size, total)))

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
        st.radio("보기", labels, key=f"cbte_radio_{qid}", index=None, label_visibility="collapsed")
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


def _build_subject_exam_pool(ids, picked_subject, year_range=None):
    ids = _filter_ids_by_year_range(ids, year_range)
    if picked_subject == "전체":
        return logic.pick_cbt_exam_pool(QUESTIONS, ids, exam_cfg)
    subj = int(picked_subject)
    count = exam_cfg["exam_subject_counts"].get(subj, 20)
    return logic.pick_cbt_pool(QUESTIONS, ids, [subj], limit=count)


def _cbt_subject_year_viewmode_picker(key_prefix, with_year=True):
    picked_subject = st.radio(
        "과목", subject_choices(), format_func=lambda s: "전체" if s == "전체" else subject_label(int(s)),
        horizontal=True, key=f"{key_prefix}_subject",
    )
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
    return picked_subject, year_range, view_mode


def _cbt_exam_random():
    if not ss.cbt_pool:
        picked_subject, year_range, view_mode = _cbt_subject_year_viewmode_picker("cbt_exam_random")
        if st.button("실전 시작", key="cbt_exam_start_random"):
            ss.cbt_pool = _build_subject_exam_pool(CBT_IDS, picked_subject, year_range)
            ss.cbt_submitted = False
            ss.cbt_view_mode = view_mode
            ss.cbt_page = 0
            ss.cbt_start_at = time.time()
            st.rerun()
        return
    _run_cbt_exam(lambda: ss.cbt_pool, "random")


def _cbt_exam_mixed():
    st.caption("실제 기출문제와 AI가 만든 신규 문제를 함께 섞어서, 더 폭넓게 연습하는 모드예요. (기존 실전/연습 모드는 기출문제만 그대로 사용해요)")
    if not ss.cbt_pool:
        picked_subject, year_range, view_mode = _cbt_subject_year_viewmode_picker("cbt_exam_mixed")
        if st.button("실전 시작", key="cbt_exam_start_mixed"):
            ss.cbt_pool = _build_subject_exam_pool(ALL_IDS, picked_subject, year_range)
            ss.cbt_submitted = False
            ss.cbt_view_mode = view_mode
            ss.cbt_page = 0
            ss.cbt_start_at = time.time()
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
        picked_subject = st.radio(
            "과목", subject_choices(), format_func=lambda s: "전체" if s == "전체" else subject_label(int(s)),
            horizontal=True, key="cbt_round_subject",
        )
        view_mode = st.radio(
            "보기 방식", ["전체 풀기", "1문제씩", "3~4문제씩"],
            key="cbt_viewmode_round", horizontal=True,
        )
        if st.button("이 회차 실전 시작", key="cbt_round_start"):
            pool = logic.pick_cbt_round_pool(QUESTIONS, CBT_IDS, picked_round)
            if picked_subject != "전체":
                pool = [qid for qid in pool if QUESTIONS[qid]["subject"] == int(picked_subject)]
            ss.cbt_pool = pool
            ss.cbt_submitted = False
            ss.cbt_view_mode = view_mode
            ss.cbt_page = 0
            ss.cbt_start_at = time.time()
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

    if st.button("다시 시작", key="cbt_exam_restart"):
        ss.cbt_pool = []
        ss.cbt_submitted = False
        st.rerun()


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

        user_input = st.text_input("정답 입력", key=f"card_input_{qid}_{card_mode}")
        c1, c2 = st.columns(2)
        if c1.button("확인", key=f"card_check_{qid}_{card_mode}"):
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


def _gather_mindmap_items(subject, limit=40):
    """마인드맵 재료 수집. 이 앱엔 문제별 세부 개념 태그가 없어서(회차별 CBT는 tag가 회차명일 뿐)
    core_id(같은 문제의 회차별 중복 묶음)당 대표 문제 하나씩을 뽑아 AI에게 넘긴다.
    자주 틀린 문제를 우선하고, 너무 많으면 limit개로 자른다."""
    ids_in_subject = [qid for qid in ALL_IDS if QUESTIONS[qid]["subject"] == subject]
    by_core = {}
    for qid in ids_in_subject:
        by_core.setdefault(QUESTIONS[qid]["core_id"], []).append(qid)

    per_q = db.get_per_question_stats(con, ss.user, ss.exam)
    reps = []
    for qids in by_core.values():
        wrong_first = [qid for qid in qids if per_q.get(qid, {}).get("wrong", 0) > 0]
        reps.append(wrong_first[0] if wrong_first else qids[0])
    reps.sort(key=lambda qid: per_q.get(qid, {}).get("wrong", 0), reverse=True)
    reps = reps[:limit]

    items, idx_to_qid = [], {}
    for i, qid in enumerate(reps):
        q = QUESTIONS[qid]
        snippet = " ".join(q["question"].split())[:70]
        items.append({"idx": i, "question": snippet, "wrong": per_q.get(qid, {}).get("wrong", 0) > 0})
        idx_to_qid[i] = qid
    return items, idx_to_qid


def _view_mindmap(subjects):
    if len(subjects) != 1:
        st.info("마인드맵은 과목을 하나 골랐을 때 볼 수 있어요. 위에서 과목을 하나 선택해주세요.")
        return
    subject = subjects[0]

    client = _get_gemini_client()
    if client is None:
        st.warning("마인드맵은 AI 학습 코치 기능이라 Gemini API 키가 필요해요.")
        st.caption("'AI 학습 코치' 메뉴에서 키를 먼저 등록하면 여기서도 바로 쓸 수 있어요.")
        return

    ss.setdefault("mindmap_cache", {})
    cache_key = f"{ss.exam}_{subject}"
    has_cached = cache_key in ss.mindmap_cache
    if st.button("🔄 마인드맵 다시 생성" if has_cached else "🧠 마인드맵 생성", key=f"mindmap_gen_{subject}"):
        items, idx_to_qid = _gather_mindmap_items(subject)
        if len(items) < 3:
            st.info("마인드맵을 만들기엔 이 과목 문제가 아직 너무 적어요.")
        else:
            with st.spinner("문제들을 개념 단위로 묶어서 마인드맵을 만들고 있어요..."):
                try:
                    result = ai_coach.generate_concept_mindmap(client, subject_label(subject), items)
                    ss.mindmap_cache[cache_key] = {"result": result, "idx_to_qid": idx_to_qid}
                    st.rerun()
                except Exception as e:
                    st.error(f"마인드맵을 만들지 못했어요: {e}")

    cached = ss.mindmap_cache.get(cache_key)
    if not cached:
        st.caption("위 버튼을 누르면 이 과목의 문제(오답 위주)를 바탕으로 개념 마인드맵을 만들어줘요.")
        return

    result, idx_to_qid = cached["result"], cached["idx_to_qid"]
    concepts = result.get("concepts", [])
    edges = result.get("edges", [])
    if not concepts:
        st.info("마인드맵을 만들 만한 개념을 찾지 못했어요.")
        return

    per_q = db.get_per_question_stats(con, ss.user, ss.exam)
    weak_ids = set()
    for c in concepts:
        for idx in c.get("covers", []):
            qid = idx_to_qid.get(idx)
            if qid and per_q.get(qid, {}).get("wrong", 0) > 0:
                weak_ids.add(c["id"])
                break

    svg = _render_mindmap_svg(concepts, edges, weak_ids)
    st.markdown(f'<div style="overflow-x:auto;">{svg}</div>', unsafe_allow_html=True)
    st.caption("🔴 빨간 박스 = 오답이 있는 개념 · 선/박스에 마우스를 올리면 설명이 떠요.")

    with st.expander("개념별 문제 목록 보기"):
        for c in concepts:
            qids = [idx_to_qid[i] for i in c.get("covers", []) if i in idx_to_qid]
            if not qids:
                continue
            st.markdown(f"**{c['label']}** ({len(qids)}문제)")
            for qid in qids:
                q = QUESTIONS.get(qid)
                if q:
                    mark = "❌" if per_q.get(qid, {}).get("wrong", 0) > 0 else "·"
                    st.caption(f"{mark} {' '.join(q['question'].split())[:60]}")


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
                               label_visibility="collapsed")
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

    for qid, s in repeated[:15]:
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
            c1, c2 = st.columns(2)
            with c1:
                if st.button("💬 AI 선생님에게 질문하기", key=f"coach_ask_{qid}"):
                    _coach_start_chat(qid, q, choices, correct_text)
                    st.rerun()
            with c2:
                _render_coach_variant(client, qid, q, choices, correct_text)


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
                "    document.addEventListener('keydown', function(e) {",
                '        if (!document.__cbtKbdModeOn) return;',
                '        var active = document.activeElement;',
                '        var isTypingField = active && (',
                "            active.tagName === 'TEXTAREA' ||",
                '            active.isContentEditable ||',
                "            (active.tagName === 'INPUT' && ['radio', 'checkbox', 'button', 'submit'].indexOf((active.type || '').toLowerCase()) === -1)",
                '        );',
                '        if (isTypingField) return;',
                "        if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {",
                "            var btn = findNavButton(e.key === 'ArrowRight' ? '다음' : '이전');",
                '            if (btn) { btn.click(); e.preventDefault(); }',
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
                '        }',
                '    });',
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
else:
    view_coach()
