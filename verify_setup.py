#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""하네스 세팅 점검 (스모크 테스트).

새 팀원이 clone 직후 실행해서 "내 PC에서 하네스가 돌아갈 준비가 됐는가"를
한 번에 확인한다. 실패 항목마다 무엇을 어떻게 고치는지 함께 출력한다.

이 스크립트 자체는 표준 라이브러리만 쓴다 (pip install 전에도 실행 가능).

사용:
  python3 verify_setup.py                      # 로컬 환경만 점검
  python3 verify_setup.py <구글_시트_URL>       # 시트 접근 권한까지 실제 확인
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
OK, WARN, FAIL = "OK", "주의", "실패"
results = []


def record(status, name, detail="", fix=""):
    results.append({"status": status, "name": name, "detail": detail, "fix": fix})
    mark = {OK: "  \033[32m[OK]\033[0m", WARN: "\033[33m[주의]\033[0m", FAIL: "\033[31m[실패]\033[0m"}[status]
    print("%s %s%s" % (mark, name, (" — " + detail) if detail else ""))


def check_python():
    v = sys.version_info
    label = "Python %d.%d.%d" % (v.major, v.minor, v.micro)
    if v < (3, 9):
        record(FAIL, "Python 버전", label, "Python 3.9 이상을 설치하세요.")
    else:
        record(OK, "Python 버전", label)


def check_packages():
    # (import 이름, pip 이름, 용도, 필수 여부)
    pkgs = [
        ("fitz", "pymupdf", "PDF → PNG 변환", True),
        ("PIL", "pillow", "이미지 판독·크롭", True),
        ("numpy", "numpy", "빨강 검출·선명도 지표", True),
        ("google.auth", "google-auth", "서비스 계정 인증", True),
        ("googleapiclient", "google-api-python-client", "Sheets API 호출", True),
        ("google_auth_oauthlib", "google-auth-oauthlib", "새 시트 생성(OAuth2)", False),
        ("openpyxl", "openpyxl", "메뉴 IA 엑셀 읽기", True),
    ]
    missing = []
    for mod, pip_name, purpose, required in pkgs:
        try:
            __import__(mod)
            record(OK, "패키지 %s" % pip_name, purpose)
        except ImportError:
            missing.append(pip_name)
            record(FAIL if required else WARN, "패키지 %s" % pip_name,
                   "미설치 (%s)" % purpose,
                   "python3 -m pip install -r requirements.txt")
    return missing


def check_symlinks():
    expected = [
        "figma_api.py", "pdf_to_images.py", "detect_red_regions.py",
        "detect_strikethrough.py", "check_image_quality.py", "prd_cache.py",
        "build_brief.py", "read_tc_inventory.py", "verify_sheet_rows.py",
        "sheets_api.py", "oauth_sheet.py", "parse_menu_ia.py", "render_digest.py",
    ]
    broken = []
    for name in expected:
        path = os.path.join(ROOT, "scripts", name)
        if not os.path.exists(path):          # 깨진 링크는 exists()가 False
            broken.append(name)
    if broken:
        record(FAIL, "scripts/ 링크", "연결 안 됨: %s" % ", ".join(broken),
               "clone이 온전한지 확인하세요. git은 심볼릭 링크를 보존합니다 "
               "(zip으로 받았다면 링크가 깨졌을 수 있습니다).")
    else:
        record(OK, "scripts/ 링크", "%d개 정상" % len(expected))


def check_harness_files():
    skills = os.path.join(ROOT, ".claude", "skills")
    agents = os.path.join(ROOT, ".claude", "agents")
    need_skills = ["prd-analyzer", "sheet-operator", "testcase-auto",
                   "testcase-augment", "testcase-generator", "testcase-reviewer"]
    need_agents = ["prd-analyst.md", "sheet-analyst.md",
                   "testcase-writer.md", "testcase-reviewer.md",
                   "tc-augmenter.md"]
    miss = [s for s in need_skills if not os.path.isfile(os.path.join(skills, s, "SKILL.md"))]
    miss += [a for a in need_agents if not os.path.isfile(os.path.join(agents, a))]
    if miss:
        record(FAIL, "하네스 구성", "누락: %s" % ", ".join(miss),
               "저장소를 다시 clone 하세요.")
    else:
        record(OK, "하네스 구성",
               "스킬 %d개 + 에이전트 %d개" % (len(need_skills), len(need_agents)))


