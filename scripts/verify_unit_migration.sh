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
        .claude/skills/prd-digest/SKILL.md
        .claude/skills/testcase-generator/SKILL.md
        .claude/skills/testcase-reviewer/SKILL.md
        .claude/skills/sheet-operator/SKILL.md)
AGENTS=(.claude/agents/prd-analyst.md
        .claude/agents/prd-digester.md
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
      .claude/skills/testcase-augment/SKILL.md
      .claude/skills/prd-digest/SKILL.md)
# _workspace 문자열이 한 번도 나오면 안 되는 파일들 (루트 정의는 ORCH 에만 둔다)
NOWS=(.claude/agents/prd-analyst.md
      .claude/agents/testcase-writer.md
      .claude/agents/testcase-reviewer.md
      .claude/agents/sheet-analyst.md
      .claude/agents/tc-augmenter.md
      .claude/agents/prd-digester.md
      .claude/skills/prd-analyzer/SKILL.md
      .claude/skills/prd-analyzer/references/image-input.md
      .claude/skills/prd-analyzer/references/change-mode.md
      .claude/skills/prd-analyzer/references/figma.md
      .claude/skills/prd-analyzer/references/digest-mode.md
      .claude/skills/testcase-generator/SKILL.md
      .claude/skills/testcase-reviewer/SKILL.md
      .claude/skills/testcase-reviewer/references/augment-mode.md
      .claude/skills/testcase-reviewer/references/digest-mode.md
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

exists() { # $1=라벨 $2..=파일 — `absent` 계열에 넘기는 배열의 경로가 실재하는지 본다.
           # `absent` 는 `grep ... 2>/dev/null` 이라 **없는 파일에 대해 아무것도 내지 않고
           # `ok` 를 찍는다.** 경로 하나가 오타이거나 다른 배열에 잘못 들어가면 그 파일에
           # 걸린 금지 검사가 통째로 사라지는데 전체는 PASS 로 보인다(Task 4 에서 실제로
           # 그랬다). 여기 오는 배열은 전부 커밋된 하네스 파일이다 — 선택적으로 없을 수
           # 있는 파일은 `absent` 로 검사할 수 없으므로 애초에 이 배열에 넣지 않는다.
  local label="$1"; shift
  local f missing=""
  for f in "$@"; do
    [ -e "$f" ] || missing="$missing $f"
  done
  if [ -n "$missing" ]; then
    printf 'FAIL  %s — 파일 없음:%s\n' "$label" "$missing"
    fail=1
  else
    printf 'ok    %s (%d개)\n' "$label" "$#"
  fi
}

echo "── 가드 자체 점검 ─────────────────────────────────────────"
exists "금지 검사 대상 파일 실재" "${CORE[@]}" "${DOCS[@]}" "${NOWS[@]}" "${ORCH[@]}"

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

# 근거 경로 태그 2종 등재 (2026-09-26 · BF v3 589행 실측).
# ⚠️ 낱말로 세면 안 된다 — `취소선` 은 common.md 에 수십 번 나오고 `Document History` 도
#    다른 문맥에 있다. 표 행과 선언 문장을 **따로** 겨눠야 한 쪽만 지우는 회귀가 잡힌다.
# 표 행에 고정한다 — 같은 문자열이 아래 인용문에도 있어, 행만 지워도 통과하는
# 약한 패턴이었다(음성 대조에서 드러났다). `^\|` 로 표 행임을 요구한다.
present "[취소선] 태그 표 행"     '^\| \*\*`\[취소선\]`\*\* \|' .claude/formats/common.md
present "[Document History] 태그 표 행" '^\| \*\*`\[Document History p\{NNN\}\]`\*\* \|' .claude/formats/common.md
present "Document History = 다섯 번째 경로 선언" '다섯 번째 경로' .claude/formats/common.md
present "Document History = 문서 축 근거 선언"   '문서 축 근거'   .claude/formats/common.md

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
# 단순히 '{WS}' 가 있는지 보면 안 된다 — 두 파일에 60여 회 나오므로, **두 변수에 값을
# 주는 0-0 의 정의 행**(이 재편 전체의 단일 출처)을 지워도 8개 가드가 전부 통과한다.
# 그래서 정의 행의 형태를 그대로 찾되 **두 변수를 한 패턴에 함께 요구한다** — `{WS}` 쪽만
# 고정하면 같은 줄의 `{SHARED}` 정의만 지워도 통과하고, `{SHARED}` 는 60여 회 쓰인다.
# ORCH 전체가 아닌 이유: testcase-augment 는 원천이 시트라 공용 이미지 트리가 없어 정의
# 행에 `{SHARED}` 가 **의도적으로** 없다. 그쪽 정의 행은 바로 위
# `present '_workspace/augment'` 가 이미 정확히 한 줄로 고정한다.
# prd-digest 는 `{WS}`·`{SHARED}` 를 **둘 다** 정의하므로(같은 shared 트리를 testcase-auto 와
# 공유하는 것이 그 배치의 목적이다) 이 가드가 덮는다 — 신설이 아니라 파일 목록 확장이다.
present "작업 루트 변수 정의 행" '\{WS\}` = `_workspace/.*\{SHARED\}` = `_workspace/' \
        .claude/skills/testcase-auto/SKILL.md \
        .claude/skills/prd-digest/SKILL.md
absent "오케스트레이터의 산출물 경로 하드코딩" \
       '_workspace/[0-9]|_workspace/pdf_images|_workspace/red_regions' "${ORCH[@]}"
# 패턴에서 단독 '남긴다' 를 뺀 이유 — 바로 아래 해설 단락이 `shared/` 와 '남기는' 을 함께
# 갖고 있어, 그 한 낱말만 '남긴다' 로 고쳐도 0-5 의 규칙 행이 사라진 채 통과한다.
present "재실행 시 shared 보존" 'shared/.{0,12}(제자리|이동하지)' \
        .claude/skills/testcase-auto/SKILL.md

echo "── 기획서 분석 절차 (2026-09-21) ──────────────────────────"
# 라벨은 `분류 5종` 을 말하는데 패턴은 `확인 필요` 한 낱말만 봤다 — **`미변경` 을 두 파일에서
# 전부 지워도 `ok` 가 찍히고 검사 전체가 통과한다**(실측 확인). 이 저장소가 2026-09-15 에
# 「권위 선언」·「분모」 가드에서 겪은 것과 같은 형태다: 라벨이 주장하는 범위보다 패턴이 좁으면
# 규칙의 절반이 사라져도 초록으로 보인다.
# 한 패턴에 합치지 않고 두 줄로 나눈 이유 — `present` 의 ERE 는 파일 단위 `grep -qE` 라
# `확인 필요|미변경` 은 **OR** 가 되어 오히려 더 약해지고(한쪽만 남아도 통과), 두 낱말은
# 분류 표의 **서로 다른 행**에 있어 한 줄 패턴(`작업 루트 변수 정의 행` 방식)으로 묶을 수도 없다.
# 나눠 두면 어느 분류가 사라졌는지가 FAIL 메시지에 그대로 나온다.
present "분류 5종에 확인 필요 포함" '확인 필요' \
        .claude/skills/prd-analyzer/references/digest-mode.md \
        .claude/agents/prd-digester.md
present "분류 5종에 미변경 포함" '미변경' \
        .claude/skills/prd-analyzer/references/digest-mode.md \
        .claude/agents/prd-digester.md
# 패턴을 절 제목에서 **규칙 행 자체**로 옮겼다 — 제목만 고정하면 **그 아래 13행을 전부
# 지워도 `ok` 가 찍힌다**(음성 대조로 재현). 스펙이 묶으라고 한 것은 역방향 오판 규칙이지
# 그 규칙을 소개하는 제목이 아니다. `present` 는 파일 단위 `grep -qE` 라 한 패턴으로 13행을
# 모두 요구할 수 없으므로(알파로 이으면 **OR** 가 되어 오히려 약해진다) **가장 새로
# 들어왔고 가장 쉽게 사라지는 `미변경` 대다수 규칙**을 닻으로 삼는다 — 그 행은 2026-09-21
# 에 `미변경` 분류를 신설하며 들어왔고, 없으면 리뷰가 매 실행 "변경 검출이 부족하다"를
# 올려 재작업 루프가 돈다. 사유 칸까지 요구하므로 행을 껍데기만 남겨도 FAIL 한다.
present "리뷰 역방향 오판 금지" '^\| \*\*`미변경` 이 산출물의 대다수다.*\|.*변경 문서에서는 대다수 기능' \
        .claude/skills/testcase-reviewer/references/digest-mode.md
# 아래 셋은 오케스트레이터(`prd-digest` SKILL)가 혼자 지는 규칙이다 — 에이전트도 스크립트도
# 이 판단을 대신할 수 없어, 선언이 사라지면 아무 데서도 드러나지 않는다.
#
# `IA 는 권위가 아니다` 패턴은 본문 다른 문장에 걸리기 쉬운 형태다(2026-09-15 「권위 선언」·
# 「분모」 가드와 같은 함정). 그래서 낱말 하나가 아니라 **`IA 부재`/`IA 에 없다` 와
# `신호`/`근거가 아니` 를 한 줄에서 함께** 요구한다 — 그 선언 문장만이 이 형태를 만족한다.
# 음성 대조로 확인했다: 선언 한 줄을 지우면 FAIL 한다(본문의 `IA 에 없는 화면` 목록 서술은
# `에 없다` 가 아니라 `에 없는` 이라 걸리지 않는다).
present "IA 는 권위가 아니다"     'IA (부재|에 없다).*(신호|근거가 아니)' \
        .claude/skills/prd-digest/SKILL.md
present "두 MD 는 한 TSV 에서 렌더" '한 벌의 TSV|같은 TSV 에서' \
        .claude/skills/prd-digest/SKILL.md
# 패턴을 `TROMBONE.*(중단|미지원|추후)` 에서 **선언 문장 자체**로 좁혔다 — 그 형태는 0-2 의
# enum 셀(`… / \`TROMBONE\`(중단)`)과 에러 표 행까지 셋이 만족해, **규칙을 서술한 두 줄을
# 지우고 enum 셀만 남겨도 `ok` 가 찍힌다**(음성 대조로 재현). 이 저장소가 2026-09-15 에
# 「권위 선언」·「분모」 가드에서 겪은 것과 같은 형태다. 이제 선언 한 줄이 이 패턴의 유일한
# 적중이고, 그 줄을 지우면 나머지 두 줄이 남아 있어도 FAIL 한다.
present "TROMBONE 미지원"          'TROMBONE.{0,3}을 고르면 진행하지 않' \
        .claude/skills/prd-digest/SKILL.md

# ── BootFactory 지원 (2026-09-22) ──
# 세 가드 모두 **선언 문장 자체**를 겨눈다. 바로 위 TROMBONE 가드에서 얻은 교훈이다 —
# 처음엔 `TROMBONE.*(중단|미지원)` 로 썼는데 enum 셀과 에러 표 행까지 셋이 만족해
# **규칙을 서술한 두 줄을 지우고 enum 셀만 남겨도 `ok`** 가 찍혔다.
#
# ① BootFactory 가 enum 에서 사라지면 `prd-digest` 는 이 값에 대해 **진행도 중단도 아닌
#    미정의 상태**로 돌아간다. TROMBONE 은 명시적 중단 행이 있는데 BootFactory 만 없던 것이
#    이 작업 직전의 상태였고, 그때 사용자가 그 값을 고르면 오케스트레이터가 즉흥 판단했다.
present "BootFactory 진행 선언" '^\| `BootFactory` \| 진행' \
        .claude/skills/prd-digest/SKILL.md
# ② 이 한 줄이 BootFactory 지원의 **전부를 지탱한다.** BF 는 `v{N}종류` 붙임형이 0건이고
#    `종류 - 날짜` 형이 133건인데, 앞의 0건을 「종류 원문 없음」으로 읽으면 D-3 이 전 기능을
#    `확인 필요` 로 보내 `04_신규변경.md` 가 통째로 무의미해진다. **표의 두 행만으로는
#    만족되지 않게** 금지 문장에 고정했다 — 표는 남기고 이 문장만 지우는 회귀가 실제 위험이다.
present "종류 원문 두 형태 병기" '종류 원문 없음.{0,10}으로 읽지 마라' \
        .claude/skills/prd-analyzer/references/digest-mode.md
# ③ 구분자만 다른 두 화면 ID 를 하네스가 임의로 합치면 **기획서에 없는 동일성을 단정**하는
#    것이고, 합친 결과는 `SCREEN_MISSING` 으로도 드러나지 않아 아무도 감지하지 못한다.
#    반대로 그냥 두면 한 화면이 둘로 갈린다. 유일한 출구가 1-F 게이트의 사용자 확정이므로
#    「정규화하지 않는다 + 게이트에 올린다」 선언이 사라지면 둘 중 하나로 조용히 틀어진다.
present "표기 흔들림은 정규화 금지" '정규화하지 않는다' \
        .claude/skills/prd-digest/SKILL.md
present "표기 흔들림 후보를 게이트에 올린다" '표기 흔들림 후보' \
        .claude/skills/prd-digest/SKILL.md

# 트리거 문구 독점 가드 — **스킬 선택은 `CLAUDE.md` 분기 표가 아니라 스킬 `description`
# 매칭으로 일어난다.** 분기 표는 모델이 이미 이 저장소의 규칙을 읽고 있을 때만 이기고,
# `description` 은 그보다 먼저 읽힌다. 두 스킬이 같은 문구를 명령형으로 주장하면
# `기획서 분석해줘` 가 도구 스킬(`prd-analyzer`)로 갈 수 있는데, 그 경로에는 Phase 0 도
# 작업 디렉터리도 메뉴 IA 단계도 없어 **산출물 2개가 아예 만들어지지 않는다.**
# `기획서 분석 결과` 는 입력 산출물을 가리키는 명사구이지 사용자가 타이핑하는 트리거가
# 아니므로(`testcase-generator`) 지우고 나서 센다 — 안 그러면 이 가드가 영구 FAIL 이거나,
# 그걸 피하려다 패턴이 느슨해져 진짜 중복을 놓친다.
# frontmatter 의 `description` 필드 **전문**을 한 줄로 낸다. 첫 줄만 읽으면 YAML 접힌
# 스칼라(`description: >` 뒤 들여쓴 여러 줄)로 쓴 주장이 통째로 새어 나간다.
desc_field() { # $1=SKILL.md
  awk '
    NR == 1 && $0 == "---" { infm = 1; next }
    infm && $0 == "---"    { exit }
    !infm                  { exit }
    /^description:/ { ind = 1; sub(/^description:[ \t]*/, ""); print; next }
    ind && /^[A-Za-z_][A-Za-z0-9_-]*:/ { ind = 0 }
    ind { print }
  ' "$1" | tr '\n' ' '
}

trigger_owner() {
  local f owner=".claude/skills/prd-digest/SKILL.md" n=0 hits=""
  for f in .claude/skills/*/SKILL.md; do
    [ -e "$f" ] || continue
    if desc_field "$f" | sed 's/기획서 분석 결과//g' | grep -q '기획서 분석'; then
      n=$((n + 1)); hits="${hits:+$hits }$f"
    fi
  done
  # **개수가 아니라 소유자를 본다.** 개수만 보면 문구를 `prd-digest` 에서 떼어 다른 스킬에
  # 옮겨 붙여도 1개라서 `ok` 가 찍히는데, 그것이 바로 이 가드가 막으려던 실패다
  # (`기획서 분석해줘` 가 Phase 0 도 작업 디렉터리도 메뉴 IA 단계도 없는 도구 스킬로 간다).
  # 옆의 `기획서 분석 트리거 분기` 가드도 `CLAUDE.md` 안의 `prd-digest` 만 보므로 함께 통과한다.
  if [ "$hits" = "$owner" ]; then
    printf 'ok    기획서 분석 트리거 문구 독점 (%s)\n' "$owner"
  else
    printf 'FAIL  기획서 분석 트리거 문구의 소유자는 %s 하나여야 한다 — 실제 주장 %d개: %s\n' \
           "$owner" "$n" "${hits:-없음}"
    fail=1
  fi
}
trigger_owner

# 트리거 충돌 가드 — `CLAUDE.md` 의 트리거 절이 `기획서 분석` 을 `testcase-auto` 로 보내고
# 있었다(2026-09-21 이전). 그 상태에서는 이 절차가 **문서에만 있고 아무도 부르지 않는다.**
# 분기 표에서 `prd-digest` 가 사라지면 같은 상태로 조용히 되돌아가므로 선언을 못 박는다.
#
# 패턴을 맨 `prd-digest` 에서 **분기 표의 행 자체**로 좁혔다 — 파일 전체를 grep 하면
# **이 가드는 구조적으로 실패할 수 없다.** `prd-digest` 는 2026-09-21 변경 이력 행에도 있고
# **이 저장소는 변경 이력 행을 지우지 않으므로**, 분기 표에서 `기획서 분석` 행을 통째로
# 지워도 영원히 `ok` 가 찍힌다(음성 대조로 재현). 이 저장소가 「권위 선언」·「분모」·
# `TROMBONE` enum 칸·트리거 소유자에서 겪은 것과 같은 계열이며, **자기가 존재하는 이유인
# 실패를 통과시키는 가드는 없는 것보다 해롭다 — 탐색을 끝내 버리기 때문이다.**
# 이제 `기획서 분석` 을 왼쪽 칸에 담고 오른쪽 칸이 정확히 `` `prd-digest` `` 인 표 행만
# 이 패턴을 만족한다(실측: CLAUDE.md 안에서 적중 1줄 = 분기 표 행. 변경 이력 행은
# 표 행이 아니므로 걸리지 않는다).
present "기획서 분석 트리거 분기" '^\|.*기획서 분석.*\| *`prd-digest` *\|$' CLAUDE.md

# `분류 5종` 선언 자체를 묶는다 — 위의 두 가드는 `확인 필요` 와 `미변경` 을 **낱말로만** 본다.
# 그래서 다섯을 나열한 그 문장을 두 파일에서 통째로 지워도, 다른 문단에 낱말이 한 번씩만
# 남아 있으면 둘 다 `ok` 가 찍힌다. 분류가 몇 종인지를 선언하는 곳이 사라지면
# 에이전트는 자기가 아는 값을 쓰고 `verify_digest.py` 의 `CLASS_ENUM` 이 뒤늦게 잡는다.
present "분류 5종 선언" '신규.{0,8}변경.{0,8}삭제.{0,8}확인 필요.{0,8}미변경' \
        .claude/skills/prd-analyzer/references/digest-mode.md \
        .claude/agents/prd-digester.md

# 렌더러와 점검기는 같은 상수를 **각자 선언한다**(공용 모듈을 두지 않았다 — 스크립트 3개가
# 서로를 import 하지 않는 것이 이 저장소의 관행이다). 한쪽만 고치면 **렌더러가 통과시킨
# 행을 점검기가 위반으로 잡거나 그 반대**가 되고, 둘 다 자기 기준으로는 옳으므로
# 어느 `--selftest` 도 울리지 않는다. 그래서 세 상수를 값까지 못 박아 대조한다.
# 한 패턴으로 합치지 않는 이유는 위 「분류 5종」과 같다 — `present` 는 파일 단위
# `grep -qE` 라 서로 다른 줄의 세 상수를 한 줄 패턴으로 묶을 수 없고, 알파(`|`)로 이으면
# 셋 중 하나만 남아도 통과해 오히려 약해진다.
present "공유 상수 CLASSES 일치" '^CLASSES = \("신규", "변경", "삭제", "확인 필요", "미변경"\)$' \
        scripts/render_digest.py scripts/verify_digest.py
present "공유 상수 GLOBAL_ID 일치" '^GLOBAL_ID = "문서 전역"$' \
        scripts/render_digest.py scripts/verify_digest.py
present "공유 상수 COLS 일치" '^COLS = 7$' \
        scripts/render_digest.py scripts/verify_digest.py

echo
if [ "$fail" -eq 0 ]; then
  echo "PASS — 처리 단위 재편 검사 통과"
else
  echo "FAIL — 위 항목을 고칠 것"
fi
exit "$fail"
