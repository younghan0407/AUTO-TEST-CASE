#!/usr/bin/env bash
# 처리 단위 재편(챕터 → 화면 ID 1개, 2026-09-02) 이후 잔존 참조 검사기.
#
# 금지 대상은 "처리 단위로서의 챕터"다. 아래 용법은 정당하므로 검사 대상에서 뺀다.
#   - CLAUDE.md 변경 이력 테이블의 과거 기록
#   - common.md 「탭 분할 기준 = 기능 챕터 / 모듈 / 변경분 단위」
#   - 화면 인덱스의 「소속 간지」 라벨
set -u
cd "$(dirname "$0")/.." || exit 1

SKILLS=(.claude/skills/testcase-auto/SKILL.md
        .claude/skills/prd-analyzer/SKILL.md
        .claude/skills/testcase-generator/SKILL.md
        .claude/skills/testcase-reviewer/SKILL.md
        .claude/skills/sheet-operator/SKILL.md)
AGENTS=(.claude/agents/prd-analyst.md
        .claude/agents/testcase-writer.md
        .claude/agents/testcase-reviewer.md
        .claude/agents/sheet-analyst.md)
FORMATS=(.claude/formats/common.md)
DOCS=(README.md SETUP.md docs/AT_A_GLANCE.md docs/BASICS.md docs/PROMPTS.md docs/DESIGN_DECISIONS.md
      HARNESS_PIPELINE.md HARNESS_WORKFLOW.md HARNESS_OVERVIEW.md
      HARNESS_SETUP_PROMPT.md)
AUGMENT=(.claude/skills/testcase-augment/SKILL.md
         .claude/agents/tc-augmenter.md
         .claude/skills/testcase-generator/references/exception-catalog.md
         .claude/skills/testcase-generator/references/permission-mode.md
         .claude/skills/testcase-reviewer/references/augment-mode.md)
ORCH=(.claude/skills/testcase-auto/SKILL.md
      .claude/skills/testcase-augment/SKILL.md)
# _workspace 문자열이 한 번도 나오면 안 되는 파일들 (루트 정의는 ORCH 에만 둔다)
NOWS=(.claude/agents/prd-analyst.md
      .claude/agents/testcase-writer.md
      .claude/agents/testcase-reviewer.md
      .claude/agents/sheet-analyst.md
      .claude/agents/tc-augmenter.md
      .claude/skills/prd-analyzer/SKILL.md
      .claude/skills/prd-analyzer/references/image-input.md
      .claude/skills/prd-analyzer/references/change-mode.md
      .claude/skills/prd-analyzer/references/figma.md
      .claude/skills/testcase-generator/SKILL.md
      .claude/skills/testcase-reviewer/SKILL.md
      .claude/skills/testcase-reviewer/references/augment-mode.md
      .claude/formats/common.md)
CORE=("${SKILLS[@]}" "${AGENTS[@]}" "${FORMATS[@]}")
CORE=("${CORE[@]}" "${AUGMENT[@]}")

fail=0

absent() { # $1=라벨 $2=ERE 패턴 $3..=파일
  local label="$1" pat="$2"; shift 2
  local hits
  hits=$(grep -nE "$pat" "$@" 2>/dev/null)
  if [ -n "$hits" ]; then
    printf 'FAIL  %s\n' "$label"
    printf '%s\n' "$hits" | sed 's/^/        /'
    fail=1
  else
    printf 'ok    %s\n' "$label"
  fi
}

absent_h() { # absent 와 같으나, 날짜(20NN-NN)를 담은 줄은 제외한다.
             # 변경 이력·설계 근거 표는 과거 방식을 서술해야 하므로 정당하다.
  local label="$1" pat="$2"; shift 2
  local hits
  hits=$(grep -nE "$pat" "$@" 2>/dev/null | grep -vE '20[0-9]{2}-[0-9]{2}')
  if [ -n "$hits" ]; then
    printf 'FAIL  %s\n' "$label"
    printf '%s\n' "$hits" | sed 's/^/        /'
    fail=1
  else
    printf 'ok    %s (이력 행 제외)\n' "$label"
  fi
}

