"""OAuth2 기반 스프레드시트 생성 헬퍼.

서비스 계정은 자체 Drive 저장 공간이 없어 새 파일을 만들 수 없다.
이 스크립트는 사용자 OAuth2 인증으로 시트를 생성한 뒤,
반복 작업(읽기/쓰기/리뷰)을 담당할 서비스 계정에 자동으로 공유한다.

전제 조건:
- .credentials/oauth_client.json (Google Cloud에서 다운로드)
- 최초 1회 인증 후 .credentials/oauth_token.json 자동 생성

CLI 사용:
  python oauth_sheet.py auth                    # 최초 인증 (브라우저 로그인)
  python oauth_sheet.py create <title> [<share_with_email>]
"""

from __future__ import annotations

import json
import os
import sys

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print(
        "필수 라이브러리가 없습니다. 설치:\n"
        "  pip install google-auth-oauthlib google-api-python-client",
        file=sys.stderr,
    )
    raise

def _find_project_root() -> str:
    """.credentials/ 디렉토리를 가진 상위 디렉토리를 프로젝트 루트로 판단.

    이 스크립트는 .claude/skills/sheet-operator/scripts/ 원본과
    프로젝트 루트 scripts/ 심볼릭 링크 양쪽에서 실행될 수 있다.
    realpath로 링크를 따라간 뒤 위로 올라가며 .credentials/를 찾고,
    없으면 현재 작업 디렉토리 기준으로 재탐색한다.
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
    # 찾지 못하면 현재 작업 디렉토리 사용 (에러 메시지에 경로가 표시됨)
    return os.getcwd()


PROJECT_ROOT = _find_project_root()

CLIENT_SECRET_PATH = os.path.join(PROJECT_ROOT, ".credentials", "oauth_client.json")
TOKEN_PATH = os.path.join(PROJECT_ROOT, ".credentials", "oauth_token.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def _load_or_authenticate() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
        return creds
    if not os.path.exists(CLIENT_SECRET_PATH):
        raise FileNotFoundError(
            f"OAuth 클라이언트 시크릿 파일이 없습니다: {CLIENT_SECRET_PATH}\n"
            "Google Cloud Console에서 OAuth 클라이언트 ID(데스크톱 앱)를 만들고 "
            "JSON을 다운받아 위 경로에 저장하세요."
        )
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    return creds


def _save_token(creds: Credentials) -> None:
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())


def authenticate() -> str:
    """최초 인증(브라우저 로그인)을 수행하고 토큰을 저장. 사용자 이메일 반환."""
    creds = _load_or_authenticate()
    # 토큰에 사용자 정보가 직접 들어있지 않으므로 oauth2 API 호출
    service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
    info = service.userinfo().get().execute()
    return info.get("email", "(unknown)")


def create_spreadsheet(title: str, share_with: str | None = None) -> dict:
    """OAuth2 사용자 권한으로 새 스프레드시트 생성. share_with 지정 시 편집자로 공유.

    반환: {'spreadsheetId', 'spreadsheetUrl', 'owner_email', 'shared_with': [...]}
    """
    creds = _load_or_authenticate()
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    try:
        res = sheets.spreadsheets().create(body={"properties": {"title": title}}).execute()
    except HttpError as e:
        raise RuntimeError(f"스프레드시트 생성 실패: {e}") from e

    sid = res["spreadsheetId"]
    url = res["spreadsheetUrl"]
    shared = []

    if share_with:
        try:
            drive.permissions().create(
                fileId=sid,
                body={"type": "user", "role": "writer", "emailAddress": share_with},
                sendNotificationEmail=False,
                fields="id,role,emailAddress",
            ).execute()
            shared.append({"email": share_with, "role": "writer"})
        except HttpError as e:
            print(f"공유 실패({share_with}): {e}", file=sys.stderr)

    return {
        "spreadsheetId": sid,
        "spreadsheetUrl": url,
        "shared_with": shared,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "auth":
        email = authenticate()
        print(f"인증 완료: {email}")
        print(f"토큰 저장: {TOKEN_PATH}")
        return 0
    if cmd == "create":
        if len(argv) < 3:
            print("사용: oauth_sheet.py create <title> [<share_with_email>]")
            return 1
        title = argv[2]
        share_with = argv[3] if len(argv) > 3 else None
        result = create_spreadsheet(title, share_with=share_with)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"알 수 없는 명령: {cmd}")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
