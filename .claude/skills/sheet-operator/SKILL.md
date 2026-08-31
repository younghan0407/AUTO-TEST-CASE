---
name: sheet-operator
description: Google Sheets 읽기·쓰기·메타데이터 조회·탭 추가 등 모든 구글 시트 조작을 수행. Google Sheets URL을 언급하거나 시트에서 데이터 읽기, 시트에 행 추가, 시트 양식 분석, 새 탭 생성이 필요할 때 반드시 이 스킬을 사용할 것. 서비스 계정 인증 기반.
---

# Sheet Operator

Google Sheets API v4를 서비스 계정 인증으로 호출하여 시트 읽기·쓰기·메타데이터 조회를 수행한다. `sheet-analyst`와 `testcase-writer`, `testcase-reviewer`가 공유하는 스킬.

## 트리거 키워드

- Google Sheets URL 언급
- "시트 양식 분석", "기존 케이스 읽어와", "테스트 케이스 시트에 작성", "탭 추가"
- "시트 메타데이터 확인", "시트에 데이터 append"

## 사전 조건

1. `GOOGLE_APPLICATION_CREDENTIALS` 환경변수가 서비스 계정 JSON 키 경로를 가리킴
2. 대상 시트를 서비스 계정 이메일(`testcase-auto-agent@testcase-auto.iam.gserviceaccount.com`)과 **편집자 권한**으로 공유

권한 누락 시 API는 403을 반환한다. 사용자에게 다음 안내:
> "구글 시트의 '공유' 버튼을 누르고 `testcase-auto-agent@testcase-auto.iam.gserviceaccount.com`을 편집자로 추가해 주세요."

## 작업 흐름

### 읽기 (sheet-analyst, testcase-reviewer가 사용)

1. **먼저 메타데이터 조회** — 어떤 탭이 있는지, 각 탭의 크기는 얼마인지 확인.

   ```bash
   python scripts/sheets_api.py metadata <SHEET_URL>
   ```

   > **⚠️ CLI 하위 명령은 `metadata` 다. `get_metadata` 는 CLI에 없다.**
   > `get_metadata` 는 **Python 메서드 이름**(`SheetsClient.get_metadata()`)이며, 둘 다 실재하지만
   > 쓰는 자리가 다르다. 아래 표대로 쓴다 — 헷갈려 `get_metadata` 를 셸에서 부르면
   > `알 수 없는 명령: get_metadata` 로 실패한다.
   >
   > | 호출 방식 | 이름 | 예 |
   > |---|---|---|
   > | **셸(CLI)** | `metadata` | `python scripts/sheets_api.py metadata <SHEET_URL>` |
   > | **Python** | `get_metadata()` | `SheetsClient().get_metadata(sheet_id)` |
   >
   > CLI 하위 명령 전체는 `metadata` · `read` · `write` · `append` · `add_tab` 5개다
   > (인자 없이 실행하면 사용법이 출력된다).

2. **드리프트 검증 읽기 (기본 — 매 실행)** — 양식 사양(`.claude/formats/`)이 있을 때 쓰는 최소 읽기.
   전수 스캔하지 않고 **2회 호출**로 끝낸다.

   ```bash
   # ① 헤더 1행 — 사양의 컬럼 구조와 대조
   python scripts/sheets_api.py read <SHEET_URL> "'탭이름'!A1:AZ1"

   # ② 마지막 20~50행 — 마지막 TC ID 추출 + 사양 외 enum 등장 여부
   python scripts/sheets_api.py read <SHEET_URL> "'탭이름'!A180:W228"
   ```

   범위의 끝 행 번호는 1번 `metadata` 의 실제 데이터 행 수로 정한다.
   **헤더는 `AZ`까지 넓게 읽는다** — 사양보다 컬럼이 늘어난 경우를 잡기 위한 것이다.
   좁은 범위로 읽으면 뒤에 추가된 컬럼을 놓친다. **VIOLA는 `관리대상` 포함 24컬럼(A~X)이고 TROMBONE은 23컬럼(A~W)** 이므로, 헤더는 넉넉히(`A1:Z1`) 읽어 실제 컬럼 수를 확인한다.

3. **전수 스캔 읽기 (사양 갱신 시에만)** — `"양식 사양 갱신해줘"` 요청 시.
   모든 탭의 전 행을 읽는다. 앞·중간·뒤를 고르게 봐야 enum을 놓치지 않는다.

   ```bash
   python scripts/sheets_api.py read <SHEET_URL> "'탭이름'!A1:Z1444"
   ```

