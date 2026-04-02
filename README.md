# 전공기초 프로젝트 - 수강신청 시뮬레이터(CLI)

워드 기획서 골조(로그인, 학생/관리자 메뉴, 데이터 요소)를 기준으로 구성한 콘솔 프로그램입니다.

## 문서 골조 반영

- 로그인 프롬프트(학생/관리자)
- 로그인 프롬프트(학생/관리자) + 학생 회원가입
- 학생 메뉴: 과목조회/검색, 기이수 관리, 수강신청, 수강취소, 신청내역, 시간표
- 관리자 메뉴: 학생 등록/삭제, 강의 등록/수정/삭제, 전체 수강 현황
- 데이터 요소: 학생/관리자/개설과목/기이수/신청내역
- 시간표 중복 검사, 재수강 처리, 최대 18학점 검사 포함
- 선수과목 검사는 이번 버전에서 제외

## 폴더 구조

```text
src/major_basics/
├─ cli/app.py
├─ data/repository.py
├─ models/
│  ├─ student.py
│  ├─ admin.py
│  ├─ course.py
│  └─ enrollment.py
├─ services/
│  ├─ auth_service.py
│  ├─ registration_manager.py
│  ├─ admin_manager.py
│  └─ schedule_utils.py
└─ main.py
```

## 데이터 파일

`data/raw/` 아래 파일을 사용합니다.
- `students.txt`
- `admins.txt`
- `courses.txt`
- `completed_courses.txt`
- `enrollments.txt`

처음 실행 시 파일이 없으면 기본 더미 데이터가 자동 생성됩니다.

## 실행

```bash
python main.py
```
