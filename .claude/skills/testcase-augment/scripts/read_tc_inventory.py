#!/usr/bin/env python3
"""원본 테스트 케이스 인벤토리 — `testcase-augment` Phase 1.

기존 테스트 케이스를 원천으로 파생 케이스(예외 사항·권한)를 만들기 전에,
**원본 탭을 스크립트가 읽어** 기능 단위 인벤토리와 기존 커버리지 맵을 만든다.

에이전트에게 시트를 읽히지 않는 이유: 원본 탭은 수백~수천 행이고 그 텍스트가
오케스트레이터 컨텍스트에 쌓이면 이후 모든 턴에서 다시 읽힌다 (2026-09-08 실측:
오케스트레이터 평균 40만 토큰 · 전체 비용의 25.5%). 인벤토리 집계에는 판단할
값이 없으므로 `verify_sheet_rows.py` 와 같은 논리로 스크립트가 맡는다.

의존성: google-auth, google-api-python-client (시트 입력일 때만)

CLI 사용:
  python read_tc_inventory.py --source-sheet=<ID|URL> --source-tab='03_파드' \\
      --target-sheet=<ID|URL> --target-tab='03_파드_예외' \\
      --out-dir=_workspace/augment
  python read_tc_inventory.py --source-tsv=rows.tsv --out-dir=_workspace/augment
  python read_tc_inventory.py --selftest

  --source-tab: 여러 번 지정 가능 (탭마다 읽고 합산한다)
  --source-tsv: 로컬 TSV(헤더 포함) 입력 — 시트 접근 없이 검증할 때
  --target-sheet / --target-tab: 생략 가능 (생략 시 대상 탭 실측을 건너뛴다)
  --formats-dir: 사양 디렉터리 (기본 `.claude/formats`)
  --out-dir: 산출물 디렉터리 (기본 `_workspace/augment`)
  --selftest: 심어 둔 상황이 전부 잡히는지 자기검증 (사양을 고친 뒤 실행)

종료 코드: 0 정상 / 2 Critical 있음 / 3 실행 오류

⚠️ 규칙은 **사양 파일에서 파싱**한다. 헤더 원문·`솔루션` 고정값·파생 태그 접두를
   스크립트에 박지 않는다. 파싱 실패 시 하드코딩으로 넘어가지 않고 즉시 실패한다
   (종료 코드 3) — 낡은 값으로 조용히 집계하는 것이 집계를 안 하는 것보다 해롭다.

⚠️ 이 스크립트가 **판정하지 않는 것** (에이전트·리뷰어가 봐야 한다):
   어떤 예외 유형이 이 기능에 적용되는가 · 중복 여부의 의미 판정 ·
   권한 자료의 기능 ↔ 원본 기능 단위 매핑 · 케이스 문안
"""

from __future__ import annotations

import json
import os
import re
import sys

CRITICAL, MAJOR = "Critical", "Major"


class SpecParseError(RuntimeError):
    """사양에서 규칙을 읽지 못했다. 하드코딩 폴백 금지 — 그대로 실패시킨다."""


# ─────────────────────────────────────────────── 사양 파싱

