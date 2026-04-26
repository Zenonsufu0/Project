# 모듈 설계 개요

본 문서는 `src/major_basics/` 하위 각 모듈의 **역할**, **설계 의도**, **기획서 대응 관계**를 정리한다. 각 파일이 왜 그렇게 분리되어 있는지, 무엇을 책임지고 무엇을 책임지지 않는지를 명확히 한다.

---

## 전체 구조

```
src/major_basics/
├── main.py              프로그램 진입점 (CLI 루프 + 무결성 검사 호출)
└── modules/
    ├── models.py        데이터 클래스 정의 (Student/Admin/Course/Enrollment/Config)
    ├── storage.py       파일 I/O + 무결성 검사 (DataStore)
    ├── auth.py          로그인·회원가입·입력 검증 (AuthService)
    ├── student_service.py   학생 도메인 로직 (조회/신청/취소/시간표)
    └── admin_service.py     관리자 도메인 로직 (학생/강의/기간 관리)
```

## 설계 3대 원칙

1. **계층 분리** — 파일 I/O(`storage`) / 도메인 로직(`*_service`) / 프레젠테이션(`main`)을 분리한다. 도메인 서비스는 입출력(`print`/`input`)을 직접 호출하지 않는다.
2. **기획서 단일 출처** — 모든 검증 규칙·오류 메시지·수강신청 검사 순서는 기획서 4·5·6절을 단일 출처로 삼는다. 코드 주석에 `기획서 X.Y절` 식으로 참조를 남겨 추적성을 유지한다.
3. **상태 변경 → 저장 즉시 반영** — 서비스 레이어가 상태를 바꾼 뒤, `main.py`의 각 핸들러가 `_save_all`을 호출해 즉시 파일에 반영한다 (기획서 2.3절 "즉시 반영" 요구 대응).

## 의존 그래프

```
main.py ─┬─> storage.py (무결성 검사, load/save)
         ├─> auth.py ───> models.py
         ├─> student_service.py ─> models.py
         └─> admin_service.py ──> models.py
```

- `models.py`는 외부 의존 없음 (dataclass만).
- `storage.py`는 `models.py`만 의존 (I/O 책임 캡슐화).
- 서비스 레이어들은 서로 참조하지 않는다 (각자 역할 독립).
- `main.py`가 모든 모듈을 조립하는 Composition Root.

## 상세 설계 문서

각 모듈별 상세 의도는 아래 문서 참고:

- [models.md](models.md)
- [storage.md](storage.md)
- [auth.md](auth.md)
- [student_service.md](student_service.md)
- [admin_service.md](admin_service.md)
- [main.md](main.md)