4. **여러 탭을 점검** — 메타데이터로 받은 모든 탭을 한 번씩 샘플링 (전수 스캔 시).

### 쓰기 (testcase-writer가 사용)

1. **append vs write 선택**
   - `append`: 기존 데이터 끝에 행 추가. 대부분의 경우 권장.
   - `write`: 지정 범위 덮어쓰기. 헤더 작성이나 특정 셀 갱신 시.

2. **컬럼 순서 맞추기** — sheet-analyst가 분석한 컬럼 순서대로 값을 배열한다. 컬럼 수가 맞지 않으면 API는 그대로 받지만 시트가 깨진다.

3. **batch 쓰기** — 케이스 하나마다 append를 호출하지 않는다. 모든 케이스를 모아 한 번의 append로 전송한다.

   ```bash
   python scripts/sheets_api.py append <SHEET_URL> 'Sheet1!A:Z' '[["TC-001","로그인","..."]]'

   # 이미 쓰인 범위를 고치는 경우 append가 아니라 write를 쓴다 (중복 행 방지)
   python scripts/sheets_api.py write <SHEET_URL> 'Sheet1!V2:V43' '[["..."],["..."]]'
   ```

4. **새 탭·빈 시트에 쓸 때** — 헤더가 없으면 **양식 사양의 헤더 원문**으로 만들어 준다.
   사양이 있으면 참고 시트 없이도 시작할 수 있다.

   ```bash
   # ① 탭 생성 (기존 탭에 쓰는 경우 생략)
   python scripts/sheets_api.py add_tab <SHEET_URL> "01_챕터명"

   # ② 헤더 1행 — .claude/formats/{사양}.md 의 "헤더 원문"을 그대로 사용
   # 범위는 사양의 컬럼 수에 맞춘다 — VIOLA 24컬럼이면 A1:X1, TROMBONE 23컬럼이면 A1:W1
   python scripts/sheets_api.py write <SHEET_URL> "'01_챕터명'!A1:X1" '[["No","솔루션","관리대상","기능테스트 ID", ...]]'

   # ③ 2행부터 케이스 batch append
   python scripts/sheets_api.py append <SHEET_URL> "'01_챕터명'!A:W" '[[...],[...]]'
   ```

   - 헤더 컬럼명은 **사양 원문 그대로** 쓴다. 임의로 다듬으면 이후 드리프트 검증이 불일치로 잡는다.
   - 빈 기본 탭(`시트1` 등)은 API로 삭제할 수 없다 → 사람이 수동 정리해야 함을 보고한다.

## API 응답 핵심 정보

### 메타데이터

```json
{
  "title": "스프레드시트 제목",
  "sheets": [
    {"title": "탭1", "sheetId": 0, "rows": 1000, "cols": 26},
    ...
  ]
}
```

### append 응답

```json
{
  "spreadsheetId": "...",
  "updates": {
    "updatedRange": "Sheet1!A50:H60",  // 실제로 쓰인 범위
    "updatedRows": 11
  }
}
```

`updatedRange`를 항상 확인하여 사용자/리뷰어에게 보고한다.

## 값 입력 옵션

- **`RAW` (스크립트 기본값 — `read`/`write`/`append` 모두)**: 문자열 그대로 저장. 테스트 케이스 작성에는 항상 이것을 쓴다.
- `USER_ENTERED`: 사람이 입력한 것처럼 처리. 수식·날짜 자동 변환. `write --user-entered`로만 사용.

**왜 RAW가 기본인가** — 테스트 케이스 텍스트에는 다음 문자가 정상적으로 등장하며, `USER_ENTERED`는 이를 훼손한다:

| 텍스트 | USER_ENTERED 결과 |
|--------|------------------|
| `-` (4/5 Depth의 No-data 표기) | 날짜·수식으로 해석될 수 있음 |
| `1. 검색어 입력` (절차 번호 접두) | 목록·숫자 변환 위험 |
| `'클러스터 관리' 권한` (선행 작은따옴표) | 작은따옴표를 이스케이프로 소비해 값이 깨짐 |
| `2026-01-02` (일시 형식 검증 케이스) | 날짜 직렬값으로 변환되어 원문 표기 소실 |

수식을 넣어야 하는 예외 상황에서만 `--user-entered`를 쓴다.

## 시트 구조 주의사항

