from major_basics.models.course import Course
from major_basics.models.enrollment import EnrollmentRecord
from major_basics.models.student import Student
from major_basics.services.schedule_utils import is_time_overlap


class RegistrationManager:
    MAX_CREDITS = 18

    def __init__(
        self,
        student: Student,
        courses: dict[str, Course],
        completed: dict[str, set[str]],
        enrollments: list[EnrollmentRecord],
    ) -> None:
        self.student = student
        self.courses = courses
        self.completed = completed
        self.enrollments = enrollments

    def list_active_courses(self) -> list[Course]:
        return [c for c in self.courses.values() if c.status == "active"]

    def search_courses(self, keyword: str) -> list[Course]:
        key = keyword.lower()
        return [
            c for c in self.list_active_courses() if key in c.name.lower() or key in c.code.lower()
        ]

    def get_completed_courses(self) -> list[str]:
        return sorted(self.completed.get(self.student.student_id, set()))

    def add_completed_course(self, course_code: str) -> tuple[bool, str]:
        if course_code not in self.courses:
            return False, "존재하지 않는 과목코드입니다."
        bucket = self.completed.setdefault(self.student.student_id, set())
        if course_code in bucket:
            return False, "이미 기이수 과목으로 등록되어 있습니다."
        bucket.add(course_code)
        return True, "기이수 과목 등록 완료."

    def register_course(self, course_code: str) -> tuple[bool, str]:
        course = self.courses.get(course_code)
        if not course or course.status != "active":
            return False, "신청 가능한 과목이 아닙니다."

        if self._is_currently_enrolled(course_code):
            return False, "이미 신청한 과목입니다."

        conflict = self._find_conflict(course)
        if conflict is not None:
            return False, f"시간표 충돌: {conflict.code} {conflict.schedule_text()}"

        if self.current_credits() + course.credits > self.MAX_CREDITS:
            return False, f"최대 신청 학점({self.MAX_CREDITS})을 초과합니다."

        is_retake = course_code in self.completed.get(self.student.student_id, set())
        self.enrollments.append(
            EnrollmentRecord(
                student_id=self.student.student_id,
                course_code=course_code,
                status="enrolled",
                is_retake=is_retake,
            )
        )

        if is_retake:
            return True, "신청 완료 (재수강 Y)."
        return True, "신청 완료."

    def cancel_course(self, course_code: str) -> tuple[bool, str]:
        active = self._latest_active_record(course_code)
        if active is None:
            return False, "현재 신청 내역에 없는 과목입니다."

        self.enrollments.append(
            EnrollmentRecord(
                student_id=self.student.student_id,
                course_code=course_code,
                status="cancelled",
                is_retake=active.is_retake,
            )
        )
        return True, "수강취소 완료."

    def current_credits(self) -> int:
        total = 0
        for code in self.current_enrolled_course_codes():
            course = self.courses.get(code)
            if course:
                total += course.credits
        return total

    def current_enrolled_course_codes(self) -> list[str]:
        state: dict[str, str] = {}
        for record in self.enrollments:
            if record.student_id != self.student.student_id:
                continue
            state[record.course_code] = record.status
        return [code for code, status in state.items() if status == "enrolled"]

    def enrollment_history(self) -> list[EnrollmentRecord]:
        return [r for r in self.enrollments if r.student_id == self.student.student_id]

    def timetable_courses(self) -> list[Course]:
        result: list[Course] = []
        for code in self.current_enrolled_course_codes():
            c = self.courses.get(code)
            if c:
                result.append(c)
        return sorted(result, key=lambda c: (c.day, c.start_time))

    def _is_currently_enrolled(self, course_code: str) -> bool:
        return course_code in self.current_enrolled_course_codes()

    def _latest_active_record(self, course_code: str) -> EnrollmentRecord | None:
        latest: EnrollmentRecord | None = None
        for record in self.enrollment_history():
            if record.course_code != course_code:
                continue
            latest = record
        if latest and latest.status == "enrolled":
            return latest
        return None

    def _find_conflict(self, target: Course) -> Course | None:
        for code in self.current_enrolled_course_codes():
            enrolled = self.courses.get(code)
            if enrolled and is_time_overlap(target, enrolled):
                return enrolled
        return None