def _cells(line: str) -> list[str]:
    """마크다운 표 한 줄을 셀 목록으로."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _plain(text: str) -> str:
    """마크다운 강조(`**`)를 벗긴다. 사양 표는 셀에 강조를 섞어 쓴다."""
    return text.replace("**", "").strip()


def _ticks(text: str) -> list[str]:
    """백틱으로 감싼 토큰 목록."""
    return re.findall(r"`([^`]+)`", text)


def spec_header(formats_dir: str) -> list[str]:
    """`common.md` 의 「헤더 원문」 코드블록에서 컬럼명 목록을 읽는다."""
    path = os.path.join(formats_dir, "common.md")
    md = open(path, encoding="utf-8").read()
    m = re.search(r"### 헤더 원문[^\n]*\n+```\n(.+?)\n```", md, re.S)
    if not m:
        raise SpecParseError(f"{path}: 「헤더 원문」 코드블록을 찾지 못했다")
    cols = [c.strip() for c in m.group(1).split("\t")]
    if len(cols) < 2 or not all(cols):
        raise SpecParseError(f"{path}: 「헤더 원문」을 컬럼으로 나누지 못했다: {cols!r}")
    return cols


def derived_prefixes(formats_dir: str) -> list[str]:
    """`common.md` 「파생 케이스의 원천」 절의 파생 태그 접두 목록.

    접두를 스크립트에 박지 않는 이유: 태그 이름이 바뀌었는데 스크립트가 모르면
    그 태그가 붙은 행이 원본으로 다시 읽혀 **파생의 파생**이 생긴다.
    """
    path = os.path.join(formats_dir, "common.md")
    md = open(path, encoding="utf-8").read()
    m = re.search(
        r"\*\*파생 태그 접두 \(스크립트 파싱 대상\):\*\*\s*\n+```\n(.+?)\n```", md, re.S
    )
    if not m:
        raise SpecParseError(f"{path}: 「파생 태그 접두」 코드블록을 찾지 못했다")
    pref = [ln.strip() for ln in m.group(1).split("\n") if ln.strip()]
    if not pref:
        raise SpecParseError(f"{path}: 「파생 태그 접두」 코드블록이 비어 있다")
    return pref


def profile_solutions(formats_dir: str) -> dict[str, str]:
    """{`솔루션` 고정값: 프로파일 이름}.

    「제품 고유 값」 표에서 `솔루션` 행의 **「단일값 고정」 문구가 있는 행**만 읽는다.
    `profile-bootfactory.md` 처럼 같은 컬럼을 두 번 언급하는 파일이 있어,
    문구로 가려내지 않으면 근거 서술 행이 먼저 잡힌다.
    """
    out: dict[str, str] = {}
    for fn in sorted(os.listdir(formats_dir)):
        if not (fn.startswith("profile-") and fn.endswith(".md")):
            continue
        name = fn[len("profile-"):-len(".md")]
        md = open(os.path.join(formats_dir, fn), encoding="utf-8").read()
        val = ""
        for line in md.splitlines():
            c = _cells(line)
            if len(c) < 2 or "솔루션" not in c[0]:
                continue
            if "단일값 고정" not in _plain(c[1]):
                continue
            t = _ticks(c[1])
            if t:
                val = t[0]
                break
        if not val:
            raise SpecParseError(f"{fn}: `솔루션` 단일값 고정값을 읽지 못했다")
        out[val] = name
    if not out:
        raise SpecParseError(f"{formats_dir}: profile-*.md 를 찾지 못했다")
    return out


# ─────────────────────────────────────────────── selftest

def _fixture(tmp: str) -> str:
    """사양 파서 검증용 최소 사양 디렉터리를 만든다.

    **실제 사양값(23컬럼·`VIOLA` 등)을 테스트에 박지 않는다.** 파서가 사양을
    읽는지만 확인해야 하므로, 픽스처는 실제와 다른 5컬럼·다른 솔루션명을 쓴다.
    실제값을 박으면 사양이 바뀔 때 테스트가 사양을 거스르게 된다.
    """
    os.makedirs(tmp, exist_ok=True)
    with open(os.path.join(tmp, "common.md"), "w", encoding="utf-8") as f:
        f.write(
            "## 컬럼 구조\n\n"
            "### 헤더 원문 (탭 문자 구분)\n\n"
            "```\nNo\t솔루션\t기능테스트 ID\t비고\t피드백\n```\n\n"
            "## 파생 케이스의 원천\n\n"
            "**파생 태그 접두 (스크립트 파싱 대상):**\n\n"
            "```\n[테스트 파생\n[테스트 매트릭스\n```\n"
        )
    with open(os.path.join(tmp, "profile-fixt.md"), "w", encoding="utf-8") as f:
        f.write(
            "## 제품 고유 값\n\n"
            "| 항목 | 값 |\n|---|---|\n"
            "| `솔루션`(B) | **`FIXTURE`** | 강조만 있는 행 — 잡히면 안 된다 |\n"
            "| **`솔루션`(B)** | **`FIXTPROD` 단일값 고정.** 접미사 금지 |\n"
        )
    return tmp


def selftest() -> int:
    import shutil
    import tempfile

    tmp = tempfile.mkdtemp(prefix="tcinv_")
    fails: list[str] = []

    def check(name: str, cond: bool, got=None) -> None:
        if cond:
            print(f"  ok    {name}")
        else:
            print(f"  FAIL  {name}" + (f" — got {got!r}" if got is not None else ""))
            fails.append(name)

    try:
        fdir = _fixture(os.path.join(tmp, "formats"))

        print("── 사양 파싱 ─────────────────────────────────")
        h = spec_header(fdir)
        check("S1 헤더 원문을 사양에서 읽는다",
              h == ["No", "솔루션", "기능테스트 ID", "비고", "피드백"], h)

        p = derived_prefixes(fdir)
        check("S2 파생 태그 접두를 사양에서 읽는다",
              p == ["[테스트 파생", "[테스트 매트릭스"], p)

        s = profile_solutions(fdir)
        check("S3 솔루션 고정값 → 프로파일 이름", s == {"FIXTPROD": "fixt"}, s)

        print("── 파싱 실패 시 즉시 실패 (하드코딩 폴백 금지) ──")
        bad = os.path.join(tmp, "bad")
        os.makedirs(bad, exist_ok=True)
        open(os.path.join(bad, "common.md"), "w", encoding="utf-8").write("## 빈 사양\n")
        open(os.path.join(bad, "profile-x.md"), "w", encoding="utf-8").write("## 빈 프로파일\n")
        for name, fn in (
            ("S4 헤더 원문 없음 → SpecParseError", lambda: spec_header(bad)),
            ("S5 파생 태그 접두 없음 → SpecParseError", lambda: derived_prefixes(bad)),
            ("S6 솔루션 고정값 없음 → SpecParseError", lambda: profile_solutions(bad)),
        ):
            try:
                fn()
                check(name, False, "예외가 나지 않았다")
            except SpecParseError:
                check(name, True)

        print("── 실제 사양으로도 파싱된다 ─────────────────")
        real = os.path.join(".claude", "formats")
        if os.path.isdir(real):
            rh = spec_header(real)
            check("S7 실제 사양 헤더 파싱 (컬럼 수 > 20)", len(rh) > 20, len(rh))
            rp = derived_prefixes(real)
            check("S8 실제 사양 파생 태그 접두 2종 이상", len(rp) >= 2, rp)
            rs = profile_solutions(real)
            check("S9 실제 프로파일 전부에서 솔루션값 파싱",
                  len(rs) >= 3 and all(v for v in rs.values()), rs)
        else:
            print("  skip  실제 사양 디렉터리 없음 (프로젝트 루트에서 실행하라)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if fails:
        print(f"FAIL — {len(fails)}건: " + ", ".join(fails))
        return 1
    print("PASS — selftest 통과")
    return 0


def main(argv: list[str]) -> int:
    opts: dict = {}
    tabs: list[str] = []
    for a in argv[1:]:
        if not a.startswith("--"):
            print(f"오류: 위치 인자를 받지 않는다: {a}", file=sys.stderr)
            return 3
        k, _, v = a.partition("=")
        if k == "--source-tab":
            tabs.append(v)
        else:
            opts[k] = v or True
    opts["--source-tab"] = tabs

    if opts.get("--selftest"):
        return selftest()

    print(__doc__)
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