present() { # $1=라벨 $2=ERE 패턴 $3..=파일
  local label="$1" pat="$2"; shift 2
  local f missing=""
  for f in "$@"; do
    grep -qE "$pat" "$f" 2>/dev/null || missing="$missing $f"
  done
  if [ -n "$missing" ]; then
    printf 'FAIL  %s — 패턴 없음:%s\n' "$label" "$missing"
    fail=1
  else
    printf 'ok    %s\n' "$label"
  fi
}

echo "── 금지: 챕터 처리 단위 잔존 ──────────────────────────────"
absent "산출물 접미사 _ch{N}"        '_ch\{N\}'                "${CORE[@]}" "${DOCS[@]}"
absent "00_chapters.md 참조"          '00_chapters'             "${CORE[@]}" "${DOCS[@]}"
absent "red_regions/ch{N} 경로"       'red_regions/ch'          "${CORE[@]}" "${DOCS[@]}"
absent "CH{챕터2자리} 표기"           'CH\{챕터2자리\}'          "${CORE[@]}" "${DOCS[@]}"
absent_h "챕터 루프"                  '챕터 루프'                "${CORE[@]}" "${DOCS[@]}"
absent_h "간지 감지"                  '간지 감지'                "${CORE[@]}" "${DOCS[@]}"
absent_h "챕터 단위 순차"             '챕터.{0,2}단위.{0,2}순차'  "${CORE[@]}" "${DOCS[@]}"
absent_h "챕터 분석/챕터별 산출물"    '챕터 분석|챕터별'          "${CORE[@]}"
absent_h "첫 챕터 게이트"             '첫 (번째 )?챕터'          "${CORE[@]}" "${DOCS[@]}"

echo "── 필수: 화면 단위 구조 ───────────────────────────────────"
present "화면 인덱스 파일"  '00_screen_index'  .claude/skills/testcase-auto/SKILL.md \
                                               .claude/skills/prd-analyzer/SKILL.md \
                                               .claude/agents/prd-analyst.md
present "C-ID 레지스터"     '00_cid_register'  .claude/skills/testcase-auto/SKILL.md \
                                               .claude/skills/prd-analyzer/SKILL.md \
                                               .claude/agents/prd-analyst.md \
                                               .claude/formats/common.md
present "산출물 접미사 _s{NN}" '_s\{NN\}'      .claude/skills/testcase-auto/SKILL.md \
                                               .claude/skills/prd-analyzer/SKILL.md \
                                               .claude/skills/testcase-generator/SKILL.md \
                                               .claude/skills/testcase-reviewer/SKILL.md
present "CH-ID = CH{NN}-N, NN=화면 순번" 'CH\{NN\}-N' .claude/formats/common.md \
                                               .claude/skills/testcase-generator/SKILL.md
present "CH-ID 충돌 방지 절"  'CH-ID 충돌 방지' .claude/formats/common.md \
                                               .claude/agents/sheet-analyst.md
present "전체 집계 리뷰"      '전체 집계 리뷰'   .claude/skills/testcase-auto/SKILL.md \
                                               .claude/skills/testcase-reviewer/SKILL.md
present "첫 화면 검토 게이트" '첫 화면'          .claude/skills/testcase-auto/SKILL.md \
                                               .claude/agents/testcase-writer.md

echo "── 회귀 가드: 유지돼야 하는 규칙 (스펙 §8) ────────────────"
present "변경 표시색 묻지 않음"  '변경 표시색'   .claude/skills/testcase-auto/SKILL.md
present "취소선=삭제 정상케이스 금지" '정상 동작|정상 케이스' .claude/formats/common.md \
                                               .claude/skills/testcase-generator/SKILL.md
