# 부하 AI 질문/멈춤 대응 레퍼런스

> SKILL.md Section 10 — cmux 오케스트레이션 중 부하 AI가 DONE 대신 질문하거나 멈출 때의 대응 프로토콜

## 문제 유형 및 원인

| 유형 | 증상 | 원인 |
|------|------|------|
| **환경 문제** | pip install 실패, node_modules 없음, cargo 빌드 실패 | 실행 환경 미비 |
| **요구사항 불명확** | "어떻게 해야 하나요?", "어떤 방식을 선호하시나요?" | 지시사항 부족 |
| **에러 발생** | 컴파일 에러, 런타임 에러, 예외 | 코드 문제 |
| **무한 루프/멈춤** | 진행 바만 표시, 반응 없음 | 로직 오류 또는 대기 상태 |

## 대응 패턴

### 1단계: 화면 분석

```bash
# 질문/에러 내용 확인
cmux read-screen --surface surface:N --lines 20
```

### 2단계: 답변 전송

```bash
# 환경 문제 — 해결 방법 직접 전송
cmux send --surface surface:N "pip 불필요. 기존 패키지만 사용해. 완료 후 DONE 2회 출력."
cmux send-key --surface surface:N enter

# 요구사항 불명확 — 구체적 지시 추가
cmux send --surface surface:N "가장 합리적인 방식으로 직접 판단해서 구현해. 질문하지 말고 판단해."
cmux send-key --surface surface:N enter

# 에러 발생 — 수정 지시 전송
cmux send --surface surface:N "에러 원인: {분석}. 수정 방법: {지시}. 완료 후 DONE 2회 출력."
cmux send-key --surface surface:N enter
```

### 3단계: 해결 안 될 때

```bash
# 5분 후에도 해결 안 되면 → 컨텍스트 초기화 + 재배정
cmux send-key --surface surface:N escape
sleep 2
cmux send --surface surface:N "/clear"
cmux send-key --surface surface:N enter
sleep 3
# 기존 작업 내용은 이미 파일에 저장되어 있으므로 유실 없음
cmux send --surface surface:N "TASK: {재배정 프롬프트}"
```

## 예방적 지시 (Footer Template에 포함 필수)

```
[지침]
- 환경 설치(pip/npm/cargo install) 실패 시 → 설치 없이 기존 패키지로 구현
- 불확실한 부분 있으면 → 질문하지 말고 가장 합리적인 방식으로 직접 판단하여 구현
- 에러 발생 시 → 다른 방법으로 시도. 3회 실패 시에만 에러 보고 후 DONE 출력
```

## 2분 폴링 패턴

```bash
# 2분 간격으로 상태 확인
sleep 120 && cmux read-screen --surface surface:N --lines 1
```

- DONE 발견 → 즉시 재배정
- WORKING → 대기
- 질문/에러 → 대응 패턴 적용

## 문제 유형별 구체적 지시 예시

### 환경 문제

```bash
# pip install 실패 시
"pip install 불필요. Python 표준 라이브러리만 사용해서 구현해."

# node_modules 없음 시
"node_modules 불필요. 순수 JavaScript 또는 이미 설치된 전역 패키지만 사용해."

# cargo 빌드 실패 시
"cargo 빌드 불필요. 기존 crate 의존성만으로 구현하거나, 별도 의존성 없이 구현해."
```

### 요구사항 불명확

```bash
# 가장 합리적인 기본값 사용 지시
"모호한 부분은:
1) 가장 간단한 구현 선택
2) 설정 가능하면 기본값 사용
3) 질문 대신 직접 판단
완료 후 DONE 2회 출력."
```

### 에러 발생

```bash
# 컴파일 에러 시
"컴파일 에러 발생. 에러 메시지 읽고 수정해. 3회 재시도 후에도 실패하면:
1) 에러 메시지 요약
2) 시도한 해결 방법
3) DONE 출력"

# 런타임 에러 시
"런타임 에러 발생. 스택 트레이스 읽고 수정해.無法 해결 시:
1) 에러 원인 분석
2) 가장 가능성 높은 수정 시도
3) 그래도 안 되면 에러 요약 + DONE"
```
