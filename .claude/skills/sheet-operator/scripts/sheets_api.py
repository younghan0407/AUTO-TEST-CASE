"""Google Sheets API 헬퍼 (서비스 계정 인증).

서비스 계정 키 탐색 순서: 생성자 인자 → 환경변수 GOOGLE_APPLICATION_CREDENTIALS
→ `<프로젝트 루트>/.credentials/google-service-account.json` (환경변수 없이도 동작).

대상 시트는 사전에 서비스 계정 이메일로 편집자 공유되어야 한다.

CLI 사용:
  python sheets_api.py read <url_or_id> <range>           # 예: A1:H50 또는 'Sheet1!A1:H50'
  python sheets_api.py metadata <url_or_id>               # 모든 탭 메타정보
  python sheets_api.py append <url_or_id> <range> <json>  # json: [["a","b"],["c","d"]]
  python sheets_api.py write <url_or_id> <range> <json>   # 덮어쓰기
  python sheets_api.py add_tab <url_or_id> <tab_title>    # 새 탭 추가

Python 사용:
  from sheets_api import SheetsClient
  c = SheetsClient()
  rows = c.read('SHEET_ID', 'A1:H50')
"""

from __future__ import annotations

import json
import os
import re
import sys

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print(
        "필수 라이브러리가 없습니다. 설치:\n"
        "  pip install google-auth google-auth-httplib2 google-api-python-client",
        file=sys.stderr,
    )
    raise


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


DEFAULT_KEY_NAME = "google-service-account.json"


def _find_project_root() -> str | None:
    """`.credentials/` 디렉토리를 가진 상위 디렉토리를 프로젝트 루트로 판단.

    이 스크립트는 `.claude/skills/sheet-operator/scripts/` 원본과 프로젝트 루트
    `scripts/` 심볼릭 링크 양쪽에서 실행될 수 있다. realpath로 링크를 따라간 뒤
    위로 올라가며 `.credentials/`를 찾고, 없으면 현재 작업 디렉토리로 재탐색한다.
    """
    for start in (os.path.dirname(os.path.realpath(__file__)), os.getcwd()):
        d = start
        while True:
            if os.path.isdir(os.path.join(d, ".credentials")):
                return d
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    return None


def _default_key_path() -> str | None:
    """환경변수가 없을 때 쓰는 기본 키 위치: <프로젝트 루트>/.credentials/<키>."""
    root = _find_project_root()
    if not root:
        return None
    candidate = os.path.join(root, ".credentials", DEFAULT_KEY_NAME)
    return candidate if os.path.exists(candidate) else None


class SheetsError(Exception):
    pass