present "취소선 0건도 육안 재판독" '육안 재판독'  .claude/skills/prd-analyzer/SKILL.md \
                                               .claude/skills/testcase-reviewer/SKILL.md
present "색 박스 확정력 없음"    '범위를 확정하지 않는다|범위 후보' .claude/formats/common.md \
                                               .claude/skills/prd-analyzer/SKILL.md
present "[변경 범위 불명] 태그"  '변경 범위 불명' .claude/formats/common.md
present "C-ID 상호 참조 판정"    '상호 참조'      .claude/formats/common.md \
                                               .claude/agents/prd-analyst.md
present "23컬럼 A~W"             '23.{0,2}컬럼'   .claude/formats/common.md \
                                               .claude/skills/testcase-auto/SKILL.md
present "양식 두 파일 함께 로드" '함께 읽는다|함께 로드' .claude/skills/testcase-auto/SKILL.md
present "정책 예외 태그"         '\[정책 예외\]'  .claude/skills/testcase-auto/SKILL.md \
                                               .claude/skills/testcase-generator/SKILL.md \
                                               .claude/skills/testcase-reviewer/SKILL.md

echo "── 회귀 가드: 토큰 구조 개선의 안전장치 (2026-09-08) ─────"
# 아래는 "비용을 줄이려다 품질 장치를 잃지 않았는가" 를 지킨다.
present "합본 미독 규약"        '합본을 .Read. 로 열지 않는다|행 수·크기' \
                                               .claude/skills/testcase-auto/SKILL.md
present "서브에이전트 리턴 제한" '리턴은 20줄|리턴 규약' \
                                               .claude/skills/testcase-auto/SKILL.md \
                                               .claude/agents/prd-analyst.md \
                                               .claude/agents/testcase-writer.md \
                                               .claude/agents/testcase-reviewer.md
present "타일링 = 해상도 확보"   'tile=auto'    .claude/skills/prd-analyzer/SKILL.md \
                                               .claude/skills/testcase-auto/SKILL.md
present "결정적 점검 스크립트"   'verify_sheet_rows' \
                                               .claude/skills/testcase-reviewer/SKILL.md \
                                               .claude/agents/testcase-reviewer.md
present "브리핑은 요약이 아니다" '요약이 아니라|원문 발췌|발췌 원문' \
                                               .claude/skills/testcase-auto/SKILL.md
present "절 배정 가드 안내"      'coverage-check' .claude/skills/testcase-auto/SKILL.md
present "배치는 호출 단위"       '산출물은 화면별|화면별로 분리' \
                                               .claude/skills/testcase-auto/SKILL.md
present "첫 배치는 단독"         '첫 배치|B01' .claude/skills/testcase-auto/SKILL.md
present "케이스 본문 시트 단일출처" '03_rows_s|단일 출처' \
                                               .claude/skills/testcase-generator/SKILL.md \
                                               .claude/skills/testcase-reviewer/SKILL.md

echo "── 회귀 가드: 추가 작업 절차의 안전장치 (2026-09-10) ─────"
# 새 절차가 기존 품질 장치를 우회하지 않았는가.
# `present` 는 열거한 **모든** 파일에 패턴이 있어야 통과한다 — 그 문구를 실제로
# 담는 파일만 열거한다. 넓게 잡으면 통과시키려고 문구를 억지로 흩뿌리게 된다.
present "원본 TC는 스크립트가 읽는다"   'read_tc_inventory' \
                                               .claude/skills/testcase-augment/SKILL.md
present "결정적 점검 재사용"            'verify_sheet_rows' \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/skills/testcase-reviewer/references/augment-mode.md
present "분포 편차 점검 제외"           '분포 편차' \
                                               .claude/formats/common.md \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/skills/testcase-reviewer/SKILL.md \
                                               .claude/skills/testcase-reviewer/references/augment-mode.md
present "파생 태그 행은 원본 제외"      '파생 태그' \
                                               .claude/formats/common.md \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/agents/tc-augmenter.md
