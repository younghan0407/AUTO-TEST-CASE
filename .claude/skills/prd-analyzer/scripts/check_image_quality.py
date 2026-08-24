"""기획서 이미지의 판독 품질을 사전 진단한다.

기획서가 PDF/Figma 없이 이미지로만 전달되는 경우, 이미지 자체가 판독에 부적합할 수
있다(해상도 부족, 흐림, 파일 훼손, 잘림, 빈 페이지). 이 스크립트는 분석 착수 전에
그 사실을 **정량 지표로** 잡아내어, 분석 결과와 테스트 케이스에 기록할 근거를 만든다.

판정 등급
  OK   — 그대로 분석 진행
  주의 — 분석은 가능하나 일부 텍스트 오독 가능. 결과에 판독 이슈 기록 필요
  불가 — 판독 신뢰 불가. 사용자에게 재전달 요청 + 케이스에 판독 불가 기록 필수

지표
  short_side   짧은 변 픽셀. 기획서 슬라이드는 150 DPI 환산 시 1200px 이상이 안전
  sharpness    라플라시안 분산(선명도). 낮으면 흐림·확대 열화·JPEG 손상
  contrast     그레이스케일 표준편차. 매우 낮으면 백지·단색(내용 없음)
  truncated    파일이 중간에서 끊겼는지 (훼손 신호)

의존성: pillow, numpy

CLI 사용:
  python check_image_quality.py <image_or_dir> [--json=<path>] [--min-short-side=1200]
                                [--min-sharpness=60] [--quiet]

출력:
  - stdout: 이미지별 지표 + 판정 표, 그리고 `주의`/`불가` 목록 요약
  - --json 지정 시 동일 결과를 JSON으로 저장 (분석 보고서에 인용)

Python 사용:
  from check_image_quality import check
  report = check("_workspace/prd_images/ch01")
"""

from __future__ import annotations

import json
import os
import sys

try:
    import numpy as np
    from PIL import Image, ImageFile
except ImportError:
    print("필수 라이브러리가 없습니다. 설치:\n  pip install pillow numpy", file=sys.stderr)
    raise

# 훼손 감지를 위해 잘린 이미지를 자동 보정하지 않는다
ImageFile.LOAD_TRUNCATED_IMAGES = False
Image.MAX_IMAGE_PIXELS = None

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

# 판정 임계값 (기획서 슬라이드 실측 기준)
MIN_SHORT_SIDE = 1200      # 이 미만이면 주의, 절반 미만이면 불가
MIN_SHARPNESS = 60.0       # 이 미만이면 주의, 1/4 미만이면 불가
MIN_CONTRAST = 6.0         # 이 미만이면 사실상 백지·단색


def _list_targets(path: str) -> list[str]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"경로가 없습니다: {path}")
    if os.path.isfile(path):
        return [path]
    names = sorted(
        n for n in os.listdir(path)
        if os.path.splitext(n)[1].lower() in IMAGE_EXTS
    )
    if not names:
        raise ValueError(f"디렉터리에 이미지 파일이 없습니다: {path}")
    return [os.path.join(path, n) for n in names]


