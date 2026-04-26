import re
from datetime import date

from major_basics.modules.models import Config, Course, Enrollment, Student, VALID_DAYS


class AdminService:
    def __init__(
        self,
        students: dict[str, Student],
        courses: dict[tuple[str, str], Course],
        enrollments: list[Enrollment],
        completed: dict[str, set[str]],
        colleges: dict[str, list[str]],
        config: Config,
    ) -> None:
        self.students = students
        self.courses = courses
        self.enrollments = enrollments
        self.completed = completed
        self.colleges = colleges
        self.config = config

    def register_student(self, student: Student) -> tuple[bool, str]:
        if not (student.student_id.isdigit() and len(student.student_id) == 9):
            return False, "!!! 오류: 학번은 숫자 9자리이어야 합니다."
        if student.student_id in self.students:
            return False, "!!! 오류: 이미 존재하는 학번입니다."
        if not re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]{6,12}", student.password):
            return False, "!!! 오류: 비밀번호는 영문자와 숫자를 각각 1자 이상 포함한 6~12자이어야 합니다."
        if not re.fullmatch(r"[가-힣]+", student.name):
            return False, "!!! 오류: 이름은 한국어 완성형 글자로만 이루어져야 합니다."
        if student.college not in self.colleges or student.major not in self.colleges[student.college]:
            return False, "!!! 오류: 단과대학/전공 정보가 올바르지 않습니다."
        if student.status not in ("active", "inactive"):
            return False, "!!! 오류: 상태 값이 올바르지 않습니다."
        self.students[student.student_id] = student
        return True, f"✓ 학생 등록 완료: {student.name} ({student.student_id})"

    def delete_student(self, student_id: str) -> tuple[bool, str]:
        student = self.students.get(student_id)
        if not student:
            return False, "!!! 오류: 해당 학번의 학생이 없습니다."
        if student.status == "inactive":
            return False, "!!! 안내: 이미 inactive 상태의 학생입니다."
        student.status = "inactive"
        return True, f"✓ 학생 삭제 완료: {student_id}"

    def activate_student(self, student_id: str) -> tuple[bool, str]:
        student = self.students.get(student_id)
        if not student:
            return False, "!!! 오류: 해당 학번의 학생이 없습니다."
        if student.status == "active":
            return False, "!!! 안내: 이미 active 상태의 학생입니다."
        student.status = "active"
        return True, f"✓ 학생 활성화 완료: {student_id}"

    def add_course(self, course: Course) -> tuple[bool, str]:
        valid, msg = self._validate_course_fields(course)
        if not valid:
            return False, msg
        if course.key() in self.courses:
            return False, "!!! 오류: 이미 존재하는 개설 강의입니다."
        self.courses[course.key()] = course
        return True, f"✓ 강의 등록 완료: {course.name} ({course.code}-{course.section})"

    def update_course(self, course: Course) -> tuple[bool, str]:
        if self.config.reg_start <= self.config.current_date <= self.config.reg_end:
            return False, "!!! 오류: 수강신청 기간 중에는 강의를 수정할 수 없습니다."
        existing = self.courses.get(course.key())
        if not existing:
            return False, "!!! 오류: 존재하지 않는 개설 강의입니다."
        if existing.status == "inactive":
            return False, "!!! 오류: inactive 상태의 강의는 수정할 수 없습니다. 먼저 강의를 활성화하세요."
        valid, msg = self._validate_course_fields(course)
        if not valid:
            return False, msg
        self.courses[course.key()] = course
        return True, f"✓ 강의 수정 완료: {course.name} ({course.code}-{course.section})"

    def delete_course(self, code: str, section: str) -> tuple[bool, str]:
        if not (code.isdigit() and len(code) == 4):
            return False, "!!! 오류: 과목코드는 숫자 4자리여야 합니다."
        if not (section.isdigit() and len(section) == 2):
            return False, "!!! 오류: 분반코드는 숫자 2자리여야 합니다."
        key = (code, section)
        course = self.courses.get(key)
        if not course:
            return False, "!!! 오류: 존재하지 않는 과목코드입니다."
        if course.status == "inactive":
            return False, "!!! 안내: 이미 inactive 상태의 강의입니다."
        course.status = "inactive"
        return True, f"✓ 강의 삭제 완료: {course.name} ({code}-{section}) → inactive 처리됨"

    def activate_course(self, code: str, section: str) -> tuple[bool, str]:
        if not (code.isdigit() and len(code) == 4):
            return False, "!!! 오류: 과목코드는 숫자 4자리여야 합니다."
        if not (section.isdigit() and len(section) == 2):
            return False, "!!! 오류: 분반코드는 숫자 2자리여야 합니다."
        key = (code, section)
        course = self.courses.get(key)
        if not course:
            return False, "!!! 오류: 존재하지 않는 개설 강의입니다."
        if course.status == "active":
            return False, "!!! 안내: 이미 active 상태의 강의입니다."
        course.status = "active"
        return True, f"✓ 강의 활성화 완료: {course.name} ({code}-{section})"

    def set_registration_period(self, start: date, end: date) -> tuple[bool, str]:
        if not (date(2000, 1, 1) <= start <= date(2099, 12, 31)):
            return False, "!!! 오류: 날짜는 2000-01-01 ~ 2099-12-31 범위여야 합니다."
        if not (date(2000, 1, 1) <= end <= date(2099, 12, 31)):
            return False, "!!! 오류: 날짜는 2000-01-01 ~ 2099-12-31 범위여야 합니다."
        if end < start:
            return False, "!!! 오류: 종료일은 시작일과 같거나 이후여야 합니다."
        self.config.reg_start = start
        self.config.reg_end = end
        return True, f"✓ 수강신청 기간 설정 완료: {start.isoformat()} ~ {end.isoformat()}"

    def enrollment_summary(self) -> list[tuple[Course, int]]:
        latest: dict[tuple[str, tuple[str, str]], str] = {}
        for enrollment in self.enrollments:
            latest[(enrollment.student_id, enrollment.key())] = enrollment.status

        counts: dict[tuple[str, str], int] = {}
        for (_, key), status in latest.items():
            if status == "enrolled":
                counts[key] = counts.get(key, 0) + 1

        result: list[tuple[Course, int]] = []
        for key in sorted(self.courses.keys()):
            result.append((self.courses[key], counts.get(key, 0)))
        return result

    @staticmethod
    def _validate_course_fields(course: Course) -> tuple[bool, str]:
        if not (course.code.isdigit() and len(course.code) == 4):
            return False, "!!! 오류: 과목코드는 숫자 4자리여야 합니다."
        if not (course.section.isdigit() and len(course.section) == 2):
            return False, "!!! 오류: 분반코드는 숫자 2자리여야 합니다."
        if not course.name or "\t" in course.name:
            return False, "!!! 오류: 과목명은 1자 이상이어야 하며 탭/개행을 포함할 수 없습니다."
        if not (1 <= course.credits <= 6):
            return False, "!!! 오류: 학점은 1 이상 6 이하의 정수여야 합니다."
        if not course.professor or "\t" in course.professor:
            return False, "!!! 오류: 담당교수는 1자 이상이어야 하며 탭/개행을 포함할 수 없습니다."
        if course.day not in VALID_DAYS:
            return False, "!!! 오류: 요일은 MON, TUE, WED, THU, FRI 중 하나여야 합니다."
        if course.start_time % 30 != 0 or course.end_time % 30 != 0:
            return False, "!!! 오류: 시각의 분은 00 또는 30만 허용됩니다."
        if course.start_time >= course.end_time:
            return False, "!!! 오류: 종료 시각은 시작 시각보다 이후여야 합니다."
        if course.capacity < 1:
            return False, "!!! 오류: 정원은 1 이상의 정수여야 합니다."
        if course.status not in ("active", "inactive"):
            return False, "!!! 오류: 상태는 active 또는 inactive여야 합니다."
        return True, "OK"