present "파생 태그 접두 파싱 블록"      '파생 태그 접두 \(스크립트 파싱 대상\)' \
                                               .claude/formats/common.md
present "첫 배치는 단독"                '첫 배치' \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/agents/tc-augmenter.md
present "리턴 20줄 제한"                '리턴은 20줄|리턴 규약' \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/agents/tc-augmenter.md
present "케이스 본문 시트 단일출처"     '단일 출처' \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/agents/tc-augmenter.md
present "엑셀 미지원 명시"              '엑셀' \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/agents/tc-augmenter.md
present "예외 카탈로그는 하한"          '상한이 아니라 하한' \
                                               .claude/skills/testcase-generator/references/exception-catalog.md
present "예외 제외 상황 5종"            '제외 상황' \
                                               .claude/skills/testcase-generator/references/exception-catalog.md \
                                               .claude/agents/tc-augmenter.md \
                                               .claude/skills/testcase-reviewer/references/augment-mode.md
present "제외는 하한 규칙보다 우선"      '하한.{0,2}규칙보다 우선' \
                                               .claude/skills/testcase-generator/references/exception-catalog.md \
                                               .claude/agents/tc-augmenter.md
present "제외 유형은 표에 남긴다"        '제외 \(E3\)' \
                                               .claude/skills/testcase-generator/references/exception-catalog.md
present "제외 0건 지적은 오판"           '제외 유형' \
                                               .claude/skills/testcase-reviewer/references/augment-mode.md
present "권한 규모 = 검증 지점 수"      '검증 지점' \
                                               .claude/skills/testcase-generator/references/permission-mode.md \
                                               .claude/skills/testcase-augment/SKILL.md
absent  "추가 작업 문서에 열 문자 박기" '\bV열\b|\bW열\b|A1:W1' \
                                               "${AUGMENT[@]}"
present "범위는 화면 ID 목록"          '범위' \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/agents/tc-augmenter.md \
                                               .claude/skills/testcase-generator/references/exception-catalog.md \
                                               .claude/skills/testcase-reviewer/references/augment-mode.md
present "범위 필터는 스크립트가 한다"    'screen-id' \
                                               .claude/skills/testcase-augment/SKILL.md
present "범위 밖 TC ID도 번호에 센다"    '번호 실측' \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/skills/testcase-augment/scripts/read_tc_inventory.py
present "범위 오타는 Critical"           'SCOPE_NO_MATCH' \
                                               .claude/skills/testcase-augment/SKILL.md \
                                               .claude/skills/testcase-augment/scripts/read_tc_inventory.py
present "작업 유형은 한 실행에 하나"     '한 실행에 한 유형|하나만' \
                                               .claude/skills/testcase-augment/SKILL.md

echo "── 문서 체계 가드 (2026-09-15) ────────────────────────────"
# 문서가 낡은 채 방치된 원인은 가드의 검사 대상(DOCS)에서 빠져 있던 것이다.
# 삭제·개명된 것을 가리키는 링크는 클론한 사람에게 404 가 된다.
absent_h "삭제된 HARNESS_SUMMARY 참조" 'HARNESS_SUMMARY'   "${CORE[@]}" "${DOCS[@]}"
absent   "제거된 루트 렌더 PDF 참조"   'HARNESS_[A-Z_]+\.pdf' "${DOCS[@]}"
absent   "폐지된 사양 파일 경로"       'formats/team-'      "${CORE[@]}" "${DOCS[@]}"
present  "원리 문서 3종의 문서 지도"   '이 문서가 답하는 질문' HARNESS_PIPELINE.md \
                                               HARNESS_WORKFLOW.md \
                                               HARNESS_OVERVIEW.md
