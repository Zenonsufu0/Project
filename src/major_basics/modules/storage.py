import re
from datetime import date
from pathlib import Path

from major_basics.modules.models import Admin, Config, Course, Enrollment, Student, VALID_DAYS


class IntegrityError(Exception):
    pass


class DataStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.students_path = data_dir / "students.txt"
        self.admins_path = data_dir / "admins.txt"
        self.courses_path = data_dir / "courses.txt"
        self.enrollments_path = data_dir / "enrollments.txt"
        self.completed_path = data_dir / "completed_courses.txt"
        self.colleges_path = data_dir / "colleges.txt"
        self.config_path = data_dir / "config.txt"

    def ensure_defaults(self, current_date: date) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if not self.students_path.exists():
            self.students_path.write_text("", encoding="utf-8")

        if not self.admins_path.exists():
            self.admins_path.write_text("admin01,Admin@1234,관리자\n", encoding="utf-8")

        if not self.courses_path.exists():
            self.courses_path.write_text("", encoding="utf-8")

        if not self.enrollments_path.exists():
            self.enrollments_path.write_text("", encoding="utf-8")

        if not self.completed_path.exists():
            self.completed_path.write_text("", encoding="utf-8")

        if not self.colleges_path.exists():
            self.colleges_path.write_text(
                "공과대학,컴퓨터공학부\n"
                "공과대학,전기공학부\n"
                "공과대학,기계공학부\n"
                "문과대학,국어국문학과\n"
                "문과대학,영어영문학과\n"
                "문과대학,철학과\n"
                "이과대학,수학과\n"
                "이과대학,물리학과\n"
                "이과대학,화학과\n",
                encoding="utf-8",
            )

        if not self.config_path.exists():
            text = f"{current_date.isoformat()},{current_date.isoformat()}\n"
            self.config_path.write_text(text, encoding="utf-8")

    def load_students(self) -> dict[str, Student]:
        students: dict[str, Student] = {}
        for row in self._rows(self.students_path):
            if len(row) != 6:
                continue
            student = Student(row[0], row[1], row[2], row[3], row[4], row[5])
            students[student.student_id] = student
        return students

    def save_students(self, students: dict[str, Student]) -> None:
        lines = []
        for student in sorted(students.values(), key=lambda x: x.student_id):
            lines.append(
                f"{student.student_id},{student.password},{student.name},"
                f"{student.college},{student.major},{student.status}"
            )
        self._write_lines(self.students_path, lines)

    def load_admins(self) -> dict[str, Admin]:
        admins: dict[str, Admin] = {}
        for row in self._rows(self.admins_path):
            if len(row) != 3:
                continue
            admin = Admin(row[0], row[1], row[2])
            admins[admin.admin_id] = admin
        return admins

    def save_admins(self, admins: dict[str, Admin]) -> None:
        lines = []
        for admin in sorted(admins.values(), key=lambda x: x.admin_id):
            lines.append(f"{admin.admin_id},{admin.password},{admin.name}")
        self._write_lines(self.admins_path, lines)

    def load_courses(self) -> dict[tuple[str, str], Course]:
        courses: dict[tuple[str, str], Course] = {}
        for row in self._rows(self.courses_path):
            if len(row) != 10:
                continue
            try:
                course = Course(
                    code=row[0],
                    section=row[1],
                    name=row[2],
                    credits=int(row[3]),
                    professor=row[4],
                    day=row[5].upper(),
                    start_time=self._parse_time(row[6]),
                    end_time=self._parse_time(row[7]),
                    status=row[8],
                    capacity=int(row[9]),
                )
            except ValueError:
                continue
            courses[course.key()] = course
        return courses

    def save_courses(self, courses: dict[tuple[str, str], Course]) -> None:
        lines = []
        for course in sorted(courses.values(), key=lambda x: (x.code, x.section)):
            lines.append(
                f"{course.code},{course.section},{course.name},{course.credits},{course.professor},"
                f"{course.day},{self._format_time(course.start_time)},{self._format_time(course.end_time)},"
                f"{course.status},{course.capacity}"
            )
        self._write_lines(self.courses_path, lines)

    def load_enrollments(self) -> list[Enrollment]:
        enrollments: list[Enrollment] = []
        for row in self._rows(self.enrollments_path):
            if len(row) != 4:
                continue
            enrollments.append(
                Enrollment(
                    student_id=row[0],
                    course_code=row[1],
                    section=row[2],
                    status=row[3],
                )
            )
        return enrollments

    def save_enrollments(self, enrollments: list[Enrollment]) -> None:
        lines = []
        for enrollment in enrollments:
            lines.append(
                f"{enrollment.student_id},{enrollment.course_code},{enrollment.section},"
                f"{enrollment.status}"
            )
        self._write_lines(self.enrollments_path, lines)

    def load_completed(self) -> dict[str, set[str]]:
        completed: dict[str, set[str]] = {}
        for row in self._rows(self.completed_path):
            if len(row) != 2:
                continue
            completed.setdefault(row[0], set()).add(row[1])
        return completed

    def save_completed(self, completed: dict[str, set[str]]) -> None:
        lines = []
        for student_id in sorted(completed.keys()):
            for code in sorted(completed[student_id]):
                lines.append(f"{student_id},{code}")
        self._write_lines(self.completed_path, lines)

    def load_colleges(self) -> dict[str, list[str]]:
        colleges: dict[str, list[str]] = {}
        for row in self._rows(self.colleges_path):
            if len(row) != 2:
                # 의도된 동작: 5.5절 무결성 검사에서 형식 오류를 이미 검출·종료하므로
                # 런타임 로드 시에는 비정상 행을 조용히 건너뛴다.
                continue
            college = row[0]
            major = row[1]
            bucket = colleges.setdefault(college, [])
            if major not in bucket:
                bucket.append(major)
        return colleges

    def save_colleges(self, colleges: dict[str, list[str]]) -> None:
        lines = []
        for college in colleges.keys():
            for major in colleges[college]:
                lines.append(f"{college},{major}")
        self._write_lines(self.colleges_path, lines)

    def load_config(self, current_date: date) -> Config:
        rows = self._rows(self.config_path)
        if not rows or len(rows[0]) != 2:
            return Config(current_date, current_date, current_date)

        try:
            start = date.fromisoformat(rows[0][0])
            end = date.fromisoformat(rows[0][1])
        except ValueError:
            start = current_date
            end = current_date

        if end < start:
            end = start

        return Config(start, end, current_date)

    def save_config(self, config: Config) -> None:
        self._write_lines(self.config_path, [f"{config.reg_start.isoformat()},{config.reg_end.isoformat()}"])

    # ------------------------------------------------------------
    # 무결성 확인 (기획서 5.5절)
    # ------------------------------------------------------------
    def validate_integrity(self) -> list[str]:
        errors: list[str] = []

        errors.extend(self._check_students_syntax())
        errors.extend(self._check_admins_syntax())
        errors.extend(self._check_courses_syntax())
        errors.extend(self._check_enrollments_syntax())
        errors.extend(self._check_completed_syntax())
        errors.extend(self._check_colleges_syntax())
        errors.extend(self._check_config_syntax())

        if errors:
            return errors

        errors.extend(self._check_referential_integrity())
        return errors

    def _check_students_syntax(self) -> list[str]:
        errors = []
        seen_ids: set[str] = set()
        for line_no, row in self._enumerated_rows(self.students_path):
            if len(row) != 6:
                errors.append(f"students.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '필드 수 오류'")
                continue
            sid, pw, name, college, major, status = row
            if not (sid.isdigit() and len(sid) == 9):
                errors.append(f"students.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '학번 형식 오류'")
            if sid in seen_ids:
                errors.append(f"students.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '학번 중복'")
            seen_ids.add(sid)
            if not re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]{6,12}", pw):
                errors.append(f"students.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '비밀번호 형식 오류'")
            if not re.fullmatch(r"[가-힣]+", name):
                errors.append(f"students.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '이름 형식 오류'")
            if status not in ("active", "inactive"):
                errors.append(f"students.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '상태 값 오류'")
        return errors

    def _check_admins_syntax(self) -> list[str]:
        errors = []
        seen: set[str] = set()
        for line_no, row in self._enumerated_rows(self.admins_path):
            if len(row) != 3:
                errors.append(f"admins.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '필드 수 오류'")
                continue
            aid, pw, name = row
            if not re.fullmatch(r"[a-z0-9]{6,12}", aid):
                errors.append(f"admins.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '관리자ID 형식 오류'")
            if aid in seen:
                errors.append(f"admins.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '관리자ID 중복'")
            seen.add(aid)
            if not re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)(?=.*[!@#$%^&*])[A-Za-z0-9!@#$%^&*]{8,16}", pw):
                errors.append(f"admins.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '비밀번호 형식 오류'")
            if not re.fullmatch(r"[가-힣 ]+", name) or not name.strip():
                errors.append(f"admins.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '이름 형식 오류'")
        return errors

    def _check_courses_syntax(self) -> list[str]:
        errors = []
        seen: set[tuple[str, str]] = set()
        for line_no, row in self._enumerated_rows(self.courses_path):
            if len(row) != 10:
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '필드 수 오류'")
                continue
            code, section, name, credits_s, prof, day, start_s, end_s, status, capacity_s = row
            if not (code.isdigit() and len(code) == 4):
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '과목코드 형식 오류'")
            if not (section.isdigit() and len(section) == 2):
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '분반코드 형식 오류'")
            if (code, section) in seen:
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '과목코드-분반코드 중복'")
            seen.add((code, section))
            if not name or "\t" in name:
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '과목명 형식 오류'")
            if not credits_s.isdigit() or not (1 <= int(credits_s) <= 6):
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '학점 형식 오류'")
            if not prof or "\t" in prof:
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '담당교수 형식 오류'")
            if day not in VALID_DAYS:
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '요일 형식 오류'")
            start_min = self._check_hhmm(start_s)
            end_min = self._check_hhmm(end_s)
            if start_min is None:
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '시작시각 형식 오류'")
            if end_min is None:
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '종료시각 형식 오류'")
            if start_min is not None and end_min is not None and start_min >= end_min:
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '종료시각은 시작시각보다 이후'")
            if status not in ("active", "inactive"):
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '상태 값 오류'")
            if not capacity_s.isdigit() or int(capacity_s) < 1:
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '정원 형식 오류'")
        return errors

    def _check_enrollments_syntax(self) -> list[str]:
        errors = []
        for line_no, row in self._enumerated_rows(self.enrollments_path):
            if len(row) != 4:
                errors.append(f"enrollments.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '필드 수 오류'")
                continue
            sid, code, section, status = row
            if not (sid.isdigit() and len(sid) == 9):
                errors.append(f"enrollments.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '학번 형식 오류'")
            if not (code.isdigit() and len(code) == 4):
                errors.append(f"enrollments.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '과목코드 형식 오류'")
            if not (section.isdigit() and len(section) == 2):
                errors.append(f"enrollments.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '분반코드 형식 오류'")
            if status not in ("enrolled", "cancelled"):
                errors.append(f"enrollments.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '신청상태 값 오류'")
        return errors

    def _check_completed_syntax(self) -> list[str]:
        errors = []
        seen: set[tuple[str, str]] = set()
        for line_no, row in self._enumerated_rows(self.completed_path):
            if len(row) != 2:
                errors.append(f"completed_courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '필드 수 오류'")
                continue
            sid, code = row
            if not (sid.isdigit() and len(sid) == 9):
                errors.append(f"completed_courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '학번 형식 오류'")
            if not (code.isdigit() and len(code) == 4):
                errors.append(f"completed_courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '과목코드 형식 오류'")
            if (sid, code) in seen:
                errors.append(f"completed_courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '학번-과목코드 중복'")
            seen.add((sid, code))
        return errors

    def _check_colleges_syntax(self) -> list[str]:
        errors = []
        for line_no, row in self._enumerated_rows(self.colleges_path):
            if len(row) != 2:
                errors.append(f"colleges.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '필드 수 오류'")
                continue
            college, major = row
            if not college or not major:
                errors.append(f"colleges.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '빈 필드'")
        return errors

    def _check_config_syntax(self) -> list[str]:
        errors = []
        rows = list(self._enumerated_rows(self.config_path))
        if len(rows) != 1:
            errors.append(f"config.txt 1행 - 문법 형식이 올바르지 않습니다: '행 수는 정확히 1이어야 함'")
            return errors
        line_no, row = rows[0]
        if len(row) != 2:
            errors.append(f"config.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '필드 수 오류'")
            return errors
        start_s, end_s = row
        try:
            start = date.fromisoformat(start_s)
        except ValueError:
            errors.append(f"config.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '시작일 형식 오류'")
            start = None
        try:
            end = date.fromisoformat(end_s)
        except ValueError:
            errors.append(f"config.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '종료일 형식 오류'")
            end = None
        lo = date(2000, 1, 1)
        hi = date(2099, 12, 31)
        if start and not (lo <= start <= hi):
            errors.append(f"config.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '시작일 범위 오류(2000~2099)'")
        if end and not (lo <= end <= hi):
            errors.append(f"config.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '종료일 범위 오류(2000~2099)'")
        if start and end and end < start:
            errors.append(f"config.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '종료일은 시작일과 같거나 이후'")
        return errors

    def _check_referential_integrity(self) -> list[str]:
        errors: list[str] = []
        students = self.load_students()
        courses = self.load_courses()
        colleges = self.load_colleges()

        flat_majors: set[tuple[str, str]] = set()
        for college, majors in colleges.items():
            for major in majors:
                flat_majors.add((college, major))

        for student in students.values():
            if (student.college, student.major) not in flat_majors:
                errors.append(
                    f"참조 무결성 위반 - students.txt에서 존재하지 않는 단과대/전공을 참조하고 있습니다."
                )
                break

        for row in self._rows(self.enrollments_path):
            if len(row) != 4:
                continue
            sid, code, section, _ = row
            if sid not in students:
                errors.append(
                    f"참조 무결성 위반 - enrollments.txt에서 존재하지 않는 학번을 참조하고 있습니다."
                )
                break
            if (code, section) not in courses:
                errors.append(
                    f"참조 무결성 위반 - enrollments.txt에서 존재하지 않는 과목코드/분반코드를 참조하고 있습니다."
                )
                break

        known_codes = {c.code for c in courses.values()}
        for row in self._rows(self.completed_path):
            if len(row) != 2:
                continue
            sid, code = row
            if sid not in students:
                errors.append(
                    f"참조 무결성 위반 - completed_courses.txt에서 존재하지 않는 학번을 참조하고 있습니다."
                )
                break
            if code not in known_codes:
                errors.append(
                    f"참조 무결성 위반 - completed_courses.txt에서 존재하지 않는 과목코드를 참조하고 있습니다."
                )
                break

        return errors

    # ------------------------------------------------------------
    # 내부 유틸
    # ------------------------------------------------------------
    @staticmethod
    def _rows(path: Path) -> list[list[str]]:
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            clean = line.lstrip("\ufeff")
            if not clean.strip():
                continue
            rows.append([part for part in clean.split(",")])
        return rows

    @staticmethod
    def _enumerated_rows(path: Path):
        if not path.exists():
            return
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            clean = line.lstrip("\ufeff")
            if not clean.strip():
                continue
            yield line_no, [part for part in clean.split(",")]

    @staticmethod
    def _write_lines(path: Path, lines: list[str]) -> None:
        text = "\n".join(lines)
        if text:
            text += "\n"
        path.write_text(text, encoding="utf-8")

    @staticmethod
    def _parse_time(value: str) -> int:
        hour_s, minute_s = value.split(":")
        return int(hour_s) * 60 + int(minute_s)

    @staticmethod
    def _format_time(value: int) -> str:
        return f"{value // 60:02d}:{value % 60:02d}"

    @staticmethod
    def _check_hhmm(value: str) -> int | None:
        if not re.fullmatch(r"\d{2}:\d{2}", value):
            return None
        hour = int(value[:2])
        minute = int(value[3:])
        if hour < 0 or hour > 23:
            return None
        if minute not in (0, 30):
            return None
        return hour * 60 + minute
