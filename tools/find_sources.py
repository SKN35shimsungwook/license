# -*- coding: utf-8 -*-
"""정보처리산업기사 필기 기출자료를 '로그인 없이 접근 가능한 공개 출처'에서만 찾아
링크 목록(CSV)으로 정리한다. 실제 파일 다운로드는 하지 않는다 - 사람이 링크를
열어 저작권/신뢰도를 직접 확인한 뒤 받는다.

왜 자동 다운로드를 하지 않는가:
  시나공(sinagong.co.kr) 등 상업 자료실은 "회원/도서구매자 전용", "무단 복제·배포 금지"를
  명시하고 있어 로그인 자동화·대량 수집 대상으로 삼을 수 없다. 이 스크립트는 그런 도메인을
  BLOCKED_DOMAINS에서 자동 제외하고, 그 밖의 공개 블로그/커뮤니티/공식 사이트 링크만 모은다.
  단, 블로그·커뮤니티 자료는 '복원문제'(응시자 기억 기반)일 수 있어 공식 기출과 다를 수 있고,
  경우에 따라 원 저작물을 무단 전재한 것일 수도 있으니 각 링크는 반드시 사람이 검토해야 한다.

시험명 필터링:
  "정보처리산업기사"와 "정보처리기사"는 등급이 다른 별개의 국가기술자격이다.
  "산업기사"가 포함된 결과만 채택해 상위 등급 시험(정보처리기사) 자료 혼입을 막는다.

사용법:
  1) 네이버 오픈API 검색 client id/secret 무료 발급: https://developers.naver.com/apps/#/register
  2) 환경변수 설정 (PowerShell): $env:NAVER_CLIENT_ID="..."; $env:NAVER_CLIENT_SECRET="..."
  3) python find_sources.py
결과: ../data/sources/정보처리산업기사_공개자료_링크.csv
"""
import csv
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

EXAM_RE = re.compile(r"정보처리\s*산업기사")
# "필기"가 없으면 실기(코딩형) 자료일 수 있어 raw_cbt(필기 전용) 파이프라인과 형식이 다르다
WRITTEN_RE = re.compile(r"필기")
PRACTICAL_ONLY_RE = re.compile(r"실기")
# 후기/합격 수기, 2021년 이전(옛 100문항 형식) 자료는 실제 문제 원문이 아니거나
# raw_cbt 파이프라인이 다루는 현재(2021년 CBT 개편 이후) 형식과 달라 제외한다
NOISE_TITLE_RE = re.compile(r"후기|합격|이전")
YEAR_ROUND_RE = re.compile(r"(20\d{2})\D{0,6}([1-4])\s*회")

YEARS = range(2021, 2027)
ROUNDS = (1, 2, 3)

QUERY_TEMPLATES = [
    "{year}년 {round}회 정보처리산업기사 필기 기출문제",
    "{year}년 정보처리산업기사 필기 CBT 기출 복원",
    "정보처리산업기사 필기 {year} 기출문제 정답",
]

# 회원가입/도서구매/결제가 필요하다고 확인된(또는 강하게 추정되는) 도메인 - 자동 제외
BLOCKED_DOMAINS = {
    "sinagong.co.kr", "www.sinagong.co.kr", "sinagong.gilbut.co.kr",
    "gilbut.co.kr", "www.gilbut.co.kr",
    "kyobobook.co.kr", "product.kyobobook.co.kr", "search.kyobobook.co.kr",
    "yes24.com", "m.yes24.com", "www.yes24.com",
    "aladin.co.kr", "www.aladin.co.kr",
    "comcbt.com", "www.comcbt.com",
    "license.youngjin.com",
    "scribd.com", "www.scribd.com",
    # 교재/상품 판매 페이지 (기출문제 원문이 아니라 책을 파는 곳)
    "coupang.com", "www.coupang.com",
    "book.willbes.net",
    "kobic.net", "www.kobic.net",
    "bnk.kpipa.or.kr",
    # 유료 온라인 강의 플랫폼으로 추정
    "airklass.com", "www.airklass.com",
    "modenedu.com", "www.modenedu.com",
}

NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "sources")
OUT_PATH = os.path.join(OUT_DIR, "정보처리산업기사_공개자료_링크.csv")

FIELDNAMES = ["연도", "회차", "제목", "URL", "도메인", "자료형태", "검색어", "확인필요사항"]


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "")


def naver_search(query, kind="webkr", display=20):
    if not (NAVER_CLIENT_ID and NAVER_CLIENT_SECRET):
        raise SystemExit(
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 없습니다. "
            "https://developers.naver.com/apps/#/register 에서 무료로 발급받아 설정하세요."
        )
    url = "https://openapi.naver.com/v1/search/%s.json?%s" % (
        kind, urllib.parse.urlencode({"query": query, "display": display, "sort": "sim"})
    )
    req = urllib.request.Request(url, headers={
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        print("검색 실패(%s): %s %s" % (kind, query, e))
        return []
    return data.get("items", [])


def guess_year_round(text, fallback_year, fallback_round):
    m = YEAR_ROUND_RE.search(text)
    if m:
        return m.group(1), m.group(2)
    return str(fallback_year), str(fallback_round)


def file_kind(url):
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    return {
        ".pdf": "PDF", ".hwp": "HWP", ".hwpx": "HWPX",
        ".docx": "DOCX", ".doc": "DOC", ".xlsx": "XLSX", ".zip": "ZIP",
    }.get(ext, "웹페이지")


def is_blocked(url):
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in BLOCKED_DOMAINS)


def collect():
    seen = {}
    for year in YEARS:
        for rnd in ROUNDS:
            for tmpl in QUERY_TEMPLATES:
                query = tmpl.format(year=year, round=rnd)
                for kind in ("webkr", "blog"):
                    for it in naver_search(query, kind=kind):
                        link = it.get("link", "")
                        title = strip_tags(it.get("title", ""))
                        desc = strip_tags(it.get("description", ""))
                        combined = title + " " + desc
                        if not EXAM_RE.search(combined):
                            continue
                        if not WRITTEN_RE.search(combined) or PRACTICAL_ONLY_RE.search(title):
                            continue  # 필기 언급이 없거나 제목이 실기 위주인 자료는 제외
                        if NOISE_TITLE_RE.search(title):
                            continue  # 후기/합격 수기, 2021년 이전 옛 형식 자료 제외
                        if is_blocked(link) or link in seen:
                            continue
                        y, r = guess_year_round(combined, year, rnd)
                        seen[link] = {
                            "연도": y, "회차": r, "제목": title, "URL": link,
                            "도메인": urllib.parse.urlparse(link).netloc,
                            "자료형태": file_kind(link),
                            "검색어": query,
                            "확인필요사항": "로그인/저작권/정답 정확도 직접 확인 필요",
                        }
                    time.sleep(0.15)
    return list(seen.values())


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = collect()
    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["연도"], r["회차"])))
    print("%d건 저장 -> %s" % (len(rows), OUT_PATH))
    print("주의: 자동 다운로드는 하지 않습니다. 각 링크를 직접 열어 저작권/신뢰도를 확인한 뒤 사용하세요.")


if __name__ == "__main__":
    main()
