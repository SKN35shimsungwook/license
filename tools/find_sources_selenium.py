# -*- coding: utf-8 -*-
"""정보처리산업기사 기출자료의 공개 출처 링크를 네이버 통합검색에서 직접 검색해 모은다.
naver_disability_news_crawler.py와 같은 방식(API 없이 브라우저를 직접 열어 검색)이고,
필터링 정책은 find_sources.py(네이버 오픈API 버전)와 동일하게 맞춘다:

- 로그인/구매가 필요한 것으로 확인된 도메인은 자동 제외 (find_sources.BLOCKED_DOMAINS)
- "정보처리산업기사"가 제목에 명시된 결과만 채택 (다른 등급 시험인 정보처리기사와 구분)
- 실제 파일 다운로드는 하지 않음 - 링크만 모아 사람이 검토하도록 CSV로 저장

주의: 검색 엔진 결과 페이지의 HTML 구조에 의존하므로, 네이버가 마크업을 바꾸면
RESULT_LINK_SEL / HEADLINE_SEL 두 선택자가 깨질 수 있다 (2026-08-18 렌더링 결과로 확인함).
"""
import csv
import os
import random
import time
import urllib.parse

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from find_sources import (
    BLOCKED_DOMAINS, EXAM_RE, NOISE_TITLE_RE, OUT_DIR, PRACTICAL_ONLY_RE,
    QUERY_TEMPLATES, ROUNDS, WRITTEN_RE, YEARS, file_kind, guess_year_round,
    is_blocked,
)

RESULT_LINK_SEL = 'a[data-heatmap-target=".link"]'
HEADLINE_SEL = "span.sds-comps-text-type-headline1"

# 실제 검색 결과가 아니라 네이버 자체 서비스로 가는 바로가기 링크(콘텐츠 아님)
NAVER_UTILITY_DOMAINS = {"mate.naver.com", "keep.naver.com", "search.naver.com"}

OUT_PATH = os.path.join(OUT_DIR, "정보처리산업기사_공개자료_링크_selenium.csv")
FIELDNAMES = ["연도", "회차", "제목", "URL", "도메인", "자료형태", "문제확인", "검색어", "확인필요사항"]

CHOICE_MARKS = ("①", "②", "③", "④")


def verify_candidate(driver, url):
    """페이지를 실제로 열어 문제(①②③④)+정답이 있는 것으로 보이는지 가볍게 확인한다.
    PDF/HWP 등 파일 링크는 브라우저가 뷰어로 열거나 다운로드를 시도하므로 검사하지 않는다."""
    if any(url.lower().endswith(ext) for ext in (".pdf", ".hwp", ".hwpx", ".docx", ".doc", ".xlsx", ".zip")):
        return "미확인(파일링크)"
    try:
        driver.get(url)
        time.sleep(1.5)
        # 네이버 블로그는 본문이 iframe(#mainFrame) 안에 있다
        try:
            driver.switch_to.frame(driver.find_element(By.ID, "mainFrame"))
        except NoSuchElementException:
            pass
        text = driver.execute_script("return document.body.innerText;") or ""
        driver.switch_to.default_content()
    except WebDriverException:
        return "확인실패"

    mark_count = sum(text.count(m) for m in CHOICE_MARKS)
    has_answer_word = ("정답" in text) or ("해설" in text)
    if mark_count >= 8 and has_answer_word:  # 최소 2문항 분량(4지선다 x 2)
        return "문제+정답 있음(추정, 보기기호 %d개)" % mark_count
    if mark_count > 0:
        return "일부 문제만 있는 듯(보기기호 %d개)" % mark_count
    return "문제 내용 없음(후기/안내 글로 추정)"


def build_driver(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,2000")
    options.add_argument("--disable-blink-features=AutomationControlled")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def is_naver_utility(url):
    return urllib.parse.urlparse(url).netloc.lower() in NAVER_UTILITY_DOMAINS


def search_once(driver, query):
    url = "https://search.naver.com/search.naver?" + urllib.parse.urlencode({"where": "nexearch", "query": query})
    driver.get(url)
    try:
        WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, RESULT_LINK_SEL)))
    except TimeoutException:
        print("검색 결과 없음/로드 실패:", query)
        return []
    time.sleep(random.uniform(1.0, 1.8))

    items = []
    for a in driver.find_elements(By.CSS_SELECTOR, RESULT_LINK_SEL):
        href = a.get_attribute("href") or ""
        try:
            title = a.find_element(By.CSS_SELECTOR, HEADLINE_SEL).text.strip()
        except NoSuchElementException:
            continue
        if href and title:
            items.append((href, title))
    return items


def collect(headless=True, verify=True):
    driver = build_driver(headless=headless)
    seen = {}
    try:
        for year in YEARS:
            for rnd in ROUNDS:
                for tmpl in QUERY_TEMPLATES:
                    query = tmpl.format(year=year, round=rnd)
                    for href, title in search_once(driver, query):
                        if not EXAM_RE.search(title):
                            continue
                        if not WRITTEN_RE.search(title) or PRACTICAL_ONLY_RE.search(title):
                            continue  # 필기 언급이 없거나 제목이 실기 위주인 자료는 제외
                        if NOISE_TITLE_RE.search(title):
                            continue  # 후기/합격 수기, 2021년 이전 옛 형식 자료 제외
                        if is_blocked(href) or is_naver_utility(href) or href in seen:
                            continue
                        y, r = guess_year_round(title, year, rnd)
                        seen[href] = {
                            "연도": y, "회차": r, "제목": title, "URL": href,
                            "도메인": urllib.parse.urlparse(href).netloc,
                            "자료형태": file_kind(href),
                            "문제확인": "",
                            "검색어": query,
                            "확인필요사항": "로그인/저작권/정답 정확도 직접 확인 필요",
                        }
                    time.sleep(random.uniform(1.2, 2.0))

        if verify:
            print("후보 %d건 내용 확인 중..." % len(seen))
            for i, (href, row) in enumerate(seen.items(), 1):
                row["문제확인"] = verify_candidate(driver, href)
                if i % 10 == 0:
                    print(" - %d/%d 확인" % (i, len(seen)))
                time.sleep(random.uniform(0.8, 1.4))
    finally:
        driver.quit()
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