def check_service_account():
    key = os.path.join(ROOT, ".credentials", "google-service-account.json")
    env_key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    path = key if os.path.exists(key) else (env_key if env_key and os.path.exists(env_key) else None)
    if not path:
        record(FAIL, "서비스 계정 키", "찾을 수 없음",
               "키 파일을 `.credentials/google-service-account.json` 으로 저장하세요. "
               "(SETUP.md 3단계)")
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        email = data.get("client_email", "(client_email 없음)")
        if data.get("type") != "service_account":
            record(FAIL, "서비스 계정 키", "서비스 계정 키 형식이 아님 (type=%s)" % data.get("type"),
                   "OAuth 클라이언트 파일과 혼동하지 않았는지 확인하세요.")
            return None
        record(OK, "서비스 계정 키", email)
        return email
    except (ValueError, OSError) as e:
        record(FAIL, "서비스 계정 키", "읽기 실패: %s" % e, "키 파일이 손상되지 않았는지 확인하세요.")
        return None


def check_figma_token():
    token = os.environ.get("FIGMA_ACCESS_TOKEN", "")
    if not token or token.startswith("<"):
        record(WARN, "Figma 토큰", "미설정 — PDF·이미지 기획서만 쓸 경우 문제 없음",
               "Figma 기획서를 쓰려면 `.claude/settings.json` 의 FIGMA_ACCESS_TOKEN 을 채우세요.")
        return
    try:
        import urllib.request
        req = urllib.request.Request("https://api.figma.com/v1/me",
                                     headers={"X-Figma-Token": token})
        with urllib.request.urlopen(req, timeout=10) as r:
            who = json.loads(r.read().decode("utf-8"))
        record(OK, "Figma 토큰", "인증 성공 (%s)" % who.get("email", who.get("handle", "?")))
    except Exception as e:
        record(FAIL, "Figma 토큰", "인증 실패: %s" % e,
               "토큰이 만료·오타가 아닌지 확인하세요 (Figma → Settings → Personal access tokens).")


def check_sheet_access(url):
    print("\n시트 접근 확인 중… (%s)" % url[:60])
    try:
        out = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "sheets_api.py"), "metadata", url],
            capture_output=True, text=True, timeout=60, cwd=ROOT,
        )
    except Exception as e:
        record(FAIL, "시트 접근", "실행 실패: %s" % e)
        return
    if out.returncode == 0:
        try:
            title = json.loads(out.stdout).get("title", "?")
        except ValueError:
            title = "(제목 파싱 실패)"
        record(OK, "시트 접근", "읽기 성공 — %s" % title)
    else:
        err = (out.stderr or out.stdout).strip().splitlines()
        record(FAIL, "시트 접근", err[-1] if err else "원인 불명",
               "시트에 서비스 계정 이메일을 **편집자**로 공유했는지 확인하세요. (SETUP.md 4단계)")


def main():
    print("=" * 68)
    print("testcase-auto 하네스 세팅 점검")
    print("=" * 68)
    check_python()
    missing = check_packages()
    check_symlinks()
    check_harness_files()
    email = check_service_account()
    check_figma_token()

    if len(sys.argv) > 1:
        if missing:
            record(WARN, "시트 접근", "패키지 미설치로 건너뜀",
                   "먼저 requirements.txt 를 설치한 뒤 다시 실행하세요.")
        else:
            check_sheet_access(sys.argv[1])
    else:
        record(WARN, "시트 접근", "미확인 — 시트 URL을 인자로 주면 실제 권한까지 확인합니다",
               "python3 verify_setup.py <구글_시트_URL>")

    fails = [r for r in results if r["status"] == FAIL]
    warns = [r for r in results if r["status"] == WARN]
    print("\n" + "=" * 68)
    print("결과: 정상 %d · 주의 %d · 실패 %d"
          % (len(results) - len(fails) - len(warns), len(warns), len(fails)))
    if fails:
        print("\n조치가 필요한 항목:")
        for r in fails:
            print("  • %s — %s\n    → %s" % (r["name"], r["detail"], r["fix"]))
    if warns:
        print("\n참고 (필수는 아님):")
        for r in warns:
            print("  • %s — %s" % (r["name"], r["detail"]))
    if not fails:
        print("\n필수 항목 모두 통과. 이제 Claude Code에서 기획서와 시트 URL을 주고")
        print("\"테스트 케이스 만들어줘\" 라고 요청하면 됩니다.")
        if email:
            print("\n대상 구글 시트에 아래 이메일을 **편집자**로 공유해야 합니다:")
            print("  %s" % email)
    print("=" * 68)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
