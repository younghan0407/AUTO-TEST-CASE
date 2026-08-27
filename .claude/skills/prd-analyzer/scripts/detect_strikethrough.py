"""기획서의 취소선(strikethrough) 표기 후보를 검출한다 — 삭제 변경분 탐지용.

개정판 기획서에서 **삭제**는 취소선으로 표기되는 경우가 많다.
그런데 취소선은 `detect_red_regions.py` 로도, PDF 텍스트 레이어로도 잡히지 않는다:

  - 색 검출 실패 — 취소선은 선 몇 픽셀이라 "색 영역"으로 라벨링되지 않는다
  - 텍스트 레이어 실패 — 서식(취소선 여부) 정보가 없다. 폰트가 Type3면 색조차 없다

즉 **삭제 유형 변경분은 다른 검출 경로에 전혀 나타나지 않는다.**
`testcase-generator` 0-H 는 삭제 변경분에 "더는 노출되지 않음" 검증을 필수로 요구하는데,
검출 수단이 없으면 그 케이스가 조용히 누락된다. 이 스크립트가 그 공백을 메운다.

## 검출 원리

취소선의 기하학적 정의를 직접 찾는다 — **글자를 가로지르는 얇은 수평선**:

  1. 수평으로 연속된 잉크 런(run)을 찾는다
  2. 두께가 `--max-thick` 이하다 (기본 8px). 두꺼우면 밑줄 강조·구분선·표 테두리다
  3. **런의 위·아래 밴드에 글자 잉크가 양쪽 모두 있다** — 이것이 취소선과 밑줄을 가르는 조건이다.
     밑줄은 아래에 글자가 없고, 구분선은 위아래 어느 쪽도 글자에 붙어 있지 않다
  4. 길이가 `--min-len` 이상이다 (기본 70px)

## ⚠️ `--min-len` 은 글자 폭으로 정해야 한다

한글 가로획(`ㅗ` `ㅍ` `ㅌ` `ㅡ`)은 그 자체가 짧은 수평선이므로, 임계값이 글자 폭보다 작으면
글자획이 통째로 후보가 된다. **DPI·폰트 크기에 따라 글자 폭이 달라지므로 문서마다 실측하라.**

  실측 예 (VIOLA V4.0 기획서, 150 DPI 렌더): DESC 본문 한글 1자 폭 = **40~42px**
  → 55px 이상이면 글자 경계를 넘은 선. 기본값 70px 은 "글자 2자 이상을 가로지름"에 해당

## ⚠️ 양성 대조를 먼저 하라

취소선이 **실재하는 페이지**에 먼저 돌려 검출되는지 확인한 뒤, 나머지 페이지에 적용한다.
그 페이지가 없으면 이 스크립트의 "0건"은 "취소선이 없다"가 아니라 "임계값이 안 맞는다"일 수 있다.
0건을 근거로 삭제 변경분이 없다고 결론 내리려면 **반드시 대조군이 필요하다.**

## ⚠️ 출력은 후보다 — 육안 판독으로 확정한다

밑줄, 표 내부 괘선, 스티커 구분선, 취소선처럼 보이는 아이콘·화살표가 섞인다.
**최종 근거는 렌더 이미지 육안 판독이다.** 이 스크립트는 어디를 볼지 좁혀주는 수단이다.

의존성: pillow, numpy

CLI 사용:
  python detect_strikethrough.py <이미지|디렉터리> [--min-len=70] [--max-thick=8]
                                 [--band=22] [--density=0.06] [--color-only]
                                 [--json=<path>]

  --min-len     : 이 길이(px) 미만의 런은 버린다 (기본 70). **문서의 글자 폭으로 실측해 정할 것**
  --max-thick   : 이 두께(px)를 넘으면 취소선이 아니라 밑줄·구분선으로 본다 (기본 8)
  --band        : 위·아래로 글자 잉크를 확인할 밴드 높이 (기본 22)
  --density     : 밴드 내 잉크 밀도 최소값 (기본 0.06). 양쪽 모두 넘어야 후보가 된다
  --color-only  : **유채색 런만** 남긴다. 변경 표기를 반드시 색으로 하는 기획서에서
                  무채색 글자획·괘선을 걸러내 오탐을 크게 줄인다
  --json        : 결과를 JSON으로 저장

Python 사용:
  from detect_strikethrough import detect
  runs, (w, h) = detect("page_010.png", min_len=70)
"""

