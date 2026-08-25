# OKE-AUTO-TEST-CASE

기획서(PRD)를 분석해 **팀 양식에 맞는 테스트 케이스를 자동 생성하고 구글 시트에 작성·리뷰**하는 Claude Code 하네스.

## 무엇을 하나

```
기획서(PDF / 이미지 / Figma) ─┐
                              ├─→ 챕터 단위 순차 처리 ─→ 구글 시트 작성 ─→ QA 리뷰
양식 사양 (커밋된 파일) ──────┘     (분석 → 케이스 생성 → 리뷰)
```

팀 양식은 `.claude/formats/` 에 **제품별 사양으로 커밋**되어 있습니다 (VIOLA / TROMBONE).
그래서 실행할 때 참고 시트 URL이 필요하지 않고, 대상 시트에서는 **헤더와 마지막 TC ID만** 확인합니다.
사양은 대상 시트의 솔루션 컬럼으로 **자동 선택**됩니다.

에이전트 4명이 협업합니다.

| 에이전트 | 역할 |
|---------|------|
| `prd-analyst` | 기획서 화면·Description 전수 분석 |
| `sheet-analyst` | 양식 사양 로드 + 대상 시트 드리프트 검증 (헤더·마지막 ID·신규 enum) |
| `testcase-writer` | 케이스 생성 + 시트 작성 |
| `testcase-reviewer` | 기획 ↔ 케이스 ↔ 양식 ↔ 시트 교차 검증 |

## 특징

- **팀 양식을 그대로 따릅니다.** 331행 전수 실측으로 만든 양식 사양(컬럼 순서·enum·문체·표기 컨벤션)을 기준으로 생성하므로, 기존 케이스와 섞여도 이질감이 없습니다.
- **양식 사양은 커밋되어 재사용됩니다.** 매 실행 참고 시트를 다시 분석하지 않아 실행 간 판정이 흔들리지 않고, 빈 새 시트에도 헤더를 만들어 쓸 수 있습니다. 대상 시트 헤더가 사양과 다르면 **작성을 멈추고 알립니다.**
- **제품별 사양을 지원합니다.** VIOLA(24컬럼)와 TROMBONE(23컬럼)은 거의 같은 양식을 쓰지만 문체(백틱 vs 대괄호)·ID 체계(전역 vs 모듈별 연속)·우선순위 결합 규칙이 다릅니다. 대상 시트의 솔루션 컬럼으로 사양이 자동 선택되고, 리뷰도 그 사양 기준으로 판정합니다.
- **제품 내 관리대상을 구분합니다.** VIOLA는 관리대상이 `K8S` / `CI·CD` / `BF(공통)`로 갈립니다. 같은 화면이라도 권한 범위·리소스 종류가 달라지므로 **`관리대상` 전용 컬럼**에 남기며, **판정 단위는 화면이 아니라 케이스**입니다 — 같은 팝업이라도 "언제 뜨는가"는 `BF(공통)`, "무엇을 고르는가"는 `K8S`일 수 있습니다. **기획서에 근거가 없는 관리대상 케이스는 만들지 않고** 적용 범위 확인만 요구합니다.
- **atomic 단위 생성.** 한 케이스 = 한 검증. 실패 원인 추적과 팀 공동 작성에 맞춘 단위입니다.
- **Description 100% 커버리지.** 기획서 Description 항목은 전부 케이스화하고, 근거를 비고 컬럼에 태그로 남깁니다.
- **변경분 한정 모드.** "변경된 내용만"이라고 요청하면 개정판 기획서의 빨간색 표기만 케이스화합니다.
- **판독 품질 게이트.** 해상도 부족·훼손 이미지를 조용히 넘기지 않고 보고하며, 판독 불가 페이지는 추측하지 않고 그 사실을 케이스로 남깁니다.
- **추측 금지.** 기획서에 없는 내용은 단정하지 않고 "기획 확인 필요"로 분리 보고합니다.

## 시작하기

