from datetime import date

from major_basics.modules.admin_service import AdminService
from major_basics.modules.models import (
    Classroom,
    Config,
    Course,
    Enrollment,
    Schedule,
    Student,
)


def _classrooms():
    return {
        "1001": Classroom("1001", "공학관", "101", 60),
        "1002": Classroom("1002", "공학관", "201", 80),
        "1003": Classroom("1003", "과학관", "102", 40),
    }


def _colleges():
    return {"공과대학": ["컴퓨터공학부", "전기공학부"], "이과대학": ["수학과"]}


def _service(current_date=date(2026, 3, 1), reg_start=date(2026, 4, 1), reg_end=date(2026, 4, 7),
             courses=None, schedules=None, enrollments=None):
    config = Config(reg_start, reg_end, current_date, "2026-1")
    return AdminService(
        students={},
        courses=courses if courses is not None else {},
        enrollments=enrollments if enrollments is not None else [],
        completed={},
        colleges=_colleges(),
        config=config,
        schedules=schedules if schedules is not None else {},
        classrooms=_classrooms(),
        prerequisites={},
    )


def test_add_course_requires_schedule() -> None:
    a = _service()
    course = Course("1005", "01", "DB", 3, "박교수", semester="2026-1")
    ok, msg = a.add_course(course, [])
    assert not ok
    assert "스케줄을 1개 이상" in msg


def test_add_course_capacity_exceeds_min_seats() -> None:
    a = _service()
    course = Course("1005", "01", "DB", 3, "박교수", capacity=50, semester="2026-1")
    sched = [Schedule("1005", "01", "MON", 9 * 60, 10 * 60 + 30, "1003")]  # 과학관102=40석
    ok, msg = a.add_course(course, sched)
    assert not ok
    assert "가장 작은 강의실" in msg


def test_add_course_success() -> None:
    a = _service()
    course = Course("1005", "01", "DB", 3, "박교수", capacity=30, semester="2026-1")
    sched = [Schedule("1005", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")]
    ok, msg = a.add_course(course, sched)
    assert ok
    assert ("1005", "01") in a.courses
    assert ("1005", "01") in a.schedules


def test_update_name_blocked_after_period_start() -> None:
    courses = {("1001", "01"): Course("1001", "01", "A", 3, "김교수", semester="2026-1")}
    schedules = {("1001", "01"): [Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")]}
    # 기간 시작 후
    a = _service(current_date=date(2026, 4, 3), courses=courses, schedules=schedules)
    ok, msg = a.update_course_name("1001", "01", "새이름")
    assert not ok
    assert "수강신청 기간 시작 이후" in msg


def test_update_name_allowed_before_period() -> None:
    courses = {("1001", "01"): Course("1001", "01", "A", 3, "김교수", semester="2026-1")}
    schedules = {("1001", "01"): [Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")]}
    a = _service(current_date=date(2026, 3, 1), courses=courses, schedules=schedules)
    ok, _ = a.update_course_name("1001", "01", "새이름")
    assert ok
    assert courses[("1001", "01")].name == "새이름"


def test_update_capacity_decrease_below_enrolled_blocked() -> None:
    courses = {("1001", "01"): Course("1001", "01", "A", 3, "김교수", capacity=30, semester="2026-1")}
    schedules = {("1001", "01"): [Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")]}
    enr = [
        Enrollment("202200001", "1001", "01", "enrolled"),
        Enrollment("202200002", "1001", "01", "enrolled"),
    ]
    a = _service(current_date=date(2026, 4, 3), courses=courses, schedules=schedules, enrollments=enr)
    ok, msg = a.update_course_capacity("1001", "01", 1)
    assert not ok
    assert "현재 신청 인원" in msg


def test_update_professor_conflict() -> None:
    courses = {
        ("1001", "01"): Course("1001", "01", "A", 3, "김교수", semester="2026-1"),
        ("2001", "01"): Course("2001", "01", "B", 3, "신교수", semester="2026-1"),
    }
    schedules = {
        ("1001", "01"): [Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")],
        ("2001", "01"): [Schedule("2001", "01", "MON", 9 * 60, 10 * 60 + 30, "1002")],
    }
    a = _service(current_date=date(2026, 4, 3), courses=courses, schedules=schedules)
    ok, msg = a.update_course_professor("1001", "01", "신교수")  # 신교수는 2001을 MON 09:00에 담당
    assert not ok
    assert "요시가 충돌" in msg


def test_delete_last_schedule_blocked() -> None:
    courses = {("1001", "01"): Course("1001", "01", "A", 3, "김교수", semester="2026-1")}
    schedules = {("1001", "01"): [Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")]}
    a = _service(current_date=date(2026, 3, 1), courses=courses, schedules=schedules)
    ok, msg = a.delete_schedule("1001", "01", "MON")
    assert not ok
    assert "최소 1개" in msg


def test_update_schedule_classroom_too_small() -> None:
    courses = {("1001", "01"): Course("1001", "01", "A", 3, "김교수", capacity=50, semester="2026-1")}
    schedules = {("1001", "01"): [Schedule("1001", "01", "MON", 9 * 60, 10 * 60 + 30, "1001")]}
    enr = [Enrollment(f"20220000{i}", "1001", "01", "enrolled") for i in range(5)]  # 5명
    a = _service(current_date=date(2026, 4, 3), courses=courses, schedules=schedules, enrollments=enr)
    # 과학관102(1003)=40석 >= 5명 → 가능
    ok, _ = a.update_schedule_classroom("1001", "01", "MON", "1003")
    assert ok


def test_add_classroom_duplicate() -> None:
    a = _service()
    ok, msg = a.add_classroom(Classroom("1001", "공학관", "999", 10))
    assert not ok
    assert "이미 존재하는 강의실코드" in msg


def test_set_period_semester_format() -> None:
    a = _service()
    ok, msg = a.set_registration_period(date(2026, 4, 1), date(2026, 4, 7), "2026-3")
    assert not ok
    assert "학기 형식" in msg
    ok2, _ = a.set_registration_period(date(2026, 4, 1), date(2026, 4, 7), "2026-2")
    assert ok2
    assert a.config.semester == "2026-2"


def test_register_student_grade_validation() -> None:
    a = _service()
    bad = Student("202500001", "Pass123", "김건국", "공과대학", "컴퓨터공학부", "active", 5)
    ok, msg = a.register_student(bad)
    assert not ok
    assert "학년" in msg