from __future__ import annotations

import json
import os
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:
    print("필수 라이브러리가 없습니다. 설치:\n  pip install pillow numpy", file=sys.stderr)
    raise

Image.MAX_IMAGE_PIXELS = None

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

DEFAULT_MIN_LEN = 70
DEFAULT_MAX_THICK = 8
DEFAULT_BAND = 22
DEFAULT_DENSITY = 0.06
INK_LUM_MAX = 200      # 이 밝기 미만을 잉크로 본다
RUN_SOLID_RATIO = 0.9  # 두께 측정 시 같은 폭에서 잉크가 이어지는 비율
CHROMA_MIN = 40        # --color-only 에서 유채색으로 인정할 최소 채도 (max-min 채널차)


def _is_chromatic(color: list) -> bool:
    return (max(color) - min(color)) >= CHROMA_MIN


def detect(
    path: str,
    min_len: int = DEFAULT_MIN_LEN,
    max_thick: int = DEFAULT_MAX_THICK,
    band: int = DEFAULT_BAND,
    density: float = DEFAULT_DENSITY,
    color_only: bool = False,
) -> tuple:
    """이미지 한 장에서 취소선 후보를 찾는다. (후보 목록, (width, height)) 반환."""
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im).astype(np.int16)
    height, width, _ = arr.shape

    ink = arr.mean(axis=2) < INK_LUM_MAX
    results = []
    gap = 3

    for y in range(2, height - 3):
        row = ink[y]
        if row.sum() < min_len:
            continue

        diff = np.diff(row.astype(np.int8))
        starts = list(np.where(diff == 1)[0] + 1)
        ends = list(np.where(diff == -1)[0] + 1)
        if row[0]:
            starts = [0] + starts
        if row[-1]:
            ends = ends + [width]

        for s, e in zip(starts, ends):
            length = e - s
            if length < min_len:
                continue

            # 위로 몇 줄이 같은 폭에서 이어지는지 (이 런이 밴드의 최상단인지 판정)
            thick_up = 0
            yy = y - 1
            while yy >= 0 and ink[yy, s:e].mean() > RUN_SOLID_RATIO and thick_up < max_thick + 2:
                thick_up += 1
                yy -= 1
            # 같은 밴드를 여러 번 보고하지 않도록 최상단 행에서만 처리한다
            if thick_up > 0:
                continue

            thick_dn = 0
            yy = y + 1
            while yy < height and ink[yy, s:e].mean() > RUN_SOLID_RATIO and thick_dn < max_thick + 2:
                thick_dn += 1
                yy += 1

            thickness = thick_dn + 1
            if thickness > max_thick:
                continue  # 밑줄 강조·구분선·표 테두리

            top, bot = y, y + thick_dn

            # 핵심 조건 — 위·아래 모두에 글자 잉크가 있는가 (밑줄·구분선 배제)
            up0, up1 = max(0, top - gap - band), max(0, top - gap)
            dn0, dn1 = min(height, bot + gap), min(height, bot + gap + band)
            above = ink[up0:up1, s:e].mean() if up1 > up0 else 0.0
            below = ink[dn0:dn1, s:e].mean() if dn1 > dn0 else 0.0
            if not (above > density and below > density):
                continue

            px = arr[top:bot + 1, s:e].reshape(-1, 3)
            dark = px[px.mean(axis=1) < INK_LUM_MAX]
            color = dark.mean(axis=0).round().astype(int).tolist() if len(dark) else [0, 0, 0]

            if color_only and not _is_chromatic(color):
                continue

            results.append({
                "y": int(top), "y2": int(bot), "x": int(s), "x2": int(e),
                "len": int(length), "thick": int(thickness),
                "above": round(float(above), 3), "below": round(float(below), 3),
                "color": color, "chromatic": _is_chromatic(color),
            })

    return results, (width, height)


