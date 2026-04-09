from datetime import date

from major_basics.modules.models import Config, Course, Student
from major_basics.modules.student_service import StudentService


def test_time_conflict_rule() -> None:
    student = Student("202111376", "Abc12345!", "홍길동", "공과대학", "컴퓨터공학부")
    courses = {
        ("1001", "01"): Course("1001", "01", "프로그래밍기초", 3, "김교수", "MON", 9 * 60, 10 * 60 + 30),
        ("1002", "01"): Course("1002", "01", "자료구조", 3, "이교수", "MON", 10 * 60, 11 * 60 + 30),
    }
    completed = {"202111376": {"1001"}}
    enrollments = []
    config = Config(date(2026, 4, 1), date(2026, 4, 7), date(2026, 4, 3))

    service = StudentService(student, courses, enrollments, completed, config)
    ok1, _ = service.register("1001", "01")
    ok2, msg = service.register("1002", "01")

    assert ok1
    assert not ok2
    assert "시간표 충돌" in msg


def test_retake_mark() -> None:
    student = Student("202111376", "Abc12345!", "홍길동", "공과대학", "컴퓨터공학부")
    courses = {
        ("1001", "01"): Course("1001", "01", "프로그래밍기초", 3, "김교수", "MON", 9 * 60, 10 * 60 + 30),
    }
    completed = {"202111376": {"1001"}}
    enrollments = []
    config = Config(date(2026, 4, 1), date(2026, 4, 7), date(2026, 4, 3))

    service = StudentService(student, courses, enrollments, completed, config)
    ok, msg = service.register("1001", "01")

    assert ok
    assert "재수강" in msg
