# admin_service.py — 관리자 도메인 로직

## 역할

로그인한 관리자가 수행하는 학생/강의/수강신청 기간 관리 기능의 **비즈니스 규칙**을 담는다. 학생 서비스와 동일한 철학(출력 없음, 튜플 반환)을 따른다.

- 기획서 6.13~6.16 관리자 메뉴 전체 대응
- 기획서 4.1·4.3 데이터 형식을 서버 측에서 재검증

## 설계 의도

### 1. 학생/강의 "삭제"는 soft delete
기획서 6.13.2 / 6.14.3: **삭제 = `inactive` 전환**이다.
```python
def delete_student(self, student_id):
    student.status = "inactive"  # ❌ del self.students[...] 금지
```
이유:
- 수강 내역(`enrollments.txt`)에 학번/과목코드 참조가 남아 있어 물리 삭제 시 참조 무결성 위반.
- 기획서는 "복원 가능해야 함"을 명시 (`activate_student`).
- 데이터 손실 방지.

### 2. 입력값을 서비스 레이어에서도 재검증
`main.py`가 `_input_course()`로 1차 검증을 하더라도, `_validate_course_fields`가 한 번 더 검증한다.
- 기본 원칙: **서비스 경계 안쪽에서는 입력을 신뢰하지 않는다**.
- 기획서 4.3 규칙을 서비스 레이어의 단일 출처로 집중 → 테스트 시 `_input_course` 없이도 규칙 전체 검증 가능.
- 관리자가 잘못된 입력을 우회해 들어와도 데이터 무결성 보호.

### 3. 기간 제약을 코드로 강제
기획서 5.3: "관리자의 강의 수정은 수강신청 기간 시작 전에만 가능하다."
```python
def update_course(self, course):
    if self.config.current_date >= self.config.reg_start:
        return False, "!!! 오류: 수강신청 기간 중에는 강의를 수정할 수 없습니다."
```
- 메뉴 표시 조건(`main.py`)과 서비스 검증을 **둘 다** 둔다. 방어적 이중 검사.

## 활성화 로직의 대칭성

`delete_*` / `activate_*`는 현재 상태를 먼저 검사해 **무의미한 호출을 거절**한다:

| 함수 | 대상 상태 | 결과 |
|---|---|---|
| `delete_student` | `active` | `inactive`로 전환 ✓ |
| `delete_student` | `inactive` | `!!! 안내: 이미 inactive 상태입니다.` |
| `activate_student` | `inactive` | `active`로 전환 ✓ |
| `activate_student` | `active` | `!!! 안내: 이미 active 상태입니다.` |

기획서 6.13.2의 "이미 inactive 상태인 학생을 다시 삭제하려 할 경우 ... 안내 메시지" 요구 대응.

## `_validate_course_fields` 규칙

| 필드 | 검증 | 기획서 |
|---|---|---|
| `code` | 숫자 4자리 | 4.3.1 |
| `section` | 숫자 2자리 | 4.3.2 |
| `name` | 1자 이상, 탭/개행 없음 | 4.3.3 |
| `credits` | 1~6 정수 | 4.3.4 |
| `professor` | 1자 이상, 탭/개행 없음 | 4.3.5 |
| `day` | MON/TUE/WED/THU/FRI | 4.3.6 |
| `start_time` / `end_time` | 분이 00 또는 30, start < end | 4.3.7 / 4.3.8 |
| `capacity` | 1 이상 정수 | 4.3.10 |
| `status` | `active` 또는 `inactive` | 4.3.9 |

### 분 단위 검사 방법
```python
if course.start_time % 30 != 0 or course.end_time % 30 != 0:
```
- `Course.start_time`은 이미 정수(분 단위). 30으로 나누어 떨어지면 00분 또는 30분.
- 입력 단계(`main._parse_hhmm`)에서도 검사하고, 서비스에서 재확인 (이중 방어).

## 주요 메서드

| 메서드 | 역할 | 기획서 |
|---|---|---|
| `register_student(student)` | 학번/비밀번호/이름/단과대·전공 검증 후 등록 | 6.13.1 |
| `delete_student(id)` | 학생 inactive 전환 | 6.13.2 |
| `activate_student(id)` | 학생 active 복원 | 6.13.3 |
| `add_course(course)` | 필드 검증 + 과목코드·분반 중복 확인 | 6.14.1 |
| `update_course(course)` | 기간 제약 + inactive 금지 + 필드 검증 | 6.14.2 |
| `delete_course(code, section)` | 강의 inactive 전환 | 6.14.3 |
| `activate_course(code, section)` | 강의 active 복원 | 6.14.4 |
| `set_registration_period(start, end)` | 종료일 ≥ 시작일 검증 | 6.15 |
| `enrollment_summary()` | 모든 과목별 enrolled 인원 집계 | 6.16 |

## `enrollment_summary()` 구현

```python
latest = {(학번, (과목, 분반)): 최신 상태}
counts = {(과목, 분반): enrolled 인원 수}
```
- `enrollments` 리스트를 순회하며 `(학번, 키)`별 **최신 상태**로 덮어쓴다.
- cancelled 후 다시 enrolled된 레코드가 있으면 정확히 enrolled로 카운트됨.
- 모든 과목을 과목코드·분반 오름차순으로 정렬해 반환 (기획서 6.16 요구).

## 비의도적으로 하지 않은 것

- **관리자 로그 없음**: 누가 언제 무엇을 수정했는지 기록하지 않음 (기획서 요구 없음).
- **강의 수정 충돌 감지 없음**: 수정 후 시간표가 겹치는 학생이 있어도 체크하지 않음 (기획서 6.14.2에 기술 없음).
- **관리자 삭제/비활성화 없음**: 기획서는 관리자 계정 조작 기능을 정의하지 않음 → `admins.txt` 직접 편집 가정.
