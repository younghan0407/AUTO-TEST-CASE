"""PDF를 페이지별 PNG 이미지로 변환.

의존성: pymupdf (pip install pymupdf)

CLI 사용:
  python pdf_to_images.py <pdf_path> [--dpi=150] [--output-dir=<dir>] [--pages=START-END]
  python pdf_to_images.py <pdf_path> --crop-desc [--dpi=200] [--output-dir=<dir>] [--pages=START-END]

  --crop-desc: Description 패널 영역(x 53%~100%)만 크롭하여 저장.
               스펙 페이지 판독에 사용. 전체 변환과 함께 쓰는 것을 권장.
  --pages=START-END: 변환할 페이지 범위 (1-indexed, 양 끝 포함).
                     예: --pages=1-13 → 1~13페이지만 변환.
                     생략 시 전체 페이지 변환.
  출력: 변환된 파일 경로를 한 줄씩 stdout에 출력
  기본 출력 디렉토리: _workspace/pdf_images/<pdf_basename>/

DPI 권장값:
  - 전체 페이지 (UI 화면 파악): 150 DPI
  - Description 패널 크롭 (스펙 텍스트 판독): 200 DPI

페이지 분할 예시 (멀티 에이전트):
  python pdf_to_images.py doc.pdf --pages=1-13   # 에이전트 A
  python pdf_to_images.py doc.pdf --pages=14-26  # 에이전트 B
  python pdf_to_images.py doc.pdf --pages=27-37  # 에이전트 C

Python 사용:
  from pdf_to_images import convert_pdf, crop_description_panels
  paths = convert_pdf("input.pdf", output_dir="_workspace/pdf_images/doc", dpi=150)
  paths = convert_pdf("input.pdf", output_dir="_workspace/pdf_images/doc", dpi=150, pages=(1, 13))
  desc_paths = crop_description_panels("input.pdf", output_dir="_workspace/pdf_images/doc_desc", dpi=200)
  desc_paths = crop_description_panels("input.pdf", output_dir="_workspace/pdf_images/doc_desc", dpi=200, pages=(14, 26))
"""

from __future__ import annotations

import os
import sys

# Description 패널이 시작하는 x 비율 (페이지 너비 기준)
# 스펙 페이지는 좌측 UI 화면(~53%) + 우측 Description 패널(53%~100%) 구조
_DESC_X_RATIO = 0.53


def convert_pdf(
    pdf_path: str,
    output_dir: str,
    dpi: int = 150,
    pages: tuple[int, int] | None = None,
) -> list[str]:
    """PDF 파일을 페이지별 전체 PNG로 변환하여 경로 목록 반환.

    Args:
        pages: (start, end) 1-indexed, 양 끝 포함. None이면 전체 변환.
               예: (1, 13) → 1~13페이지만 변환.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError(
            "PyMuPDF가 설치되지 않았습니다. 다음 명령 실행 후 재시도하세요:\n"
            "  pip install pymupdf"
        )

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    total = len(doc)
    start_idx = (pages[0] - 1) if pages else 0
    end_idx = min(pages[1], total) if pages else total
    scale = dpi / 72  # 72 DPI가 PDF 기준 해상도
    matrix = fitz.Matrix(scale, scale)

    paths: list[str] = []
    for i in range(start_idx, end_idx):
        pix = doc[i].get_pixmap(matrix=matrix)
        out_path = os.path.join(output_dir, f"page_{i + 1:03d}.png")
        pix.save(out_path)
        paths.append(out_path)

    doc.close()
    return paths


def crop_description_panels(
    pdf_path: str,
    output_dir: str,
    dpi: int = 200,
    pages: tuple[int, int] | None = None,
) -> list[str]:
    """각 페이지의 Description 패널 영역(우측 47%)만 크롭하여 저장.

    스펙 페이지의 Description 텍스트를 정밀 판독할 때 사용한다.
    전체 페이지 변환(convert_pdf)과 함께 사용하여 UI는 전체 이미지로,
    Description은 크롭 이미지로 분석하는 것을 권장한다.

    Args:
        pages: (start, end) 1-indexed, 양 끝 포함. None이면 전체 변환.
               예: (14, 26) → 14~26페이지만 크롭.
    """
    try:
        import fitz
    except ImportError:
        raise RuntimeError(
            "PyMuPDF가 설치되지 않았습니다. pip install pymupdf 실행 후 재시도하세요."
        )

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

    os.makedirs(output_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    total = len(doc)
    start_idx = (pages[0] - 1) if pages else 0
    end_idx = min(pages[1], total) if pages else total
    scale = dpi / 72
    matrix = fitz.Matrix(scale, scale)

    paths: list[str] = []
    for i in range(start_idx, end_idx):
        page = doc[i]
        rect = page.rect
        x_start = rect.width * _DESC_X_RATIO
        clip = fitz.Rect(x_start, 0, rect.width, rect.height)
        pix = page.get_pixmap(matrix=matrix, clip=clip)
        out_path = os.path.join(output_dir, f"page_{i + 1:03d}_desc.png")
        pix.save(out_path)
        paths.append(out_path)

    doc.close()
    return paths


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1

    pdf_path = argv[1]
    dpi = None  # crop-desc 여부에 따라 기본값 결정
    output_dir: str | None = None
    crop_desc = False
    pages: tuple[int, int] | None = None

    for arg in argv[2:]:
        if arg.startswith("--dpi="):
            dpi = int(arg.split("=", 1)[1])
        elif arg.startswith("--output-dir="):
            output_dir = arg.split("=", 1)[1]
        elif arg == "--crop-desc":
            crop_desc = True
        elif arg.startswith("--pages="):
            raw = arg.split("=", 1)[1]
            parts = raw.split("-")
            if len(parts) != 2:
                print(f"오류: --pages 형식은 START-END여야 합니다. 예: --pages=1-13", file=sys.stderr)
                return 1
            pages = (int(parts[0]), int(parts[1]))

    base = os.path.splitext(os.path.basename(pdf_path))[0]

    try:
        if crop_desc:
            if dpi is None:
                dpi = 200
            if output_dir is None:
                output_dir = os.path.join("_workspace", "pdf_images", f"{base}_desc")
            paths = crop_description_panels(pdf_path, output_dir, dpi, pages=pages)
        else:
            if dpi is None:
                dpi = 150
            if output_dir is None:
                output_dir = os.path.join("_workspace", "pdf_images", base)
            paths = convert_pdf(pdf_path, output_dir, dpi, pages=pages)

        for p in paths:
            print(p)
        page_range = f" (p{pages[0]}~{pages[1]})" if pages else ""
        mode = "Description 크롭" if crop_desc else "전체 페이지"
        print(f"\n총 {len(paths)}페이지{page_range} {mode} 변환 완료 → {output_dir}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"오류: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
