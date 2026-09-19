# 새 프로젝트에 하네스 재구성하기

> 대상: **이 하네스를 다른 저장소에서 다시 쓰려는 사람**
> 팀원이 이 저장소를 clone 해서 쓰는 경우는 [SETUP.md](SETUP.md) 를 보세요. 이 문서가 아닙니다.

방법은 하나입니다 — **구성 파일을 복사한다.**

---

## 1. 복사할 것

`.claude/` 만으로는 동작하지 않습니다. 루트의 `scripts/` 는 `.claude/skills/*/scripts/` 를 가리키는
**심볼릭 링크**이고, 스킬 문서가 `scripts/sheets_api.py` 같은 루트 기준 경로를 안내하기 때문입니다.

```bash
SRC=/path/to/testcase-auto          # 원본 저장소
DST=/path/to/new-project            # 새 프로젝트

mkdir -p "$DST" && cd "$DST"

# 하네스 본체 — 스킬·에이전트·양식 사양
cp -r "$SRC/.claude" .

# 루트 실행 경로 (심볼릭 링크 유지: -a 로 복사한다)
cp -a "$SRC/scripts" .

# 세팅 검증·의존성·트리거 규칙
cp "$SRC/verify_setup.py" "$SRC/requirements.txt" "$SRC/CLAUDE.md" .

# 사용자 문서 (선택이지만 권장 — 게이트에서 무엇을 봐야 하는지가 여기 있다)
cp "$SRC/SETUP.md" "$SRC/README.md" "$SRC/HARNESS_PIPELINE.md" .
mkdir -p docs && cp "$SRC/docs/PROMPTS.md" docs/
```

복사되는 것의 내역:

| 경로 | 내용 | 없으면 |
|------|------|--------|
| `.claude/skills/` | 오케스트레이터 2 + 실무 스킬 4 (`testcase-auto` · `testcase-augment` · `prd-analyzer` · `sheet-operator` · `testcase-generator` · `testcase-reviewer`) | 트리거가 동작하지 않음 |
| `.claude/agents/` | `prd-analyst` · `sheet-analyst` · `testcase-writer` · `testcase-reviewer` · `tc-augmenter` | 실행 주체가 없음 |
| `.claude/formats/` | `common.md` + 제품 프로파일 3종 | **양식 원천이 사라져 케이스를 쓸 수 없음** |
| `scripts/` | 루트 실행용 심볼릭 링크 10 + `verify_unit_migration.sh` | 스킬이 안내하는 경로가 깨짐 |
| `CLAUDE.md` | 트리거 규칙 + 변경 이력 | 하네스가 호출되지 않음 |
| `verify_setup.py` · `requirements.txt` | 세팅 검증·의존성 | 설정 오류를 첫 실행에서야 발견 |

**`_workspace/` · `.credentials/` · `PDF/` · `img/` 는 복사하지 않습니다.** 산출물과 자격증명이고,
새 프로젝트에서는 새로 만들어집니다.

---

## 2. 환경값 교체

`.claude/settings.json` 의 `env` 3개는 **원본 프로젝트 기준 절대경로**라 반드시 바꿔야 합니다.

```json
{
  "env": {
    "FIGMA_ACCESS_TOKEN": "<새 프로젝트용 Figma 토큰 — Figma를 안 쓰면 빈 문자열>",
    "GOOGLE_APPLICATION_CREDENTIALS": "<새 프로젝트 절대경로>/.credentials/google-service-account.json",
    "GOOGLE_SERVICE_ACCOUNT_EMAIL": "<서비스계정>@<프로젝트>.iam.gserviceaccount.com"
  }
}
```

`settings.json` 은 커밋 대상이 아닙니다. `.claude/settings.json.example` 을 복사해 채우세요.

GCP 준비물이 아직 없다면:

| 항목 | 방법 |
|------|------|
| 서비스 계정 + JSON 키 | GCP Console → IAM → 서비스 계정 → 키 발급 → `.credentials/google-service-account.json` |
| API 활성화 | Google **Sheets** API + Google **Drive** API |
| 대상 시트 공유 | 시트에 서비스 계정 이메일을 **편집자**로 추가 (미공유 `403` 이 가장 흔한 실패) |
| Figma 토큰 | Figma → Settings → Personal access tokens (Figma 기획서를 쓸 때만) |
| OAuth 클라이언트 | 새 스프레드시트를 **생성**할 때만 필요 → `.credentials/oauth_client.json` + `python3 scripts/oauth_sheet.py auth` |

---

## 3. 검증

```bash
python3 -m pip install -r requirements.txt
python3 verify_setup.py "<대상 시트 URL>"     # 실패 0 이어야 한다
bash scripts/verify_unit_migration.sh          # PASS 여야 한다
```

앞의 것은 **환경**(키·권한·패키지·경로)을, 뒤의 것은 **하네스 문서의 정합성**(폐기된 처리 단위
잔존, 품질 장치 누락)을 봅니다. 복사 과정에서 파일이 빠지면 두 번째가 잡습니다.

---

## 4. 제품 양식 확인

`.claude/formats/` 에는 `VIOLA` · `TROMBONE` · `BootFactory` 프로파일이 들어 있습니다.
**새 프로젝트의 제품이 이 셋이 아니면 프로파일이 없습니다.** 팀이 이미 쓰는 시트가 있다면
프로파일을 실측으로 만드는 것이 정공법입니다.

```
참고 시트로 양식 사양 갱신해줘: <시트 URL>
```

실측 없이 기존 프로파일을 유용하면 `솔루션` 값과 TC ID 코드가 **전 행에 박히는 상수**라
나중에 바꾸려면 열 전체를 고쳐야 합니다 (`profile-bootfactory` 가 그 상태이며, 파일 최상단에
경고가 붙어 있습니다).

---

## 왜 "프롬프트로 전체 구성" 방법이 사라졌는가

이 문서에는 스킬·에이전트·스크립트 정의를 코드블록으로 담아 Claude Code에게 통째로 생성시키는
**방법 B** 가 있었습니다(2026-08-25 기준 1,535줄). 걷어낸 이유는 **그 복제본이 드리프트했기**
때문입니다 — 폐기된 챕터 단위를 37곳에서 서술하고, 지금은 없는 `관리대상` 컬럼과 옛 `CLAUDE.md`
를 담고 있었습니다. 즉 **그대로 실행하면 낡은 하네스가 만들어지는** 상태였습니다.

정의의 단일 출처는 `.claude/` 입니다. 복제본을 두면 원본이 바뀔 때마다 두 곳을 고쳐야 하고,
한쪽을 잊으면 조용히 갈라집니다. 복사가 느려서 프롬프트 방식을 썼던 것이 아니므로 —
`cp -r` 가 더 빠릅니다 — 복제본을 유지할 이유가 없습니다.
