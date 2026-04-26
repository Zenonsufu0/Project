from dataclasses import dataclass
from datetime import date

DAY_ORDER = {"MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5}
VALID_DAYS = frozenset(DAY_ORDER.keys())


@dataclass
class Student:
    student_id: str
    password: str
    name: str
    college: str
    major: str
    status: str = "active"


@dataclass
class Admin:
    admin_id: str
    password: str
    name: str


@dataclass
class Course:
    code: str
    section: str
    name: str
    credits: int
    professor: str
    day: str
    start_time: int
    end_time: int
    status: str = "active"
    capacity: int = 30

    def key(self) -> tuple[str, str]:
        return self.code, self.section

    def time_text(self) -> str:
        return f"{self._to_hhmm(self.start_time)} ~ {self._to_hhmm(self.end_time)}"

    @staticmethod
    def _to_hhmm(value: int) -> str:
        hour = value // 60
        minute = value % 60
        return f"{hour:02d}:{minute:02d}"


@dataclass
class Enrollment:
    student_id: str
    course_code: str
    section: str
    status: str

    def key(self) -> tuple[str, str]:
        return self.course_code, self.section


@dataclass
class Config:
    reg_start: date
    reg_end: date
    current_date: date
