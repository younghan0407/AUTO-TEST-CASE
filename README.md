# OKE-AUTO-TEST-CASE

기획서(PRD)를 분석해 **팀 양식에 맞는 테스트 케이스를 자동 생성하고 구글 시트에 작성·리뷰**하는 Claude Code 하네스.

## 무엇을 하나

```
[기본 정보 5가지를 먼저 묻는다]
기획서(PDF / 이미지 / Figma) ─┐
                              ├─→ 화면 ID 단위 순차 처리 ─→ 구글 시트 작성 ─→ QA 리뷰
양식 사양 (커밋된 파일) ──────┘     (분석 → 케이스 생성 → 리뷰)
```

**요청하면 하네스가 먼저 5가지를 물어봅니다** — ① 제품 유형 ② 기획서 유형(`신규`/`변경`)과 예외 항목
③ 기획서 경로 ④ 대상 시트 URL ⑤ 탭(신규/기존). 프롬프트에 미리 적어 보내면 확인만 하고 넘어갑니다.
**추정하지 않습니다** — 잘못 추정한 항목 하나가 수백 행에 그대로 박히기 때문입니다.

팀 양식은 `.claude/formats/` 에 **공통 골격 1개 + 제품 프로파일 3개로 커밋**되어 있습니다
(`common.md` + `profile-viola` / `profile-trombone` / `profile-bootfactory`).
**양식은 공통 골격과 해당 프로파일 두 개를 함께 읽어야 성립합니다.**
그래서 실행할 때 참고 시트 URL이 필요하지 않고, 대상 시트에서는 **헤더와 마지막 TC ID만** 확인합니다.
프로파일은 ① 제품 유형으로 정해지고, 시트에 데이터가 있으면 솔루션 컬럼과 대조합니다.

에이전트 4명이 협업합니다.

| 에이전트 | 역할 |
|---------|------|
| `prd-analyst` | 기획서 화면·Description 전수 분석 |
| `sheet-analyst` | 양식 사양 로드 + 대상 시트 드리프트 검증 (헤더·마지막 ID·신규 enum) |
| `testcase-writer` | 케이스 생성 + 시트 작성 |
| `testcase-reviewer` | 기획 ↔ 케이스 ↔ 양식 ↔ 시트 교차 검증 |

## 특징

- **기본 정보를 먼저 확정합니다.** 제품 유형·기획서 유형·예외 항목·기획서·시트·탭 5가지를 분석 착수 전에 묻고, 확정값을 표로 보여줍니다. **답이 없으면 진행하지 않습니다.**
- **팀 양식을 그대로 따릅니다.** 전수 실측(VIOLA 331행 / TROMBONE 3,953행)으로 만든 양식 사양(컬럼 순서·enum·문체·표기 컨벤션)을 기준으로 생성하므로, 기존 케이스와 섞여도 이질감이 없습니다.
- **양식 사양은 커밋되어 재사용됩니다.** 매 실행 참고 시트를 다시 분석하지 않아 실행 간 판정이 흔들리지 않고, 빈 새 시트에도 헤더를 만들어 쓸 수 있습니다. 대상 시트 헤더가 사양과 다르면 **작성을 멈추고 알립니다.**
- **제품별 프로파일을 지원합니다.** 컬럼은 **전 제품 23컬럼(A~W)으로 통일**되어 있고, 제품마다 실측으로 갈리는 것만 프로파일에 있습니다 — 문체(백틱 vs 대괄호)·ID 체계(전역 vs 모듈별 연속)·지배 구분(`표시` 56% vs `정상` 65%)·우선순위 결합 규칙. 리뷰도 선택된 프로파일 기준으로 판정합니다.
- **관리 영역은 컬럼이 아니라 제품 유형으로 받습니다.** VIOLA의 `K8s` / `CI·CD` 구분은 **탭 분리 + `1 Depth`**(Breadcrumb 최상위 원문)로 표현됩니다. 2026-08-25에 도입했던 `관리대상` 전용 컬럼(VIOLA 24컬럼)은 **2026-09-02에 폐지**됐고, 그 결과 오히려 팀 원본 시트(23컬럼)와 일치하게 됐습니다.
- **⚠️ `profile-bootfactory` 는 실측이 아니라 VIOLA 파생입니다.** 화면 ID 패턴(`BOOT-NN_NN_NN`)만 실측이고, `솔루션` 값 `BOOTFACTORY` 와 TC ID 코드 `BF` 는 **제안값**입니다. 팀 BootFactory 원본 시트가 나오면 전수 스캔으로 교체하는 것이 정공법입니다.
- **atomic 단위 생성.** 한 케이스 = 한 검증. 실패 원인 추적과 팀 공동 작성에 맞춘 단위입니다.
- **Description 100% 커버리지.** 기획서 Description 항목은 전부 케이스화하고, 근거를 비고 컬럼에 태그로 남깁니다.
- **변경분 한정 모드.** 기획서 유형을 `변경` 으로 지정하면 개정판 기획서의 변경 표기(색 박스 / `변경사항` 스티커 / Description 색 텍스트 / `ChangeLog` 패널 / 취소선)가 있는 항목만 케이스화합니다. **문서 안의 일부 신규건은 예외 항목으로 지정**해 그 화면만 전수로 돌릴 수 있습니다.
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