def _list_targets(path: str) -> list:
    if os.path.isdir(path):
        names = sorted(n for n in os.listdir(path)
                       if os.path.splitext(n)[1].lower() in IMAGE_EXTS)
        if not names:
            raise ValueError(f"디렉터리에 이미지 파일이 없습니다: {path}")
        return [os.path.join(path, n) for n in names]
    if os.path.splitext(path)[1].lower() not in IMAGE_EXTS:
        raise ValueError(f"이미지 파일이 아닙니다: {path}")
    return [path]


def _group_consecutive(runs: list, tol: int = 90) -> list:
    """세로로 규칙적으로 이어지는 런을 묶는다 — 하위 트리 전체 취소선의 신호다."""
    groups = []
    for r in sorted(runs, key=lambda x: x["y"]):
        if groups and (r["y"] - groups[-1][-1]["y"]) <= tol:
            groups[-1].append(r)
        else:
            groups.append([r])
    return groups


def main(argv: list) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    opts = {a.split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else True)
            for a in argv[1:] if a.startswith("--")}

    if not args:
        print(__doc__)
        return 1

    try:
        targets = _list_targets(args[0])
    except (FileNotFoundError, ValueError) as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1

    min_len = int(opts.get("--min-len", DEFAULT_MIN_LEN))
    color_only = "--color-only" in opts
    out = {"input": args[0], "min_len": min_len, "color_only": color_only, "pages": []}
    total = 0

    for path in targets:
        runs, (w, h) = detect(
            path,
            min_len=min_len,
            max_thick=int(opts.get("--max-thick", DEFAULT_MAX_THICK)),
            band=int(opts.get("--band", DEFAULT_BAND)),
            density=float(opts.get("--density", DEFAULT_DENSITY)),
            color_only=color_only,
        )
        total += len(runs)
        label = os.path.splitext(os.path.basename(path))[0]
        out["pages"].append({"page": label, "width": w, "height": h,
                             "candidate_count": len(runs), "candidates": runs})

        if not runs:
            print(f"\n{label} ({w}x{h}): 취소선 후보 없음")
            continue

        print(f"\n{label} ({w}x{h}): {len(runs)}개 후보")
        for group in _group_consecutive(runs):
            if len(group) >= 3:
                ys = [g["y"] for g in group]
                print(f"  ⬐ 연속 {len(group)}줄 (y {ys[0]}~{ys[-1]}) — "
                      f"하위 트리 전체 취소선일 가능성 높음")
            for r in group:
                mark = "유채색" if r["chromatic"] else "무채색"
                print(f"    y={r['y']:<6} x={r['x']}~{r['x2']:<6} len={r['len']:<5} "
                      f"thick={r['thick']} {mark} rgb={tuple(r['color'])} "
                      f"위{r['above']:.2f}/아래{r['below']:.2f}")

    print(f"\n총 {len(out['pages'])}장 / 후보 {total}개 (min-len={min_len}"
          f"{', 유채색만' if color_only else ''})")

    if isinstance(opts.get("--json"), str):
        with open(opts["--json"], "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"JSON 저장: {opts['--json']}")

    print(
        "\n⚠️  후보에는 밑줄·표 괘선·스티커 구분선·아이콘이 섞인다. **육안 판독으로 확정할 것.**\n"
        "⚠️  `--min-len` 은 이 문서의 글자 폭을 실측해 정하라 — 한글 가로획(`ㅗ` `ㅍ` `ㅌ`)이\n"
        "    글자 폭만큼의 수평선이므로, 임계값이 낮으면 글자획이 통째로 후보가 된다.\n"
        "⚠️  **0건을 '삭제 변경분 없음'의 근거로 쓰려면 양성 대조를 먼저 하라** — 취소선이\n"
        "    실재하는 페이지에서 검출되는지 확인해야 임계값이 맞다는 것이 증명된다."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
