# models.py — 데이터 모델 설계

## 역할

프로그램 전체에서 공유하는 **도메인 데이터 클래스**를 정의한다. 파일 I/O와 도메인 로직 양쪽이 의존하는 최하위 계층이며, 외부 의존이 없다.

기획서 4절 "데이터 요소"에 1:1 대응되는 데이터 컨테이너를 제공한다.

## 설계 의도

### 1. dataclass 사용 이유
- 기획서가 정의한 필드 스키마를 **코드로 한눈에 볼 수 있게** 한다.
- `__init__`/`__repr__`/`__eq__` 자동 생성으로 보일러플레이트 제거.
- 나중에 JSON/딕셔너리 직렬화가 필요해지면 `dataclasses.asdict`로 즉시 전환 가능.

### 2. 계산 로직을 모델에 두지 않는 이유
- `Course.time_text()` 같은 **순수 표현 헬퍼**만 모델에 둔다.
- "신청 가능한가?", "시간 충돌인가?" 같은 **규칙 판단**은 전부 서비스 레이어(`student_service.py`) 담당.
- 모델은 값, 서비스는 규칙 — 이 경계를 지키면 규칙이 바뀔 때 모델을 건드릴 필요가 없다.

### 3. `DAY_ORDER` / `VALID_DAYS` 상수
- 기획서 4.3.6: 요일은 `MON, TUE, WED, THU, FRI`만 허용.
- `DAY_ORDER`는 시간표 정렬 시 사용 (`student_service.timetable()`).
- `VALID_DAYS`는 검증 시 사용 (`admin_service`, `storage` 공용).
- 한 상수의 키를 다른 상수가 참조하도록 해 **단일 출처**를 유지한다.

## 클래스별 매핑

| 클래스 | 기획서 절 | 주요 필드 |
|---|---|---|
| `Student` | 4.1 | `student_id`, `password`, `name`, `college`, `major`, `status` |
| `Admin` | 4.2 | `admin_id`, `password`, `name` |
| `Course` | 4.3 | `code`, `section`, `name`, `credits`, `professor`, `day`, `start_time`, `end_time`, `status`, `capacity` |
| `Enrollment` | 4.5 | `student_id`, `course_code`, `section`, `status` |
| `Config` | 5.2.5 | `reg_start`, `reg_end`, `current_date` |

## 주요 설계 결정

### `Enrollment`에서 `is_retake` 필드 제거
- 기획서 4.5절은 `〈학번〉,〈과목코드〉,〈분반코드〉,〈신청상태〉` 4필드만 규정.
- 재수강 여부는 `completed_courses.txt`에 해당 과목코드가 있는지로 **동적 판단** (기획서 5.3 "재수강 처리" 명세와 일치).
- 파일 스펙과 코드 모델을 일치시키기 위해 필드를 지우고, 조회 시 `StudentService.is_retake()`로 계산.

### `Course.start_time` / `end_time`을 `int`(분 단위)로
- 원본 문자열 `"09:30"`을 저장하지 않고 `570`(분)으로 저장.
- 시간 충돌/정렬 연산이 정수 비교로 끝나므로 서비스 로직이 단순해진다.
- 표현이 필요할 때만 `time_text()`로 변환.

### `Config.current_date`
- 파일에는 `reg_start`, `reg_end`만 저장 (기획서 5.2.5 준수).
- `current_date`는 프로그램 시작 시 사용자가 입력한 오늘 날짜(기획서 6.1)이며 **런타임에만** 유효.
- 같은 `Config` 객체에 넣어 서비스 레이어 호출 시 인자 수를 줄였다.

## 비의도적으로 하지 않은 것

- **검증 로직 없음**: `Student("xx", ...)`를 만들어도 학번 형식 검사를 하지 않는다. 검증은 `auth.py` / `admin_service.py` / `storage.validate_integrity()` 담당.
- **직렬화 메서드 없음**: `to_csv()` 같은 메서드를 모델에 두지 않는다. 포맷 변경이 쉽도록 `storage.py`가 직렬화까지 책임진다.
