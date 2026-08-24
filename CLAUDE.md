# testcase-auto

## 하네스: 테스트 케이스 자동 생성

**목표:** 기획서(PRD)를 분석하여 팀 양식에 맞는 테스트 케이스를 자동 생성하고 구글 시트에 작성·리뷰한다.

**트리거:** 테스트 케이스 자동 생성·기획서 분석·시트 작성 관련 요청 시 `testcase-auto` 스킬을 사용하라. 기획서(Figma URL 또는 PDF)와 구글 시트 URL이 등장하는 케이스 생성 요청도 동일. 단순 질문(스킬 의미, 환경 설정 방법 등)은 직접 응답 가능.

**환경:**
- `FIGMA_ACCESS_TOKEN` — Figma 토큰 (`.claude/settings.json`의 env)
- `GOOGLE_APPLICATION_CREDENTIALS` — 서비스 계정 JSON 키 경로
- Python 패키지 — `pymupdf`(PDF 입력), `pillow`·`numpy`(이미지 입력·빨강 검출·품질 진단), `google-auth`·`google-api-python-client`(시트)
- 팀 양식 사양 — `.claude/formats/team-viola.md` (VIOLA), `team-trombone.md` (TROMBONE). 참고 시트 대신 이 사양을 기준으로 생성하고, 대상 시트 솔루션 컬럼으로 자동 선택. 갱신은 `"양식 사양 갱신해줘"`
- 서비스 계정 이메일: `testcase-auto-agent@testcase-auto.iam.gserviceaccount.com`
- 대상 구글 시트는 사전에 위 이메일로 편집자 공유 필요

**변경 이력:**

| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-05-13 | 초기 구성 | 에이전트 4개, 스킬 4개, 오케스트레이터 1개 | 기획서(PRD)→테스트 케이스 자동화 도입 |
| 2026-05-13 | OAuth2 시트 생성 + 서비스 계정 공유 흐름 추가 | scripts/oauth_sheet.py, sheet-operator SKILL | 서비스 계정 Drive 할당량 제약 우회 (storageQuotaExceeded) |
| 2026-05-13 | 생성 모드 도입 (atomic / scenario) | testcase-generator, testcase-writer, testcase-auto 오케스트레이터 | 팀원 시트 비교 결과 — 팀 양식은 atomic 단위. 시나리오 단위 자동 생성은 협업 부적합 |
| 2026-05-13 | 표시 형식 검증 자동 도출 추가 | testcase-generator | 비교 결과 Critical 누락 7건 — 컬럼 순서, enum, 일시 형식, No data(-) 등이 자동 도출되지 않음 |
| 2026-05-13 | P4 enum 인식 + 솔루션 분리 컨벤션 인식 | sheet-analyst, testcase-writer | 비교 결과 — P4(취소·비활성·권한 없음), VIOLA_CICD 같은 모듈별 솔루션 분리 누락 |
| 2026-05-13 | 분포 표 정확성 강화 | testcase-writer | 03_testcases.md 분포 표가 실제 작성과 불일치하는 회귀 방지 |
| 2026-06-09 | PDF 분석 경로 추가 | prd-analyzer SKILL, prd-analyst, testcase-auto | Figma URL 외 PDF 파일 입력 지원 (pdf_to_images.py 신규) |
| 2026-06-09 | PDF DPI 전략 개선 | pdf_to_images.py, prd-analyzer SKILL | 전체 페이지 150 DPI + Description 패널 크롭 200 DPI 이중 변환 전략 도입 |
| 2026-06-09 | Description 100% 커버리지 규칙 추가 | testcase-generator, prd-analyst | 샘플링 리뷰 결과 — Description 누락 다수 발견. Description 최우선·전수 케이스화 의무화 |
| 2026-06-09 | Page ID → 화면 ID 컬럼 매핑 규칙 추가 | testcase-generator, prd-analyst | 기획서 스펙 페이지 우측 상단 Page ID(예: ADM-TCK-0100-02)를 화면 ID 컬럼에 기입 |
| 2026-06-09 | 오탈자 검수 단계 의무화 | testcase-generator | 샘플링 리뷰 결과 — 기획서 용어 불일치·상태 enum 오류 다수 발견 |
| 2026-06-09 | 사전조건 명시 의무화 | testcase-generator | 화면 상황별 사전조건 누락으로 케이스 구분 불가 문제 방지 |
| 2026-06-10 | PDF 페이지 분할 분석 도입 (`--pages` 파라미터) | pdf_to_images.py, prd-analyzer SKILL | 단일 에이전트 멀티이미지 컨텍스트 한도 초과 방지 — 에이전트당 ~13페이지 청크 분할. **`--pages` 파라미터는 현행 유지**, 다만 멀티 에이전트 청크 분할 용도는 2026-06-11 챕터 순차 처리로 대체됨 |
| ~~2026-06-10~~ | ~~트리 합성 전략 추가 (C > 6, 총 페이지 > 78)~~ **[폐기 — 2026-06-11]** | ~~prd-analyzer SKILL, testcase-auto SKILL~~ | 대용량 PDF(78p 초과) 대응으로 도입했으나, 다음 날 챕터 단위 순차 처리로 전면 전환되면서 폐기. 현재 스킬 본문에 트리 합성 절차 없음 |
| 2026-06-11 | 공통 Description 독립 TC 의무화 + UI↔Description 불일치 감지·확인사항 자동 추가 | prd-analyzer SKILL, prd-analyst, testcase-generator SKILL, testcase-reviewer SKILL | 동일 Description이 여러 페이지에 걸쳐 있을 때 공통 항목 생략 패턴 방지 (`[공통 DESC]` 태그). UI와 Description 내용 불일치 시 TC 확인사항 자동 기재 (`[UI↔DESC 불일치]` 태그) |
| 2026-06-11 | 챕터(간지) 단위 순차 처리 전략으로 전면 전환 | testcase-auto SKILL, prd-analyzer SKILL, prd-analyst, testcase-writer | 전체 일괄 처리 방식의 품질 문제(누락 다수) + 처리 시간 과다 개선 — 간지 감지→사용자 확인→챕터 루프(분석→TC생성→리뷰) 구조로 변경. 다중 병렬 청크 에이전트 제거, 1개 에이전트 순차 분석으로 교체. 챕터별 산출물 파일 + 전체 합본 이중 저장 도입 |
| 2026-06-15 | figma → prd 명칭 변경 | prd-analyst, prd-analyzer SKILL, 전체 참조 | 기획서 분석 도구가 Figma에 국한되지 않음 — 개념 프레이밍을 "기획서(PRD) 분석"으로 통일 |
| 2026-08-06 | 하네스 구성 문서화 + 스크립트 경로 정합화 | HARNESS_OVERVIEW.md 신규, scripts/ 심볼릭 링크, oauth_sheet.py, prd-analyzer·sheet-operator SKILL | 스킬 문서가 안내하는 `scripts/sheets_api.py` 등 루트 기준 경로에 실제 파일이 없어 실행 불가 → 루트 `scripts/`에 원본(.claude/skills/*/scripts/) 심볼릭 링크 4개 연결. 링크 경유 실행 시 자격증명 경로가 깨지던 `oauth_sheet.py`의 PROJECT_ROOT 계산을 `.credentials/` 상향 탐색으로 교체. 루트 pdf_to_images.py 중복 사본은 링크로 대체(내용 동일) |
| 2026-08-21 | 화면 식별자 추출 규칙 일반화 (`Page ID` → `Screen ID` → 기타 폴백) | prd-analyzer SKILL, prd-analyst, testcase-generator SKILL, testcase-reviewer SKILL | VIOLA V4.0 기획서는 헤더 필드가 `Page ID`가 아닌 `Screen ID`(`VIOE-00_00_05` 형식)여서 화면 ID 컬럼 매핑이 되지 않음. 우선순위 탐색 + 원문 표기 유지(형식 정규화 금지) 규칙으로 대체 |
| 2026-08-21 | 변경분(빨강 표시) 한정 분석·생성·리뷰 모드 정식 도입 | prd-analyzer SKILL(PDF-3.5), prd-analyst, testcase-generator SKILL(0-H), testcase-reviewer SKILL(5-2), testcase-auto SKILL(Phase 0·1-A), scripts/detect_red_regions.py 신규 | 개정판 기획서는 변경 부분만 3중(빨간 박스 / `변경사항` 스티커 / DESC 빨간 텍스트)으로 표기. 기존엔 ad hoc으로 처리했으나 전 단계 연동 규칙이 없어 리뷰가 비변경분 미작성을 "누락"으로 오판. 빨강 검출 스크립트는 글자 단위 조각을 줄→문단으로 병합(162개→5개), 원형 번호 배지 등 오탐은 육안 확정 의무화 |
| 2026-08-24 | 변경분 비고 태그에 CH-ID 필수화 + 기획 미정의 예상결과 패턴 통일 + 절차↔비고 정합성 점검 추가 | testcase-generator SKILL(0-H), testcase-reviewer SKILL(5-2) | ch01 리뷰 결과 — ① 비고에 CH-ID가 없어 시트 행→분석서 변경분 역추적 불가 (참고 시트 실측 컨벤션은 `[변경 CH-N 신규추가 v1추가-26.05.26]`) ② 날짜 미표기를 `-`로 적어 4/5 Depth No-data 의미와 충돌 → `날짜미표기`로 교체 ③ 예상 결과를 단정하면서 피드백에 `[확인 불가]`를 적는 자기모순 4건 → 실행자 오판 유발 ④ 비고가 선언한 변경분을 절차가 실제로 건드리지 않는 실질적 범위 초과 1건 |
| 2026-08-24 | 준수도 기준선 측정 + 분포 정책을 사양 기반으로 전환 | `docs/baselines/trombone-general-v2.md` 신규, testcase-generator SKILL(1-0·1-1·1-A·C-1~C-3·출력 형식·체크리스트), testcase-reviewer SKILL(3-1·3-2), formats 2종(생성 분포 기준) | 하네스 출력물(`일반 v2` 763행)을 **팀 작성분으로만 만든 사양**으로 채점 — 자기 채점이 아닌 독립 측정. 22개 항목 중 18 통과, 4 위반. 구조·enum·TC ID·대괄호 문체는 준수했으나 ① **비고(V) 공란 212행(27.8%)** — 근거 태그를 W열에 써서 생긴 **열 오배치** ② 미사용 컬럼 채움 69행 ③ 결합 규칙 위반 14행. 최대 문제는 **구분 분포 편차 `정상` -44.9%p / `표시` +29.4%p** 로, 원인은 `testcase-generator` §1의 분류별 권장 개수 표가 **VIOLA 양식에서 도출된 값인데 스킬 본문에 하드코딩**되어 제품 무관하게 적용된 것. 분포 기준을 **사양의 실측 분포**로 이관하고 하드코딩 표는 사양 없을 때의 폴백으로 격하. 리뷰에 분포 편차·열 오배치 점검 신설(지배 구분 역전은 Critical) |
| 2026-08-24 | TROMBONE 양식 사양 추가 + 제품별 사양 선택 경로 도입 | `.claude/formats/team-trombone.md` 신규, sheet-analyst(A-1 사양 선택), testcase-auto SKILL(Phase 0·1-D), testcase-generator SKILL, testcase-reviewer SKILL·에이전트, docs/PROMPTS.md(7절 신설·제품 중립화), README | 하네스가 VIOLA 전용처럼 굳어 있었음 — 프롬프트 예시가 `Screen ID`·백틱·`표시` 과반을 전제해, TROMBONE에 그대로 쓰면 화면 ID 매핑 실패·문체 위반·잘못된 커버리지 지적이 발생. 팀 작성 8탭 **3,953행 전수 실측**으로 사양 신설. **`일반 v2` 탭(763행)은 하네스 자체 출력물이라 측정 제외**(자기 참조 순환 방지). 실측으로 옛 분석 2건을 교정 — ① 3 Depth는 7종이 아니라 **탭별 3~7종**(6탭은 `목록`/`상세`/`생성` 3종만) ② A1 헤더 공란은 `07.일반` 단독 예외이고 **표준은 `No`**. W열 근거태그 혼용 쟁점도 전수로 해소(대세는 V=근거/W=확인사항, 혼용은 `07.일반` 4%). 사양 선택은 **대상 시트 솔루션(B) 컬럼 실측값으로 자동 판정**(꼬리 읽기에서 이미 읽으므로 추가 호출 없음) |
| 2026-08-24 | 팀 양식 사양 파일 도입 — 참고 시트 상시 의존 제거 | `.claude/formats/team-viola.md` 신규, sheet-analyst(모드 A 드리프트 검증 / 모드 B 사양 갱신), sheet-operator SKILL(헤더+꼬리 읽기·빈 시트 헤더 생성), testcase-generator SKILL(사전 조건·권위 표), testcase-writer, testcase-reviewer SKILL·에이전트, testcase-auto SKILL(Phase 0·1-D·3), README/SETUP | 매 실행마다 참고 시트를 전수 스캔해 같은 사양서(430줄)를 재생성하고 있었고, 그 산출물이 `_workspace/`(gitignore)에 있어 ① **팀원 저장소에는 사양이 없어 참고 시트 URL 없이는 시작 불가** ② 재도출이라 실행마다 판정이 흔들릴 위험(P4 enum을 샘플링에서 놓친 전례) ③ **빈 새 시트에는 양식 원천이 없어 진행 불가**. 사양을 커밋 파일로 승격하고, 대상 시트에서는 헤더 1행+꼬리 20~50행만 읽어 드리프트만 검증. 참고 시트 전수 스캔은 `"양식 사양 갱신"` 명시 요청 전용으로 격하(삭제하면 갱신 수단이 없어짐). **사양 고정 단독 도입은 "항상 최신"을 잃으므로 드리프트 감지와 한 묶음으로 반영** — 헤더 불일치는 Critical(작성 중단), 사양 외 enum은 Major(보고 후 확인) |
| 2026-08-24 | 이미지 기획서 직접 분석 경로 + 이미지 판독 품질 게이트 추가 | prd-analyzer SKILL(입력 유형 판별·공통 품질 게이트·IMG 경로), prd-analyst, testcase-generator SKILL(0-J), testcase-writer, testcase-reviewer SKILL(5-3), testcase-reviewer 에이전트, testcase-auto SKILL(Phase 0·1-A·1-A-2·2·3·5), scripts/check_image_quality.py 신규, scripts/detect_red_regions.py 이미지 입력 지원 | ① 기획서가 PDF·Figma 없이 이미지로만 오는 경우 경로가 없어 변환 단계를 찾다 멈췄음 → 이미지는 변환 없이 즉시 분석 ② 해상도 부족·훼손 이미지를 조용히 스킵해 누락으로 이어졌음 → 정량 진단(`OK`/`주의`/`불가`) + 사용자 통보 의무 + 케이스에 판독 이슈 기록. `detect_red_regions.py`는 이미지 입력도 받도록 확장(변경분 한정 모드를 이미지 기획서에서도 쓸 수 있게) |
| ~~2026-08-24~~ | ~~빨강 상시 확인 + 시트 `변경` 식별 컬럼(`O`) 도입~~ **[철회 — 2026-08-24 사용자 지시]** | ~~prd-analyzer SKILL(공통 빨강 절), prd-analyst, testcase-generator SKILL(0-I), testcase-writer, testcase-reviewer SKILL(5-3), sheet-analyst, sheet-operator SKILL, testcase-auto SKILL(1-A-3·3)~~ | 전체 분석 모드에서도 빨강을 확인해 시트에 변경 식별 컬럼을 채우는 규칙으로 도입했으나 같은 날 사용자 지시로 전면 롤백. 빨강 처리는 기존 **변경분 한정 모드**(2026-08-21, `prd-analyzer` PDF-3.5 / `testcase-generator` 0-H / `testcase-reviewer` 5-2)로만 유지하고, 시트 컬럼은 팀 양식(A~W) 그대로 두며 변경 사실은 비고 태그로만 표현한다 |
| 2026-08-24 | `sheets_api.py` write 기본값 USER_ENTERED → RAW + `--user-entered` 옵션 | scripts/sheets_api.py, sheet-operator SKILL | 테스트 케이스 텍스트에 정상 등장하는 `-`(No-data 표기)·`1. `(절차 번호)·`'클러스터 관리'`(선행 작은따옴표)·`2026-01-02`(일시 형식 검증)가 USER_ENTERED로 날짜·수식 변환되거나 값이 깨짐. `append`는 이미 같은 이유로 RAW였는데 `write`만 누락되어, 리뷰 반영 시 작성자가 스킬을 우회해 API를 직접 호출해야 했음. RAW 기본화 후 실측 검증(`-`/`1. 절차`/`2026-01-02` 원문 보존) 통과 |
