# Figma API 경로

> `prd-analyzer` SKILL의 분리된 참조 문서다. **기획서 입력이 Figma URL일 때에만 읽는다.**
> 본문 절 번호는 원래 SKILL의 것을 그대로 유지하므로 다른 문서의 상호 참조
> (예: `prd-analyzer` PDF-3.5)가 그대로 유효하다.

## Figma API 경로

### 1. 파일 키 추출 및 메타정보 확인

Figma URL에서 파일 키를 추출하고 작은 요청으로 접근 가능 여부를 먼저 확인한다. 큰 파일을 전체 가져오기 전에 `depth=1`로 최상위 페이지 구조만 본다.

```bash
python scripts/figma_api.py file <FIGMA_URL> 1
```

### 2. 분석 범위 결정

`depth=1` 응답에서 페이지(`CANVAS`) 목록을 본다. 큰 파일은 모든 페이지를 깊게 가져오면 응답이 수십 MB가 될 수 있다. 다음 전략 중 선택:

- **소규모 파일** (페이지 ≤ 3, 프레임 ≤ 20): `get_file` 전체 가져오기
- **중대형 파일**: 페이지별로 `depth=3~4` 또는 주요 프레임 ID만 `get_file_nodes`로 추출
- **사용자가 특정 노드만 지정한 경우**: 해당 노드 ID로 `get_file_nodes` 호출

URL 쿼리에 `?node-id=...`가 있으면 사용자가 특정 프레임을 가리킨 것이므로 그 노드 중심으로 분석한다.

### 3. 기능 단위 추출

노드 트리를 그대로 옮기지 않는다. 다음 규칙으로 추상화:

1. **프레임 분류**
   - 화면 단위 프레임: `type=FRAME`이면서 카드보드 크기(보통 width 320~1440)
   - 컴포넌트 정의: `type=COMPONENT` / `COMPONENT_SET`
   - 작업 영역(아트보드 외부, 메모 등): 분석 제외

2. **기능 단위 묶기**
   - 같은 사용자 행동을 다루는 화면들을 묶는다 (예: 로그인 화면 + 비밀번호 입력 + 2FA → "로그인" 기능)
   - 화면 이름의 prefix·suffix로 묶기 (예: "로그인-1", "로그인-2", "로그인-에러")

3. **UI 요소 추출 (화면별)**
   - 입력 필드: `INPUT` 컴포넌트, placeholder 텍스트
   - 버튼: `BUTTON` 컴포넌트, 라벨 텍스트
   - 상태 변형: 같은 컴포넌트의 hover/disabled/error 변형
   - 모달/토스트: 별도 프레임으로 존재하는 피드백 UI

4. **플로우 추론**
   - Figma의 prototype 연결 정보(`flowStartingPoints`, `transitionNodeID` 등)가 있으면 사용
   - 없으면 화면 이름 순서로 추정하고 "추론" 표시

### 4. 비주얼 확인이 필요할 때만 이미지 export

텍스트로 충분한 화면은 이미지를 가져오지 않는다. 다음 경우에만 export:
- 복잡한 레이아웃 검증이 필요한 화면
- 사용자가 명시적으로 시각적 확인을 요청한 경우

```bash
python scripts/figma_api.py images <FILE_KEY> <NODE_IDS> --format=png --scale=1
```

응답의 이미지 URL은 일시적(약 30일)이므로 분석 시점에만 사용한다.

### 5. 결과 저장

`_workspace/01_prd_analysis.md`에 저장. 형식은 `prd-analyst` 에이전트 정의 참조.

## Figma API 응답 핵심 필드

| 필드 | 의미 | 활용 |
|------|------|------|
| `document.children[]` | 페이지 목록 | 페이지 분류 |
| `node.type` | 노드 종류 | FRAME(화면), TEXT(라벨), COMPONENT(컴포넌트) |
| `node.name` | 디자이너가 붙인 이름 | 기능 분류 기준 |
| `node.characters` | TEXT 노드의 실제 문자열 | 라벨, 안내 문구 추출 |
| `node.componentId` | INSTANCE가 가리키는 원본 | 재사용 컴포넌트 식별 |
| `node.absoluteBoundingBox` | 화면상 위치/크기 | 모바일/데스크탑 추정 |

