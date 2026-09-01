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

## 코드 구성

`logic.py`(채점/출제 규칙)와 `app.py`(화면)를 분리해뒀고, 기출문제·CBT문제 데이터는
`data/*.csv` → `build_db.py`로 SQLite에 적재해서 `db.py`로 조회해요. 이 저장소는 커밋이
50개에 가까운데, 그중 상당수가 **실제 배포 후 발견한 버그를 고친 기록**이에요 — 특히
Streamlit 특유의 "위젯이 이번 렌더링에 안 나오면 그 상태가 사라진다"는 특성 때문에 생긴
버그가 여럿이라, 아래 트러블슈팅에서 자세히 다뤄요.

## 트러블슈팅

**① 무작위로 문제를 뽑으면 같은 문제가 한 세트 안에 두 번 나옴**

- 원인: 같은 문제가 여러 회차에 실수 없이 그대로 재출제되는 경우가 있는데(예: "에러 검출 및
  교정 코드" 문제가 2022_1/2023_3/2025_1에 동일하게 등장), 무작위 추출 로직이 이런 중복을
  걸러내지 않고 회차별 사본을 그냥 별개의 문제로 취급했음. 30문제 단일과목 추출 기준
  **200번 중 198번꼴로 중복 발생**을 재현해서 확인.
- 해결: `(source, core_id)`로 묶어서 그룹당 하나만 무작위로 남기는 `_dedupe_by_core()`를
  추가하고 나서 뽑음. 수정 후 200번 재시행 결과 **중복 0건**.

```python
def _dedupe_by_core(questions, ids):
    groups = {}
    for qid in ids:
        key = (questions[qid]["source"], questions[qid]["core_id"])
        groups.setdefault(key, []).append(qid)
    return [random.choice(qids) for qids in groups.values()]
```

**② CBT 시험을 "1문제씩"/"여러 문제씩" 보기로 풀면, 페이지를 넘겼다가 돌아왔을 때 이전 답이 사라짐**

- 원인: Streamlit은 **이번 렌더링에 그려지지 않은 위젯의 `session_state` 값을 그냥 지워버림**.
  페이지 모드에서는 그 페이지에 있는 문제만 라디오 위젯으로 그려지니까, 다른 페이지로 넘어가는
  순간 이전 페이지 문제들의 답이 전부 날아가서 4페이지쯤 가면 "0문제 풀었음"으로 표시됨.
  `streamlit.testing.v1.AppTest`로 브라우저 없이 격리 재현해서 앱 로직이 아니라 Streamlit 자체의
  동작임을 확인.
- 해결: 답을 위젯 상태에 의존하지 않는 별도의 `session_state` 딕셔너리(`cbt_answers_store`)에
  따로 저장해두고, 렌더링할 때마다 그 값으로 라디오의 초기 선택을 맞춰줌.

**③ 답을 확인한 뒤 다른 보기를 눌러보면, 정답/오답 배너가 새로 고른 보기 기준인 것처럼 헷갈려 보임**

- 원인: "확인" 버튼을 누른 뒤에도 라디오 버튼 자체는 계속 클릭 가능한 상태로 남아있어서, 정답을
  맞고 나서 호기심에 다른 보기를 눌러보면 배너는 처음 채점 시점 그대로인데 화면엔 새로 고른
  보기가 표시돼서 마치 정답을 오답으로 잘못 채점한 것처럼 보였음 (실제 채점 자체는 항상 정확했음).
- 해결: 한 번 채점되면 그 문제의 라디오/입력창을 `disabled=True`로 잠가서, 표시된 선택지가
  배너 내용과 절대 어긋날 수 없게 함.

**④ Streamlit Cloud처럼 파일 쓰기가 안 되는 배포 환경에서 API 키를 저장하려고 하면 앱이 죽음**

- 원인: `save_key_locally()`가 로컬 `.streamlit/secrets.toml`에 키를 파일로 저장하는데,
  Streamlit Cloud의 소스 폴더는 읽기 전용이라 쓰기 시도 자체가 처리되지 않은 `OSError`를 던져
  앱 전체가 죽었음.
- 해결: `OSError`를 잡아서 저장 실패를 `False`로 반환하도록 하고, 실패 시 "이 환경은 파일 저장이
  안 돼서 이번 세션 동안만 키가 유지돼요"라는 안내와 함께 세션 전용 키로 자연스럽게 넘어가도록 함.

```diff
+ try:
      ... (파일 쓰기) ...
+     return True
+ except OSError:
+     return False
```

---

🤖 이 저장소의 README는 Claude Code와 함께 작성했어요.
