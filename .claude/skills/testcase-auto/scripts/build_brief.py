"""역할별 브리핑 생성 — 에이전트가 읽을 고정 문서를 실행 조건에 맞게 좁힌다.

에이전트 호출마다 사양·인덱스 전문이 다시 컨텍스트에 올라가고, 캐시읽기 단가가
낮아도 **컨텍스트 크기 × 턴 수**가 비용이라 그대로 비용이 된다.
(실측: 화면 34개 실행에서 고정 문서가 화면당 479KB · 34화면 15.9MB 재전송)

**요약하지 않는다 — 사양 절을 원문 그대로 발췌한다.**
요약은 규칙을 조용히 빠뜨릴 수 있고, 빠진 규칙은 전 행에 번진다.
이 스크립트가 하는 일은 **역할에 필요한 절만 골라 원문을 옮기는 것**뿐이다.

의존성: 없음 (표준 라이브러리)

CLI 사용:
  python build_brief.py --role=analyst --profile=viola --doc-type=변경 \\
      --out=_workspace/00_brief_analyst.md \\
      --index=_workspace/00_screen_index.md
  python build_brief.py --coverage-check        # 절 배정 누락 검사 (사양 수정 후 필수)
  python build_brief.py --role=writer --profile=trombone --doc-type=신규 --out=-

  --role: analyst | writer | reviewer | sheet-analyst | augmenter
  --profile: viola | trombone | bootfactory
  --doc-type: 신규 | 변경 | 추가
              `신규` + 예외 없음 / `추가` 는 변경분 모드 절을 제외한다.
              `추가` 는 기획서가 아니라 기존 테스트 케이스를 원천으로 삼는
              `testcase-augment` 절차용이다.
  --has-change-exception: 문서 기본이 `신규` 라도 변경 정책 화면이 있으면 지정
  --index: 화면 인덱스 경로. **`--role=analyst` 일 때만** 슬림판(ID·페이지·간지·정책·CH-ID)을
           함께 넣는다. writer·reviewer 는 담당 화면 분석서로 작업하므로 인덱스가 필요 없다
  --phase0: Phase 0 확정값 표를 담은 파일 (있으면 그대로 앞에 붙인다)
  --formats-dir: 사양 디렉터리 (기본 `.claude/formats`)
  --out: 출력 경로 (`-` 는 stdout)

종료 코드: 0 정상 / 3 실행 오류·미배정 절 발견

⚠️ 아래 ROLE_SECTIONS 는 **규칙 값이 아니라 라우팅 표**다. 규칙은 사양 파일에만 있다.
   사양에 새 절이 생기면 `--coverage-check` 가 **미배정으로 실패**하므로,
   절을 추가한 사람이 어느 역할에 필요한지 결정하게 된다 (조용히 누락되지 않는다).
"""

from __future__ import annotations

import os
import re
import sys

ROLES = ("analyst", "writer", "reviewer", "sheet-analyst", "augmenter")

# 변경분 모드에서만 필요한 절 — `신규` + 예외 없음이면 제외한다
CHANGE_ONLY = {
    "변경 표기 경로의 위계 — 박스는 범위를 확정하지 않는다",
    "규칙",
    "취소선 = 삭제 — 정상 동작 케이스를 만들지 않는다",
    "금지 — 삭제된 내용으로 만들 수 있는 케이스는 하나뿐이다",
    '경계 — "삭제 자리의 대체 동작"',
    "검출 한계 — 취소선은 스크립트로 완전히 잡히지 않는다",
    "변경분 모드 태그 (기획서 유형 = `변경` 일 때)",
    "비고 — 변경분 전용 태그",
    "피드백 — 변경분 전용 태그",
    "CH-ID 네임스페이스",
    "CH-ID 충돌 방지 — 기존 탭에 이어 쓸 때",
}

