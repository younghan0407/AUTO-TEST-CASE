#!/usr/bin/env python3
"""기획서 분석 산출물의 결정적 점검.

사람이 판단할 값이 없는 것만 본다 — 분류 enum, 근거 공란, 화면 누락, TSV ↔ MD 대조.
판정 타당성은 리뷰어가 본다.

⚠️ `--selftest` 를 함께 만든 이유 — **통과만 확인하면 아무것도 검사하지 않는 검사기도
   통과한다.** 심어 둔 위반을 실제로 잡는지 확인한다.

사용:
  python verify_digest.py --ws=<디렉터리> [--pages=<총 페이지 수>]
  python verify_digest.py --selftest

종료 코드: 0 위반 없음 / 2 Critical 있음 / 1 Major 만 있음 / 3 실행 오류

⚠️ `3` 을 따로 둔 이유 — 인자가 잘못돼 터지면 파이썬이 `1` 로 나가는데, 이 CLI 에서 `1` 은
   **Major 만 있음**이다. 호출자가 *점검은 돌았고 Critical 은 없었다* 로 읽는다.
"""
from __future__ import annotations

import glob
import os
import re
import sys

CLASSES = ("신규", "변경", "삭제", "확인 필요", "미변경")
# `미변경` 은 `변경` 문서의 **바뀌지 않은 기능**이다. 이 값이 없으면 에이전트가 그 기능을
# 버리거나(`03` 이 전체 목록이 아니게 되는데 한 화면에 한 행만 남아도 `SCREEN_MISSING` 은
# 울리지 않아 **손실을 아무도 감지하지 못한다**) `확인 필요` 로 몰아 변경 문서를 무력화한다.
GLOBAL_ID = "문서 전역"
COLS = 7
EVIDENCE_REQUIRED = ("신규", "변경", "삭제")
# `04_신규변경.md` 에 절을 얻지 못하는 분류 — `render_digest.py` 의 같은 이름 상수와 맞춘다.
# 두 스크립트가 갈리면 렌더가 쓰지 않은 화면을 점검이 요구하게 된다(Fix A 의 원인).
# 집합 연산인 이유도 그쪽과 같다 — 분류가 늘면 **기본값이 "절을 준다"** 여야 새 분류가 조용히 빠지지 않는다.
NO_SECTION = ("미변경",)
SECTION_CLASSES = tuple(c for c in CLASSES if c not in NO_SECTION)


def _read_tsv(ws: str) -> list:
    rows = []
    for p in sorted(glob.glob(os.path.join(ws, "02_features_s*.tsv"))):
        for ln, line in enumerate(open(p, encoding="utf-8"), 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            rows.append((os.path.basename(p), ln, line.split("\t")))
    return rows


def _extract_id_cell(cell: str) -> str:
    """표 셀에서 화면 ID 원문만 뽑는다.

    ⚠️ 사양 표기는 화면 ID 를 백틱으로 감싼다(`` `CICD-00_00_01` ``). 백틱을 벗기지 않으면
       TSV 의 화면ID 열(백틱 없는 원문)과 절대 일치하지 않아 **정상 산출물도 전 화면이
       `SCREEN_MISSING` Critical 로 잡힌다**(실측: 백틱 포함 인덱스에서 69/69 오탐).
       괄호 구별 표기(중복 오류 화면에 붙이는 `` `CICD-02_01_01` (원소유, [p050]) `` 같은 것)가
       백틱 뒤에 병기될 수 있으므로 **첫 백틱 쌍 안의 내용만** 취한다 — 그래야 TSV 원문과 맞는다.
       백틱이 없는 셀(레거시 표기)은 그대로 쓴다.
    """
    m = re.match(r"`([^`]+)`", cell)
    return m.group(1) if m else cell


def _index_screens(ws: str) -> set:
    """`00_screen_index.md` 의 화면 ID 집합. 헤더에서 열을 찾고 표 끝에서 멈춘다.

    ⚠️ 「번호로 시작하는 표 행」을 전부 읽으면 안 된다 — 같은 파일 아래쪽 「판독 메모」
       표도 행에 번호를 매겨, **산문 한 줄이 화면 ID 로 잡힌다**(실측 오탐 9건).
       그 값은 `SCREEN_MISSING` Critical 로 올라가 *있지도 않은 화면이 누락됐다* 고
       보고하게 되고, **오탐을 내는 검사기는 무시당해 검사 자체가 무력해진다.**
       `render_digest.py` 의 `read_index_titles` 와 같은 방식으로 읽는다.

    ⚠️ 헤더 판정 조건도 `read_index_titles` 와 **같아야 한다** — `Page Title` 이 있고 그 행에
       `화면 ID` 열이 있을 때만 헤더로 본다. 조건이 갈리면 두 스크립트가 서로 다른 행을
       헤더로 잡아 **화면 집합 자체가 어긋난다**(같이 읽으라고 맞춘 것이 도로 갈라진다).
    """
    p = os.path.join(ws, "00_screen_index.md")
    out = set()
    if not os.path.isfile(p):
        return out
    lines = open(p, encoding="utf-8").readlines()
    # 헤더 행 찾기 — `Page Title` + `화면 ID` 가 함께 있는 표 행 (파일 끝까지 스캔)
    id_col = None
    header_idx = None
    for i, hdr_line in enumerate(lines):
        if not hdr_line.startswith("|"):
            continue
        cells = [c.strip() for c in hdr_line.split("|")[1:-1]]
        if cells and cells[0].startswith("-"):  # 구분선 건너뛰기
            continue
        if "Page Title" not in cells:
            continue
        for j, cell in enumerate(cells):
            if "화면 ID" in cell:
                id_col = j
                header_idx = i
                break
        if header_idx is not None:
            break
    if id_col is None or header_idx is None:
        return out  # 화면 ID 열 없음 — 빈 집합
    # 데이터 행 읽기 — 표 밖 첫 줄에서 멈춘다(다음 표로 넘어가지 않는다)
    for line in lines[header_idx + 1:]:
        if not line.startswith("|"):
            break
        if re.match(r"\|\s*-", line):  # 구분선 건너뛰기
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) > id_col and cells[id_col]:
            out.add(_extract_id_cell(cells[id_col]))
    return out


