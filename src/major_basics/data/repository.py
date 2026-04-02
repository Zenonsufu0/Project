from pathlib import Path

from major_basics.models.admin import Admin
from major_basics.models.course import Course
from major_basics.models.enrollment import EnrollmentRecord
from major_basics.models.student import Student


class FileRepository:
    """Simple text-file repository following the planning document layout."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.students_file = data_dir / "students.txt"
        self.admins_file = data_dir / "admins.txt"
        self.courses_file = data_dir / "courses.txt"
        self.completed_file = data_dir / "completed_courses.txt"
        self.enrollments_file = data_dir / "enrollments.txt"

    def bootstrap_if_missing(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if not self.students_file.exists():
            self.students_file.write_text(
                "20260001,1234,홍길동,공과대학,컴퓨터공학부,active\n",
                encoding="utf-8",
            )
        if not self.admins_file.exists():
            self.admins_file.write_text("admin,admin123,관리자\n", encoding="utf-8")
        if not self.courses_file.exists():
            self.courses_file.write_text(
                "1001,프로그래밍기초,3,김교수,MON,900,1030,major_required,active\n"
                "1002,자료구조,3,이교수,MON,1000,1130,major_required,active\n"
                "1003,영어회화,2,박교수,TUE,1300,1430,general_elective,active\n"
                "1004,파이썬프로그래밍,2,최교수,WED,900,1030,major_elective,active\n",
                encoding="utf-8",
            )
        if not self.completed_file.exists():
            self.completed_file.write_text("20260001,1001\n", encoding="utf-8")
        if not self.enrollments_file.exists():
            self.enrollments_file.write_text("", encoding="utf-8")

    def load_students(self) -> dict[str, Student]:
        result: dict[str, Student] = {}
        for row in self._read_rows(self.students_file):
            if len(row) != 6:
                continue
            student = Student(
                student_id=row[0],
                password=row[1],
                name=row[2],
                college=row[3],
                major=row[4],
                status=row[5],
            )
            result[student.student_id] = student
        return result

    def save_students(self, students: dict[str, Student]) -> None:
        lines = []
        for s in students.values():
            lines.append(
                f"{s.student_id},{s.password},{s.name},{s.college},{s.major},{s.status}"
            )
        self.students_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def load_admins(self) -> dict[str, Admin]:
        result: dict[str, Admin] = {}
        for row in self._read_rows(self.admins_file):
            if len(row) != 3:
                continue
            admin = Admin(admin_id=row[0], password=row[1], name=row[2])
            result[admin.admin_id] = admin
        return result

    def load_courses(self) -> dict[str, Course]:
        result: dict[str, Course] = {}
        for row in self._read_rows(self.courses_file):
            if len(row) != 9:
                continue
            try:
                course = Course(
                    code=row[0],
                    name=row[1],
                    credits=int(row[2]),
                    professor=row[3],
                    day=row[4],
                    start_time=int(row[5]),
                    end_time=int(row[6]),
                    category=row[7],
                    status=row[8],
                )
            except ValueError:
                continue
            result[course.code] = course
        return result

    def save_courses(self, courses: dict[str, Course]) -> None:
        lines = []
        for c in courses.values():
            lines.append(
                f"{c.code},{c.name},{c.credits},{c.professor},{c.day},{c.start_time},{c.end_time},{c.category},{c.status}"
            )
        self.courses_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def load_completed(self) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for row in self._read_rows(self.completed_file):
            if len(row) != 2:
                continue
            sid, code = row[0], row[1]
            result.setdefault(sid, set()).add(code)
        return result

    def save_completed(self, completed: dict[str, set[str]]) -> None:
        lines = []
        for sid, codes in completed.items():
            for code in sorted(codes):
                lines.append(f"{sid},{code}")
        self.completed_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def load_enrollments(self) -> list[EnrollmentRecord]:
        result: list[EnrollmentRecord] = []
        for row in self._read_rows(self.enrollments_file):
            if len(row) != 4:
                continue
            result.append(
                EnrollmentRecord(
                    student_id=row[0],
                    course_code=row[1],
                    status=row[2],
                    is_retake=(row[3] == "Y"),
                )
            )
        return result

    def save_enrollments(self, enrollments: list[EnrollmentRecord]) -> None:
        lines = []
        for e in enrollments:
            retake = "Y" if e.is_retake else "N"
            lines.append(f"{e.student_id},{e.course_code},{e.status},{retake}")
        self.enrollments_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _read_rows(self, path: Path) -> list[list[str]]:
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rows.append([part.strip() for part in line.split(",")])
        return rows
