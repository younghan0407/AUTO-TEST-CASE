"""작성된 시트 행의 **결정적(기계 판정 가능) 양식 점검**.

리뷰어가 매 화면마다 눈으로 훑던 항목 중 **판단이 필요 없는 것**을 여기로 내린다.
리뷰어는 판단이 필요한 것만 본다 — 기획 커버리지, 삭제 항목 오케이스, 변경 범위 초과,
추측 케이스 표시, `[UI↔DESC 불일치]` 기재, 정책 예외 양방향.

의존성: google-auth, google-api-python-client (시트 입력일 때만)

CLI 사용:
  python verify_sheet_rows.py --profile=viola --sheet=<ID_또는_URL> --tab='시트1'
  python verify_sheet_rows.py --profile=viola --sheet=<ID> --tab='시트1' --rows=2-56
  python verify_sheet_rows.py --profile=trombone --tsv=rows.tsv        # 로컬 TSV(헤더 포함)
  python verify_sheet_rows.py --profile=viola --tsv=rows.tsv --json=out.json

  --profile: viola | trombone | bootfactory  (`.claude/formats/profile-{name}.md`)
  --rows=START-END: 검사할 시트 행 범위 (1-indexed, 헤더 제외분만 주어도 된다)
  --formats-dir: 사양 디렉터리 (기본 `.claude/formats`)
  --json: 결과를 JSON으로 저장
  --quiet: 위반 요약만 출력
  --selftest: 심어 둔 위반이 전부 잡히는지 자기검증 (사양을 고친 뒤 실행)
  --diff: `--tsv` 와 `--sheet`/`--tab` 을 **함께** 주면 로컬 원본 ↔ 시트를 셀 단위로 대조한다
          (「로컬 ↔ 시트」 경계면. 케이스 본문을 눈으로 비교하지 않는다)
          `.tsv` 의 **헤더 행은 있어도 없어도 된다** — 첫 행이 사양 헤더와 정확히 같으면
          건너뛴다. 파이프라인마다 관행이 다르기 때문이다
          (`03_rows_s{NN}.tsv` 헤더 없음 / `13_rows_*.tsv` 1행이 헤더 원문)

종료 코드: 0 = 위반 없음 / 1 = Major 이하만 / 2 = Critical 있음 / 3 = 실행 오류

⚠️ 규칙은 **사양 파일에서 파싱**한다. 스크립트 안에 값을 박지 않는다.
   파싱에 실패하면 **하드코딩으로 넘어가지 않고 즉시 실패**한다 (종료 코드 3).
   2026-08-24에 VIOLA 분포를 스킬 본문에 하드코딩한 탓에 TROMBONE 출력이
   `정상` -44.9%p 편차를 낸 전례가 있다. 낡은 값으로 조용히 채점하는 것이
   검사를 안 하는 것보다 해롭다.

⚠️ 이 스크립트가 **판정하지 않는 것** (리뷰어가 봐야 한다):
   기획 커버리지 · Description 100% · 삭제 항목이 정상 케이스로 만들어졌는지 ·
   변경 범위 초과 · 추측 케이스 · 태그 내용의 타당성 · 분포 편차(전체 집계 리뷰)
"""

from __future__ import annotations

import json
import os
import re
import sys

CRITICAL, MAJOR, MINOR = "Critical", "Major", "Minor"


class SpecParseError(RuntimeError):
    """사양에서 규칙을 읽지 못했다. 하드코딩 폴백 금지 — 그대로 실패시킨다."""


# ─────────────────────────────────────────────────────────── 사양 파싱

