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
        # storage/main에서 불러온 원본 데이터를 참조하여 직접 수정한다.
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

        # 관리자 등록 학생은 기본적으로 active 상태로 추가한다.
        student.status = "active"
        self.students[student.student_id] = student
        return True, f"학생 등록 완료: {student.name} ({student.student_id})"

    def delete_student(self, student_id: str) -> tuple[bool, str]:
        if student_id not in self.students:
            return False, "해당 학번의 학생이 없습니다."

        if self.students[student_id].status == "inactive":
            return False, "이미 inactive 상태의 학생입니다."

        # 학생 삭제는 실제 삭제가 아니라 inactive 처리한다.
        self.students[student_id].status = "inactive"
        return True, f"학생 삭제 완료: {student_id}"

    def activate_student(self, student_id: str) -> tuple[bool, str]:
        student = self.students.get(student_id)

        if not student:
            return False, "해당 학번의 학생이 없습니다."

        if student.status == "active":
            return False, "이미 active 상태의 학생입니다."

        student.status = "active"
        return True, f"학생 활성화 완료: {student_id}"

    def add_course(self, course: Course) -> tuple[bool, str]:
        valid, msg = self._validate_course_fields(course)
        if not valid:
            return False, msg

        if course.key() in self.courses:
            return False, "이미 존재하는 개설 강의입니다."

        # 강의 등록 시 기본 상태는 active로 저장한다.
        self.courses[course.key()] = course
        return True, f"강의 등록 완료: {course.name} ({course.code}-{course.section})"

    def update_course(self, course: Course) -> tuple[bool, str]:
        # 수강신청 시작일 이후에는 강의 수정이 불가능하다.
        if self.config.current_date >= self.config.reg_start:
            return False, "수강신청 기간 중에는 강의를 수정할 수 없습니다."

        if course.key() not in self.courses:
            return False, "존재하지 않는 개설 강의입니다."

        if self.courses[course.key()].status == "inactive":
            return False, "inactive 상태의 강의는 수정할 수 없습니다. 먼저 강의를 활성화하세요."

        valid, msg = self._validate_course_fields(course)
        if not valid:
            return False, msg

        self.courses[course.key()] = course
        return True, f"강의 수정 완료: {course.name} ({course.code}-{course.section})"

    def delete_course(self, code: str, section: str) -> tuple[bool, str]:
        if not (len(code) == 4 and all("0" <= ch <= "9" for ch in code)):
            return False, "과목코드는 숫자 4자리여야 합니다."

        if not (len(section) == 2 and all("0" <= ch <= "9" for ch in section)):
            return False, "분반코드는 숫자 2자리여야 합니다."

        key = (code, section)

        if key not in self.courses:
            return False, "존재하지 않는 과목코드입니다."

        if self.courses[key].status == "inactive":
            return False, "이미 inactive 상태의 강의입니다."

        # 강의 삭제도 실제 삭제가 아니라 inactive 처리한다.
        self.courses[key].status = "inactive"
        return True, f"강의 삭제 완료: {self.courses[key].name} ({code}-{section}) → inactive 처리됨"

    def activate_course(self, code: str, section: str) -> tuple[bool, str]:
        if not (len(code) == 4 and all("0" <= ch <= "9" for ch in code)):
            return False, "과목코드는 숫자 4자리여야 합니다."

        if not (len(section) == 2 and all("0" <= ch <= "9" for ch in section)):
            return False, "분반코드는 숫자 2자리여야 합니다."

        key = (code, section)
        course = self.courses.get(key)

        if not course:
            return False, "존재하지 않는 개설 강의입니다."

        if course.status == "active":
            return False, "이미 active 상태의 강의입니다."

        course.status = "active"
        return True, f"강의 활성화 완료: {course.name} ({code}-{section})"

    def set_registration_period(self, start: date, end: date) -> tuple[bool, str]:
        if start < date(2000, 1, 1) or start > date(2099, 12, 31):
            return False, "날짜 형식이 올바르지 않습니다."

        if end < date(2000, 1, 1) or end > date(2099, 12, 31):
            return False, "날짜 형식이 올바르지 않습니다."

        if end < start:
            return False, "종료일은 시작일과 같거나 이후여야 합니다."

        self.config.reg_start = start
        self.config.reg_end = end
        return True, f"수강신청 기간 설정 완료: {start.isoformat()} ~ {end.isoformat()}"

    def enrollment_summary(self) -> list[tuple[Course, int]]:
        latest: dict[tuple[str, tuple[str, str]], str] = {}

        # 같은 학생이 같은 강의에 대해 여러 기록을 가진 경우 마지막 상태만 사용한다.
        for enrollment in self.enrollments:
            latest[(enrollment.student_id, enrollment.key())] = enrollment.status

        counts: dict[tuple[str, str], int] = {}

        # 전체 수강 현황은 enrolled 상태만 신청 인원으로 집계한다.
        for (_, key), status in latest.items():
            if status == "enrolled":
                counts[key] = counts.get(key, 0) + 1

        result: list[tuple[Course, int]] = []

        # 관리자 조회이므로 active/inactive와 관계없이 모든 강의를 출력 대상으로 반환한다.
        for key in sorted(self.courses.keys()):
            result.append((self.courses[key], counts.get(key, 0)))

        return result

    @staticmethod
    def _validate_course_fields(course: Course) -> tuple[bool, str]:
        # 강의 등록/수정에서 공통으로 사용하는 강의 필드 검증이다.
        if not (len(course.code) == 4 and all("0" <= ch <= "9" for ch in course.code)):
            return False, "과목코드는 숫자 4자리여야 합니다."

        if not (len(course.section) == 2 and all("0" <= ch <= "9" for ch in course.section)):
            return False, "분반코드는 숫자 2자리여야 합니다."

        if not course.name or "\t" in course.name or "\n" in course.name or "\r" in course.name:
            return False, "과목명은 비어 있을 수 없습니다."

        if course.credits < 1 or course.credits > 6:
            return False, "학점은 1~6 정수이어야 합니다."

        if not course.professor or "\t" in course.professor or "\n" in course.professor or "\r" in course.professor:
            return False, "담당교수는 비어 있을 수 없습니다."

        if course.day not in {"MON", "TUE", "WED", "THU", "FRI"}:
            return False, "요일은 MON, TUE, WED, THU, FRI 중 하나여야 합니다."

        if course.start_time >= course.end_time:
            return False, "종료 시각은 시작 시각보다 이후여야 합니다."

        if course.start_time % 30 != 0 or course.end_time % 30 != 0:
            return False, "시작 시각과 종료 시각의 분 값은 00 또는 30만 허용합니다."

        if course.capacity <= 0:
            return False, "정원은 1 이상의 정수여야 합니다."

        if course.status not in {"active", "inactive"}:
            return False, "상태는 active 또는 inactive만 가능합니다."

        return True, "OK"
