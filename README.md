# 수강신청 관리 프로그램 (B04 1차 기획서 반영)

기획서 `B04_1차 기획서 원판_수강신청 관리 프로그램.pdf` 골조를 따라 CLI 프로그램을 재구성했습니다.

## 하위 모듈 5개

`src/major_basics/modules/` 아래를 정확히 5개 모듈로 구성했습니다.

1. `models.py`
2. `storage.py`
3. `auth.py`
4. `student_service.py`
5. `admin_service.py`

## 데이터 파일 (7개)

`data/raw/`
- `students.txt`
- `admins.txt`
- `courses.txt`
- `enrollments.txt`
- `completed_courses.txt`
- `colleges.txt`
- `config.txt`

파일이 없으면 첫 실행 시 자동 생성됩니다.

## 실행

```bash
python main.py
```

프로그램 시작 시 `YYYY-MM-DD` 형식으로 현재 날짜를 입력하면,
기획서 흐름대로 `로그인/회원가입 -> 학생/관리자 메뉴`가 동작합니다.
