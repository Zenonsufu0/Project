from datetime import date

import pytest

from major_basics.modules.storage import DataStore, IntegrityError


def _store(tmp_path):
    store = DataStore(tmp_path)
    store.ensure_defaults(date(2026, 4, 1))
    return store


def test_defaults_pass_integrity(tmp_path) -> None:
    store = _store(tmp_path)
    assert store.validate_integrity() == []


def test_default_files_created(tmp_path) -> None:
    store = _store(tmp_path)
    for name in ("schedules.txt", "classrooms.txt", "prerequisites.txt"):
        assert (tmp_path / name).exists()


def test_roundtrip_courses(tmp_path) -> None:
    store = _store(tmp_path)
    courses = store.load_courses()
    assert ("1002", "01") in courses
    c = courses[("1002", "01")]
    assert c.limit_grade == 2 and c.limit_major == "컴퓨터공학부" and c.semester == "2026-1"
    store.save_courses(courses)
    assert store.load_courses() == courses


def test_roundtrip_schedules(tmp_path) -> None:
    store = _store(tmp_path)
    schedules = store.load_schedules()
    assert ("1001", "01") in schedules
    assert {s.day for s in schedules[("1001", "01")]} == {"MON", "WED"}
    store.save_schedules(schedules)
    assert store.load_schedules() == schedules


def test_students_field_count_error(tmp_path) -> None:
    store = _store(tmp_path)
    # 6필드 (1차 스키마) → 오류
    store.students_path.write_text("202111376,Pass123,홍길동,공과대학,컴퓨터공학부,active\n", encoding="utf-8")
    errors = store.validate_integrity()
    assert any("students.txt" in e and "필드 수" in e for e in errors)


def test_config_requires_semester(tmp_path) -> None:
    store = _store(tmp_path)
    store.config_path.write_text("2026-04-01,2026-04-07\n", encoding="utf-8")  # 2필드
    errors = store.validate_integrity()
    assert any("config.txt" in e and "필드 수" in e for e in errors)


def test_schedule_bad_classroom_ref(tmp_path) -> None:
    store = _store(tmp_path)
    store.schedules_path.write_text("1001,01,MON,09:00,10:30,9999\n", encoding="utf-8")
    errors = store.validate_integrity()
    assert any("강의실코드" in e for e in errors)


def test_prerequisite_bad_course_ref(tmp_path) -> None:
    store = _store(tmp_path)
    store.prerequisites_path.write_text("9999,1001\n", encoding="utf-8")
    errors = store.validate_integrity()
    assert any("prerequisites.txt" in e or "선수과목" in e or "과목코드" in e for e in errors)


def test_prerequisite_self_reference(tmp_path) -> None:
    store = _store(tmp_path)
    store.prerequisites_path.write_text("1001,1001\n", encoding="utf-8")
    errors = store.validate_integrity()
    assert any("자기 자신" in e for e in errors)


def test_course_limit_grade_range(tmp_path) -> None:
    store = _store(tmp_path)
    store.courses_path.write_text("1001,01,프로그래밍기초,3,김교수,active,30,2026-1,5,전체\n", encoding="utf-8")
    errors = store.validate_integrity()
    assert any("제한학년" in e for e in errors)


def test_classroom_field_count(tmp_path) -> None:
    store = _store(tmp_path)
    store.classrooms_path.write_text("1001,공학관,101\n", encoding="utf-8")  # 3필드
    errors = store.validate_integrity()
    assert any("classrooms.txt" in e and "필드 수" in e for e in errors)


def test_colleges_bad_row_raises(tmp_path) -> None:
    store = _store(tmp_path)
    store.colleges_path.write_text("공과대학\n", encoding="utf-8")  # 1필드
    with pytest.raises(IntegrityError):
        store.load_colleges()
