# JARVIS Capability Targets

> 정본. JARVIS의 Phase별 품질 목표와 acceptance criteria를 정의한다.

## 출처

`referense/2.jpeg`의 문구를 JARVIS 품질 목표로 변환. 외부 성능 주장의 사실 근거가 아닌 제품 원칙으로만 사용.

## 5대 품질 목표

### 1. Security

이미지 원칙: 사이버 보안 능력.

cmux 대응:
- secret/path/permission gate 적용
- GATE J-1으로 settings.json 접근 물리 차단
- Worker는 제안만 가능, 적용 권한 없음
- `.env`, credentials, API key 패턴 자동 감지

acceptance criteria:
- 승인 없이 settings.json에 쓰기가 물리적으로 불가능한가
- Worker가 제안 외 변경을 시도하면 gate가 차단하는가

### 2. Software Engineering

이미지 원칙: 고도화된 소프트웨어 엔지니어링.

cmux 대응:
- tests/typecheck/build 기반 evidence (Iron Law #2, #3)
- evidence.json 자동 생성 (jarvis-verify.sh)
- TDD: 실패 테스트 → 구현 → 통과 확인
- 변경 후 `bash -n`, `py_compile`, `pytest` 검증

acceptance criteria:
- evidence.json 없이 KEEP이 불가능한가
- 검증 없이 완료 주장이 차단되는가

### 3. Alignment

이미지 원칙: 높은 정렬 수준.

cmux 대응:
- user approval/scope lock (Iron Law #1)
- 구조화 선택지만 인정 (free-text 승인 금지)
- Scope Lock template으로 bounded/out_of_scope/followup 구분
- 사용자 피드백 즉시 반영 의무

acceptance criteria:
- 승인 없이 진화가 진행되지 않는가
- scope 밖 변경이 차단되는가

### 4. Calibration

이미지 원칙: 높은 교정/보정 능력.

cmux 대응:
- confidence 필드 필수 (모든 advice/evolution/report)
- "검증 불가" 명시 + 구체적 차단 사유
- insufficient evidence 시 조언 보류
- 실제 outcome이 예상과 어긋나면 다음 advice confidence 하향
- predicted-vs-actual 비교

acceptance criteria:
- 표본 부족 시 "insufficient evidence"가 출력되는가
- 예상과 실제가 어긋난 후 confidence가 조정되는가

### 5. Visual Reasoning

이미지 원칙: 시각적 추론 능력.

cmux 대응:
- Watcher/Eagle/OCR/screenshot 기반 surface 상태 판정
- 4계층 판정 엔진 (L1 패턴 + L2 OCR + L2.5 Vision Diff + L3 pipe-pane)
- DONE 판정 시 30초 재검증 필수
- 코드 진실성은 tests/review/build로 검증 (시각 신호만으로 판단 금지)

acceptance criteria:
- surface 상태 판정이 최소 2계층 이상 교차 확인되는가
- DONE 재검증 없이 확정되지 않는가

## Phase별 매핑

| 품질 목표 | Phase 1 | Phase 2 | Phase 3 |
|-----------|---------|---------|---------|
| Security | 필수 (GATE 강제) | 유지 | 유지 |
| Software Engineering | 필수 (evidence.json) | 유지 | 유지 |
| Alignment | 필수 (2단계 승인) | 유지 | 유지 |
| Calibration | 기본 (confidence 필드) | 목표 (signal engine) | 고도화 |
| Visual Reasoning | 기본 (Watcher 4계층) | 유지 | 선택 (palace memory 연동) |

Phase 1에서 Security, Engineering, Alignment은 필수. Calibration과 Visual Reasoning은 기본 수준으로 시작하고 Phase 2~3에서 고도화한다.

## SRP

Capability Targets는 **품질 목표와 acceptance criteria 정의만** 담당한다.

담당하지 않는 것:
- 목표 달성을 위한 실행 → Evolution Lane, Mentor Lane
- GATE 구현 → gate.sh, hook
- 검증 실행 → jarvis-verify.sh
- 메트릭 수집 → jarvis_telemetry.py

## 참조

- JARVIS Constitution: [jarvis-constitution.md](jarvis-constitution.md)
- Phase Roadmap: [phase-roadmap.md](phase-roadmap.md)
- 이미지 원천: `referense/2.jpeg`
