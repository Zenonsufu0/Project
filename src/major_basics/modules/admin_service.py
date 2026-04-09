from datetime import date

from major_basics.modules.models import Config, Course, Enrollment, Student


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
        if student.student_id in self.students:
            return False, "이미 존재하는 학번입니다."
        if student.college not in self.colleges or student.major not in self.colleges[student.college]:
            return False, "단과대학/전공 정보가 올바르지 않습니다."
        self.students[student.student_id] = student
        return True, "학생 등록 완료"

    def delete_student(self, student_id: str) -> tuple[bool, str]:
        if student_id not in self.students:
            return False, "존재하지 않는 학번입니다."
        del self.students[student_id]
        self.completed.pop(student_id, None)
        self.enrollments[:] = [enrollment for enrollment in self.enrollments if enrollment.student_id != student_id]
        return True, "학생 삭제 완료"

    def activate_student(self, student_id: str) -> tuple[bool, str]:
        student = self.students.get(student_id)
        if not student:
            return False, "존재하지 않는 학번입니다."
        student.status = "active"
        return True, "학생 활성화 완료"

    def add_course(self, course: Course) -> tuple[bool, str]:
        valid, msg = self._validate_course_fields(course)
        if not valid:
            return False, msg
        if course.key() in self.courses:
            return False, "이미 존재하는 과목코드-분반코드 조합입니다."
        self.courses[course.key()] = course
        return True, "강의 등록 완료"

    def update_course(self, course: Course) -> tuple[bool, str]:
        if self.config.current_date >= self.config.reg_start:
            return False, "강의 수정은 수강신청 시작 전까지만 가능합니다."
        if course.key() not in self.courses:
            return False, "존재하지 않는 과목코드-분반코드입니다."
        valid, msg = self._validate_course_fields(course)
        if not valid:
            return False, msg
        self.courses[course.key()] = course
        return True, "강의 수정 완료"

    def delete_course(self, code: str, section: str) -> tuple[bool, str]:
        key = (code, section)
        if key not in self.courses:
            return False, "존재하지 않는 과목코드-분반코드입니다."
        del self.courses[key]
        return True, "강의 삭제 완료"

    def activate_course(self, code: str, section: str) -> tuple[bool, str]:
        key = (code, section)
        course = self.courses.get(key)
        if not course:
            return False, "존재하지 않는 과목코드-분반코드입니다."
        course.status = "active"
        return True, "강의 활성화 완료"

    def set_registration_period(self, start: date, end: date) -> tuple[bool, str]:
        if end < start:
            return False, "종료일은 시작일보다 빠를 수 없습니다."
        self.config.reg_start = start
        self.config.reg_end = end
        return True, "수강신청 기간 설정 완료"

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
            return False, "과목코드는 숫자 4자리여야 합니다."
        if not (course.section.isdigit() and len(course.section) == 2):
            return False, "분반코드는 숫자 2자리여야 합니다."
        if course.credits <= 0:
            return False, "학점은 1 이상이어야 합니다."
        if course.day not in {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}:
            return False, "요일은 MON~SUN 형식이어야 합니다."
        if course.start_time >= course.end_time:
            return False, "종료 시각은 시작 시각보다 늦어야 합니다."
        if course.capacity <= 0:
            return False, "정원은 1 이상이어야 합니다."
        if course.status not in {"active", "inactive"}:
            return False, "상태는 active 또는 inactive만 가능합니다."
        return True, "OK"