present  "세팅 문서의 게이트 3곳"      '멈추는 곳 3군데|게이트.{0,3}3곳' SETUP.md
present  "이식 문서는 .claude 단일출처" '단일 출처' HARNESS_SETUP_PROMPT.md
present  "설계 백서의 권위 선언"       '권위는 .CLAUDE.md. 변경 이력 표' docs/DESIGN_DECISIONS.md
present  "설계 백서가 문서 지도에 있음" 'DESIGN_DECISIONS' README.md
present  "기초 문서가 문서 지도에 있음"   'BASICS' README.md SETUP.md \
                                               HARNESS_PIPELINE.md \
                                               HARNESS_WORKFLOW.md \
                                               HARNESS_OVERVIEW.md
present  "기초 문서는 흐름을 복제하지 않음" '흐름을 설명하지 않는다' docs/BASICS.md
present  "기초 문서는 규칙의 권위가 아님"   '그쪽이 맞다' docs/BASICS.md
present  "한 장 요약이 문서 지도에 있음"   'AT_A_GLANCE' README.md \
                                               HARNESS_PIPELINE.md \
                                               HARNESS_WORKFLOW.md \
                                               HARNESS_OVERVIEW.md \
                                               docs/BASICS.md
present  "한 장 요약에 구조적 공백 절"   '구조적 공백' docs/AT_A_GLANCE.md
present  "한 장 요약에 커버리지 분모 명시" '분모는 제품이 아니라 기획서' docs/AT_A_GLANCE.md

echo "── CLI 명령 오표기 가드 ───────────────────────────────────"
absent "get_metadata 셸 명령 표기" 'sheets_api\.py get_metadata' "${CORE[@]}" "${DOCS[@]}"

echo "── 작업 디렉터리 재편 (2026-09-19) ────────────────────────"
present "이미지 재사용 manifest 대조" 'manifest\.json' \
        .claude/skills/prd-analyzer/SKILL.md
present "manifest 키는 PDF 내용 해시"  'sha256' \
        .claude/skills/prd-analyzer/SKILL.md
present "에이전트는 치환된 실제 경로를 받는다" '스스로 치환하지 않는다' \
        .claude/agents/prd-analyst.md .claude/agents/testcase-writer.md \
        .claude/agents/testcase-reviewer.md .claude/agents/sheet-analyst.md \
        .claude/agents/tc-augmenter.md
absent "에이전트·비오케스트레이터 문서의 _workspace 하드코딩" '_workspace' "${NOWS[@]}"
present "augment 는 제품·버전 폴더 밖" '_workspace/augment' \
        .claude/skills/testcase-augment/SKILL.md
# 단순히 '{WS}' 가 있는지 보면 안 된다 — 두 파일에 60여 회 나오므로, **값을 주는
# 0-0 의 정의 행**(이 재편 전체의 단일 출처)을 지워도 8개 가드가 전부 통과한다.
# 그래서 정의 행의 형태(`{WS}` = `_workspace/…`)를 그대로 찾는다. 실측상 이 패턴은
# 두 오케스트레이터에서 각각 한 줄에만 걸린다.
present "작업 루트 변수 정의 행" '\{WS\}` = `_workspace/' "${ORCH[@]}"
absent "오케스트레이터의 산출물 경로 하드코딩" \
       '_workspace/[0-9]|_workspace/pdf_images|_workspace/red_regions' "${ORCH[@]}"
# 패턴에서 단독 '남긴다' 를 뺀 이유 — 바로 아래 해설 단락이 `shared/` 와 '남기는' 을 함께
# 갖고 있어, 그 한 낱말만 '남긴다' 로 고쳐도 0-5 의 규칙 행이 사라진 채 통과한다.
present "재실행 시 shared 보존" 'shared/.{0,12}(제자리|이동하지)' \
        .claude/skills/testcase-auto/SKILL.md

echo
if [ "$fail" -eq 0 ]; then
  echo "PASS — 처리 단위 재편 검사 통과"
else
  echo "FAIL — 위 항목을 고칠 것"
fi
exit "$fail"
