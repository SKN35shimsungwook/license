# 정보처리산업기사 기출자료 수집 파이프라인

## 흐름

```
1) find_sources.py   로그인 없이 접근 가능한 공개 출처의 "링크"만 검색해 CSV로 정리
                      (자동 다운로드 없음 - 사람이 링크를 열어 직접 확인 후 저장)
2) (수동) 확인한 파일을 Downloads 등 로컬 폴더에 저장
3) parse_cbt.py       로컬 PDF를 열 컬럼 인식으로 재구성해 문항(과목/번호/보기4개/정답) 추출
                      -> data/raw_cbt/{year}_{round}.json
4) (수작업/추후 스크립트) raw_cbt json -> data/cbt_questions.csv (exam/tag/explanation 등 보강)
5) build_db.py        questions.csv + cbt_questions.csv -> data/quiz.db (Streamlit 앱이 사용)
```

## 왜 자동 다운로드를 만들지 않았는가

시나공(sinagong.co.kr) 자료실은 "시나공 카페 회원 대상, 개인적 용도로만 사용 가능, 무단 복제·배포·상업적 이용 금지"를
명시하고 있다. 로그인 자동화나 대량 자동 다운로드는 이 이용약관을 위반하게 되므로 만들지 않았다.
지금까지 `data/raw_cbt`에 있는 2021~2026년 자료는 사용자가 시나공 카페 회원으로서 직접 받아온 파일을
로컬에서 텍스트 추출만 한 것으로, 개인 학습 앱(license_quiz) 용도이므로 "개인적 용도" 범위 안에 있다.

`find_sources.py`는 그 대신 **로그인이 필요 없는 출처**(공식 사이트, 공개 블로그/커뮤니티 등)의 링크만
찾아 목록화한다. 아래 도메인은 회원가입/도서구매/결제가 필요한 것으로 확인되어 자동 제외된다:
sinagong.co.kr, gilbut.co.kr, kyobobook.co.kr, yes24.com, aladin.co.kr, comcbt.com, license.youngjin.com, scribd.com

## find_sources.py 사용법

1. 네이버 오픈API 검색 client id/secret 무료 발급: https://developers.naver.com/apps/#/register
2. 환경변수 설정 후 실행 (PowerShell 예시):
   ```powershell
   $env:NAVER_CLIENT_ID="발급받은 ID"
   $env:NAVER_CLIENT_SECRET="발급받은 SECRET"
   python find_sources.py
   ```
3. 결과: `../data/sources/정보처리산업기사_공개자료_링크.csv`
   (같은 파일에 2026-08-18 기준으로 수동 조사한 gisafirst.com 예시 1건이 이미 들어있음 - 재실행 시 덮어써짐)

## 주의사항 (중요)

- **자동으로 채택하지 말 것**: 블로그/커뮤니티 자료는 응시자가 시험 후 기억으로 복원한 "복원문제"인 경우가
  많다. 실제 출제와 문구·정답이 다를 수 있으니 반드시 사람이 내용을 확인해야 한다.
- **시험명 혼동 주의**: "정보처리기사"(상위 등급)와 "정보처리산업기사"는 다른 시험이다.
  `find_sources.py`는 "산업기사"가 포함된 결과만 채택하지만, 결과를 쓸 때도 한 번 더 확인할 것.
- 어떤 출처든 원 저작자의 저작권 표시·출처를 지우거나 상업적으로 재배포하지 말 것.
