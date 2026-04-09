from datetime import date
from pathlib import Path

from major_basics.modules.models import Admin, Config, Course, Enrollment, Student


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
            self.students_path.write_text(
                "202111376,Abc12345!,홍길동,공과대학,컴퓨터공학부,active\n",
                encoding="utf-8",
            )

        if not self.admins_path.exists():
            self.admins_path.write_text("admin01,Admin@1234,관리자\n", encoding="utf-8")

        if not self.courses_path.exists():
            self.courses_path.write_text(
                "1001,01,프로그래밍기초,3,김교수,MON,09:00,10:30,active,30\n"
                "1001,02,프로그래밍기초,3,김교수,TUE,09:00,10:30,active,30\n"
                "1002,01,자료구조,3,이교수,WED,10:30,12:00,active,30\n"
                "1003,01,영어회화,2,Park,FRI,14:00,15:30,active,30\n"
                "1004,03,파이썬프로그래밍,2,최교수,TUE,13:00,14:30,active,30\n",
                encoding="utf-8",
            )

        if not self.enrollments_path.exists():
            self.enrollments_path.write_text("", encoding="utf-8")

        if not self.completed_path.exists():
            self.completed_path.write_text("202111376,1001\n", encoding="utf-8")

        if not self.colleges_path.exists():
            self.colleges_path.write_text(
                "공과대학,컴퓨터공학부|전기공학부|기계공학부\n"
                "문과대학,국어국문학과|영어영문학과|사학과\n"
                "이과대학,수학과|물리학과|화학과\n",
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
            if len(row) != 5:
                continue
            enrollments.append(
                Enrollment(
                    student_id=row[0],
                    course_code=row[1],
                    section=row[2],
                    status=row[3],
                    is_retake=(row[4] == "Y"),
                )
            )
        return enrollments

    def save_enrollments(self, enrollments: list[Enrollment]) -> None:
        lines = []
        for enrollment in enrollments:
            retake = "Y" if enrollment.is_retake else "N"
            lines.append(
                f"{enrollment.student_id},{enrollment.course_code},{enrollment.section},"
                f"{enrollment.status},{retake}"
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
                continue
            majors = [major.strip() for major in row[1].split("|") if major.strip()]
            colleges[row[0]] = majors
        return colleges

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

    @staticmethod
    def _rows(path: Path) -> list[list[str]]:
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            clean = line.lstrip("\ufeff").strip()
            if not clean or clean.startswith("#"):
                continue
            rows.append([part.strip() for part in clean.split(",")])
        return rows

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
