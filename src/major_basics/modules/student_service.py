from major_basics.modules.models import (
    Classroom,
    Config,
    Course,
    DAY_ORDER,
    Enrollment,
    Schedule,
    Student,
)


class StudentService:
    MAX_CREDITS = 18

    def __init__(
        self,
        student: Student,
        courses: dict[tuple[str, str], Course],
        enrollments: list[Enrollment],
        completed: dict[str, set[str]],
        config: Config,
        schedules: dict[tuple[str, str], list[Schedule]],   # ★2차 추가
        classrooms: dict[str, Classroom],                   # ★2차 추가
        prerequisites: dict[str, set[str]],                 # ★2차 추가
    ) -> None:
        self.student = student
        self.courses = courses
        self.enrollments = enrollments
        self.completed = completed
        self.config = config
        self.schedules = schedules
        self.classrooms = classrooms
        self.prerequisites = prerequisites

    def list_courses(self) -> list[Course]:
        # ★2차: 현재 학기(config.semester) 일치 과목만 반환
        result = [
            course
            for course in self.courses.values()
            if course.status == "active" and course.semester == self.config.semester
        ]
        return sorted(result, key=lambda course: (course.code, course.section))

    def search_courses(self, keyword: str) -> list[Course]:
        key = keyword.lower()
        return [
            course
            for course in self.list_courses()
            if key in course.name.lower()
            or key in course.code.lower()
            or key in course.section.lower()
        ]

    def list_completed(self) -> list[str]:
        return sorted(self.completed.get(self.student.student_id, set()))

    def add_completed(self, course_code: str) -> tuple[bool, str]:
        if not self._course_code_exists(course_code):
            return False, "!!! 오류: 존재하지 않는 과목코드입니다."

        bucket = self.completed.setdefault(self.student.student_id, set())
        if course_code in bucket:
            return False, "!!! 오류: 이미 기이수 처리된 과목입니다."

        bucket.add(course_code)
        return True, "✓ 기이수 과목 등록 완료"

    def is_retake(self, course_code: str) -> bool:
        return course_code in self.completed.get(self.student.student_id, set())

    def schedules_of(self, key: tuple[str, str]) -> list[Schedule]:
        return self.schedules.get(key, [])

    def register(self, course_code: str, section: str) -> tuple[bool, str, bool]:
        """Returns (ok, message, is_retake). 11단계 순차 검사 (설계 9.3)."""
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

        # 6단계 — 스케줄 충돌 확인
        conflict = self._find_schedule_conflict(self.schedules_of(key))
        if conflict is not None:
            conflict_course = self.courses.get(conflict.course_key())
            conflict_name = conflict_course.name if conflict_course else "(알 수 없음)"
            return (
                False,
                f"!!! 오류: 스케줄 충돌 - {conflict_name} ({conflict.day} {conflict.time_text()})과 겹칩니다.",
                False,
            )

        # 7단계 — 최대 학점 확인
        if self.current_credits() + course.credits > self.MAX_CREDITS:
            return False, f"!!! 오류: 최대 신청 학점({self.MAX_CREDITS})을 초과합니다.", False

        # 8단계 — 현재 학기 일치 확인 ★2차
        if not self._check_semester(course):
            return False, f"!!! 오류: 현재 학기({self.config.semester})에 개설된 과목이 아닙니다.", False

        # 9단계 — 학년 제한 확인 ★2차
        if not self._check_grade_limit(course):
            return False, f"!!! 오류: 이 과목은 {course.limit_grade}학년 학생만 수강신청할 수 있습니다.", False

        # 10단계 — 학과 제한 확인 ★2차
        if not self._check_major_limit(course):
            return False, f"!!! 오류: 이 과목은 {course.limit_major} 학생만 수강신청할 수 있습니다.", False

        # 11단계 — 선수과목 이수 확인 ★2차
        missing = self._check_prerequisites(course_code)
        if missing:
            names = ", ".join(missing)
            return False, f"!!! 오류: 선수과목을 이수하지 않았습니다. 미이수 선수과목: {names}", False

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
        return [e for e in self.enrollments if e.student_id == self.student.student_id]

    def timetable(self) -> list[tuple[Course, Schedule]]:
        """enrolled 과목의 모든 스케줄을 (요일, 시작시각, 과목코드, 분반) 오름차순으로 반환."""
        result: list[tuple[Course, Schedule]] = []
        for key in self._active_enrolled_map().keys():
            course = self.courses.get(key)
            if not course:
                continue
            for schedule in self.schedules.get(key, []):
                result.append((course, schedule))
        return sorted(
            result,
            key=lambda pair: (
                DAY_ORDER.get(pair[1].day, 99),
                pair[1].start_time,
                pair[0].code,
                pair[0].section,
            ),
        )

    def current_credits(self) -> int:
        # 동일 과목(분반 단위 key)의 학점은 1회만 합산 (스케줄이 여러 개여도 중복 없음)
        total = 0
        for key in self._active_enrolled_map().keys():
            course = self.courses.get(key)
            if course:
                total += course.credits
        return total

    def is_registration_open(self) -> bool:
        return self.config.reg_start <= self.config.current_date <= self.config.reg_end

    # ------------------------------------------------------------
    # 2차 보조 검사 메서드
    # ------------------------------------------------------------
    def _check_semester(self, course: Course) -> bool:
        return course.semester == self.config.semester

    def _check_grade_limit(self, course: Course) -> bool:
        if course.limit_grade == 0:
            return True
        return course.limit_grade == self.student.grade

    def _check_major_limit(self, course: Course) -> bool:
        if course.limit_major == "전체":
            return True
        return course.limit_major == self.student.major

    def _check_prerequisites(self, course_code: str) -> list[str]:
        """미이수 선수과목의 과목명 목록 반환 (모두 이수했으면 빈 목록)."""
        required = self.prerequisites.get(course_code, set())
        done = self.completed.get(self.student.student_id, set())
        missing_codes = [code for code in sorted(required) if code not in done]
        return [self._course_name(code) for code in missing_codes]

    def _find_schedule_conflict(self, target_schedules: list[Schedule]) -> Schedule | None:
        enrolled = self._enrolled_schedules()
        for ts in target_schedules:
            for es in enrolled:
                if ts.day != es.day:
                    continue
                if ts.start_time < es.end_time and es.start_time < ts.end_time:
                    return es
        return None

    def _enrolled_schedules(self) -> list[Schedule]:
        result: list[Schedule] = []
        for key in self._active_enrolled_map().keys():
            result.extend(self.schedules.get(key, []))
        return result

    def _course_name(self, code: str) -> str:
        for course in self.courses.values():
            if course.code == code:
                return f"[{code}] {course.name}"
        return f"[{code}]"

    def _course_code_exists(self, code: str) -> bool:
        return any(course.code == code for course in self.courses.values())

    def _active_enrolled_map(self) -> dict[tuple[str, str], Enrollment]:
        state: dict[tuple[str, str], Enrollment] = {}
        for enrollment in self.enrollments:
            if enrollment.student_id != self.student.student_id:
                continue
            state[enrollment.key()] = enrollment
        return {key: e for key, e in state.items() if e.status == "enrolled"}

    def _count_course_enrolled(self, key: tuple[str, str]) -> int:
        latest: dict[tuple[str, tuple[str, str]], str] = {}
        for enrollment in self.enrollments:
            latest[(enrollment.student_id, enrollment.key())] = enrollment.status

        count = 0
        for (_, course_key), status in latest.items():
            if course_key == key and status == "enrolled":
                count += 1
        return count