def _md_screens(text: str, candidates) -> set:
    """MD 본문의 `### ` 헤딩이 가리키는 화면 ID 집합.

    `render_digest.py` 는 `### {화면ID} {화면명} 〈{페이지}〉` 로 쓴다. 헤딩만 보고는 ID 가
    어디서 끝나는지 알 수 없으므로 **후보(TSV 의 화면 ID) 중 가장 긴 것**으로 판정한다.

    ⚠️ 문자열 포함(`sid in text`)으로 보면 안 된다 — 실측 인덱스에 **접두 쌍이 11건** 있다
       (`VIOE-04_04_02` ⊂ `VIOE-04_04_02-01`). 짧은 쪽이 MD 에서 통째로 빠져도 긴 쪽 헤딩
       안에서 발견되어 **`MD_MISSING` 이 영영 울리지 않는다.** 11건 중 2건은 공백으로만
       갈린다(`VIOE-02_01_01-10` ⊂ `VIOE-02_01_01-10 (flow)`) — 그래서 낱말 경계로도
       부족하고 **집합 비교**여야 한다.
    """
    out = set()
    for line in text.splitlines():
        if not line.startswith("### "):
            continue
        head = line[4:].strip()
        best = ""
        for sid in candidates:
            if not sid:
                continue
            if (head == sid or head.startswith(sid + " ")) and len(sid) > len(best):
                best = sid
        if best:
            out.add(best)
    return out


