---
name: feedback-tc-completeness
description: 테스트 케이스 작성 시 누락·요약 금지 — 꼼꼼한 전수 분석 요구
metadata:
  type: feedback
---

모든 화면·팝업·모달·처리 결과·에러 상태에 대해 TC를 빠짐없이 작성해야 한다.

**Why:** 이전 실행(2026-06-14, _workspace_일반_v1/)에서 사용자 일괄등록 처리 결과 팝업 화면 TC 누락 등 보조 화면 누락이 다수 발견됨. 또한 여러 케이스가 나올 수 있는 항목을 1개 TC로 요약하는 문제도 있었음.

**How to apply:**
- prd-analyst: 팝업·모달·처리 결과·에러 화면 등 모든 보조 화면을 메인 화면과 동등하게 별도 식별
- testcase-writer: Description 항목별·케이스 유형별 1:1 분해 — 요약 금지
- 예시 누락 1건은 대표 예시일 뿐, 그 외에도 더 많은 누락이 있을 수 있으므로 항상 전수 분석