# 절 제목(원문) → 그 절이 필요한 역할
# 제목은 `#` 과 번호를 뗀 원문이며, 사양 파일의 표기를 그대로 쓴다.
ROLE_SECTIONS: dict[str, tuple[str, ...]] = {
    # ── common.md
    "메타": ROLES,
    "권위 규칙 — 사양과 대상 시트가 충돌할 때": ROLES,
    "이 사양이 낡았는지 알아내는 능력의 한계": ("reviewer", "sheet-analyst"),
    "컬럼 구조 (A~W, 23컬럼) — 전 제품 공통": ("writer", "reviewer", "sheet-analyst", "augmenter"),
    "헤더 원문 (탭 문자 구분 — 빈 시트에 헤더 생성 시 그대로 사용)": ("writer", "sheet-analyst", "augmenter"),
    "폐지된 `관리대상` 컬럼 (2026-09-02)": ("writer", "reviewer", "sheet-analyst", "augmenter"),
    "enum — 공통": ("writer", "reviewer", "sheet-analyst", "augmenter"),
    "우선순위 (G) — 4종": ("writer", "reviewer", "sheet-analyst", "augmenter"),
    "구분 (H) — 6종": ("writer", "reviewer", "sheet-analyst", "augmenter"),
    "3 Depth (K)": ("writer", "reviewer", "sheet-analyst", "augmenter"),
    "실제 결과 (R)": ("writer", "reviewer", "sheet-analyst", "augmenter"),
    "검증 단위 — atomic (전 제품 확정)": ("writer", "reviewer", "augmenter"),
    "표기 컨벤션 — 공통": ("writer", "reviewer", "augmenter"),
    "절차 번호 접두": ("writer", "reviewer", "augmenter"),
    "예상 결과 어조와 `ㄴ`": ("writer", "reviewer", "augmenter"),
    "UI 라벨 표기 — **프로파일마다 정반대다**": ("writer", "reviewer", "augmenter"),
    "`-` (No data) vs 빈칸 — 가장 자주 틀리는 구분": ("writer", "reviewer", "sheet-analyst", "augmenter"),
    "일시·날짜 형식": ("writer", "reviewer", "augmenter"),
    "화면 ID — 공통 원칙": ROLES,
    "팝업 처리 — 공통": ("analyst", "writer", "reviewer", "augmenter"),
    "비고(V) / 피드백(W) — 역할 분리": ("analyst", "writer", "reviewer", "augmenter"),
    "비고 = 근거 태그": ("analyst", "writer", "reviewer", "augmenter"),
    "피드백 = 확인사항 태그": ("analyst", "writer", "reviewer", "augmenter"),
    "공통 DESC C-ID는 **공유 키**다 — 소진되는 번호가 아니다": ("analyst", "writer", "reviewer"),
    '"하나의 정의"의 판단 기준 — 내용 유사성이 아니라 **기획서의 상호 참조**': ("analyst", "reviewer"),
    "DESC 번호 두 체계 — 섞지 말고 분석서를 따른다": ("analyst", "writer", "reviewer"),
    "CH-ID 네임스페이스": ("analyst", "writer", "reviewer", "sheet-analyst", "augmenter"),
    "CH-ID 충돌 방지 — 기존 탭에 이어 쓸 때": ("analyst", "writer", "sheet-analyst", "augmenter"),
    "파생 케이스의 원천 — 기획서가 아닌 근거": ("writer", "reviewer", "augmenter"),
    "변경 표기 경로의 위계 — 박스는 범위를 확정하지 않는다": ("analyst", "writer", "reviewer", "augmenter"),
    "규칙": ("analyst", "writer", "reviewer", "augmenter"),
    "취소선 = 삭제 — 정상 동작 케이스를 만들지 않는다": ("analyst", "writer", "reviewer", "augmenter"),
    "금지 — 삭제된 내용으로 만들 수 있는 케이스는 하나뿐이다": ("writer", "reviewer", "augmenter"),
    '경계 — "삭제 자리의 대체 동작"': ("writer", "reviewer", "augmenter"),
    "검출 한계 — 취소선은 스크립트로 완전히 잡히지 않는다": ("analyst", "reviewer"),
    "변경분 모드 태그 (기획서 유형 = `변경` 일 때)": ("analyst", "writer", "reviewer", "augmenter"),
    "비고 — 변경분 전용 태그": ("analyst", "writer", "reviewer", "augmenter"),
    "피드백 — 변경분 전용 태그": ("analyst", "writer", "reviewer", "augmenter"),
    "탭 구조 / 작성 절차": ("writer", "sheet-analyst", "augmenter"),
    "새 케이스 작성 시 암묵 규칙 (공통 요약)": ("writer", "reviewer", "augmenter"),
    # ── profile-*.md
    "`K8s` 와 `CI/CD` 는 같은 프로파일을 쓴다": ROLES,
    "제품 고유 값": ("writer", "reviewer", "sheet-analyst", "augmenter"),
    "화면 ID (F열)": ROLES,
    "enum — VIOLA 실측": ("writer", "reviewer", "augmenter"),
    "enum — TROMBONE 실측": ("writer", "reviewer", "augmenter"),
    "우선순위 분포": ("writer", "reviewer", "augmenter"),
    "구분 분포 — 지배 구분은 **`표시`**": ("writer", "reviewer", "augmenter"),
    "구분 × 우선순위 결합 규칙 (실측 근거)": ("writer", "reviewer", "augmenter"),
    "구분 × 우선순위 결합 규칙 (실측)": ("writer", "reviewer", "augmenter"),
    "구분 × 우선순위 결합 규칙 (VIOLA 승계)": ("writer", "reviewer", "augmenter"),
    "3 Depth (K) — 4종 고정": ("writer", "reviewer", "augmenter"),
    "3 Depth (K) — 4종 고정 (VIOLA 승계)": ("writer", "reviewer", "augmenter"),
    "표기 컨벤션 — VIOLA 고유": ("writer", "reviewer", "augmenter"),
    "표기 컨벤션 — TROMBONE 고유": ("writer", "reviewer", "augmenter"),
    "UI 라벨 = **백틱**": ("writer", "reviewer", "augmenter"),
    "절차·예상 결과 실측값": ("writer", "reviewer", "augmenter"),
    "작성 예시 (익명화)": ("writer", "augmenter"),
    "VIOLA 암묵 규칙 (프로파일 고유분만)": ("writer", "reviewer", "augmenter"),
    # ── profile-trombone.md 고유
    "TC ID 모듈코드 (실측)": ("writer", "reviewer", "sheet-analyst", "augmenter"),
    "구분 분포 — 지배 구분은 **`정상`**": ("writer", "reviewer", "augmenter"),
    "3 Depth (K) — 7종, **탭별 실사용 범위가 다르다**": ("writer", "reviewer", "augmenter"),
    "⚠️ UI 라벨 = **대괄호**. 백틱을 쓰지 않는다": ("writer", "reviewer", "augmenter"),
    "메시지 코드 인용 (TROMBONE 고유)": ("writer", "reviewer", "augmenter"),
    "팝업 `3 Depth` — 고정되지 않는다": ("analyst", "writer", "reviewer", "augmenter"),
    "V/W 소수 혼용에 대한 방침": ("writer", "reviewer", "augmenter"),
    "피드백 태그 실측 분포": ("writer", "reviewer", "augmenter"),
    "비고 태그 실측": ("writer", "reviewer", "augmenter"),
    "TROMBONE 암묵 규칙 (프로파일 고유분만)": ("writer", "reviewer", "augmenter"),
    # ── profile-bootfactory.md 고유
    # 「실측이 아니라 파생」 경고는 **전 역할**이 알아야 한다 —
    # 리뷰가 편차를 작성자 탓으로 몰면 안 되고, 분석·작성도 근거 강도를 알아야 한다.
    "⚠️ 이 프로파일은 실측이 아니라 파생이다": ROLES,
    "근거 없는 값 — 바꾸려면 비싸다": ROLES,
    "enum — VIOLA 분포 이식 (BF 실측 아님)": ("writer", "reviewer", "augmenter"),
    "표기 컨벤션 — VIOLA 승계": ("writer", "reviewer", "augmenter"),
    "절차·예상 결과": ("writer", "reviewer", "augmenter"),
    "BootFactory 암묵 규칙 (프로파일 고유분만)": ("writer", "reviewer", "augmenter"),
    "실행 이력": ("reviewer", "sheet-analyst"),
}