**[SETUP.md](SETUP.md) 를 따라 세팅한 뒤 `python3 verify_setup.py` 로 검증하세요.** (약 15분)

```bash
git clone https://github.com/sihan-qa/OKE-AUTO-TEST-CASE.git
cd OKE-AUTO-TEST-CASE
python3 -m pip install -r requirements.txt
# 서비스 계정 키를 .credentials/google-service-account.json 에 배치 (SETUP.md 3단계)
python3 verify_setup.py
```

세팅이 끝나면 이 폴더에서 Claude Code를 실행하고 기획서·시트 URL과 함께 "테스트 케이스 만들어줘"라고 요청하면 됩니다.
요청 문구는 [docs/PROMPTS.md](docs/PROMPTS.md) 를 참고하세요 — 품질이 갈리는 지점이 정리되어 있습니다.

## 문서

| 문서 | 용도 |
|------|------|
| [SETUP.md](SETUP.md) | **팀원 세팅 가이드 + 검증 절차** — 여기서 시작 |
| [docs/PROMPTS.md](docs/PROMPTS.md) | **프롬프트 가이드** — 무엇을 어떻게 요청하면 품질이 올라가는지 |
| [docs/baselines/](docs/baselines/) | **준수도 기준선** — 하네스 출력을 팀 양식 사양으로 채점한 결과 (회귀 판단 기준) |
| [.claude/formats/team-viola.md](.claude/formats/team-viola.md) | **VIOLA 양식 사양** — 2탭 331행 전수 실측 |
| [.claude/formats/team-trombone.md](.claude/formats/team-trombone.md) | **TROMBONE 양식 사양** — 8탭 3,953행 전수 실측 |
| [CLAUDE.md](CLAUDE.md) | 하네스 트리거 규칙 + **변경 이력** (규칙을 왜 그렇게 정했는지) |
| [HARNESS_OVERVIEW.md](HARNESS_OVERVIEW.md) | 전체 구성도 — 어떤 파일이 무엇을 담당하는지 |
| [HARNESS_WORKFLOW.md](HARNESS_WORKFLOW.md) | 실행 흐름 상세 |
| [HARNESS_SUMMARY.md](HARNESS_SUMMARY.md) | 한 장 요약 |

## 구성

```
.claude/
  skills/          testcase-auto(오케스트레이터) / prd-analyzer / sheet-operator
                   testcase-generator / testcase-reviewer
  agents/          prd-analyst / sheet-analyst / testcase-writer / testcase-reviewer
  formats/          제품별 양식 사양 (team-viola.md / team-trombone.md) — 참고 시트 대신 기준
scripts/           스킬 하위 원본에 대한 심볼릭 링크 (루트에서 실행하기 위한 것)
  figma_api.py             Figma REST API 클라이언트
  pdf_to_images.py         PDF → 페이지별 PNG 변환
  detect_red_regions.py    변경 표시(빨강) 영역 검출 — PDF·이미지 모두 지원
  check_image_quality.py   이미지 판독 품질 진단 (해상도·선명도·훼손)
  sheets_api.py            Google Sheets 읽기·쓰기 (서비스 계정)
  oauth_sheet.py           새 스프레드시트 생성 (OAuth2)
verify_setup.py    세팅 점검 스모크 테스트
_workspace/        실행 산출물 (커밋 제외)
```

## 주의

- **자격증명·기획서 원본·산출물은 커밋되지 않습니다** (`.gitignore`). `git add -f` 로 우회하지 마세요.
- 대상 구글 시트에 서비스 계정 이메일을 **편집자**로 공유해야 동작합니다. 미공유 `403`이 가장 흔한 실패 원인입니다.
- 하네스 규칙을 바꿀 때는 `CLAUDE.md` 변경 이력에 날짜·대상·사유를 남겨주세요. 규칙 대부분이 실제 리뷰에서 발견된 문제로부터 나왔고, 그 맥락이 사라지면 같은 실수가 반복됩니다.
