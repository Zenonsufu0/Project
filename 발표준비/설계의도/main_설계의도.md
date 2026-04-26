# main.py — 진입점 · CLI 컨트롤러

## 역할

프로그램의 **Composition Root** 역할. 모든 모듈을 조립하고, 기획서 6절의 각 프롬프트를 CLI로 구현한다. 서비스 레이어를 호출해 결과를 받아 화면에 출력한다.

- 기획서 6절 전체 대응 (6.1~6.16)
- 서비스 레이어에서 분리된 **입출력 책임**만 담당

## 설계 의도

### 1. UI = main.py, 규칙 = 서비스
`main.py`가 직접 하는 것:
- 사용자 입력 받기 (`input()`)
- 메시지 출력 (`print()`)
- 메뉴 표시 / 프롬프트 흐름 제어
- 서비스 호출 후 반환값을 화면에 렌더링
- 상태 변경 후 `_save_all` 호출

`main.py`가 **하지 않는** 것:
- 비밀번호 정규식 검사 → `auth.py`
- 시간표 충돌 판단 → `student_service.py`
- 파일 쓰기 → `storage.py`

이 분리 덕분에 서비스 레이어는 단위 테스트가 가능하고, CLI를 GUI로 교체해도 서비스 코드는 그대로 재사용 가능.

### 2. 시작 시퀀스 (기획서 5.5 + 6.1)
```
1. 오늘 날짜 입력 (재입력 루프)
2. store.ensure_defaults()  — 누락 파일 자동 생성
3. store.validate_integrity() — 무결성 검사 (실패 시 종료)
4. 전체 데이터 로드
5. 로그인/회원가입 메뉴 루프
```
무결성 검사를 통과해야만 메뉴에 진입하도록 강제 — 기획서 5.5 "모든 검사가 정상적으로 끝난 경우에만 로그인/회원가입 선택 화면을 출력".

### 3. 저장 시점 전략 (기획서 2.3 "즉시 반영")
**상태 변경이 있는 모든 핸들러**에서 즉시 `_save_all` 호출:
- 관리자 메뉴: 학생/강의 등록·삭제·활성화·기간설정 후 즉시 저장
- 학생 메뉴: 수강신청·취소·기이수 추가 **각 작업 직후 즉시 저장** (기획서 2.3 "즉시 반영" 준수)
- 회원가입 완료 후 즉시 저장

### 4. 입력 재대기 루프 패턴
기획서 6.3 "각각 해당 프롬프트 재대기" 요구를 충족하기 위해 각 필드마다 `while True:` 루프:
```python
while True:
    student_id = input("학번 (숫자 9자리) > ").strip()
    is_valid, msg = auth_service.validate_student_id(student_id)
    if is_valid: break
    print(f"!!! 오류: {msg}")
```
- 빈 입력(Enter)은 메시지 없이 재프롬프트하는 경우와, 오류 메시지를 출력하고 재프롬프트하는 경우를 프롬프트별로 구분.

## 헬퍼 함수

| 함수 | 역할 |
|---|---|
| `_parse_date(s)` | `YYYY-MM-DD` 파싱 (현행 그레고리력 검증) |
| `_parse_hhmm(s)` | `HH:MM` 파싱 + 분 00/30 강제 |
| `_header_sep(header)` | 헤더 문자열 → `-+-` 구분선 생성 (CJK 2열 너비 계산) |
| `_save_all(...)` | 전체 데이터 저장 (6개 파일) |
| `_choose_college_major(colleges)` | 단과대 → 전공 번호 선택 UI |
| `_print_courses(courses, counts, show_capacity)` | 과목 목록 표 출력. `show_capacity=False`면 정원 열 미표시 (기획서 6.7.2) |
| `_search_and_select_course(student_service)` | 과목명 검색 → 번호 선택 → `Course` 반환 공용 UI (기획서 6.7.2) |
| `_input_course()` | 강의 등록/수정 입력 수집 + 1차 검증 |
| `_student_menu(...)` | 학생 메뉴 루프 (기획서 6.5) |
| `_admin_menu(...)` | 관리자 메뉴 루프 (기획서 6.6) |

## 메인 루프 구조

```
main()
├── 오늘 날짜 입력
├── ensure_defaults + validate_integrity
├── 전체 로드
└── 로그인/회원가입 루프
    ├── 1. 로그인 → 역할별 메뉴
    │   ├── student → _student_menu
    │   └── admin   → _admin_menu
    ├── 2. 회원가입 → 학번/비밀번호/이름/단과대/전공 입력
    └── 0. 종료 → _save_all + 종료
```

## 주요 설계 결정

### 시작 날짜에 `2000~2099` 범위 강제하지 않음
- 기획서 6.1은 "현행 그레고리력에 존재하는 날짜"만 요구.
- 기획서 5.2.5의 `2000~2099` 범위는 **config.txt 전용** 규칙.
- 따라서 `_parse_date`는 `date.fromisoformat`의 기본 검증만 수행.
- 범위 제한은 `storage._check_config_syntax`에서만 적용.

### `_parse_hhmm`에서 분 00/30 강제
```python
if minute not in (0, 30):
    return None
```
- 입력 시점에서 기획서 4.3.7 위반을 차단.
- 서비스 레이어에서도 같은 규칙을 재검사 (이중 방어).

### 오류 메시지 접두어 통일
- 기획서 전반: `!!! 오류: ...`, `!!! 안내: ...`, `!!! 경고: ...`
- `main.py`의 출력이 이 규칙을 따르도록 통일. 관리자 메뉴의 기본 실패 메시지도 `!!! 오류: 잘못된 입력입니다. 다시 선택하세요.`로 수정.

### 강의 수정 가능 기간 조건 (기획서 6.14.2)
관리자 메뉴 "5. 강의 수정"은 **수강신청 기간 시작 전**에만 가능하다 (메뉴에도 표기).
```python
if config.current_date >= config.reg_start:
    # 기간 중 + 기간 종료 후 모두 차단
    print("!!! 오류: 수강신청 기간 시작 이후에는 강의를 수정할 수 없습니다.")
```
이전 구현은 `reg_start <= today <= reg_end` (기간 중에만 차단)로 기간 종료 후에도 수정이 가능했던 버그를 수정.

### `load_colleges()` 오류 처리
`storage.load_colleges()`가 `IntegrityError`를 raise하는 경우를 대비해 `main()`에서 try/except로 감싸고 오류 출력 후 종료. `validate_integrity()`가 먼저 걸러주므로 정상 흐름에서는 발생하지 않으나 방어적 설계.

### 시간표 과목명 15자 제한
기획서 6.12 "기타: 과목명이 15자를 초과하는 경우 15자까지만 표시하고 '...'을 붙인다."
```python
name = course.name if len(course.name) <= 15 else course.name[:15] + "..."
```
이 규칙은 UI에만 해당하므로 `main.py`에서 처리 (서비스 레이어는 원본 `Course.name` 그대로 반환).

## 비의도적으로 하지 않은 것

- **색상/그래픽 없음**: 기획서 7절 "TUI가 아니라 일반 CLI 목록 출력 방식으로 구현" 명시.
- **비밀번호 마스킹**: `_input_password()`로 구현. Windows는 `msvcrt.getwch()`, 그 외는 `getpass` 사용. 기획서 6.4 `비밀번호 > ********` 마스킹 요구 충족.
- **히스토리/자동완성 없음**: 표준 입력만 사용.
