"""Figma REST API 헬퍼.

환경변수 FIGMA_ACCESS_TOKEN 필요.

CLI 사용:
  python figma_api.py file <file_key_or_url>
  python figma_api.py nodes <file_key_or_url> <node_id1,node_id2>
  python figma_api.py images <file_key_or_url> <node_id1,node_id2> [--format=png|svg|jpg|pdf] [--scale=1]

Python 사용:
  from figma_api import FigmaClient
  c = FigmaClient()
  data = c.get_file('FILE_KEY')
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.figma.com/v1"


class FigmaError(Exception):
    pass


class FigmaClient:
    def __init__(self, token: str | None = None):
        token = token or os.environ.get("FIGMA_ACCESS_TOKEN")
        if not token:
            raise FigmaError(
                "FIGMA_ACCESS_TOKEN 환경변수가 설정되지 않았습니다. "
                ".claude/settings.json의 env에 토큰을 추가하세요."
            )
        self.token = token

    @staticmethod
    def extract_file_key(url_or_key: str) -> str:
        """Figma URL에서 file key를 추출. 이미 key이면 그대로 반환."""
        # URL 패턴: https://www.figma.com/file/{KEY}/... 또는 /design/{KEY}/...
        m = re.search(r"figma\.com/(?:file|design|proto)/([A-Za-z0-9]+)", url_or_key)
        if m:
            return m.group(1)
        # 순수 key (영문/숫자만)
        if re.fullmatch(r"[A-Za-z0-9]+", url_or_key):
            return url_or_key
        raise FigmaError(f"Figma URL이나 file key 형식이 아닙니다: {url_or_key}")

    @staticmethod
    def extract_node_ids_from_url(url: str) -> list[str]:
        """Figma URL의 ?node-id= 쿼리에서 노드 ID 추출."""
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        node_ids = qs.get("node-id", [])
        # Figma URL은 보통 1-2 형식인데 API는 1:2 형식 요구
        return [nid.replace("-", ":") for nid in node_ids]

    def _request(self, path: str, params: dict | None = None) -> dict:
        url = f"{API_BASE}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"X-Figma-Token": self.token})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise FigmaError(f"Figma API HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise FigmaError(f"Figma API 네트워크 오류: {e}") from e

    def get_me(self) -> dict:
        return self._request("/me")

    def get_file(self, file_key: str, depth: int | None = None) -> dict:
        """전체 파일 노드 트리를 반환.

        depth: 트리 깊이 제한. 큰 파일은 1~3으로 제한하면 응답이 빨라진다.
        """
        params = {}
        if depth is not None:
            params["depth"] = depth
        return self._request(f"/files/{file_key}", params=params or None)

    def get_file_nodes(self, file_key: str, node_ids: list[str]) -> dict:
        """특정 노드만 가져온다 (대용량 파일에 효율적)."""
        params = {"ids": ",".join(node_ids)}
        return self._request(f"/files/{file_key}/nodes", params=params)

    def get_images(
        self,
        file_key: str,
        node_ids: list[str],
        format: str = "png",
        scale: float = 1.0,
    ) -> dict:
        """노드를 이미지로 export. {node_id: image_url} 매핑 반환."""
        params = {
            "ids": ",".join(node_ids),
            "format": format,
            "scale": scale,
        }
        return self._request(f"/images/{file_key}", params=params)

    def get_comments(self, file_key: str) -> dict:
        return self._request(f"/files/{file_key}/comments")


def summarize_node(node: dict, max_depth: int = 3, _depth: int = 0) -> dict:
    """디자인 노드 트리를 요약. 깊이 제한 + 핵심 정보만 추출."""
    out = {
        "id": node.get("id"),
        "name": node.get("name"),
        "type": node.get("type"),
    }
    # 텍스트 노드는 실제 텍스트 포함
    if node.get("type") == "TEXT" and "characters" in node:
        out["text"] = node["characters"]
    # 컴포넌트 정보
    if node.get("componentId"):
        out["componentId"] = node["componentId"]
    # 자식 노드
    children = node.get("children", [])
    if children and _depth < max_depth:
        out["children"] = [summarize_node(c, max_depth, _depth + 1) for c in children]
    elif children:
        out["children_count"] = len(children)
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    client = FigmaClient()
    if cmd == "me":
        print(json.dumps(client.get_me(), ensure_ascii=False, indent=2))
        return 0
    if cmd == "file":
        key = client.extract_file_key(argv[2])
        depth = int(argv[3]) if len(argv) > 3 else None
        data = client.get_file(key, depth=depth)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if cmd == "nodes":
        key = client.extract_file_key(argv[2])
        ids = argv[3].split(",")
        data = client.get_file_nodes(key, ids)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if cmd == "images":
        key = client.extract_file_key(argv[2])
        ids = argv[3].split(",")
        fmt = "png"
        scale = 1.0
        for arg in argv[4:]:
            if arg.startswith("--format="):
                fmt = arg.split("=", 1)[1]
            elif arg.startswith("--scale="):
                scale = float(arg.split("=", 1)[1])
        data = client.get_images(key, ids, format=fmt, scale=scale)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print(f"알 수 없는 명령: {cmd}")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
