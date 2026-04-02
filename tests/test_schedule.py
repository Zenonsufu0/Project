from major_basics.models.course import Course
from major_basics.services.schedule_utils import is_time_overlap


def test_time_overlap_true() -> None:
    a = Course("1001", "A", 3, "Kim", "MON", 900, 1030, "major_required")
    b = Course("1002", "B", 3, "Lee", "MON", 1000, 1130, "major_required")
    assert is_time_overlap(a, b)


def test_time_overlap_false() -> None:
    a = Course("1001", "A", 3, "Kim", "MON", 900, 1030, "major_required")
    b = Course("1002", "B", 3, "Lee", "TUE", 1000, 1130, "major_required")
    assert not is_time_overlap(a, b)
