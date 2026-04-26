# student_service.py — 학생 도메인 로직

## 역할

로그인한 학생이 수행하는 모든 기능의 **비즈니스 규칙**을 담는다. 화면 출력은 하지 않고, 호출자(`main.py`)가 결과를 받아 출력한다.

- 기획서 6.5~6.12 학생 메뉴 전체 대응
- 기획서 5.3 "의미 규칙" 중 학생 행동 관련 항목 구현

## 설계 의도

### 1. 순수 도메인 서비스
- 모든 메서드는 `(bool, str)` 또는 `(bool, str, bool)` 튜플 반환.
- `print()`/`input()` 금지. 호출자가 메시지를 받아 출력을 책임진다.
- 이 규칙 덕분에 서비스 단위 테스트가 쉽고(`tests/test_student_service.py` 참고), UI가 CLI에서 웹으로 바뀌어도 그대로 재사용 가능.

### 2. 공유 상태를 파라미터로 주입
`__init__`이 받는 `courses`, `enrollments`, `completed`, `config`는 **`main.py`가 로드한 동일 객체의 참조**다. 서비스가 이 객체를 변경하면 `main.py`의 변수도 같이 바뀌며, 이후 `_save_all`에서 그대로 파일에 반영된다.

이렇게 하면:
- 서비스가 `return`으로 변경사항을 전달할 필요가 없다.
- 여러 서비스(학생/관리자)가 같은 상태를 공유한다.
- 트레이드오프: 의도치 않은 변경을 방지하려면 호출자 규율이 필요 (`main.py`에서만 `_save_all` 호출).

### 3. 재수강 판정을 동적 계산으로
- `Enrollment`에 `is_retake` 필드를 두지 않는다 (기획서 4.5 준수).
- `is_retake(code)` 메서드가 매 호출 시 `completed_courses` 조회.
- 기이수 과목을 나중에 추가/삭제해도 재수강 판정이 **즉시 반영**된다.

## 수강신청 7단계 검사 (기획서 6.9)

`register(code, section)`은 기획서 6.9의 "통과 조건 (순차 검사하여 최초 발견된 오류 출력)" 순서를 **엄격히** 따른다:

```
0단계. 수강신청 기간 확인  (기획서 5.3)
1단계. 과목 존재 여부      → "존재하지 않는 과목코드입니다."
2단계. 분반 존재 여부      → "존재하지 않는 분반입니다."
3단계. active 상태 확인    → "현재 신청 불가능한(inactive) 과목입니다."
4단계. 중복 신청 확인      → "이미 신청한 과목입니다."
   (같은 과목코드의 다른 분반 포함 — 기획서 5.3 준수)
5단계. 정원 초과 확인      → "해당 과목의 정원이 마감되었습니다."
6단계. 시간표 충돌 확인    → "시간표 충돌 - [과목명] (요일 HH:MM~HH:MM)과 겹칩니다."
7단계. 최대 학점 확인      → "최대 신청 학점(18)을 초과합니다."
```

### 왜 이 순서인가
기획서는 사용자 친화적 메시지를 보장하기 위해 **가장 근본적인 오류 먼저** 반환한다:
- 과목이 없으면 분반·상태 등을 볼 필요가 없다.
- 중복 신청이면 정원·시간표와 무관하게 거절.
- 학점 초과는 마지막 — 다른 모든 조건이 통과된 뒤에만 의미가 있다.

### "같은 과목코드 다른 분반" 중복 방지
```python
active_map = self._active_enrolled_map()
if key in active_map:
    return False, "!!! 오류: 이미 신청한 과목입니다.", False
for (c, _s) in active_map.keys():
    if c == course_code:
        return False, "!!! 오류: 이미 신청한 과목입니다.", False
```
기획서 5.3: "같은 과목코드에 이미 enrolled 상태인 레코드가 있는 학생은 동일 과목의 다른 분반까지 포함하여 중복 신청할 수 없다."

## 시간표 충돌 판정

```python
if target.start_time < enrolled.end_time and enrolled.start_time < target.end_time:
```
- 기획서 용어 정의: 시간 구간은 `[시작, 종료)` **반열림 구간**.
- 앞 과목 `end == 뒤 과목 start`는 **충돌 아님** (예: 09:00~10:30 + 10:30~12:00).
- 위 비교는 strictly less-than 2개로 반열림 조건을 정확히 표현.

## 수강취소 로직

```python
self.enrollments.append(Enrollment(..., status="cancelled"))
```
- 기존 `enrolled` 레코드를 수정하지 않고 **새 `cancelled` 레코드를 append**.
- `_active_enrolled_map`이 같은 `(학번, 과목, 분반)` 키에 대해 **마지막 상태**를 취하므로, cancelled 후 다시 신청하면 다시 enrolled로 전환.
- 기획서 5.3 "cancelled 상태인 동일 과목을 다시 신청하는 경우 신규 수강신청과 동일하게 모든 조건을 재검사" 요구를 자연스럽게 충족.

## 주요 메서드

| 메서드 | 역할 | 기획서 |
|---|---|---|
| `list_courses()` | `active` 과목만 정렬 반환 | 6.7.1 |
| `search_courses(kw)` | 과목명 부분문자열(대소문자 무시) | 6.7.2 |
| `list_completed()` | 기이수 과목코드 정렬 반환 | 6.8.1 |
| `add_completed(code)` | 기이수 등록 (중복 거부) | 6.8.2 |
| `is_retake(code)` | 재수강 여부 동적 계산 | 5.3 |
| `register(code, section)` | 7단계 검사 후 수강신청 | 6.9 |
| `cancel(code, section)` | 수강취소 (append `cancelled`) | 6.10 |
| `enrollment_history()` | 학생 전체 신청 내역 (enrolled+cancelled) | 6.11 |
| `timetable()` | 현재 enrolled 과목을 요일/시작시각 정렬 | 6.12 |
| `current_credits()` | enrolled 학점 합 | 공통 |
| `is_registration_open()` | 수강신청 기간 판정 | 5.3 |

## 비의도적으로 하지 않은 것

- **출력 포맷팅 없음**: 시간표를 `[MON]` 헤더로 그리는 작업은 `main.py` 담당. 서비스는 `Course` 리스트만 반환.
- **수강신청 로그 기록 없음**: 감사 로그 요구사항이 기획서에 없음.
- **학생 본인 외 신청 조작 불가**: `__init__`에 받은 `self.student` 외의 학번은 어떤 메서드도 건드리지 않는다.
