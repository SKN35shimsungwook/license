# 📘 정보처리산업기사 필기 퀴즈

**정보처리산업기사 필기시험** 기출문제를 풀면서 공부하는 Streamlit 퀴즈 앱이에요.
회차별 기출(2022~2025년 다수 회차)과 CBT 문제은행을 SQLite DB로 관리하고, 필요하면
Gemini AI가 오답에 대해 추가 설명도 해줘요.

(같은 구조로 만든 자매 프로젝트로 [전기산업기사 필기 퀴즈](https://github.com/SKN35shimsungwook/electrical-industrial)가 있어요.)

## 기능

- 과목·회차별로 문제를 골라서 풀기
- 채점 결과와 함께 **해설** 확인
- **AI 학습 코치**: 사용자가 버튼을 눌렀을 때만 Gemini API를 호출해서 오답에 대한
  추가 설명을 받을 수 있음 (자동 호출 없음, API 키는 로컬 `.streamlit/secrets.toml`에 저장)
- CSV 데이터가 DB보다 최신이면 앱 실행 시 **자동으로 DB를 재생성** (기존 사용자 풀이 기록은 보존)

## 기술 스택

| 기술 | 역할 |
|---|---|
| **Streamlit** | 퀴즈 화면 |
| **SQLite** | 문제은행 + 사용자 풀이 기록 저장 (`db.py`, `build_db.py`) |
| **Google Gemini API** (`google-genai`) | 오답 추가 해설을 생성하는 AI 코치 기능 |
| **pandas / CSV** | `data/questions.csv`, `data/cbt_questions.csv`가 원본 문제 데이터 |

## 파일 구조

```
license_quiz/
├── app.py             # Streamlit 앱 진입점
├── logic.py            # 채점/문제 선택 로직
├── db.py                 # SQLite 연결 및 조회
├── build_db.py           # CSV → SQLite DB 빌드
├── ai_coach.py           # Gemini 기반 AI 학습 코치
├── retag_script.py       # 문제 태그(과목/연도 등) 재정리 스크립트
├── data/
│   ├── questions.csv       # 정리된 기출문제 원본
│   └── cbt_questions.csv   # CBT(컴퓨터 기반 시험) 문제은행
├── tools/                 # 기출자료 수집 파이프라인 스크립트 + 별도 README
└── requirements.txt
```

자료 수집 파이프라인(어떻게 기출문제를 모으고 정리했는지, 저작권 관련 주의사항 포함)은
[`tools/README.md`](./tools/README.md)에 따로 정리돼 있어요.

## 실행하기

```bash
pip install -r requirements.txt
streamlit run app.py
```

AI 코치 기능을 쓰려면 `.streamlit/secrets.toml.example`을 참고해서 Gemini API 키를 설정하세요.

---

🤖 이 저장소의 README는 Claude Code와 함께 작성했어요.
