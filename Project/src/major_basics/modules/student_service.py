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
            if key in course.name.lower()
        ]

    def list_completed(self) -> list[str]:
        return sorted(self.completed.get(self.student.student_id, set()))

    # student_service.py

    def add_completed(self, course: Course) -> tuple[bool, str, bool]:
        """
        [6.8.2 기이수 과목 추가]
        반환값: (성공여부, 메시지, 확인창필요여부)
        """
        # 1. 의미 규칙: 중복 추가 방지
        completed_set = self.completed.get(self.student.student_id, set())
        if course.code in completed_set:
            # 기획서 요구 문구: !!! 오류: 이미 기이수 처리된 과목입니다.
            return False, "!!! 오류: 이미 기이수 처리된 과목입니다.", False

        # 2. 추가 확인: 현재 수강신청 중(enrolled)인 경우 (self.timetable() 활용)
        is_enrolled = any(c.code == course.code for c in self.timetable())
        if is_enrolled:
            # 기획서 요구 문구: 이 과목은 현재 수강신청 중입니다. 기이수로 추가하시겠습니까?
            return True, "이 과목은 현재 수강신청 중입니다. 기이수로 추가하시겠습니까?", True

        # 3. 정상 처리 (수강 중이 아닐 때 바로 추가)
        self._save_to_completed_set(course.code)
        return True, f"기이수 과목으로 추가되었습니다: [{course.name}]", False

    def confirm_add_completed(self, course: Course) -> str:
        """사용자가 확인창에서 '1(예)'을 선택했을 때 실행되는 최종 저장 로직"""
        self._save_to_completed_set(course.code)
        return f"기이수 과목으로 추가되었습니다: [{course.name}]"

    def _save_to_completed_set(self, course_code: str):
        """내부 저장 보조 메서드"""
        if self.student.student_id not in self.completed:
            self.completed[self.student.student_id] = set()
        self.completed[self.student.student_id].add(course_code)

    def is_retake(self, course_code: str) -> bool:
        return course_code in self.completed.get(self.student.student_id, set())

    def register(self, course_code: str, section: str) -> tuple[bool, str, bool]:
        """Returns (ok, message, is_retake). Checks follow 기획서 6.9 순서."""
        if not self.is_registration_open():
            return False, "!!! 안내: 현재 수강신청 기간이 아닙니다.", False

        # 1단계 — 과목 존재 여부 확인
        if not self._course_code_exists(course_code):
            return False, "!!! 오류: 존재하지 않는 과목코드입니다.", False

        # 2단계 — 분반 존재 여부 확인
        key = (course_code, section)
        course = self.courses.get(key)
        if not course:
            return False, "!!! 오류: 존재하지 않는 분반입니다.", False

        # 3단계 — active 상태 확인
        if course.status != "active":
            return False, "!!! 오류: 현재 신청 불가능한(inactive) 과목입니다.", False

        # 4단계 — 중복 신청 확인 (같은 과목코드 기준 — 다른 분반 포함)
        active_map = self._active_enrolled_map()
        if key in active_map:
            return False, "!!! 오류: 이미 신청한 과목입니다.", False
        for (c, _s) in active_map.keys():
            if c == course_code:
                return False, "!!! 오류: 이미 신청한 과목입니다.", False

        # 5단계 — 정원 초과 확인
        if self._count_course_enrolled(key) >= course.capacity:
            return False, "!!! 오류: 해당 과목의 정원이 마감되었습니다.", False

        # 6단계 — 시간표 충돌 확인
        conflict = self._find_time_conflict(course)
        if conflict is not None:
            return (
                False,
                f"!!! 오류: 시간표 충돌 - {conflict.name} ({conflict.day} {conflict.time_text()})과 겹칩니다.",
                False,
            )

        # 7단계 — 최대 학점 확인
        if self.current_credits() + course.credits > self.MAX_CREDITS:
            return False, f"!!! 오류: 최대 신청 학점({self.MAX_CREDITS})을 초과합니다.", False

        self.enrollments.append(
            Enrollment(self.student.student_id, course_code, section, "enrolled")
        )

        retake = self.is_retake(course_code)
        message = f"✓ 수강신청 완료: {course.name}"
        if retake:
            message += "\n안내: 재수강 과목입니다."
        return True, message, retake

    def cancel(self, course_code: str, section: str) -> tuple[bool, str]:
        if not self.is_registration_open():
            return False, "!!! 안내: 현재 수강신청 기간이 아닙니다."

        key = (course_code, section)
        active = self._active_enrolled_map()
        if key not in active:
            return False, "!!! 오류: 현재 신청 상태가 아닙니다."

        course = self.courses.get(key)
        name = course.name if course else f"{course_code}-{section}"

        self.enrollments.append(
            Enrollment(self.student.student_id, course_code, section, "cancelled")
        )
        return True, f"✓ 수강취소 완료: {name}"

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