def sections(path: str) -> list[tuple[str, str]]:
    """(제목, 절 원문) 목록. 절 원문에는 제목 줄을 포함한다."""
    md = open(path, encoding="utf-8").read()
    hs = [(m.start(), m.group(0)) for m in re.finditer(r"^#{2,3} .+$", md, re.M)]
    out = []
    for i, (pos, head) in enumerate(hs):
        end = hs[i + 1][0] if i + 1 < len(hs) else len(md)
        title = re.sub(r"^#{2,3} ", "", head).strip()
        out.append((title, md[pos:end].rstrip() + "\n"))
    return out


def slim_index(path: str) -> str:
    """화면 인덱스에서 분석에 필요한 컬럼만 남긴다.

    `색tl`·`주석/날짜`·`케이스 수`·`상태`·`시트 행` 은 오케스트레이터의 진행 관리용이고
    화면 분석에는 쓰이지 않는다. 상호 참조 판독에 필요한 것은
    **화면 ID · 페이지 · 소속 간지 · 정책 · CH-ID 접두** 다.
    """
    txt = open(path, encoding="utf-8").read()
    keep_head = ("순번", "화면 ID", "CH-ID", "페이지", "소속 간지", "정책")
    lines, head_idx, out = txt.split("\n"), None, []
    for ln in lines:
        if not ln.strip().startswith("|"):
            # 표 밖의 머리말은 유지 (기획서·식별자 출처·기본 정책·예외 목록 등)
            if ln.strip().startswith(("- ", "#")) or not ln.strip():
                out.append(ln)
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if head_idx is None:
            if any(k in c for c in cells for k in ("화면 ID",)):
                head_idx = [i for i, c in enumerate(cells)
                            if any(k in c for k in keep_head)]
                out.append("| " + " | ".join(cells[i] for i in head_idx) + " |")
            continue
        if set("".join(cells)) <= set("-: "):          # 구분선
            out.append("|" + "|".join("---" for _ in head_idx) + "|")
            continue
        if max(head_idx) < len(cells):
            out.append("| " + " | ".join(cells[i] for i in head_idx) + " |")
    if head_idx is None:
        raise RuntimeError(f"{path}: 화면 인덱스 표 머리행을 찾지 못했다")
    return "\n".join(out).rstrip() + "\n"