def _sharpness(gray: "np.ndarray") -> float:
    """라플라시안 분산. 큰 이미지는 다운샘플해서 비용을 억제한다."""
    step = max(1, min(gray.shape) // 1000)
    g = gray[::step, ::step].astype(np.float32)
    lap = (
        -4.0 * g[1:-1, 1:-1]
        + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    )
    return float(lap.var())


def _grade(entry: dict, min_short_side: int, min_sharpness: float) -> tuple[str, list[str]]:
    reasons: list[str] = []
    grade = "OK"

    def worse(level: str) -> None:
        nonlocal grade
        order = {"OK": 0, "주의": 1, "불가": 2}
        if order[level] > order[grade]:
            grade = level

    if entry.get("error"):
        return "불가", [entry["error"]]

    if entry["truncated"]:
        worse("불가")
        reasons.append("파일이 중간에서 끊김(훼손)")

    ss = entry["short_side"]
    if ss < min_short_side // 2:
        worse("불가")
        reasons.append(f"해상도 심각 부족(짧은 변 {ss}px < {min_short_side // 2}px)")
    elif ss < min_short_side:
        worse("주의")
        reasons.append(f"해상도 부족(짧은 변 {ss}px < {min_short_side}px)")

    sh = entry["sharpness"]
    if sh < min_sharpness / 4:
        worse("불가")
        reasons.append(f"심한 흐림·열화(선명도 {sh:.1f})")
    elif sh < min_sharpness:
        worse("주의")
        reasons.append(f"흐림 의심(선명도 {sh:.1f})")

    if entry["contrast"] < MIN_CONTRAST:
        worse("불가")
        reasons.append(f"내용 없음·단색 의심(대비 {entry['contrast']:.1f})")

    return grade, reasons


def _inspect(path: str) -> dict:
    entry: dict = {
        "path": path,
        "name": os.path.basename(path),
        "bytes": os.path.getsize(path) if os.path.exists(path) else 0,
        "truncated": False,
        "error": None,
    }
    try:
        img = Image.open(path)
        entry["format"] = img.format
        entry["mode"] = img.mode
        try:
            img.load()
        except OSError as e:
            # 잘린 파일: 보정 허용 후 다시 읽어 지표는 계산한다
            entry["truncated"] = True
            entry["load_note"] = str(e)
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            try:
                img = Image.open(path)
                img.load()
            finally:
                ImageFile.LOAD_TRUNCATED_IMAGES = False
        gray = np.asarray(img.convert("L"))
        entry["width"], entry["height"] = img.width, img.height
        entry["short_side"] = min(img.width, img.height)
        entry["sharpness"] = round(_sharpness(gray), 2)
        entry["contrast"] = round(float(gray.std()), 2)
    except Exception as e:  # 손상·미지원 포맷
        entry["error"] = f"이미지를 열 수 없음(손상 가능): {e}"
        entry.setdefault("width", 0)
        entry.setdefault("height", 0)
        entry["short_side"] = 0
        entry["sharpness"] = 0.0
        entry["contrast"] = 0.0
    return entry


def check(
    path: str,
    min_short_side: int = MIN_SHORT_SIDE,
    min_sharpness: float = MIN_SHARPNESS,
) -> dict:
    """이미지(또는 디렉터리)의 판독 품질을 진단한다.

    반환: {'input', 'thresholds', 'images': [...], 'summary': {...}}
    """
    targets = _list_targets(path)
    images = []
    for t in targets:
        entry = _inspect(t)
        entry["grade"], entry["reasons"] = _grade(entry, min_short_side, min_sharpness)
        images.append(entry)

    summary = {
        "total": len(images),
        "ok": sum(1 for e in images if e["grade"] == "OK"),
        "주의": sum(1 for e in images if e["grade"] == "주의"),
        "불가": sum(1 for e in images if e["grade"] == "불가"),
    }
    return {
        "input": path,
        "thresholds": {
            "min_short_side": min_short_side,
            "min_sharpness": min_sharpness,
            "min_contrast": MIN_CONTRAST,
        },
        "images": images,
        "summary": summary,
    }


def _print_report(report: dict) -> None:
    s = report["summary"]
    print(
        f"이미지 품질 진단 — 총 {s['total']}장 / OK {s['ok']} · 주의 {s['주의']} · 불가 {s['불가']}"
    )
    print(f"{'파일':<28} {'크기':>13} {'선명도':>9} {'대비':>7}  판정")
    for e in report["images"]:
        size = f"{e['width']}x{e['height']}"
        print(
            f"{e['name'][:28]:<28} {size:>13} {e['sharpness']:>9.1f} "
            f"{e['contrast']:>7.1f}  {e['grade']}"
        )
    flagged = [e for e in report["images"] if e["grade"] != "OK"]
    if flagged:
        print("\n판독 이슈 목록 (분석 결과·테스트 케이스에 반드시 기록):")
        for e in flagged:
            print(f"  [{e['grade']}] {e['name']} — {'; '.join(e['reasons'])}")
        print(
            "\n→ `주의`는 해당 페이지 케이스의 피드백 컬럼에 판독 이슈를 기재하고 진행한다.\n"
            "→ `불가`는 사용자에게 원본 재전달을 요청하고, 그때까지 해당 페이지를\n"
            "   추측으로 케이스화하지 않는다 (판독 불가 사실을 케이스로 남긴다)."
        )
    else:
        print("\n판독 이슈 없음 — 그대로 분석 진행 가능.")


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    opts = {a.split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else True)
            for a in argv[1:] if a.startswith("--")}
    if not args:
        print(__doc__)
        return 1

    try:
        report = check(
            args[0],
            min_short_side=int(opts.get("--min-short-side", MIN_SHORT_SIDE)),
            min_sharpness=float(opts.get("--min-sharpness", MIN_SHARPNESS)),
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1

    if "--quiet" not in opts:
        _print_report(report)

    out = opts.get("--json")
    if isinstance(out, str):
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nJSON 저장: {out}")

    # 판독 불가가 있으면 비정상 종료 코드로 알린다 (파이프라인에서 게이트로 사용)
    return 2 if report["summary"]["불가"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
