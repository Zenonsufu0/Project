# models.py — 전 모듈이 공유하는 데이터 클래스 정의 (공통 협업)
from dataclasses import dataclass
from datetime import date

DAY_ORDER = {"MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5}
VALID_DAYS = frozenset(DAY_ORDER.keys())


def default_semester(current_date: date) -> str:
    """config.txt 자동 생성 시 기본 학기 — 1~6월 YYYY-1, 7~12월 YYYY-2 (설계 2.7)."""
    half = 1 if current_date.month <= 6 else 2
    return f"{current_date.year}-{half}"


def to_hhmm(value: int) -> str:
    """분 단위 정수 → 'HH:MM' 문자열."""
    return f"{value // 60:02d}:{value % 60:02d}"


@dataclass
class Student:
    student_id: str
    password: str
    name: str
    college: str
    major: str
    status: str = "active"
    grade: int = 1  # ★2차 추가: 학년 (1 이상 4 이하)


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
    status: str = "active"
    capacity: int = 30
    semester: str = ""        # ★2차 추가: 학기 (YYYY-S)
    limit_grade: int = 0      # ★2차 추가: 제한학년 (0=제한없음, 1~4)
    limit_major: str = "전체"  # ★2차 추가: 제한학과 ('전체'=제한없음)

    def key(self) -> tuple[str, str]:
        return self.code, self.section


@dataclass
class Schedule:
    """★2차 신규: 한 개설 강의의 수업 시간 단위. 한 강의가 1개 이상 가질 수 있다."""

    course_code: str
    section: str
    day: str
    start_time: int  # 분 단위 (HH*60+MM)
    end_time: int    # 분 단위
    classroom_code: str

    def key(self) -> tuple[str, str, str]:
        return self.course_code, self.section, self.day

    def course_key(self) -> tuple[str, str]:
        return self.course_code, self.section

    def time_text(self) -> str:
        return f"{to_hhmm(self.start_time)}~{to_hhmm(self.end_time)}"


@dataclass
class Classroom:
    """★2차 신규: 강의실 정보."""

    classroom_code: str
    building: str
    room_number: str
    seats: int

    def display_name(self) -> str:
        return f"{self.building}{self.room_number}"


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
    semester: str = ""  # ★2차 추가: 현재 학기 (YYYY-S)