세팅이 끝나면 이 폴더에서 Claude Code를 실행하고 "테스트 케이스 만들어줘"라고 요청하면 됩니다.
**나머지는 하네스가 5가지 질문으로 채웁니다** — 기획서·시트 URL을 미리 적어 보내도 되고, 안 적어도 됩니다.
요청 문구는 [docs/PROMPTS.md](docs/PROMPTS.md) 를 참고하세요 — 5가지 질문의 의미와 품질이 갈리는 지점이 정리되어 있습니다.

## 문서

| 문서 | 용도 |
|------|------|
| [SETUP.md](SETUP.md) | **팀원 세팅 가이드 + 검증 절차** — 여기서 시작 |
| [docs/PROMPTS.md](docs/PROMPTS.md) | **프롬프트 가이드** — 무엇을 어떻게 요청하면 품질이 올라가는지 |
| [docs/baselines/](docs/baselines/) | **준수도 기준선** — 하네스 출력을 팀 양식 사양으로 채점한 결과 (회귀 판단 기준) |
| [.claude/formats/common.md](.claude/formats/common.md) | **양식 공통 골격** — 컬럼 구조(A~W 23) · 태그 체계 · C-ID/CH-ID · 변경분 모드 · 권위 규칙 |
| [.claude/formats/profile-viola.md](.claude/formats/profile-viola.md) | **VIOLA 프로파일** (`K8s`·`CI/CD` 공용) — 2탭 331행 전수 실측 |
| [.claude/formats/profile-trombone.md](.claude/formats/profile-trombone.md) | **TROMBONE 프로파일** — 8탭 3,953행 전수 실측 |
| [.claude/formats/profile-bootfactory.md](.claude/formats/profile-bootfactory.md) | **BootFactory 프로파일** — VIOLA 파생, **실측 근거 없음** |
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
  formats/         common.md(공통 골격) + profile-viola / profile-trombone / profile-bootfactory
                   — 참고 시트 대신 기준. 공통 골격 + 프로파일을 함께 읽는다
scripts/           스킬 하위 원본에 대한 심볼릭 링크 (루트에서 실행하기 위한 것)
  figma_api.py             Figma REST API 클라이언트
  pdf_to_images.py         PDF → 페이지별 PNG 변환
  detect_red_regions.py    변경 표시 색 영역 검출 — PDF·이미지 모두 지원 (--color=red|blue|both)
  detect_strikethrough.py  취소선 후보 검출 — 삭제 변경분 탐지 (색·텍스트 검출로 안 잡히는 표기)
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