1. **A1 표기법**: `Sheet1!A1:H50`. 탭 이름에 공백이 있으면 작은따옴표로 감싼다: `'My Sheet'!A1:H50`
2. **⚠️ 한글 탭 이름은 손으로 타이핑하지 마라 — `metadata` 가 돌려준 `title` 을 그대로 쓴다.**

   macOS에서 만든 탭 이름은 한글이 **NFD(분해형)** 로 저장되어 있을 수 있다. 눈으로는 똑같아 보이지만
   조합형(NFC)으로 타이핑한 문자열과 **바이트가 다르고**, Sheets API는 이를 **다른 탭 이름으로 본다.**

   ```
   실측 (2026-08-25) — 화면에는 둘 다 `02-1 토폴로지 모니터링 통합모니터링`
     메타데이터 title : \u1110\u1169\u1111\u1169\u11af\u1105\u1169\u110c\u1175  (NFD 분해형)
     타이핑한 문자열   : \ud1a0\ud3f4\ub85c\uc9c0                                  (NFC 조합형)
     → HTTP 400 "Unable to parse range: '02-1 …'!A1:X60"
   ```

   **탭이 분명히 존재하는데 400 `Unable to parse range` 가 나면 거의 이 문제다.**
   탭이 없다고 결론 내리거나 `add_tab` 으로 새로 만들지 마라 — 중복 이름 탭이 생기거나 실패한다.
   `python scripts/sheets_api.py metadata <SHEET_URL>` 로 `sheetId` 에 해당하는 `title` 문자열을 받아
   **그 값을 그대로** 범위에 넣는다.
   (정 필요하면 `unicodedata.normalize("NFC", title)` 로 비교만 하고, API에는 원본 `title` 을 보낸다.)
3. **컬럼 알파벳**: 26개 초과 시 AA, AB... (현재 한도는 시트당 최대 1,830만 셀)
4. **빈 셀**: 값이 없는 셀은 응답에 포함되지 않으므로 행 길이가 들쭉날쭉할 수 있다. 후처리로 패딩 필요.

## 에러 핸들링

| HTTP | 원인 | 대응 |
|------|------|------|
| 403 | 서비스 계정 권한 없음 | 시트에 서비스 계정 이메일 편집자 추가 안내 |
| 404 | 시트 ID 잘못됨 | URL 재확인 요청 |
| 429 | API 호출 한도 초과 | 60초 대기 후 1회 재시도 |
| 400 | 범위 표기 오류 | 탭 이름·범위 형식 재검토. **탭이 존재하는데 `Unable to parse range` 면 한글 탭 이름 NFD/NFC 불일치를 먼저 의심** — 「시트 구조 주의사항 2」 참조 |

`scripts/sheets_api.py`는 모든 HTTP 오류를 한국어 힌트와 함께 `SheetsError`로 래핑한다.

## 산출물 체크리스트

읽기 작업:
- [ ] 메타데이터 먼저 조회
- [ ] 헤더 + 샘플 데이터 확보
- [ ] 빈 행/누락 셀 처리

쓰기 작업:
- [ ] 컬럼 순서 검증
- [ ] batch로 한 번에 전송
- [ ] `updatedRange` 응답 확인하여 보고

## 하이브리드 인증 (시트 생성 시)

서비스 계정은 자체 Drive storage가 없어 새 스프레드시트 파일을 만들 수 없다(`storageQuotaExceeded`). 새 시트 생성이 필요하면 `scripts/oauth_sheet.py`로 OAuth2 사용자 인증을 사용한다.

전형적 흐름:
1. `python scripts/oauth_sheet.py create "TEST_VIOLA_AUTO" testcase-auto-agent@testcase-auto.iam.gserviceaccount.com`
   → 사용자 권한으로 시트 생성 + 서비스 계정에 편집자 권한 부여
2. 생성된 URL로 이후 모든 작업은 서비스 계정(`sheets_api.py`)이 수행

OAuth 토큰은 `.credentials/oauth_token.json`에 저장되며 자동 갱신된다. 테스트 모드 앱은 7일 만료지만 시트 생성은 일회성 작업이므로 영향 적다.

## 번들된 스크립트

원본은 `.claude/skills/sheet-operator/scripts/`에 있고, 프로젝트 루트 `scripts/`에 심볼릭 링크가 걸려 있다. **이 문서의 모든 명령은 프로젝트 루트에서 `scripts/...` 경로로 실행한다.**

- `scripts/sheets_api.py` — Google Sheets API 클라이언트 (서비스 계정, 읽기·쓰기·메타)
- `scripts/oauth_sheet.py` — OAuth2 기반 새 스프레드시트 생성 + 자동 공유