def _cells(line: str) -> list[str]:
    """마크다운 표 한 줄을 셀 목록으로."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _plain(text: str) -> str:
    """마크다운 강조(`**`)를 벗긴다. 사양 표는 셀에 강조를 섞어 쓴다."""
    return text.replace("**", "").strip()


def _outside_ticks(text: str) -> str:
    """백틱으로 감싼 구간을 지운 나머지.

    UI 라벨은 백틱 안에 원문 그대로 인용된다 — 사이드바 접기 아이콘 `|<` 처럼
    `|` 나 `[` 를 **정당하게** 포함할 수 있다. 인용 구간까지 검사하면
    오탐이 나고, 오탐을 내는 검사기는 무시당해 검사 자체가 무력해진다.
    """
    return re.sub(r"`[^`]*`", "", text)


def _ticks(text: str) -> list[str]:
    """백틱으로 감싼 토큰 목록."""
    return re.findall(r"`([^`]+)`", text)


def _before_bold(text: str) -> str:
    """첫 `**` 앞까지만 취한다.

    사양은 「허용 목록. **금지 목록**」 꼴로 한 줄에 둘을 쓴다
    (예: ``P1` / `P2` / `P3` / `P4`. **`P0`/`P5` 등 신규 값 금지.**`).
    줄 전체에서 백틱을 긁으면 **금지 값이 허용 enum에 섞인다.**
    """
    return text.split("**", 1)[0]


def _paren_letters(text: str) -> list[str]:
    """`(L·M)` 처럼 괄호 안에 `·` 로 나열된 열 문자를 뽑는다."""
    m = re.search(r"[（(]([^）)]*)[）)]", _plain(text))
    if not m:
        return []
    return [t.strip() for t in m.group(1).split("·") if re.fullmatch(r"[A-Z]", t.strip())]


def _section(md: str, heading_pat: str) -> str:
    """`### 제목` 부터 다음 같은/상위 레벨 제목까지의 본문."""
    m = re.search(heading_pat, md)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"\n#{2,3} ", md[start:])
    return md[start : start + nxt.start()] if nxt else md[start:]


def parse_common(path: str) -> dict:
    md = open(path, encoding="utf-8").read()
    out: dict = {}

    # 헤더 원문 — 탭 구분 코드블록
    m = re.search(r"### 헤더 원문[^\n]*\n+```\n(.+?)\n```", md, re.S)
    if not m:
        raise SpecParseError(f"{path}: 「헤더 원문」 코드블록을 찾지 못했다")
    out["header"] = m.group(1).split("\t")

    # 컬럼 구조 표 — 열 문자 · 컬럼명 · 사용
    cols = []
    for line in md.splitlines():
        c = _cells(line)
        if len(c) != 5:
            continue
        num, letter = _plain(c[0]), _plain(c[1])
        if not (re.fullmatch(r"\d+", num) and re.fullmatch(r"[A-Z]", letter)):
            continue
        name = _ticks(c[2])
        if name:
            cols.append({"letter": letter, "name": name[0], "use": _plain(c[3])})
    if len(cols) != len(out["header"]):
        raise SpecParseError(
            f"{path}: 컬럼 구조 표 {len(cols)}행 ≠ 헤더 원문 {len(out['header'])}개"
        )
    out["columns"] = cols

    # `-` vs 빈칸 — 「핵심 구분」 문장에서 열 문자를 읽는다
    m = re.search(r"\*\*핵심 구분:\*\*(.+)", md)
    if not m:
        raise SpecParseError(f"{path}: 「핵심 구분」(`-` vs 빈칸) 문장을 찾지 못했다")
    sent = m.group(1)
    dash_part, blank_part = sent.split("은 `-`", 1)
    out["dash_letters"] = _paren_letters(dash_part)
    out["blank_letters"] = _paren_letters(blank_part)
    if not out["dash_letters"] or not out["blank_letters"]:
        raise SpecParseError(f"{path}: 「핵심 구분」에서 열 문자를 읽지 못했다: {sent!r}")

    # enum — 우선순위 / 구분
    for key, pat in (("priority", r"### 우선순위[^\n]*\n"), ("category", r"### 구분[^\n]*\n")):
        sec = _section(md, pat)
        first = next((l for l in sec.splitlines() if l.strip().startswith("`")), "")
        vals = _ticks(_before_bold(first))
        if not vals:
            raise SpecParseError(f"{path}: {key} enum 목록을 읽지 못했다")
        out[key] = vals

    return out


def parse_profile(path: str) -> dict:
    md = open(path, encoding="utf-8").read()
    out: dict = {"path": path}

    def row_for(label: str) -> str:
        for line in md.splitlines():
            c = _cells(line)
            if len(c) >= 2 and _plain(c[0]).startswith("`") and label in c[0]:
                return c[1]
        return ""

    # 솔루션 단일값
    cell = row_for("솔루션")
    vals = _ticks(cell)
    if not vals:
        raise SpecParseError(f"{path}: `솔루션` 고정값을 읽지 못했다")
    out["solution"] = vals[0]

    # 기능테스트 ID 형식 → 정규식
    cell = row_for("기능테스트 ID")
    tok = next((t for t in _ticks(cell) if "{" in t), None)
    if not tok:
        raise SpecParseError(f"{path}: `기능테스트 ID` 형식 토큰을 읽지 못했다")
    m = re.search(r"\{(\d+)자리(\s*이상)?", tok)
    if not m:
        raise SpecParseError(f"{path}: `기능테스트 ID` 자리수를 읽지 못했다: {tok!r}")
    digits = int(m.group(1))
    # `N자리 이상` = zero-pad 최소 폭이 N 이고 번호가 자라면 늘어난다.
    # 순번이 999를 넘으면 3자리로는 표현할 수 없으므로, 자리수 소진은 위반이 아니라
    # 정상적인 증가다. 고정폭으로 검사하면 정상 행이 전부 위반으로 잡힌다
    # (2026-09-11 실측: VIOLA 원본 3자리 999행 · 4자리 1,125행).
    quant = f"{{{digits},}}" if m.group(2) else f"{{{digits}}}"
    prefix = tok.split("{")[0]                      # `TC_VIO_` 또는 `TC_`
    body = re.sub(r"\{[^}]*\}", "", tok)            # 플레이스홀더 제거
    if body.count("_") > prefix.count("_"):         # `TC_{모듈코드}_{3자리}` 형
        out["tcid_re"] = rf"^{re.escape(prefix)}[A-Z0-9]+_\d{quant}$"
    else:
        out["tcid_re"] = rf"^{re.escape(prefix)}\d{quant}$"
    out["tcid_fmt"] = tok

    # 사전조건 / 테스트 데이터 사용 여부
    out["precond_required"] = "100% 채움 필수" in row_for("사전조건")
    out["testdata_unused"] = "미사용" in row_for("테스트 데이터")

    # 3 Depth 허용 목록 — 「중 택일」(고정형) 또는 「전체 허용:」(범위형)
    sec = _section(md, r"### 3 Depth[^\n]*\n")
    line = next(
        (l for l in sec.splitlines() if "중 택일" in l or l.strip().startswith("전체 허용")),
        "",
    )
    vals = list(dict.fromkeys(_ticks(_before_bold(line))))
    if not vals:
        raise SpecParseError(f"{path}: `3 Depth` 허용 목록을 읽지 못했다")
    out["depth3"] = vals

    # UI 라벨 표기 — 백틱 / 대괄호
    if re.search(r"### .*UI 라벨 = \*\*백틱\*\*", md):
        out["label_style"] = "backtick"
    elif re.search(r"### .*UI 라벨 = \*\*대괄호\*\*", md):
        out["label_style"] = "bracket"
    else:
        raise SpecParseError(f"{path}: UI 라벨 표기(백틱/대괄호) 절을 찾지 못했다")

    # 구분 × 우선순위 결합 규칙 — **예외 0건인 것만** 강제한다
    sec = _section(md, r"### 구분 × 우선순위 결합 규칙[^\n]*\n")
    hard: dict[str, list[str]] = {}
    for line in sec.splitlines():
        c = _cells(line)
        if len(c) < 2 or not c[0].startswith("`"):
            continue
        cat = _ticks(c[0])
        if not cat:
            continue
        rest = " ".join(c[1:])
        # **절대 표현만 강제한다.** `기본`·`권장` 같은 경향 서술은 제약이 아니다.
        # 실측 마커(`예외 0건`)를 요구하지 않는다 — 그것은 근거이고, 규칙은 문장이다.
        # (`profile-bootfactory` 는 VIOLA 승계라 실측 마커가 없지만 규칙은 명시돼 있다)
        m = re.search(r"항상 `(P\d)`", rest)
        if m:
            hard[cat[0]] = [m.group(1)]
            continue
        m = re.search(r"`(P\d)` 또는 `(P\d)` 만", rest)
        if m:
            hard[cat[0]] = [m.group(1), m.group(2)]
    out["combo_hard"] = hard
    return out


# ─────────────────────────────────────────────────────────── 행 검사

class Report:
    def __init__(self) -> None:
        self.findings: list[dict] = []

    def add(self, sev: str, code: str, msg: str, rows: list | None = None) -> None:
        self.findings.append(
            {"severity": sev, "code": code, "message": msg, "rows": rows or []}
        )

    @property
    def worst(self) -> str | None:
        for s in (CRITICAL, MAJOR, MINOR):
            if any(f["severity"] == s for f in self.findings):
                return s
        return None


def _idx(common: dict, name: str) -> int:
    for i, c in enumerate(common["columns"]):
        if c["name"] == name:
            return i
    raise SpecParseError(f"컬럼 `{name}` 이 사양 컬럼 표에 없다")


def verify(header: list[str], rows: list[list[str]], common: dict, profile: dict,
           first_row_no: int) -> Report:
    r = Report()
    spec_header = common["header"]
    ncol = len(spec_header)

    # 1. 헤더 원문 일치 — 어긋나면 이후 열 판정이 전부 무의미하므로 Critical
    if header:
        got = [h.strip() for h in header[:ncol]]
        if got != spec_header:
            diff = [
                f"{i+1}번째: 사양 `{a}` ≠ 시트 `{b}`"
                for i, (a, b) in enumerate(zip(spec_header, got + [""] * ncol))
                if a != b
            ]
            r.add(CRITICAL, "H1", f"헤더가 사양과 다르다 ({len(diff)}곳): " + " / ".join(diff[:5]))
        if len(header) > ncol and any(str(c).strip() for c in header[ncol:]):
            r.add(CRITICAL, "H2", f"헤더에 {ncol+1}번째 열 이후 값이 있다 (사양은 {ncol}컬럼)")

    def col(row: list[str], i: int) -> str:
        return str(row[i]).strip() if i < len(row) else ""

    i_no = _idx(common, "No")
    i_sol = _idx(common, "솔루션")
    i_tc = _idx(common, "기능테스트 ID")
    i_pri = _idx(common, "우선순위")
    i_cat = _idx(common, "구분")
    i_d3 = _idx(common, "3 Depth")
    i_pre = _idx(common, "사전조건")
    i_proc = _idx(common, "절차")
    i_exp = _idx(common, "예상 결과")
    i_note = _idx(common, "비고")

    letter2idx = {c["letter"]: i for i, c in enumerate(common["columns"])}
    dash_idx = [letter2idx[L] for L in common["dash_letters"] if L in letter2idx]
    blank_idx = [letter2idx[L] for L in common["blank_letters"] if L in letter2idx]
    body_idx = [i_pre, i_proc, i_exp]

    bad: dict[str, list] = {}

    def flag(code: str, rn: int, detail: str = "") -> None:
        bad.setdefault(code, []).append(f"{rn}행" + (f"({detail})" if detail else ""))

    seen_tc: dict[str, int] = {}
    nos: list[tuple[int, int]] = []

    for k, row in enumerate(rows):
        rn = first_row_no + k
        if not any(str(c).strip() for c in row):
            continue

        # 2. X열 이후 오염
        if len(row) > ncol and any(str(c).strip() for c in row[ncol:]):
            flag("C_EXTRA", rn)

        # 3. 솔루션 단일값
        v = col(row, i_sol)
        if v != profile["solution"]:
            flag("SOL", rn, f"`{v}`")

        # 4. 기능테스트 ID 형식 · 중복
        v = col(row, i_tc)
        if not re.match(profile["tcid_re"], v):
            flag("TCFMT", rn, f"`{v}`")
        elif v in seen_tc:
            flag("TCDUP", rn, f"`{v}` = {seen_tc[v]}행")
        else:
            seen_tc[v] = rn

        # 5. No 정수
        v = col(row, i_no)
        if re.fullmatch(r"\d+", v):
            nos.append((int(v), rn))
        else:
            flag("NOFMT", rn, f"`{v}`")

        # 6. enum — 우선순위 / 구분 / 3 Depth
        pri, cat = col(row, i_pri), col(row, i_cat)
        if pri not in common["priority"]:
            flag("PRI", rn, f"`{pri}`")
        if cat not in common["category"]:
            flag("CAT", rn, f"`{cat}`")
        v = col(row, i_d3)
        if v not in profile["depth3"]:
            flag("D3", rn, f"`{v}`")

        # 7. 구분 × 우선순위 결합 — 예외 0건 규칙만
        allowed = profile["combo_hard"].get(cat)
        if allowed and pri and pri not in allowed:
            flag("COMBO", rn, f"`{cat}`+`{pri}` (허용 {'/'.join(allowed)})")

        # 8. `-` 위치 / 빈칸 위치
        for i in dash_idx:
            if col(row, i) != "-":
                flag("DASH", rn, f"{common['columns'][i]['name']}=`{col(row, i)}`")
        for i in blank_idx:
            if col(row, i):
                flag("BLANK", rn, f"{common['columns'][i]['name']}=`{col(row, i)}`")

        # 9. 비고 — 실질 필수 (근거 태그). 비우면 시트→분석서 역추적이 끊긴다
        if not col(row, i_note):
            flag("NOTE", rn)

        # 10. 사전조건 — 프로파일이 100% 필수인 경우 + 줄바꿈 금지
        v = col(row, i_pre)
        if profile["precond_required"] and not v:
            flag("PRE_EMPTY", rn)
        if "\n" in str(row[i_pre] if i_pre < len(row) else ""):
            flag("PRE_MULTILINE", rn)

        # 11. 테스트 데이터 — 프로파일이 미사용이면 공란
        if profile["testdata_unused"]:
            i_td = _idx(common, "테스트 데이터")
            if col(row, i_td):
                flag("TD", rn, f"`{col(row, i_td)}`")

        # 12. 절차 `N. ` 접두
        v = str(row[i_proc]) if i_proc < len(row) else ""
        for ln in [x for x in v.split("\n") if x.strip()]:
            if not re.match(r"^\s*\d+\.\s", ln):
                flag("PROC", rn, f"`{ln[:20]}`")
                break

        # 13. 예상 결과 — 명사형 종결 (서술형 어미 금지)
        v = col(row, i_exp)
        last = [x for x in v.split("\n") if x.strip()]
        if last and re.search(r"(니다|습니다|한다|된다|봅니다|하다|요)[.!]?$", last[-1].strip()):
            flag("EXP", rn, f"`{last[-1][-14:]}`")

        # 14. 본문 열 문체 — 프로파일 표기와 반대인 기호
        #     ⚠️ `[실제 결과]` 는 예외다 — common.md 가 「PASS/FAIL 판정 대신 실측 상태를
        #        [실제 결과]에 기재」 문구를 기획 미정의 항목의 **표준 표현**으로 직접 지정한다.
        #        이것은 UI 라벨을 잘못 대괄호로 쓴 것이 아니라 열 이름(`실제 결과`)을 가리키는
        #        지시문이라 태그와 성격이 다르다. 벗기지 않으면 이 문구를 쓴 행마다 매번
        #        STYLE_BRACKET 오탐이 나고(실측: 여러 배치에서 반복), 오탐을 내는 검사기는
        #        무시당해 검사 자체가 무력해진다.
        for i in body_idx:
            v = col(row, i)
            v_checked = re.sub(r"\[실제\s*결과\]", "", _outside_ticks(v))
            if profile["label_style"] == "backtick" and re.search(r"\[[^\]]+\]", v_checked):
                flag("STYLE_BRACKET", rn, common["columns"][i]["name"])
            if profile["label_style"] == "bracket" and "`" in v:
                flag("STYLE_TICK", rn, common["columns"][i]["name"])

        # 15. 셀 내 `|` — 표 파싱을 깨뜨린다.
        #     백틱 인용 안의 `|` 는 정당한 UI 라벨이므로 제외한다 (`|<` 접기 아이콘 실측).
        if any("|" in _outside_ticks(str(c)) for c in row):
            flag("PIPE", rn)

    # 16. No 연속성 (결번·역행)
    if nos:
        vals = [v for v, _ in nos]
        gaps = [
            f"{a}→{b}"
            for (a, _), (b, _) in zip(nos, nos[1:])
            if b != a + 1
        ]
        if gaps:
            bad["NOSEQ"] = gaps[:10]
        dup = {v for v in vals if vals.count(v) > 1}
        if dup:
            bad["NODUP"] = sorted(dup)[:10]

    META = {
        "H1": (CRITICAL, "헤더 불일치"),
        "H2": (CRITICAL, "헤더 열 초과"),
        "C_EXTRA": (CRITICAL, f"{ncol}번째 열 이후에 값이 있다 (전 값 밀림 위험)"),
        "SOL": (MAJOR, f"`솔루션` 이 프로파일 고정값 `{profile['solution']}` 이 아니다"),
        "TCFMT": (MAJOR, f"`기능테스트 ID` 형식 위반 (사양 {profile['tcid_fmt']})"),
        "TCDUP": (CRITICAL, "`기능테스트 ID` 중복"),
        "NOFMT": (MAJOR, "`No` 가 정수가 아니다"),
        "NOSEQ": (MAJOR, "`No` 결번·역행"),
        "NODUP": (CRITICAL, "`No` 중복"),
        "PRI": (MAJOR, f"`우선순위` 가 사양 enum({'/'.join(common['priority'])}) 밖"),
        "CAT": (MAJOR, f"`구분` 이 사양 enum({'/'.join(common['category'])}) 밖"),
        "D3": (MAJOR, f"`3 Depth` 가 프로파일 허용({'/'.join(profile['depth3'])}) 밖"),
        "COMBO": (MAJOR, "구분 × 우선순위 결합 규칙 위반 (프로파일의 절대 규칙)"),
        "DASH": (MAJOR, "Depth 계열은 전 행 `-` 여야 한다"),
        "BLANK": (MAJOR, "미사용·실행 컬럼은 빈칸이어야 한다 (`-` 아님)"),
        "NOTE": (MAJOR, "`비고` 공란 — 근거 태그가 없어 역추적이 끊긴다"),
        "PRE_EMPTY": (MAJOR, "`사전조건` 공란 (프로파일은 100% 채움 필수)"),
        "PRE_MULTILINE": (MINOR, "`사전조건` 이 여러 줄 (사양은 1줄)"),
        "TD": (MINOR, "`테스트 데이터` 는 프로파일에서 미사용 (공란 유지)"),
        "PROC": (MAJOR, "`절차` 에 `N. ` 접두가 없다"),
        "EXP": (MINOR, "`예상 결과` 가 서술형 종결 (사양은 명사형)"),
        "STYLE_BRACKET": (MINOR, "본문 열에 대괄호 — 프로파일은 백틱, 대괄호는 태그 전용"),
        "STYLE_TICK": (MINOR, "본문 열에 백틱 — 프로파일은 대괄호 표기"),
        "PIPE": (MINOR, "셀에 백틱 인용 밖의 `|` 문자 (표 파싱 깨짐)"),
    }
    for code, items in bad.items():
        sev, msg = META[code]
        r.add(sev, code, f"{msg} — {len(items)}건", [str(x) for x in items[:12]])
    return r


# ─────────────────────────────────────────────────────────── I/O

def load_tsv(path: str) -> tuple[list[str], list[list[str]]]:
    lines = open(path, encoding="utf-8").read().split("\n")
    grid = [l.split("\t") for l in lines if l.strip()]
    if not grid:
        raise RuntimeError(f"{path}: 빈 파일")
    return grid[0], grid[1:]


def _find_sheets_api() -> str:
    """`sheets_api.py` 가 있는 디렉터리를 찾는다.

    이 파일은 루트 `scripts/` 에 심볼릭 링크로도 노출된다. `__file__` 은 호출 경로를
    가리키므로 링크 경유 실행과 원본 경유 실행에서 상대 경로가 달라진다.
    두 기점에서 위로 올라가며 실제 파일을 찾는다 (`oauth_sheet.py` 와 같은 전략).
    """
    starts = {
        os.path.dirname(os.path.abspath(__file__)),
        os.path.dirname(os.path.realpath(__file__)),
        os.getcwd(),
    }
    rels = (
        ("sheets_api.py",),
        ("scripts", "sheets_api.py"),
        (".claude", "skills", "sheet-operator", "scripts", "sheets_api.py"),
        ("..", "..", "sheet-operator", "scripts", "sheets_api.py"),
    )
    for start in starts:
        cur = start
        for _ in range(6):
            for rel in rels:
                cand = os.path.join(cur, *rel)
                if os.path.isfile(cand):
                    return os.path.dirname(os.path.abspath(cand))
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    raise RuntimeError(
        "sheets_api.py 를 찾지 못했다. 프로젝트 루트에서 실행하거나 --tsv 를 쓰십시오."
    )


def load_sheet(sheet: str, tab: str, rows: tuple[int, int] | None):
    sys.path.insert(0, _find_sheets_api())
    from sheets_api import SheetsClient  # type: ignore

    sid = SheetsClient.extract_id(sheet)
    cli = SheetsClient()
    header = cli.read(sid, f"'{tab}'!1:1")
    header = header[0] if header else []
    if rows:
        data = cli.read(sid, f"'{tab}'!{rows[0]}:{rows[1]}")
        first = rows[0]
    else:
        data = cli.read(sid, f"'{tab}'!2:100000")
        first = 2
    return header, data, first


# ─────────────────────────────────────────────── 로컬 ↔ 시트 대조

def diff_local_sheet(local: list[list[str]], sheet: list[list[str]],
                     first_row_no: int, ncol: int,
                     header: list[str]) -> Report:
    """로컬 `.tsv` 와 시트 행을 셀 단위로 대조한다 (「로컬 ↔ 시트」 경계면).

    케이스 본문을 사람이 눈으로 대조할 이유가 없다 — 같은지 다른지는 기계 판정이고,
    다르면 **어느 행 어느 컬럼이** 다른지가 필요한 정보다.

    `.tsv` 의 헤더 행은 **있어도 없어도 된다.** 시트 쪽은 항상 데이터 첫 행부터 읽으므로,
    로컬 첫 행이 사양 헤더와 정확히 같으면 건너뛴다 — 두 파이프라인이 서로 다른 관행을
    쓰기 때문이다 (`testcase-generator` 의 `03_rows_s{NN}.tsv` 는 **헤더 없음**,
    `tc-augmenter` 의 `13_rows_*.tsv` 는 **1행이 헤더 원문**). 한쪽 관행대로 만든 파일을
    문서에 적힌 대로 넘겼는데 `DIFF_COUNT` 로 튕기면 안 된다 —
    **오탐을 내는 검사기는 무시당해 검사 자체가 무력해진다.**
    """
    r = Report()

    def norm(v) -> str:
        # 시트는 셀 내 개행을 그대로 돌려주고 `.tsv` 는 리터럴 `\n` 으로 담는다.
        return str(v).replace("\r\n", "\n").replace("\\n", "\n").strip()

    live = [row for row in sheet if any(str(c).strip() for c in row)]
    loc = [row for row in local if any(str(c).strip() for c in row)]

    # 로컬 첫 행이 사양 헤더와 **정확히** 같을 때만 헤더로 보고 뺀다.
    # 데이터 행의 첫 칸은 `No`(정수)라 실제 케이스 행과 혼동될 여지가 없다.
    if header and loc and [norm(c) for c in loc[0][:ncol]] == [norm(c) for c in header[:ncol]]:
        loc = loc[1:]

    if len(loc) != len(live):
        r.add(CRITICAL, "DIFF_COUNT",
              f"행 수 불일치 — 로컬 {len(loc)}행 ≠ 시트 {len(live)}행 "
              f"(차이 {abs(len(loc) - len(live))}행)")

    mismatch: list[str] = []
    for k, (a, b) in enumerate(zip(loc, live)):
        rn = first_row_no + k
        for i in range(ncol):
            va = norm(a[i]) if i < len(a) else ""
            vb = norm(b[i]) if i < len(b) else ""
            if va != vb:
                mismatch.append(f"{rn}행 {i + 1}열: 로컬 `{va[:28]}` ≠ 시트 `{vb[:28]}`")
    if mismatch:
        r.add(CRITICAL, "DIFF_CELL", f"셀 내용 불일치 — {len(mismatch)}건",
              mismatch[:12])

    if not r.findings:
        r.add(MINOR, "DIFF_OK", f"로컬 ↔ 시트 일치 — {len(loc)}행 × {ncol}컬럼 전 셀 동일")
    return r


# ─────────────────────────────────────────────────────────── 자기검증

def selftest(fdir: str) -> int:
    """심어 둔 위반이 전부 잡히는지 확인한다.

    **통과만 확인하면 검사기가 죽어 있어도 모른다.** 사양 형식이 바뀌어
    파서가 조용히 빈 규칙을 돌려주면 모든 행이 "위반 0건"으로 통과한다 —
    검사를 안 하는 것보다 해롭다. 사양을 고친 뒤에는 이 검증을 돌린다.
    """
    common = parse_common(os.path.join(fdir, "common.md"))
    profile = parse_profile(os.path.join(fdir, "profile-viola.md"))
    H = common["header"]
    n = len(H)

    def mk(**kw) -> list[str]:
        r = [""] * n
        base = {
            "No": "1", "솔루션": profile["solution"], "기능테스트 ID": "TC_VIO_001",
            "화면 ID": "VIOE-01_01_01", "우선순위": "P3", "구분": "표시",
            "1 Depth": "모니터링", "2 Depth": "목록화면", "3 Depth": profile["depth3"][0],
            "4 Depth": "-", "5 Depth": "-", "사전조건": "로그인 상태",
            "절차": "1. 화면 진입", "예상 결과": "컬럼 표출", "비고": "[DESC 1항]",
        }
        base.update(kw)
        for k, v in base.items():
            r[H.index(k)] = v
        return r

    # (코드, 그 코드만 유발하는 행)
    cases = [
        ("SOL", mk(**{"솔루션": "VIOLA_K8S"})),
        ("TCFMT", mk(**{"기능테스트 ID": "TC_VIO_1"})),
        ("PRI", mk(**{"우선순위": "P9"})),
        ("CAT", mk(**{"구분": "확인"})),
        ("D3", mk(**{"3 Depth": "없는값"})),
        ("COMBO", mk(**{"구분": "부수", "우선순위": "P2"})),
        ("DASH", mk(**{"4 Depth": ""})),
        ("BLANK", mk(**{"요구사항 ID": "REQ-1"})),
        ("NOTE", mk(**{"비고": ""})),
        ("PRE_EMPTY", mk(**{"사전조건": ""})),
        ("TD", mk(**{"테스트 데이터": "admin/1234"})),
        ("PROC", mk(**{"절차": "화면 진입"})),
        ("EXP", mk(**{"예상 결과": "컬럼이 표출된다"})),
        ("STYLE_BRACKET", mk(**{"예상 결과": "[전체] 탭 표출"})),
        ("PIPE", mk(**{"절차": "1. A | B 클릭"})),
        ("PRE_MULTILINE", mk(**{"사전조건": "로그인\n관리자"})),
        ("C_EXTRA", mk() + ["오염"]),
    ]
    fails = []
    for i, (code, row) in enumerate(cases):
        row = list(row)
        # 행마다 ID·No를 달리해 중복 코드가 끼어들지 않게 한다.
        # 단 TCFMT 케이스는 형식 위반 자체가 검사 대상이므로 덮어쓰지 않는다.
        if code != "TCFMT":
            row[H.index("기능테스트 ID")] = f"TC_VIO_{i + 10:03d}"
        row[H.index("No")] = str(i + 1)
        got = {f["code"] for f in verify(H, [row], common, profile, 2).findings}
        if code not in got:
            fails.append(f"  ✗ {code} 미검출 (검출: {sorted(got) or '없음'})")

    # 정상 행은 위반 0건이어야 한다 (오탐 검증)
    clean = verify(H, [mk()], common, profile, 2).findings
    if clean:
        fails.append(f"  ✗ 정상 행에서 오탐: {[f['code'] for f in clean]}")

    # 백틱 인용 안의 `|`·`[]` 는 오탐이 아니어야 한다 (실측 `|<` 접기 아이콘)
    quoted = verify(H, [mk(**{"예상 결과": "접기 아이콘 `|<` 표출"})],
                    common, profile, 2).findings
    if quoted:
        fails.append(f"  ✗ 백틱 인용 오탐: {[f['code'] for f in quoted]}")

    # ⚠️ `[실제 결과]` 는 common.md 가 지정한 기획 미정의 항목의 표준 표현이라
    #    STYLE_BRACKET 오탐이 나면 안 된다 (실측: 2026-09-23 여러 배치에서 반복 오탐).
    #    같은 셀에 다른 진짜 대괄호가 섞이면 여전히 잡혀야 한다(면제가 전체를 죽이면 안 됨).
    undefined_phrase = verify(
        H, [mk(**{"예상 결과": "ㄴ 기획 미정의 항목 — PASS/FAIL 판정 대신 실측 상태를 [실제 결과]에 기재"})],
        common, profile, 2).findings
    if undefined_phrase:
        fails.append(f"  ✗ [실제 결과] 표준 문구 오탐: {[f['code'] for f in undefined_phrase]}")
    mixed = verify(H, [mk(**{"예상 결과": "[실제 결과]에 기재 / [UI] 라벨도 표출"})],
                    common, profile, 2).findings
    if "STYLE_BRACKET" not in {f["code"] for f in mixed}:
        fails.append("  ✗ [실제 결과] 면제가 다른 대괄호까지 죽임 — 진짜 위반을 놓친다")

    # TC ID 자리수 소진은 위반이 아니다 (2026-09-11 실측: VIOLA 4자리 1,125행).
    # 고정폭으로 검사하면 999를 넘긴 정상 행이 전부 TCFMT 로 잡혀 검사기가 무시당한다.
    for tcid in ("TC_VIO_999", "TC_VIO_1000", "TC_VIO_2125"):
        over = verify(H, [mk(**{"기능테스트 ID": tcid})], common, profile, 2).findings
        if over:
            fails.append(f"  ✗ 자리수 오탐 `{tcid}`: {[f['code'] for f in over]}")

    # `--diff` 는 `.tsv` 헤더 유무와 무관해야 한다.
    # 두 파이프라인의 관행이 달라(`03_rows_*` 헤더 없음 / `13_rows_*` 헤더 있음),
    # 한쪽을 문서대로 넘겼을 때 DIFF_COUNT 오탐이 나면 검사를 건너뛰게 된다.
    data = mk()
    for tsv, label in (([data], "헤더 없음"), ([H, data], "헤더 있음")):
        d = diff_local_sheet(tsv, [data], 2, n, H)
        if {f["code"] for f in d.findings} != {"DIFF_OK"}:
            fails.append(f"  ✗ --diff {label} 오탐: "
                         f"{[f['code'] for f in d.findings]}")
    # 헤더를 건너뛴 뒤 실제 불일치는 여전히 잡아야 한다 (건너뛰기가 검사를 먹지 않는다)
    other = mk(**{"예상 결과": "다른 값 표출"})
    d = diff_local_sheet([H, data], [other], 2, n, H)
    if "DIFF_CELL" not in {f["code"] for f in d.findings}:
        fails.append("  ✗ --diff 헤더 스킵 후 불일치 미검출")

    # 중복·연속성
    a, b = mk(), mk()
    a[H.index("No")], b[H.index("No")] = "1", "1"
    codes = {f["code"] for f in verify(H, [a, b], common, profile, 2).findings}
    for want in ("NODUP", "TCDUP"):
        if want not in codes:
            fails.append(f"  ✗ {want} 미검출")

    print(f"자기검증 — 규칙 출처 {fdir} · 컬럼 {n}개 · 케이스 {len(cases) + 9}개")
    if fails:
        print("\n실패:")
        print("\n".join(fails))
        return 3
    print(f"\n✅ 전 항목 통과 — 심어 둔 위반 {len(cases)}종 검출 + 오탐 0건")
    return 0


def main(argv: list[str]) -> int:
    opts = {}
    for a in argv[1:]:
        if a.startswith("--"):
            k, _, v = a.partition("=")
            opts[k] = v or True
        else:
            print(f"오류: 위치 인자를 받지 않는다: {a}", file=sys.stderr)
            return 3

    fdir_early = opts.get("--formats-dir") or os.path.join(".claude", "formats")
    if opts.get("--selftest"):
        try:
            return selftest(fdir_early)
        except SpecParseError as e:
            print(f"오류: 사양에서 규칙을 읽지 못했다 — {e}", file=sys.stderr)
            return 3

    prof_name = opts.get("--profile")
    if not prof_name or prof_name is True:
        print(__doc__)
        return 3

    fdir = opts.get("--formats-dir") or os.path.join(".claude", "formats")
    common_path = os.path.join(fdir, "common.md")
    prof_path = os.path.join(fdir, f"profile-{prof_name}.md")
    for p in (common_path, prof_path):
        if not os.path.isfile(p):
            print(f"오류: 사양 파일이 없다: {p}", file=sys.stderr)
            return 3

    try:
        common = parse_common(common_path)
        profile = parse_profile(prof_path)
    except SpecParseError as e:
        print(f"오류: 사양에서 규칙을 읽지 못했다 — {e}", file=sys.stderr)
        print("      하드코딩 값으로 채점하지 않는다. 사양 형식이 바뀌었으면 "
              "이 스크립트의 파서를 함께 고쳐야 한다.", file=sys.stderr)
        return 3

    rng = None
    if isinstance(opts.get("--rows"), str):
        a, _, b = opts["--rows"].partition("-")
        rng = (int(a), int(b))

    # ── 로컬 ↔ 시트 대조 모드
    if opts.get("--diff"):
        if not (opts.get("--tsv") and opts.get("--sheet") and opts.get("--tab")):
            print("오류: --diff 는 --tsv 와 --sheet/--tab 을 함께 요구한다", file=sys.stderr)
            return 3
        try:
            loc = [l.split("\t") for l in
                   open(opts["--tsv"], encoding="utf-8").read().split("\n") if l.strip()]
            _, live, first = load_sheet(opts["--sheet"], opts["--tab"], rng)
        except Exception as e:
            print(f"오류: 입력을 읽지 못했다 — {e}", file=sys.stderr)
            return 3
        rep = diff_local_sheet(loc, live, first, len(common["header"]),
                               common["header"])
        print(f"로컬 ↔ 시트 대조 — `{opts['--tsv']}` vs {opts['--tab']} "
              f"{f'{rng[0]}~{rng[1]}행' if rng else '전체'}\n")
        for f in rep.findings:
            print(f"[{f['severity']:8s}] {f['code']:12s} {f['message']}")
            if f["rows"] and not opts.get("--quiet"):
                print(f"{'':24s}→ " + "\n".ljust(27).join(f["rows"]))
        return {CRITICAL: 2, MAJOR: 1, MINOR: 0, None: 0}[rep.worst]

    try:
        if opts.get("--tsv"):
            header, data = load_tsv(opts["--tsv"])
            first = rng[0] if rng else 2
        else:
            if not opts.get("--sheet") or not opts.get("--tab"):
                print("오류: --sheet 와 --tab 이 필요하다 (또는 --tsv)", file=sys.stderr)
                return 3
            header, data, first = load_sheet(opts["--sheet"], opts["--tab"], rng)
    except Exception as e:
        print(f"오류: 입력을 읽지 못했다 — {e}", file=sys.stderr)
        return 3

    rep = verify(header, data, common, profile, first)

    n_rows = sum(1 for r in data if any(str(c).strip() for c in r))
    print(f"검사 대상 {n_rows}행 · 프로파일 `{prof_name}` · 컬럼 {len(common['header'])}개")
    print(f"규칙 출처: {common_path} + {prof_path}")
    if not rep.findings:
        print("\n✅ 결정적 점검 위반 0건")
    else:
        order = {CRITICAL: 0, MAJOR: 1, MINOR: 2}
        print()
        for f in sorted(rep.findings, key=lambda x: order[x["severity"]]):
            print(f"[{f['severity']:8s}] {f['code']:14s} {f['message']}")
            if f["rows"] and not opts.get("--quiet"):
                print(f"{'':26s}→ {', '.join(f['rows'])}")
    print("\n※ 커버리지·삭제 오케이스·변경 범위·추측 케이스·분포는 이 스크립트가 "
          "판정하지 않는다 — 리뷰어가 본다.")

    if isinstance(opts.get("--json"), str):
        with open(opts["--json"], "w", encoding="utf-8") as fp:
            json.dump(
                {"profile": prof_name, "rows": n_rows, "findings": rep.findings},
                fp, ensure_ascii=False, indent=2,
            )
        print(f"JSON 저장: {opts['--json']}")

    return {CRITICAL: 2, MAJOR: 1, MINOR: 1, None: 0}[rep.worst]


if __name__ == "__main__":
    sys.exit(main(sys.argv))
