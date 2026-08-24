# testcase-auto 하네스 요약

기획서(PRD) → 팀 양식 테스트 케이스 자동 생성 → 구글 시트 작성·리뷰 | 상세: `HARNESS_OVERVIEW.md` | 2026-08-06

## 전체 흐름

```
[입력] PDF/Figma 기획서 + 참고 시트 URL + 대상 시트 URL
 P0 환경변수·입력·기존 산출물 확인 → 실행 모드(초기/재실행/부분/이어) 결정
 P1 ①PDF→이미지(전체 150DPI + Description 크롭 200DPI) ‖ ②sheet-analyst 양식 분석
    → 간지 감지로 챕터 목록 → ★사용자 확인 게이트 → 00_chapters.md
 P2~4 챕터 루프 (ch01→ch02→… 순차, 챕터당 완결)
    prd-analyst 분석 → writer 생성+시트 append → reviewer 리뷰
                       (★첫 챕터만 검토)      (Critical 시 재작성, 최대 1회)
 P5 챕터별 산출물 합본 + 종합 보고        P6 피드백 → 하네스 진화
```

## 구성 요소

| 에이전트 (opus) | 역할 | 사용 스킬 | 산출물 |
|---|---|---|---|
| prd-analyst | 기획서 판독 → 화면·Description·UI·플로우·Page ID | prd-analyzer | `01_prd_analysis_ch{N}.md` |
| sheet-analyst | 팀 시트 양식 역공학 (컬럼·ID·enum·검증단위) | sheet-operator | `02_sheet_format.md` |
| testcase-writer | TC 도출 + 시트 batch 작성 | testcase-generator, sheet-operator | `03_testcases_ch{N}.md` + 시트 |
| testcase-reviewer | 3경계면 교차 검증 QA | testcase-reviewer, sheet-operator | `04_review_report_ch{N}.md` |

스킬 6개 — `testcase-auto`(오케스트레이터) / `prd-analyzer`·`sheet-operator`(도구) / `testcase-generator`·`testcase-reviewer`(판단·검증 규칙) / `harness`(하네스 자체 진화). 스크립트 5개는 원본이 `.claude/skills/*/scripts/`, 루트 `scripts/`에 심볼릭 링크. 데이터 전달은 `_workspace/` 파일 기반, 모호함·Critical만 에이전트 간 직접 통신.

## 핵심 설계 사상 4가지

- **챕터 단위 순차 처리** — 일괄 처리 시 누락 다수 → 간지 기준으로 잘라 한 챕터씩 완결 (2026-06-11 전면 전환)
- **Description 최우선** — 우측 Description 패널이 1순위 소스, UI는 보완용. 항목 **100% 케이스화 의무**
- **atomic 단위 생성** — 팀 정착 양식이 단일 검증 1케이스. 절차 1~2단계, 예상 결과 1~3줄
- **판단하지 않고 기록** — 불명확·불일치는 `[UI↔DESC 불일치]`·`확인 불가`로 명시하고 사용자에게 위임

## 케이스 도출 (testcase-generator)

- **품질 규칙** — Description 100% 커버리지 / 화면 ID = 기획서 Page ID / 사전조건 명시 / `[공통 DESC]`는 페이지마다 독립 TC(생략 금지) / UI↔DESC 불일치 비고 기재 / 오탈자·enum·메시지 코드 검수
- **자동 도출** — 컬럼(순서·정렬·빈 값 `-`), 상태 enum(표출·호버), 일시(형식·`No data (-)`), 액션 버튼(이동·모달·취소·진행)
- **화면당 개수(atomic)** — 표시 형식 8~15 / 인터랙션 5~10 / 정상 2~4 / 비정상 3~6 / 엣지 2~4 / 부수 3~5
- **우선순위** — 시트에 P4가 있으면 A 정책: P1 라우팅·핵심 트리거(보수적) → P2 다이얼로그·임팩트 큰 비정상 → P3 UI 표시 검증 → P4 취소·비활성·권한 없음. 없으면 B 정책(P1~P3)

## 리뷰 (testcase-reviewer)

존재 확인("N개 작성됨")은 QA가 아니다. **3경계면 교차 비교** — 기획↔케이스(커버리지) / 양식↔케이스(컬럼·enum·ID) / 로컬↔시트(행 수·셀 일치). `[공통 DESC]` 누락 = **Critical**(writer 재작성), UI↔DESC 미기재 = **Major**(사용자 결정), 표현 개선 = Minor. 리뷰어는 직접 수정하지 않고 TC-ID·컬럼 단위로 구체 지적만 한다.

## 환경·인증 / 개입 지점 / 에러

`FIGMA_ACCESS_TOKEN`, `GOOGLE_APPLICATION_CREDENTIALS`, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. 서비스 계정은 Drive 할당량이 없어 **새 시트 생성 불가** → 생성만 OAuth2(`oauth_sheet.py`), 이후 읽기·쓰기는 서비스 계정(`sheets_api.py`). 참고/대상 시트를 `testcase-auto-agent@…`에 **편집자 공유** 필수. 의존성 `pymupdf`, `google-api-python-client`, `google-auth-oauthlib`.

★필수 게이트 2곳 — 챕터 목록 확정(P1-C, OK까지 반복) / 첫 챕터 TC 검토(P3, 이후 자동). 조건부: 첫 챕터 패턴성 Critical 시 방향 조정 확인. 에러는 **1회 재시도 후 해당 챕터를 건너뛰고 보고서에 누락 명시**(시트 403 공유 안내, 429 60초 후 재시도).

## 진화 배경 (규칙이 왜 이렇게 생겼는가)

현재 규칙은 대부분 **실행 후 발견된 누락에서 역산된 것**이다. 팀원 시트 비교에서 Critical 누락 7건 → 표시 형식 자동 도출·P4 enum 인식(2026-05-13). 샘플링 리뷰의 Description 누락 다수 → 100% 커버리지·Page ID 매핑·오탈자 검수(2026-06-09). 공통 항목 생략 패턴 → `[공통 DESC]` 독립 TC 의무화(2026-06-11). 일괄 처리의 누락·시간 과다 → 챕터 순차 처리 전면 전환(2026-06-11). 보조 화면(팝업·모달·처리 결과) 누락 → `.claude/memory/`에 "요약 금지·전수 분석" 피드백 축적.

## 현재 상태

`_workspace/`에 12개 챕터 전체 세트 + 합본 3종, 과거 실행본 11개 디렉토리 보관. 하네스 변경 시 `CLAUDE.md` 이력 테이블 갱신이 규칙이며, 하네스 자체 수정은 `harness` 메타 스킬이 담당한다.