def check(ws: str, total_pages=None) -> list:
    """(등급, 코드, 메시지) 목록을 돌려준다."""
    v = []
    rows = _read_tsv(ws)
    if not rows:
        return [("Critical", "NO_TSV", "%s 에 02_features_s*.tsv 가 없다" % ws)]

    seen_pages = set()
    tsv_ids = set()
    section_ids = set()  # `04` 에 절을 얻는 분류를 한 행이라도 가진 화면
    for fn, ln, cells in rows:
        if len(cells) != COLS:
            v.append(("Critical", "TSV_COLS", "%s:%d 열 %d개 (7개여야 한다)" % (fn, ln, len(cells))))
            continue
        sid, feature, _desc, cls, evidence, page, _fb = [c.strip() for c in cells]
        tsv_ids.add(sid)
        if cls not in NO_SECTION:
            section_ids.add(sid)
        if cls not in CLASSES:
            v.append(("Critical", "CLASS_ENUM",
                      "%s:%d 분류 %r — 허용: %s" % (fn, ln, cls, "·".join(CLASSES))))
        if cls in EVIDENCE_REQUIRED and not evidence:
            v.append(("Critical", "NO_EVIDENCE",
                      "%s:%d `%s` 의 %s 행에 근거가 없다" % (fn, ln, feature, cls)))
        if not sid:
            v.append(("Critical", "NO_SCREEN_ID", "%s:%d 화면 ID 가 비었다" % (fn, ln)))
        for m in re.findall(r"p(\d{1,4})", page):
            seen_pages.add(int(m))

    md_f = os.path.join(ws, "03_기능_전체.md")
    md_c = os.path.join(ws, "04_신규변경.md")
    for p in (md_f, md_c):
        if not os.path.isfile(p):
            v.append(("Critical", "NO_MD", "%s 가 없다 — render_digest.py 를 먼저 돌린다"
                      % os.path.basename(p)))
    if all(os.path.isfile(p) for p in (md_f, md_c)):
        in_f = _md_screens(open(md_f, encoding="utf-8").read(), tsv_ids)
        in_c = _md_screens(open(md_c, encoding="utf-8").read(), tsv_ids)
        # `03` 은 **모든 화면**을 싣는다(기획서에 실린 전체 기능 목록이다).
        # `04` 는 **절을 얻는 분류를 가진 화면만** 싣는다.
        #
        # ⚠️ 양쪽을 똑같이 요구하면 **규칙대로 작성한 실행이 통과할 수 없다.** 변경 표기가
        #    하나도 없는 화면은 전 행이 `미변경` 인데, `미변경` 은 `04` 에 절을 얻지 못하므로
        #    렌더러가 그 화면을 `04` 에 쓰지 않는다. 그런데 에이전트는 그 화면을 버릴 수도
        #    (`03` 이 전체 목록이 아니게 된다) `확인 필요` 로 옮길 수도(변경 문서가 미변경으로
        #    뒤덮인다) 없다 — **빠져나갈 길이 없는 Critical** 이 된다.
        #    실측 규모(화면 127개 · 변경 항목 165건)에서는 정상 실행이 Critical 수십 건과
        #    종료 코드 `2` 로 끝나고, **아무도 해소할 수 없는 위반은 검사 전체를 무력화한다.**
        for sid in sorted(tsv_ids - {GLOBAL_ID}):
            if sid not in in_f:
                v.append(("Critical", "MD_MISSING", "`%s` 가 03_기능_전체.md 에 없다" % sid))
            if sid in section_ids and sid not in in_c:
                v.append(("Critical", "MD_MISSING", "`%s` 가 04_신규변경.md 에 없다" % sid))

    # 화면 커버리지는 렌더 여부와 무관하다 — MD 가 없어도 본다.
    # ⚠️ 이 검사를 MD 존재 조건 안에 두면, 렌더가 안 돈 실행에서 **처리되지 않은 화면이
    #    통째로 보고되지 않는다**(출력이 `NO_MD` 두 줄뿐이다).
    for sid in sorted(_index_screens(ws) - tsv_ids):
        v.append(("Critical", "SCREEN_MISSING",
                  "인덱스의 `%s` 가 TSV 에 없다 — 처리되지 않은 화면이다" % sid))

    if total_pages:
        missing = [p for p in range(1, int(total_pages) + 1) if p not in seen_pages]
        if missing:
            v.append(("Major", "PAGE_GAP",
                      "어느 화면에도 귀속되지 않은 페이지 %d개: %s%s"
                      % (len(missing), ", ".join("p%03d" % p for p in missing[:10]),
                         " …" if len(missing) > 10 else "")))
    return v


