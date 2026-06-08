from datetime import date

from major_basics.modules.models import (
    Classroom,
    Config,
    Course,
    Enrollment,
    Schedule,
    Student,
)
from major_basics.modules.student_service import StudentService


def _classrooms():
    return {
        "1001": Classroom("1001", "공학관", "101", 60),
        "1002": Classroom("1002", "공학관", "201", 80),
        "1003": Classroom("1003", "과학관", "102", 40),
    }


def _config():
    return Config(date(2026, 4, 1), date(2026, 4, 30), date(2026, 4, 3), "2026-1")


def _student(grade=2, major="컴퓨터공학부"):
    return Student("202111376", "Abc1234", "홍길동", "공과대학", major, "active", grade)


def _svc(student, courses, schedules, enrollments=None, completed=None, prereq=None, config=None):
    return StudentService(
        student,
        courses,
        enrollments if enrollments is not None else [],
        completed if completed is not None else {},
        config or _config(),
        schedules,
        _classrooms(),
        prereq or {},
    )


def test_schedule_conflict_rule() -> None:
    courses = {
        ("1001", "01"): Course("1001", "01", "프로그래밍기초", 3, "김교수", semester="2026-1"),
        ("1002", "01"): Course("1002", "01", "자료구조", 3, "이교수", semester="2026-1"),
    }
    schedules = {
        ("1001", "01"): [Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")],
        ("1002", "01"): [Schedule("1002", "01", "MON", 10 * 60, 11 * 60 + 30, "1002")],
    }
    svc = _svc(_student(), courses, schedules)
    ok1, _, _ = svc.register("1001", "01")
    ok2, msg, _ = svc.register("1002", "01")
    assert ok1
    assert not ok2
    assert "스케줄 충돌" in msg


def test_schedule_no_conflict_when_touching() -> None:
    """[시작, 종료) 반열림: 앞 과목 종료 == 뒤 과목 시작이면 충돌 아님."""
    courses = {
        ("1001", "01"): Course("1001", "01", "A", 3, "김교수", semester="2026-1"),
        ("1002", "01"): Course("1002", "01", "B", 3, "이교수", semester="2026-1"),
    }
    schedules = {
        ("1001", "01"): [Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")],
        ("1002", "01"): [Schedule("1002", "01", "MON", 10 * 60 + 30, 12 * 60, "1002")],
    }
    svc = _svc(_student(), courses, schedules)
    assert svc.register("1001", "01")[0]
    assert svc.register("1002", "01")[0]


def test_retake_mark() -> None:
    courses = {("1001", "01"): Course("1001", "01", "프로그래밍기초", 3, "김교수", semester="2026-1")}
    schedules = {("1001", "01"): [Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")]}
    svc = _svc(_student(), courses, schedules, completed={"202111376": {"1001"}})
    ok, msg, retake = svc.register("1001", "01")
    assert ok and retake
    assert "재수강" in msg


def test_same_code_other_section_blocked() -> None:
    courses = {
        ("1001", "01"): Course("1001", "01", "프로그래밍기초", 3, "김교수", semester="2026-1"),
        ("1001", "02"): Course("1001", "02", "프로그래밍기초", 3, "김교수", semester="2026-1"),
    }
    schedules = {
        ("1001", "01"): [Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")],
        ("1001", "02"): [Schedule("1001", "02", "TUE", 9 * 60, 10 * 60 + 30, "1001")],
    }
    svc = _svc(_student(), courses, schedules)
    assert svc.register("1001", "01")[0]
    ok2, msg, _ = svc.register("1001", "02")
    assert not ok2
    assert "이미 신청한 과목" in msg


def test_semester_mismatch_blocked() -> None:
    courses = {("1001", "01"): Course("1001", "01", "A", 3, "김교수", semester="2026-2")}
    schedules = {("1001", "01"): [Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")]}
    svc = _svc(_student(), courses, schedules)
    ok, msg, _ = svc.register("1001", "01")
    assert not ok
    assert "현재 학기" in msg


def test_grade_limit_blocked() -> None:
    courses = {("1002", "01"): Course("1002", "01", "자료구조", 3, "박교수", semester="2026-1", limit_grade=3)}
    schedules = {("1002", "01"): [Schedule("1002", "01", "MON", 13 * 60, 14 * 60 + 30, "1003")]}
    svc = _svc(_student(grade=2), courses, schedules)
    ok, msg, _ = svc.register("1002", "01")
    assert not ok
    assert "3학년 학생만" in msg


def test_grade_limit_allowed_when_match() -> None:
    courses = {("1002", "01"): Course("1002", "01", "자료구조", 3, "박교수", semester="2026-1", limit_grade=2)}
    schedules = {("1002", "01"): [Schedule("1002", "01", "MON", 13 * 60, 14 * 60 + 30, "1003")]}
    svc = _svc(_student(grade=2), courses, schedules)
    assert svc.register("1002", "01")[0]


def test_major_limit_blocked() -> None:
    courses = {("1002", "01"): Course("1002", "01", "자료구조", 3, "박교수", semester="2026-1", limit_major="컴퓨터공학부")}
    schedules = {("1002", "01"): [Schedule("1002", "01", "MON", 13 * 60, 14 * 60 + 30, "1003")]}
    svc = _svc(_student(grade=2, major="전기공학부"), courses, schedules)
    ok, msg, _ = svc.register("1002", "01")
    assert not ok
    assert "컴퓨터공학부 학생만" in msg


def test_prerequisite_missing_blocked() -> None:
    courses = {
        ("1002", "01"): Course("1002", "01", "자료구조", 3, "박교수", semester="2026-1"),
        ("1003", "01"): Course("1003", "01", "알고리즘", 3, "최교수", semester="2026-1"),
    }
    schedules = {
        ("1002", "01"): [Schedule("1002", "01", "MON", 13 * 60, 14 * 60 + 30, "1003")],
        ("1003", "01"): [Schedule("1003", "01", "FRI", 10 * 60 + 30, 12 * 60, "1001")],
    }
    svc = _svc(_student(grade=2), courses, schedules, prereq={"1003": {"1002"}})
    ok, msg, _ = svc.register("1003", "01")
    assert not ok
    assert "선수과목" in msg and "자료구조" in msg


def test_prerequisite_satisfied_allows() -> None:
    courses = {("1003", "01"): Course("1003", "01", "알고리즘", 3, "최교수", semester="2026-1")}
    schedules = {("1003", "01"): [Schedule("1003", "01", "FRI", 10 * 60 + 30, 12 * 60, "1001")]}
    svc = _svc(_student(grade=2), courses, schedules,
               completed={"202111376": {"1002"}}, prereq={"1003": {"1002"}})
    assert svc.register("1003", "01")[0]


def test_capacity_full_blocked() -> None:
    courses = {("1001", "01"): Course("1001", "01", "A", 3, "김교수", capacity=1, semester="2026-1")}
    schedules = {("1001", "01"): [Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")]}
    enr = [Enrollment("202200001", "1001", "01", "enrolled")]
    svc = _svc(_student(), courses, schedules, enrollments=enr)
    ok, msg, _ = svc.register("1001", "01")
    assert not ok
    assert "정원이 마감" in msg


def test_max_credits_blocked() -> None:
    courses = {
        ("1001", "01"): Course("1001", "01", "A", 6, "김교수", semester="2026-1"),
        ("1002", "01"): Course("1002", "01", "B", 6, "이교수", semester="2026-1"),
        ("1003", "01"): Course("1003", "01", "C", 6, "박교수", semester="2026-1"),
        ("1004", "01"): Course("1004", "01", "D", 3, "정교수", semester="2026-1"),
    }
    schedules = {
        ("1001", "01"): [Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")],
        ("1002", "01"): [Schedule("1002", "01", "TUE", 9 * 60, 10 * 60 + 30, "1001")],
        ("1003", "01"): [Schedule("1003", "01", "WED", 9 * 60, 10 * 60 + 30, "1001")],
        ("1004", "01"): [Schedule("1004", "01", "THU", 9 * 60, 10 * 60 + 30, "1001")],
    }
    svc = _svc(_student(), courses, schedules)
    assert svc.register("1001", "01")[0]
    assert svc.register("1002", "01")[0]
    assert svc.register("1003", "01")[0]  # 18학점
    ok, msg, _ = svc.register("1004", "01")
    assert not ok
    assert "최대 신청 학점" in msg


def test_current_credits_dedupes_multi_schedule() -> None:
    """스케줄이 2개인 과목도 학점은 1회만 합산."""
    courses = {("1001", "01"): Course("1001", "01", "A", 3, "김교수", semester="2026-1")}
    schedules = {
        ("1001", "01"): [
            Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001"),
            Schedule("1001", "01", "WED", 9 * 60, 10 * 60 + 30, "1001"),
        ]
    }
    svc = _svc(_student(), courses, schedules)
    assert svc.register("1001", "01")[0]
    assert svc.current_credits() == 3
    assert len(svc.timetable()) == 2  # 두 요일 모두 표시


def test_list_courses_filters_by_semester() -> None:
    courses = {
        ("1001", "01"): Course("1001", "01", "이번학기", 3, "김교수", semester="2026-1"),
        ("9001", "01"): Course("9001", "01", "다음학기", 3, "김교수", semester="2026-2"),
    }
    svc = _svc(_student(), courses, {})
    listed = [c.code for c in svc.list_courses()]
    assert "1001" in listed
    assert "9001" not in listed