def coverage_check(fdir: str) -> int:
    """사양의 모든 절이 어느 역할엔가 배정됐는지 검사한다.

    새 절이 생겼는데 배정되지 않으면 **어느 브리핑에도 들어가지 않아 조용히 사라진다.**
    그 상태를 실패로 만들어, 절을 추가한 사람이 역할을 결정하게 한다.
    """
    files = [os.path.join(fdir, "common.md")] + sorted(
        os.path.join(fdir, f) for f in os.listdir(fdir) if f.startswith("profile-")
    )
    missing, seen = [], set()
    for f in files:
        for title, _ in sections(f):
            seen.add(title)
            if title not in ROLE_SECTIONS:
                missing.append(f"{os.path.basename(f)} :: {title}")
    stale = sorted(set(ROLE_SECTIONS) - seen)

    print(f"절 배정 검사 — 사양 {len(files)}개 · 절 {len(seen)}종")
    if missing:
        print(f"\n❌ 어느 역할에도 배정되지 않은 절 {len(missing)}개:")
        for m in missing:
            print(f"   {m}")
        print("\n   → build_brief.py 의 ROLE_SECTIONS 에 역할을 배정하라."
              "\n     배정하지 않으면 그 절은 어느 브리핑에도 들어가지 않는다.")
    if stale:
        print(f"\n⚠️ 사양에 더는 없는 배정 {len(stale)}개 (오타이거나 삭제된 절):")
        for t in stale:
            print(f"   {t}")
    if not missing and not stale:
        print("\n✅ 전 절 배정 완료 · 유령 배정 0건")
    return 3 if missing else 0


