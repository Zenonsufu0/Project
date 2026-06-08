import re
from datetime import date
from pathlib import Path

from major_basics.modules.models import (
    Admin,
    Classroom,
    Config,
    Course,
    Enrollment,
    Schedule,
    Student,
    VALID_DAYS,
    default_semester,
)


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
        self.schedules_path = data_dir / "schedules.txt"          # ★2차 추가
        self.classrooms_path = data_dir / "classrooms.txt"        # ★2차 추가
        self.prerequisites_path = data_dir / "prerequisites.txt"  # ★2차 추가

    def ensure_defaults(self, current_date: date) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        sem = default_semester(current_date)

        if not self.students_path.exists():
            self.students_path.write_text("", encoding="utf-8")

        if not self.admins_path.exists():
            self.admins_path.write_text("admin01,Admin@1234,관리자\n", encoding="utf-8")

        if not self.courses_path.exists():
            # 기획서 5.2.3: 기본 과목 6개 (요일·시각 제거, 학기·제한학년·제한학과 추가)
            self.courses_path.write_text(
                f"1001,01,프로그래밍기초,3,김교수,active,30,{sem},0,전체\n"
                f"1001,02,프로그래밍기초,3,이교수,active,30,{sem},0,전체\n"
                f"1002,01,자료구조,3,박교수,active,25,{sem},2,컴퓨터공학부\n"
                f"1003,01,알고리즘,3,최교수,active,20,{sem},3,컴퓨터공학부\n"
                f"2001,01,영어회화,2,존교수,active,40,{sem},0,전체\n"
                f"3001,01,미적분학,3,정교수,active,35,{sem},0,전체\n",
                encoding="utf-8",
            )

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
            text = f"{current_date.isoformat()},{current_date.isoformat()},{sem}\n"
            self.config_path.write_text(text, encoding="utf-8")

        if not self.classrooms_path.exists():
            # 기획서 5.2.7: 기본 강의실 3개
            self.classrooms_path.write_text(
                "1001,공학관,101,60\n"
                "1002,공학관,201,80\n"
                "1003,과학관,102,40\n",
                encoding="utf-8",
            )

        if not self.schedules_path.exists():
            # 기획서 5.2.3: 기본 스케줄
            self.schedules_path.write_text(
                "1001,01,MON,09:00,10:30,1001\n"
                "1001,01,WED,09:00,10:30,1001\n"
                "1001,02,TUE,13:00,14:30,1002\n"
                "1001,02,THU,13:00,14:30,1002\n"
                "1002,01,MON,13:00,14:30,1003\n"
                "1002,01,WED,13:00,14:30,1003\n"
                "1003,01,FRI,10:30,12:00,1001\n"
                "2001,01,TUE,10:30,12:00,1002\n"
                "3001,01,THU,09:00,10:30,1003\n",
                encoding="utf-8",
            )

        if not self.prerequisites_path.exists():
            # 기획서 5.2.3: 알고리즘(1003)의 선수과목은 자료구조(1002)
            self.prerequisites_path.write_text("1003,1002\n", encoding="utf-8")

    # ------------------------------------------------------------
    # students
    # ------------------------------------------------------------
    def load_students(self) -> dict[str, Student]:
        students: dict[str, Student] = {}
        for row in self._rows(self.students_path):
            if len(row) != 7:
                continue
            try:
                grade = int(row[6])
            except ValueError:
                continue
            student = Student(row[0], row[1], row[2], row[3], row[4], row[5], grade)
            students[student.student_id] = student
        return students

    def save_students(self, students: dict[str, Student]) -> None:
        lines = []
        for student in sorted(students.values(), key=lambda x: x.student_id):
            lines.append(
                f"{student.student_id},{student.password},{student.name},"
                f"{student.college},{student.major},{student.status},{student.grade}"
            )
        self._write_lines(self.students_path, lines)

    # ------------------------------------------------------------
    # admins
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # courses (★요일·시각 제거, 학기·제한학년·제한학과 추가 → 10 필드)
    # ------------------------------------------------------------
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
                    status=row[5],
                    capacity=int(row[6]),
                    semester=row[7],
                    limit_grade=int(row[8]),
                    limit_major=row[9],
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
                f"{course.status},{course.capacity},{course.semester},{course.limit_grade},{course.limit_major}"
            )
        self._write_lines(self.courses_path, lines)

    # ------------------------------------------------------------
    # schedules (★2차 신규)
    # ------------------------------------------------------------
    def load_schedules(self) -> dict[tuple[str, str], list[Schedule]]:
        schedules: dict[tuple[str, str], list[Schedule]] = {}
        for row in self._rows(self.schedules_path):
            if len(row) != 6:
                continue
            start = self._parse_time_safe(row[3])
            end = self._parse_time_safe(row[4])
            if start is None or end is None:
                continue
            schedule = Schedule(
                course_code=row[0],
                section=row[1],
                day=row[2].upper(),
                start_time=start,
                end_time=end,
                classroom_code=row[5],
            )
            schedules.setdefault(schedule.course_key(), []).append(schedule)
        for bucket in schedules.values():
            bucket.sort(key=lambda s: self._day_rank(s.day))
        return schedules

    def save_schedules(self, schedules: dict[tuple[str, str], list[Schedule]]) -> None:
        flat: list[Schedule] = []
        for bucket in schedules.values():
            flat.extend(bucket)
        flat.sort(key=lambda s: (s.course_code, s.section, self._day_rank(s.day), s.start_time))
        lines = [
            f"{s.course_code},{s.section},{s.day},"
            f"{self._format_time(s.start_time)},{self._format_time(s.end_time)},{s.classroom_code}"
            for s in flat
        ]
        self._write_lines(self.schedules_path, lines)

    # ------------------------------------------------------------
    # classrooms (★2차 신규)
    # ------------------------------------------------------------
    def load_classrooms(self) -> dict[str, Classroom]:
        classrooms: dict[str, Classroom] = {}
        for row in self._rows(self.classrooms_path):
            if len(row) != 4:
                continue
            try:
                seats = int(row[3])
            except ValueError:
                continue
            classroom = Classroom(row[0], row[1], row[2], seats)
            classrooms[classroom.classroom_code] = classroom
        return classrooms

    def save_classrooms(self, classrooms: dict[str, Classroom]) -> None:
        lines = []
        for room in sorted(classrooms.values(), key=lambda x: x.classroom_code):
            lines.append(f"{room.classroom_code},{room.building},{room.room_number},{room.seats}")
        self._write_lines(self.classrooms_path, lines)

    # ------------------------------------------------------------
    # prerequisites (★2차 신규)
    # ------------------------------------------------------------
    def load_prerequisites(self) -> dict[str, set[str]]:
        prerequisites: dict[str, set[str]] = {}
        for row in self._rows(self.prerequisites_path):
            if len(row) != 2:
                continue
            target, prereq = row
            prerequisites.setdefault(target, set()).add(prereq)
        return prerequisites

    def save_prerequisites(self, prerequisites: dict[str, set[str]]) -> None:
        lines = []
        for target in sorted(prerequisites.keys()):
            for prereq in sorted(prerequisites[target]):
                lines.append(f"{target},{prereq}")
        self._write_lines(self.prerequisites_path, lines)

    # ------------------------------------------------------------
    # enrollments / completed / colleges
    # ------------------------------------------------------------
    def load_enrollments(self) -> list[Enrollment]:
        enrollments: list[Enrollment] = []
        for row in self._rows(self.enrollments_path):
            if len(row) != 4:
                continue
            enrollments.append(
                Enrollment(student_id=row[0], course_code=row[1], section=row[2], status=row[3])
            )
        return enrollments

    def save_enrollments(self, enrollments: list[Enrollment]) -> None:
        lines = []
        for enrollment in enrollments:
            lines.append(
                f"{enrollment.student_id},{enrollment.course_code},{enrollment.section},{enrollment.status}"
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
        for line_no, row in self._enumerated_rows(self.colleges_path):
            if len(row) != 2:
                raise IntegrityError(
                    f"colleges.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '필드 수 오류'"
                )
            college, major = row
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

    # ------------------------------------------------------------
    # config (★학기 필드 추가 → 3 필드)
    # ------------------------------------------------------------
    def load_config(self, current_date: date) -> Config:
        rows = self._rows(self.config_path)
        if not rows or len(rows[0]) not in (2, 3):
            return Config(current_date, current_date, current_date, default_semester(current_date))

        row = rows[0]
        try:
            start = date.fromisoformat(row[0])
            end = date.fromisoformat(row[1])
        except ValueError:
            start = current_date
            end = current_date

        if end < start:
            end = start

        semester = row[2] if len(row) == 3 else default_semester(current_date)
        return Config(start, end, current_date, semester)

    def save_config(self, config: Config) -> None:
        self._write_lines(
            self.config_path,
            [f"{config.reg_start.isoformat()},{config.reg_end.isoformat()},{config.semester}"],
        )

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
        errors.extend(self._check_classrooms_syntax())
        errors.extend(self._check_schedules_syntax())
        errors.extend(self._check_prerequisites_syntax())

        if errors:
            return errors

        errors.extend(self._check_referential_integrity())
        return errors

    def _check_students_syntax(self) -> list[str]:
        errors = []
        seen_ids: set[str] = set()
        for line_no, row in self._enumerated_rows(self.students_path):
            if len(row) != 7:
                errors.append(f"students.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '필드 수 오류'")
                continue
            sid, pw, name, college, major, status, grade_s = row
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
            if not (grade_s.isdigit() and 1 <= int(grade_s) <= 4):
                errors.append(f"students.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '학년 형식 오류'")
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
            code, section, name, credits_s, prof, status, capacity_s, semester, limit_grade_s, limit_major = row
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
            if status not in ("active", "inactive"):
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '상태 값 오류'")
            if not capacity_s.isdigit() or int(capacity_s) < 1:
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '정원 형식 오류'")
            if not re.fullmatch(r"20\d{2}-[12]", semester):
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '학기 형식 오류'")
            if not (limit_grade_s.isdigit() and 0 <= int(limit_grade_s) <= 4):
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '제한학년 형식 오류'")
            if not limit_major:
                errors.append(f"courses.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '제한학과 형식 오류'")
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
            errors.append("config.txt 1행 - 문법 형식이 올바르지 않습니다: '행 수는 정확히 1이어야 함'")
            return errors
        line_no, row = rows[0]
        if len(row) != 3:
            errors.append(f"config.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '필드 수 오류'")
            return errors
        start_s, end_s, semester = row
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
        if not re.fullmatch(r"20\d{2}-[12]", semester):
            errors.append(f"config.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '학기 형식 오류'")
        return errors

    def _check_classrooms_syntax(self) -> list[str]:
        errors = []
        seen: set[str] = set()
        for line_no, row in self._enumerated_rows(self.classrooms_path):
            if len(row) != 4:
                errors.append(f"classrooms.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '필드 수 오류'")
                continue
            code, building, room, seats_s = row
            if not (code.isdigit() and len(code) == 4):
                errors.append(f"classrooms.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '강의실코드 형식 오류'")
            if code in seen:
                errors.append(f"classrooms.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '강의실코드 중복'")
            seen.add(code)
            if not building or "\t" in building:
                errors.append(f"classrooms.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '건물명 형식 오류'")
            if not room or "\t" in room:
                errors.append(f"classrooms.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '강의실번호 형식 오류'")
            if not seats_s.isdigit() or int(seats_s) < 1:
                errors.append(f"classrooms.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '좌석수 형식 오류'")
        return errors

    def _check_schedules_syntax(self) -> list[str]:
        errors = []
        seen: set[tuple[str, str, str]] = set()
        for line_no, row in self._enumerated_rows(self.schedules_path):
            if len(row) != 6:
                errors.append(f"schedules.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '필드 수 오류'")
                continue
            code, section, day, start_s, end_s, classroom_code = row
            if not (code.isdigit() and len(code) == 4):
                errors.append(f"schedules.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '과목코드 형식 오류'")
            if not (section.isdigit() and len(section) == 2):
                errors.append(f"schedules.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '분반코드 형식 오류'")
            if day not in VALID_DAYS:
                errors.append(f"schedules.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '요일 형식 오류'")
            start_min = self._check_hhmm(start_s)
            end_min = self._check_hhmm(end_s)
            if start_min is None:
                errors.append(f"schedules.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '시작시각 형식 오류'")
            if end_min is None:
                errors.append(f"schedules.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '종료시각 형식 오류'")
            if start_min is not None and end_min is not None and start_min >= end_min:
                errors.append(f"schedules.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '종료시각은 시작시각보다 이후'")
            if not (classroom_code.isdigit() and len(classroom_code) == 4):
                errors.append(f"schedules.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '강의실코드 형식 오류'")
            if (code, section, day) in seen:
                errors.append(f"schedules.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '과목코드-분반코드-요일 중복'")
            seen.add((code, section, day))
        return errors

    def _check_prerequisites_syntax(self) -> list[str]:
        errors = []
        seen: set[tuple[str, str]] = set()
        for line_no, row in self._enumerated_rows(self.prerequisites_path):
            if len(row) != 2:
                errors.append(f"prerequisites.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '필드 수 오류'")
                continue
            target, prereq = row
            if not (target.isdigit() and len(target) == 4):
                errors.append(f"prerequisites.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '대상과목코드 형식 오류'")
            if not (prereq.isdigit() and len(prereq) == 4):
                errors.append(f"prerequisites.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '선수과목코드 형식 오류'")
            if target == prereq:
                errors.append(f"prerequisites.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '자기 자신을 선수과목으로 지정 불가'")
            if (target, prereq) in seen:
                errors.append(f"prerequisites.txt {line_no}행 - 문법 형식이 올바르지 않습니다: '대상-선수 과목코드 중복'")
            seen.add((target, prereq))
        return errors

    def _check_referential_integrity(self) -> list[str]:
        errors: list[str] = []
        students = self.load_students()
        courses = self.load_courses()
        colleges = self.load_colleges()
        classrooms = self.load_classrooms()

        flat_majors: set[tuple[str, str]] = set()
        major_names: set[str] = set()
        for college, majors in colleges.items():
            for major in majors:
                flat_majors.add((college, major))
                major_names.add(major)

        for student in students.values():
            if (student.college, student.major) not in flat_majors:
                errors.append(
                    "참조 무결성 위반 - students.txt에서 존재하지 않는 단과대/전공을 참조하고 있습니다."
                )
                break

        # courses.txt 제한학과
        for course in courses.values():
            if course.limit_major != "전체" and course.limit_major not in major_names:
                errors.append(
                    "참조 무결성 위반 - courses.txt에서 존재하지 않는 제한학과(전공)를 참조하고 있습니다."
                )
                break

        for row in self._rows(self.enrollments_path):
            if len(row) != 4:
                continue
            sid, code, section, _ = row
            if sid not in students:
                errors.append("참조 무결성 위반 - enrollments.txt에서 존재하지 않는 학번을 참조하고 있습니다.")
                break
            if (code, section) not in courses:
                errors.append("참조 무결성 위반 - enrollments.txt에서 존재하지 않는 과목코드/분반코드를 참조하고 있습니다.")
                break

        known_codes = {c.code for c in courses.values()}
        for row in self._rows(self.completed_path):
            if len(row) != 2:
                continue
            sid, code = row
            if sid not in students:
                errors.append("참조 무결성 위반 - completed_courses.txt에서 존재하지 않는 학번을 참조하고 있습니다.")
                break
            if code not in known_codes:
                errors.append("참조 무결성 위반 - completed_courses.txt에서 존재하지 않는 과목코드를 참조하고 있습니다.")
                break

        # schedules.txt 참조 무결성
        for row in self._rows(self.schedules_path):
            if len(row) != 6:
                continue
            code, section, _day, _s, _e, classroom_code = row
            if (code, section) not in courses:
                errors.append("참조 무결성 위반 - schedules.txt에서 존재하지 않는 과목코드/분반코드를 참조하고 있습니다.")
                break
            if classroom_code not in classrooms:
                errors.append("참조 무결성 위반 - schedules.txt에서 존재하지 않는 강의실코드를 참조하고 있습니다.")
                break

        # prerequisites.txt 참조 무결성
        for row in self._rows(self.prerequisites_path):
            if len(row) != 2:
                continue
            target, prereq = row
            if target not in known_codes or prereq not in known_codes:
                errors.append("참조 무결성 위반 - prerequisites.txt에서 존재하지 않는 과목코드를 참조하고 있습니다.")
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
            clean = line.lstrip("﻿")
            if not clean.strip():
                continue
            rows.append([part for part in clean.split(",")])
        return rows

    @staticmethod
    def _enumerated_rows(path: Path):
        if not path.exists():
            return
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            clean = line.lstrip("﻿")
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
    def _day_rank(day: str) -> int:
        return {"MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5}.get(day, 99)

    @staticmethod
    def _parse_time_safe(value: str) -> int | None:
        if not re.fullmatch(r"\d{2}:\d{2}", value):
            return None
        hour = int(value[:2])
        minute = int(value[3:])
        if hour < 0 or hour > 23 or minute not in (0, 30):
            return None
        return hour * 60 + minute

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