class SheetsClient:
    def __init__(self, key_path: str | None = None):
        # 우선순위: 인자 → 환경변수 → <프로젝트 루트>/.credentials/google-service-account.json
        # 마지막 폴백이 있어 팀원마다 다른 절대경로를 환경변수에 넣지 않아도 동작한다.
        key_path = key_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not key_path or not os.path.exists(key_path):
            key_path = _default_key_path()
        if not key_path or not os.path.exists(key_path):
            raise SheetsError(
                "서비스 계정 키를 찾지 못했습니다. 다음 중 하나를 만족시키세요:\n"
                "  1) 프로젝트 루트에 `.credentials/%s` 배치 (권장)\n"
                "  2) 환경변수 GOOGLE_APPLICATION_CREDENTIALS에 키 경로 지정\n"
                "자세한 절차는 SETUP.md 참조." % DEFAULT_KEY_NAME
            )
        self.creds = service_account.Credentials.from_service_account_file(
            key_path, scopes=SCOPES
        )
        self.service = build("sheets", "v4", credentials=self.creds, cache_discovery=False)
        self.drive = build("drive", "v3", credentials=self.creds, cache_discovery=False)

    @staticmethod
    def extract_id(url_or_id: str) -> str:
        m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", url_or_id)
        if m:
            return m.group(1)
        if re.fullmatch(r"[A-Za-z0-9_-]+", url_or_id):
            return url_or_id
        raise SheetsError(f"Google Sheets URL 또는 ID 형식이 아닙니다: {url_or_id}")

    def get_metadata(self, sheet_id: str) -> dict:
        """모든 탭(sheet)의 이름·gid·크기 정보."""
        try:
            data = self.service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        except HttpError as e:
            raise SheetsError(self._format_http_error(e)) from e
        sheets = []
        for s in data.get("sheets", []):
            prop = s["properties"]
            sheets.append(
                {
                    "title": prop.get("title"),
                    "sheetId": prop.get("sheetId"),
                    "rows": prop.get("gridProperties", {}).get("rowCount"),
                    "cols": prop.get("gridProperties", {}).get("columnCount"),
                }
            )
        return {
            "title": data.get("properties", {}).get("title"),
            "sheets": sheets,
        }

    def read(self, sheet_id: str, range_a1: str) -> list[list]:
        """지정 범위의 값을 2차원 리스트로 반환."""
        try:
            res = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sheet_id, range=range_a1)
                .execute()
            )
        except HttpError as e:
            raise SheetsError(self._format_http_error(e)) from e
        return res.get("values", [])

    def write(self, sheet_id: str, range_a1: str, values: list[list],
              raw: bool = True) -> dict:
        """지정 범위에 덮어쓰기.

        기본 RAW 모드: `append`와 동일한 이유다. USER_ENTERED 모드는
        선행 작은따옴표(')를 이스케이프로 소비해 셀 값을 깨뜨리고,
        `-`·`1.`·`=`로 시작하는 텍스트를 날짜·수식으로 변환한다.
        테스트 케이스 텍스트에는 이 문자들이 정상적으로 등장하므로
        RAW가 안전한 기본값이다.

        수식·자동 날짜 변환이 필요하면 `raw=False`(CLI `--user-entered`).
        """
        try:
            res = (
                self.service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=sheet_id,
                    range=range_a1,
                    valueInputOption="RAW" if raw else "USER_ENTERED",
                    body={"values": values},
                )
                .execute()
            )
        except HttpError as e:
            raise SheetsError(self._format_http_error(e)) from e
        return res

    def append(self, sheet_id: str, range_a1: str, values: list[list]) -> dict:
        """지정 범위 끝에 행 추가.

        RAW 모드 사용: USER_ENTERED 모드는 선행 작은따옴표(')를 이스케이프로 소비해
        셀 값이 깨지는 버그가 있어 RAW로 교체. 수식이 필요하면 직접 batchUpdate 사용.
        """
        try:
            res = (
                self.service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=sheet_id,
                    range=range_a1,
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": values},
                )
                .execute()
            )
        except HttpError as e:
            raise SheetsError(self._format_http_error(e)) from e
        return res

    def create_spreadsheet(self, title: str) -> dict:
        """새 스프레드시트 파일을 생성. 서비스 계정 소유로 만들어진다.

        사용자가 접근하려면 별도로 share()를 호출해야 한다.
        반환: {'spreadsheetId': '...', 'spreadsheetUrl': '...', 'properties': {...}, 'sheets': [...]}
        """
        body = {"properties": {"title": title}}
        try:
            res = self.service.spreadsheets().create(body=body).execute()
        except HttpError as e:
            raise SheetsError(self._format_http_error(e)) from e
        return res

    def share(
        self,
        file_id: str,
        email: str,
        role: str = "writer",
        notify: bool = False,
    ) -> dict:
        """파일을 사용자 이메일에 공유. role: reader/commenter/writer/owner.

        notify=False면 이메일 알림을 보내지 않는다 (자동화에 적합).
        """
        body = {"type": "user", "role": role, "emailAddress": email}
        try:
            res = (
                self.drive.permissions()
                .create(
                    fileId=file_id,
                    body=body,
                    sendNotificationEmail=notify,
                    fields="id,role,emailAddress",
                )
                .execute()
            )
        except HttpError as e:
            raise SheetsError(self._format_http_error(e)) from e
        return res

    def add_tab(self, sheet_id: str, title: str) -> dict:
        """새 탭(sheet)을 추가."""
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        try:
            res = (
                self.service.spreadsheets()
                .batchUpdate(spreadsheetId=sheet_id, body=body)
                .execute()
            )
        except HttpError as e:
            raise SheetsError(self._format_http_error(e)) from e
        return res

    def batch_update(self, sheet_id: str, requests: list[dict]) -> dict:
        """포맷팅, 머지 등 복잡한 작업용 batchUpdate 직접 호출."""
        try:
            return (
                self.service.spreadsheets()
                .batchUpdate(spreadsheetId=sheet_id, body={"requests": requests})
                .execute()
            )
        except HttpError as e:
            raise SheetsError(self._format_http_error(e)) from e

    @staticmethod
    def _format_http_error(e: HttpError) -> str:
        status = e.resp.status if hasattr(e, "resp") else "?"
        try:
            content = json.loads(e.content.decode("utf-8"))
            msg = content.get("error", {}).get("message", str(e))
        except Exception:
            msg = str(e)
        hints = {
            403: " (서비스 계정에 시트 편집자 권한이 부여됐는지 확인)",
            404: " (시트 ID/URL이 올바른지 확인)",
            429: " (API 호출 한도 초과 — 잠시 후 재시도)",
        }
        return f"Sheets API HTTP {status}: {msg}{hints.get(status, '')}"


def main(argv: list[str]) -> int:
    # --user-entered: write를 USER_ENTERED 모드로 (기본은 RAW)
    user_entered = "--user-entered" in argv
    argv = [a for a in argv if a != "--user-entered"]
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    c = SheetsClient()
    if cmd == "metadata":
        sid = c.extract_id(argv[2])
        print(json.dumps(c.get_metadata(sid), ensure_ascii=False, indent=2))
        return 0
    if cmd == "read":
        sid = c.extract_id(argv[2])
        rng = argv[3]
        rows = c.read(sid, rng)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if cmd == "write":
        sid = c.extract_id(argv[2])
        rng = argv[3]
        values = json.loads(argv[4])
        print(json.dumps(c.write(sid, rng, values, raw=not user_entered),
                         ensure_ascii=False, indent=2))
        return 0
    if cmd == "append":
        sid = c.extract_id(argv[2])
        rng = argv[3]
        values = json.loads(argv[4])
        print(json.dumps(c.append(sid, rng, values), ensure_ascii=False, indent=2))
        return 0
    if cmd == "add_tab":
        sid = c.extract_id(argv[2])
        title = argv[3]
        print(json.dumps(c.add_tab(sid, title), ensure_ascii=False, indent=2))
        return 0
    print(f"알 수 없는 명령: {cmd}")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