def build(role: str, fdir: str, profile: str, doc_type: str,
          has_change_exc: bool, index_path: str | None,
          phase0_path: str | None) -> str:
    if role not in ROLES:
        raise RuntimeError(f"--role 은 {'/'.join(ROLES)} 중 하나여야 한다: {role}")
    common = os.path.join(fdir, "common.md")
    prof = os.path.join(fdir, f"profile-{profile}.md")
    for p in (common, prof):
        if not os.path.isfile(p):
            raise RuntimeError(f"사양 파일이 없다: {p}")

    include_change = (doc_type == "변경") or has_change_exc
    parts: list[str] = []
    parts.append(f"""# 브리핑 — `{role}` (이 실행 전용, 자동 생성)

**이 파일은 사양의 발췌가 아니라 원문이다.** 역할에 필요한 절만 골라 옮겼을 뿐,
문장을 요약·의역하지 않았다. 그래서 이 파일만 읽고 작업해도 규칙이 빠지지 않는다.

- 원천: `{common}` + `{prof}`
- 이 역할에 배정되지 않은 절은 들어 있지 않다. **필요하다고 판단되면 원천 파일을 직접 열어라**
- 변경분 모드 절 포함 여부: **{'포함' if include_change else '제외'}**
  (원천 유형 `{doc_type}` / 변경 정책 예외 {'있음' if has_change_exc else '없음'})
""")
    if phase0_path:
        parts.append("\n---\n\n" + open(phase0_path, encoding="utf-8").read().rstrip() + "\n")

    for label, path in (("공통 골격", common), (f"제품 프로파일 ({profile})", prof)):
        chosen = []
        for title, body in sections(path):
            if role not in ROLE_SECTIONS.get(title, ()):
                continue
            if title in CHANGE_ONLY and not include_change:
                continue
            chosen.append(body)
        parts.append(f"\n---\n\n# {label} — 발췌 원문 ({len(chosen)}절)\n\n" + "\n".join(chosen))

    # 화면 인덱스는 **analyst 만** 필요하다 — 상호 참조 판독에 다른 화면의 존재·ID가 쓰인다.
    # writer·reviewer 는 담당 화면의 분석서 하나로 작업하므로 인덱스를 넣으면 순수 낭비다.
    if index_path and role == "analyst":
        parts.append("\n---\n\n# 화면 인덱스 (슬림판)\n\n"
                     "> 진행 관리용 컬럼(`색tl`·`주석/날짜`·`케이스 수`·`상태`·`시트 행`)은 제외했다.\n"
                     "> 상호 참조 판독에 필요한 것은 화면 ID·페이지·소속 간지·정책·CH-ID 접두다.\n"
                     "> 그 값들이 필요하면 오케스트레이터에게 묻거나 원본 인덱스를 열어라.\n\n"
                     + slim_index(index_path))
    return "".join(parts)


def main(argv: list[str]) -> int:
    opts: dict = {}
    for a in argv[1:]:
        if not a.startswith("--"):
            print(f"오류: 위치 인자를 받지 않는다: {a}", file=sys.stderr)
            return 3
        k, _, v = a.partition("=")
        opts[k] = v or True

    fdir = opts.get("--formats-dir") or os.path.join(".claude", "formats")
    if not isinstance(fdir, str) or not os.path.isdir(fdir):
        print(f"오류: 사양 디렉터리가 없다: {fdir}", file=sys.stderr)
        return 3

    if opts.get("--coverage-check"):
        return coverage_check(fdir)

    role, profile = opts.get("--role"), opts.get("--profile")
    doc_type = opts.get("--doc-type")
    if not all(isinstance(x, str) for x in (role, profile, doc_type)):
        print(__doc__)
        return 3

    try:
        text = build(
            role, fdir, profile, doc_type,
            bool(opts.get("--has-change-exception")),
            opts.get("--index") if isinstance(opts.get("--index"), str) else None,
            opts.get("--phase0") if isinstance(opts.get("--phase0"), str) else None,
        )
    except Exception as e:
        print(f"오류: {e}", file=sys.stderr)
        return 3

    out = opts.get("--out")
    if out == "-" or not isinstance(out, str):
        sys.stdout.write(text)
    else:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        src = sum(
            os.path.getsize(os.path.join(fdir, n))
            for n in ("common.md", f"profile-{profile}.md")
        )
        print(f"{out} 생성 — {len(text.encode())/1024:.0f}KB "
              f"(사양 원천 {src/1024:.0f}KB 대비 {len(text.encode())/src*100:.0f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
