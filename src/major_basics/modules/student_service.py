from major_basics.modules.models import Config, Course, DAY_ORDER, Enrollment, Student


class StudentService:
    MAX_CREDITS = 18

    def __init__(
        self,
        student: Student,
        courses: dict[tuple[str, str], Course],
        enrollments: list[Enrollment],
        completed: dict[str, set[str]],
        config: Config,
    ) -> None:
        self.student = student
        self.courses = courses
        self.enrollments = enrollments
        self.completed = completed
        self.config = config

    def list_courses(self) -> list[Course]:
        result = [course for course in self.courses.values() if course.status == "active"]
        return sorted(result, key=lambda course: (course.code, course.section))

    def search_courses(self, keyword: str) -> list[Course]:
        key = keyword.lower()
        return [
            course
            for course in self.list_courses()
            if key in course.code.lower() or key in course.section.lower() or key in course.name.lower()
        ]

    def list_completed(self) -> list[str]:
        return sorted(self.completed.get(self.student.student_id, set()))

    def add_completed(self, course_code: str) -> tuple[bool, str]:
        if not self._course_code_exists(course_code):
            return False, "존재하지 않는 과목코드입니다."

        bucket = self.completed.setdefault(self.student.student_id, set())
        if course_code in bucket:
            return False, "이미 기이수 과목으로 등록되어 있습니다."

        bucket.add(course_code)
        return True, "기이수 과목 등록 완료"

    def register(self, course_code: str, section: str) -> tuple[bool, str]:
        if not self.is_registration_open():
            return False, "수강신청 기간이 아닙니다."

        key = (course_code, section)
        course = self.courses.get(key)
        if not course or course.status != "active":
            return False, "신청 가능한 강의가 아닙니다."

        if key in self._active_enrolled_map():
            return False, "이미 신청한 강의입니다."

        if self.current_credits() + course.credits > self.MAX_CREDITS:
            return False, "최대 신청 학점(18학점)을 초과합니다."

        if self._count_course_enrolled(key) >= course.capacity:
            return False, "정원이 가득 찼습니다."

        conflict = self._find_time_conflict(course)
        if conflict is not None:
            return False, f"시간표 충돌: {conflict.code}-{conflict.section} {conflict.time_text()}"

        is_retake = course_code in self.completed.get(self.student.student_id, set())
        self.enrollments.append(
            Enrollment(self.student.student_id, course_code, section, "enrolled", is_retake)
        )

        if is_retake:
            return True, "수강신청 완료 (재수강 Y)"
        return True, "수강신청 완료"

    def cancel(self, course_code: str, section: str) -> tuple[bool, str]:
        if not self.is_registration_open():
            return False, "수강신청 기간이 아닙니다."

        key = (course_code, section)
        active = self._active_enrolled_map()
        record = active.get(key)
        if record is None:
            return False, "현재 신청 상태가 아닙니다."

        self.enrollments.append(
            Enrollment(self.student.student_id, course_code, section, "cancelled", record.is_retake)
        )
        return True, "수강취소 완료"

    def enrollment_history(self) -> list[Enrollment]:
        return [enrollment for enrollment in self.enrollments if enrollment.student_id == self.student.student_id]

    def timetable(self) -> list[Course]:
        active = self._active_enrolled_map()
        courses = []
        for key in active.keys():
            course = self.courses.get(key)
            if course:
                courses.append(course)
        return sorted(
            courses,
            key=lambda course: (
                DAY_ORDER.get(course.day, 99),
                course.start_time,
                course.code,
                course.section,
            ),
        )

    def current_credits(self) -> int:
        return sum(course.credits for course in self.timetable())

    def is_registration_open(self) -> bool:
        return self.config.reg_start <= self.config.current_date <= self.config.reg_end

    def _course_code_exists(self, code: str) -> bool:
        return any(course.code == code for course in self.courses.values())

    def _active_enrolled_map(self) -> dict[tuple[str, str], Enrollment]:
        state: dict[tuple[str, str], Enrollment] = {}
        for enrollment in self.enrollments:
            if enrollment.student_id != self.student.student_id:
                continue
            state[enrollment.key()] = enrollment
        return {key: enrollment for key, enrollment in state.items() if enrollment.status == "enrolled"}

    def _count_course_enrolled(self, key: tuple[str, str]) -> int:
        latest: dict[tuple[str, tuple[str, str]], str] = {}
        for enrollment in self.enrollments:
            latest[(enrollment.student_id, enrollment.key())] = enrollment.status

        count = 0
        for (_, course_key), status in latest.items():
            if course_key == key and status == "enrolled":
                count += 1
        return count

    def _find_time_conflict(self, target: Course) -> Course | None:
        for enrolled_course in self.timetable():
            if enrolled_course.day != target.day:
                continue
            if target.start_time < enrolled_course.end_time and enrolled_course.start_time < target.end_time:
                return enrolled_course
        return None
