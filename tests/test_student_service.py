from datetime import date

from major_basics.modules.models import Config, Course, Student
from major_basics.modules.student_service import StudentService


def test_time_conflict_rule() -> None:
    student = Student("202111376", "Abc1234", "홍길동", "공과대학", "컴퓨터공학부")
    courses = {
        ("1001", "01"): Course("1001", "01", "프로그래밍기초", 3, "김교수", "MON", 9 * 60, 10 * 60 + 30),
        ("1002", "01"): Course("1002", "01", "자료구조", 3, "이교수", "MON", 10 * 60, 11 * 60 + 30),
    }
    completed = {"202111376": {"1001"}}
    enrollments = []
    config = Config(date(2026, 4, 1), date(2026, 4, 7), date(2026, 4, 3))

    service = StudentService(student, courses, enrollments, completed, config)
    ok1, _, _ = service.register("1001", "01")
    ok2, msg, _ = service.register("1002", "01")

    assert ok1
    assert not ok2
    assert "시간표 충돌" in msg


def test_retake_mark() -> None:
    student = Student("202111376", "Abc1234", "홍길동", "공과대학", "컴퓨터공학부")
    courses = {
        ("1001", "01"): Course("1001", "01", "프로그래밍기초", 3, "김교수", "MON", 9 * 60, 10 * 60 + 30),
    }
    completed = {"202111376": {"1001"}}
    enrollments = []
    config = Config(date(2026, 4, 1), date(2026, 4, 7), date(2026, 4, 3))

    service = StudentService(student, courses, enrollments, completed, config)
    ok, msg, retake = service.register("1001", "01")

    assert ok
    assert retake
    assert "재수강" in msg


def test_same_code_other_section_blocked() -> None:
    """기획서 5.3: 같은 과목코드에 이미 enrolled인 학생은 다른 분반까지 포함하여 중복 신청 불가."""
    student = Student("202111376", "Abc1234", "홍길동", "공과대학", "컴퓨터공학부")
    courses = {
        ("1001", "01"): Course("1001", "01", "프로그래밍기초", 3, "김교수", "MON", 9 * 60, 10 * 60 + 30),
        ("1001", "02"): Course("1001", "02", "프로그래밍기초", 3, "김교수", "TUE", 9 * 60, 10 * 60 + 30),
    }
    enrollments = []
    config = Config(date(2026, 4, 1), date(2026, 4, 7), date(2026, 4, 3))

    service = StudentService(student, courses, enrollments, {}, config)
    ok1, _, _ = service.register("1001", "01")
    ok2, msg, _ = service.register("1001", "02")

    assert ok1
    assert not ok2
    assert "이미 신청한 과목" in msg