def _selftest() -> int:
    import contextlib
    import io
    import tempfile
    fails = []
    ran = []
    injected = set()

    def chk(name, cond, detail=""):
        ran.append(name)
        if cond:
            print("  ok    %s" % name)
        else:
            print("  FAIL  %s  %s" % (name, detail))
            fails.append(name)

    def codes(ws, pages=None):
        return {c for _g, c, _m in check(ws, pages)}

    def chk_hit(name, ws, code, pages=None):
        """심어 둔 위반을 실제로 잡는지 본다. 잡으라고 심은 코드를 집계한다.

        ⚠️ 건수를 손으로 세어 적으면 낡는다 — 실행이 센 값만 출력한다.
        """
        injected.add(code)
        got = codes(ws, pages)
        chk(name, code in got, got)

    def build(ws, tsv_rows, md_ids=None, index_ids=None, c_ids=None):
        """`c_ids` 는 `04` 에만 쓸 화면 목록 — 두 MD 의 내용이 갈리는 경우를 만든다.

        ⚠️ 이 인자가 없으면 **렌더러의 실제 동작을 재현할 수 없다.** 렌더러는 `미변경`
           전용 화면을 `03` 에만 싣고 `04` 에는 싣지 않으므로, 두 MD 에 늘 같은 목록을
           쓰는 헬퍼로는 그 상황이 자기검증에 영영 나타나지 않는다.
        """
        with open(os.path.join(ws, "02_features_s01.tsv"), "w", encoding="utf-8") as f:
            for r in tsv_rows:
                f.write("\t".join(r) + "\n")
        ids = md_ids if md_ids is not None else [r[0] for r in tsv_rows if r[0] != GLOBAL_ID]
        for nm, which in (("03_기능_전체.md", ids),
                          ("04_신규변경.md", ids if c_ids is None else c_ids)):
            with open(os.path.join(ws, nm), "w", encoding="utf-8") as f:
                f.write("\n".join("### %s" % s for s in which) + "\n")
        with open(os.path.join(ws, "00_screen_index.md"), "w", encoding="utf-8") as f:
            f.write("| 순번 | 화면 ID(원문) | Page Title |\n|---|---|---|\n")
            for s in (index_ids if index_ids is not None else ids):
                f.write("| 01 | %s | 이름 |\n" % s)

    ok_row = ["VIOE-01", "기능", "설명", "신규", "[스티커 p001]", "p001", ""]

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        chk("S1 정상 입력은 위반 0건", codes(ws) == set(), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        injected.add("NO_TSV")
        chk("S2 TSV 가 없으면 NO_TSV", codes(ws) == {"NO_TSV"}, codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [["VIOE-01", "기능", "설명", "신설", "[스티커 p001]", "p001", ""]])
        chk_hit("S3 분류 enum 밖이면 CLASS_ENUM", ws, "CLASS_ENUM")

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [["VIOE-01", "기능", "설명", "삭제", "", "p001", ""]])
        chk_hit("S4 삭제 행의 근거 공란은 NO_EVIDENCE", ws, "NO_EVIDENCE")

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [["VIOE-01", "기능", "설명", "확인 필요", "", "p001", ""]])
        chk("S5 확인 필요 행은 근거가 없어도 통과", "NO_EVIDENCE" not in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row], md_ids=[])
        chk_hit("S6 MD 에 화면이 없으면 MD_MISSING", ws, "MD_MISSING")

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row], index_ids=["VIOE-01", "VIOE-02"])
        chk_hit("S7 인덱스에 있는데 TSV 에 없으면 SCREEN_MISSING", ws, "SCREEN_MISSING")

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        os.remove(os.path.join(ws, "03_기능_전체.md"))
        chk_hit("S8 MD 가 없으면 NO_MD", ws, "NO_MD")

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        with open(os.path.join(ws, "02_features_s02.tsv"), "w", encoding="utf-8") as f:
            f.write("A\tB\tC\n")
        chk_hit("S9 열 수가 틀리면 TSV_COLS", ws, "TSV_COLS")

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        chk_hit("S10 귀속 안 된 페이지는 PAGE_GAP(Major)", ws, "PAGE_GAP", 3)
        chk("S11 전 페이지가 귀속되면 PAGE_GAP 없음",
            "PAGE_GAP" not in codes(ws, 1), codes(ws, 1))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row, [GLOBAL_ID, "신규 메뉴", "설명", "신규", "[Menu Structure p009]", "p009", ""]])
        c = codes(ws, None)
        chk("S12 문서 전역 행은 MD 등장 검사에서 빠진다", "MD_MISSING" not in c, c)

    # 인덱스 파일에는 화면 표 말고도 번호를 매긴 표가 더 있다(실측: 「판독 메모」).
    # 표 경계를 지키지 않으면 산문 한 줄이 화면 ID 로 잡혀 오탐 Critical 이 된다.
    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        with open(os.path.join(ws, "00_screen_index.md"), "a", encoding="utf-8") as f:
            f.write("\n## 판독 메모\n\n")
            f.write("| 번호 | 메모 |\n|---|---|\n")
            f.write("| 1 | `VIOE-02_01_01-12` 가 p072·p073 두 장에 걸침 → 한 단위 |\n")
            f.write("| 2 | 헤더 밴드 없음. `3. Menu Structure` 트리 |\n")
        got = _index_screens(ws)
        chk("S13 화면 표 밖의 번호 표는 읽지 않는다", got == {"VIOE-01"}, got)

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [["", "기능", "설명", "신규", "[스티커 p001]", "p001", ""]])
        chk_hit("S14 화면 ID 공란은 NO_SCREEN_ID", ws, "NO_SCREEN_ID")

    # 접두 쌍 — 짧은 ID 가 긴 ID 의 부분 문자열이다(실측 인덱스에 11건).
    # 문자열 포함으로 보면 짧은 쪽이 MD 에서 빠져도 긴 쪽 헤딩 안에서 발견되어 조용히 통과한다.
    short_row = ["VIOE-04_04_02", "기능", "설명", "신규", "[스티커 p001]", "p001", ""]
    long_row = ["VIOE-04_04_02-01", "기능", "설명", "신규", "[스티커 p002]", "p002", ""]
    with tempfile.TemporaryDirectory() as ws:
        build(ws, [short_row, long_row], md_ids=["VIOE-04_04_02-01"])
        chk_hit("S15 접두 쌍 중 짧은 ID 가 MD 에 없으면 MD_MISSING", ws, "MD_MISSING")

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [short_row, long_row])
        c = codes(ws)
        chk("S16 접두 쌍이 둘 다 MD 에 있으면 오탐 없음", c == set(), c)

    # 공백으로만 갈리는 접두 쌍(실측 `VIOE-02_01_01-10` ⊂ `VIOE-02_01_01-10 (flow)`).
    # 낱말 경계로도 갈리지 않으므로 집합 비교여야 잡힌다.
    sp_short = ["VIOE-02_01_01-10", "기능", "설명", "신규", "[스티커 p113]", "p113", ""]
    sp_long = ["VIOE-02_01_01-10 (flow)", "기능", "설명", "신규", "[스티커 p114]", "p114", ""]
    with tempfile.TemporaryDirectory() as ws:
        build(ws, [sp_short, sp_long], md_ids=["VIOE-02_01_01-10 (flow)"])
        chk_hit("S17 공백으로만 갈리는 접두 쌍도 MD_MISSING", ws, "MD_MISSING")

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [sp_short, sp_long])
        c = codes(ws)
        chk("S18 공백 접두 쌍이 둘 다 있으면 오탐 없음", c == set(), c)

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row], index_ids=["VIOE-01", "VIOE-02"])
        os.remove(os.path.join(ws, "03_기능_전체.md"))
        os.remove(os.path.join(ws, "04_신규변경.md"))
        c = codes(ws)
        chk("S19 MD 가 없어도 SCREEN_MISSING 은 본다", "SCREEN_MISSING" in c, c)

    # CLI 종료 코드 — `1` 은 *Major 만 있음*이므로 잘못된 인자가 `1` 로 나가면 안 된다.
    def exit_code(argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            return main(argv)

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        chk("S20 정상 입력의 종료 코드는 0", exit_code(["--ws=" + ws]) == 0)
        chk("S21 --pages 가 정수가 아니면 종료 코드 3(실행 오류)",
            exit_code(["--ws=" + ws, "--pages=abc"]) == 3)
        chk("S22 --pages=0 도 종료 코드 3", exit_code(["--ws=" + ws, "--pages=0"]) == 3)
        chk("S23 --ws 없이 부르면 종료 코드 3", exit_code([]) == 3)
        chk("S24 Major 만 있으면 종료 코드 1", exit_code(["--ws=" + ws, "--pages=3"]) == 1)

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [["VIOE-01", "기능", "설명", "신설", "[스티커 p001]", "p001", ""]])
        chk("S25 Critical 이 있으면 종료 코드 2", exit_code(["--ws=" + ws]) == 2)

    # `미변경` 은 근거 면제다 — `EVIDENCE_REQUIRED` 에 넣지 않았다.
    # 바뀌지 않은 기능에 변경 근거를 요구하면 `확인 필요` 와 같은 자기모순이 된다.
    with tempfile.TemporaryDirectory() as ws:
        build(ws, [["VIOE-01", "그대로기능", "설명", "미변경", "", "p001", ""]])
        c = codes(ws)
        chk("S26 미변경은 분류 enum 안이다", "CLASS_ENUM" not in c, c)
        chk("S27 미변경 행은 근거가 없어도 통과", c == set(), c)

    # Fix A — `미변경` 전용 화면은 `04` 에 절을 얻지 못한다. 양쪽을 똑같이 요구하면
    # **규칙대로 작성한 실행이 통과할 수 없다**(에이전트는 그 화면을 버릴 수도 다른 분류로
    # 옮길 수도 없다). 두 방향을 함께 본다 — 면제가 너무 넓으면 진짜 누락을 놓친다.
    unchanged_row = ["VIOE-90", "그대로기능", "설명", "미변경", "", "p001", ""]
    changed_row = ["VIOE-91", "바뀐기능", "설명", "변경", "[스티커 p002]", "p002", ""]
    with tempfile.TemporaryDirectory() as ws:
        build(ws, [unchanged_row], c_ids=[])
        c = codes(ws)
        chk("S28 전 행이 미변경인 화면이 04 에 없어도 MD_MISSING 아니다",
            c == set(), c)

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [unchanged_row, changed_row], c_ids=["VIOE-91"])
        c = codes(ws)
        chk("S29 미변경 화면만 04 에서 빠진 것은 정상 — 변경 화면은 실려 있다",
            c == set(), c)

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [unchanged_row, changed_row], c_ids=[])
        chk_hit("S30 변경 행을 가진 화면이 04 에 없으면 여전히 MD_MISSING", ws, "MD_MISSING")

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [unchanged_row], md_ids=[])
        chk_hit("S31 미변경 화면도 03 에는 반드시 있어야 한다", ws, "MD_MISSING")

    # 한 화면이 미변경 행과 변경 행을 **함께** 가지면 그 화면은 `04` 에 실려야 한다.
    # 화면 단위로 판정하지 않고 행 단위로 면제하면 이 화면이 통째로 빠져도 통과한다.
    with tempfile.TemporaryDirectory() as ws:
        build(ws, [["VIOE-92", "그대로", "설명", "미변경", "", "p001", ""],
                   ["VIOE-92", "바뀜", "설명", "변경", "[스티커 p001]", "p001", ""]],
              c_ids=[])
        chk_hit("S32 미변경·변경을 함께 가진 화면이 04 에 없으면 MD_MISSING", ws, "MD_MISSING")

    # ⚠️ 실사양(`00_screen_index.md` 의 실제 예시 표기)은 화면 ID 를 백틱으로 감싼다.
    # 위 S1~S32 는 전부 `build()` 의 `index_ids` 를 백틱 없이 평문으로 썼으므로, 백틱을
    # 벗기지 않는 회귀가 나도 여기서는 안 잡힌다 — 이 문서 2026-09-22 실행에서 실제로
    # 69/69 화면이 이 이유로 오탐 Critical 이 났다. 음성 대조: 백틱 제거 로직을 빼면
    # 아래 두 테스트가 FAIL 로 재현되는 것을 확인했다.
    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row], index_ids=["`VIOE-01`"])
        chk("S33 인덱스 화면ID가 백틱으로 감싸여 있어도 TSV 원문과 매칭된다",
            codes(ws) == set(), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row], index_ids=["`VIOE-01` (원소유, [p050])"])
        chk("S34 백틱 뒤 괄호 구별 표기가 있어도 백틱 안의 원문만 취해 매칭된다",
            codes(ws) == set(), codes(ws))

    print()
    print("  심어 둔 위반 %d종: %s" % (len(injected), ", ".join(sorted(injected))))
    if fails:
        print("selftest FAIL — %d건: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("selftest PASS — %d건 통과" % len(ran))
    return 0


def main(argv: list) -> int:
    if "--selftest" in argv:
        return _selftest()
    opt = {}
    for a in argv:
        if a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            opt[k] = v
    ws = opt.get("ws")
    if not ws:
        print(__doc__)
        return 3
    pages = opt.get("pages")
    if pages is not None:
        try:
            pages = int(pages)
        except ValueError:
            print("실행 오류: --pages 는 정수여야 한다 — 받은 값 %r" % opt.get("pages"))
            return 3
        if pages < 1:
            print("실행 오류: --pages 는 1 이상이어야 한다 — 받은 값 %r" % opt.get("pages"))
            return 3
    viol = check(ws, pages)
    if not viol:
        print("✅ 결정적 점검 위반 0건")
        return 0
    crit = [x for x in viol if x[0] == "Critical"]
    for grade, code, msg in viol:
        print("%-9s %-15s %s" % (grade, code, msg))
    print()
    print("Critical %d · Major %d" % (len(crit), len(viol) - len(crit)))
    return 2 if crit else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
