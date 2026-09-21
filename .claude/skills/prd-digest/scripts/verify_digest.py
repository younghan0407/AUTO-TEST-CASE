#!/usr/bin/env python3
"""기획서 분석 산출물의 결정적 점검.

사람이 판단할 값이 없는 것만 본다 — 분류 enum, 근거 공란, 화면 누락, TSV ↔ MD 대조.
판정 타당성은 리뷰어가 본다.

⚠️ `--selftest` 를 함께 만든 이유 — **통과만 확인하면 아무것도 검사하지 않는 검사기도
   통과한다.** 심어 둔 위반을 실제로 잡는지 확인한다.

사용:
  python verify_digest.py --ws=<디렉터리> [--pages=<총 페이지 수>]
  python verify_digest.py --selftest

종료 코드: 0 위반 없음 / 2 Critical 있음 / 1 Major 만 있음
"""
from __future__ import annotations

import glob
import os
import re
import sys

CLASSES = ("신규", "변경", "삭제", "확인 필요")
GLOBAL_ID = "문서 전역"
COLS = 7
EVIDENCE_REQUIRED = ("신규", "변경", "삭제")


def _read_tsv(ws: str) -> list:
    rows = []
    for p in sorted(glob.glob(os.path.join(ws, "02_features_s*.tsv"))):
        for ln, line in enumerate(open(p, encoding="utf-8"), 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            rows.append((os.path.basename(p), ln, line.split("\t")))
    return rows


def _index_screens(ws: str) -> set:
    """`00_screen_index.md` 의 화면 ID 집합. 헤더에서 열을 찾고 표 끝에서 멈춘다.

    ⚠️ 「번호로 시작하는 표 행」을 전부 읽으면 안 된다 — 같은 파일 아래쪽 「판독 메모」
       표도 행에 번호를 매겨, **산문 한 줄이 화면 ID 로 잡힌다**(실측 오탐 9건).
       그 값은 `SCREEN_MISSING` Critical 로 올라가 *있지도 않은 화면이 누락됐다* 고
       보고하게 되고, **오탐을 내는 검사기는 무시당해 검사 자체가 무력해진다.**
       `render_digest.py` 의 `read_index_titles` 와 같은 방식으로 읽는다.
    """
    p = os.path.join(ws, "00_screen_index.md")
    out = set()
    if not os.path.isfile(p):
        return out
    lines = open(p, encoding="utf-8").readlines()
    # 헤더 행 찾기 — `화면 ID` 가 있는 표 행 (파일 끝까지 스캔)
    id_col = None
    header_idx = None
    for i, hdr_line in enumerate(lines):
        if not hdr_line.startswith("|"):
            continue
        cells = [c.strip() for c in hdr_line.split("|")[1:-1]]
        if cells and cells[0].startswith("-"):  # 구분선 건너뛰기
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
            out.add(cells[id_col])
    return out


def check(ws: str, total_pages=None) -> list:
    """(등급, 코드, 메시지) 목록을 돌려준다."""
    v = []
    rows = _read_tsv(ws)
    if not rows:
        return [("Critical", "NO_TSV", "%s 에 02_features_s*.tsv 가 없다" % ws)]

    seen_pages = set()
    tsv_ids = set()
    for fn, ln, cells in rows:
        if len(cells) != COLS:
            v.append(("Critical", "TSV_COLS", "%s:%d 열 %d개 (7개여야 한다)" % (fn, ln, len(cells))))
            continue
        sid, feature, _desc, cls, evidence, page, _fb = [c.strip() for c in cells]
        tsv_ids.add(sid)
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
        tf = open(md_f, encoding="utf-8").read()
        tc = open(md_c, encoding="utf-8").read()
        for sid in sorted(tsv_ids - {GLOBAL_ID}):
            if sid not in tf:
                v.append(("Critical", "MD_MISSING", "`%s` 가 03_기능_전체.md 에 없다" % sid))
            if sid not in tc:
                v.append(("Critical", "MD_MISSING", "`%s` 가 04_신규변경.md 에 없다" % sid))
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
    import tempfile
    fails = []
    ran = []

    def chk(name, cond, detail=""):
        ran.append(name)
        if cond:
            print("  ok    %s" % name)
        else:
            print("  FAIL  %s  %s" % (name, detail))
            fails.append(name)

    def codes(ws, pages=None):
        return {c for _g, c, _m in check(ws, pages)}

    def build(ws, tsv_rows, md_ids=None, index_ids=None):
        with open(os.path.join(ws, "02_features_s01.tsv"), "w", encoding="utf-8") as f:
            for r in tsv_rows:
                f.write("\t".join(r) + "\n")
        ids = md_ids if md_ids is not None else [r[0] for r in tsv_rows if r[0] != GLOBAL_ID]
        for nm in ("03_기능_전체.md", "04_신규변경.md"):
            with open(os.path.join(ws, nm), "w", encoding="utf-8") as f:
                f.write("\n".join("### %s" % s for s in ids) + "\n")
        with open(os.path.join(ws, "00_screen_index.md"), "w", encoding="utf-8") as f:
            f.write("| 순번 | 화면 ID(원문) | Page Title |\n|---|---|---|\n")
            for s in (index_ids if index_ids is not None else ids):
                f.write("| 01 | %s | 이름 |\n" % s)

    ok_row = ["VIOE-01", "기능", "설명", "신규", "[스티커 p001]", "p001", ""]

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        chk("S1 정상 입력은 위반 0건", codes(ws) == set(), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        chk("S2 TSV 가 없으면 NO_TSV", codes(ws) == {"NO_TSV"}, codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [["VIOE-01", "기능", "설명", "신설", "[스티커 p001]", "p001", ""]])
        chk("S3 분류 enum 밖이면 CLASS_ENUM", "CLASS_ENUM" in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [["VIOE-01", "기능", "설명", "삭제", "", "p001", ""]])
        chk("S4 삭제 행의 근거 공란은 NO_EVIDENCE", "NO_EVIDENCE" in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [["VIOE-01", "기능", "설명", "확인 필요", "", "p001", ""]])
        chk("S5 확인 필요 행은 근거가 없어도 통과", "NO_EVIDENCE" not in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row], md_ids=[])
        chk("S6 MD 에 화면이 없으면 MD_MISSING", "MD_MISSING" in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row], index_ids=["VIOE-01", "VIOE-02"])
        chk("S7 인덱스에 있는데 TSV 에 없으면 SCREEN_MISSING",
            "SCREEN_MISSING" in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        os.remove(os.path.join(ws, "03_기능_전체.md"))
        chk("S8 MD 가 없으면 NO_MD", "NO_MD" in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        with open(os.path.join(ws, "02_features_s02.tsv"), "w", encoding="utf-8") as f:
            f.write("A\tB\tC\n")
        chk("S9 열 수가 틀리면 TSV_COLS", "TSV_COLS" in codes(ws), codes(ws))

    with tempfile.TemporaryDirectory() as ws:
        build(ws, [ok_row])
        chk("S10 귀속 안 된 페이지는 PAGE_GAP(Major)", "PAGE_GAP" in codes(ws, 3), codes(ws, 3))
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

    print()
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
        return 1
    viol = check(ws, opt.get("pages"))
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
