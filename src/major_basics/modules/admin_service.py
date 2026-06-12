# admin_service.py — 학생·강의·강의실 관리와 수강신청 기간 설정 규칙 담당 (구현: 신경환)
import re
from datetime import date

from major_basics.modules.models import (
    Classroom,
    Config,
    Course,
    Enrollment,
    Schedule,
    Student,
    VALID_DAYS,
)


class AdminService:
    def __init__(
        self,
        students: dict[str, Student],
        courses: dict[tuple[str, str], Course],
        enrollments: list[Enrollment],
        completed: dict[str, set[str]],
        colleges: dict[str, list[str]],
        config: Config,
        schedules: dict[tuple[str, str], list[Schedule]],   # ★2차 추가
        classrooms: dict[str, Classroom],                   # ★2차 추가
        prerequisites: dict[str, set[str]],                 # ★2차 추가
    ) -> None:
        self.students = students
        self.courses = courses
        self.enrollments = enrollments
        self.completed = completed
        self.colleges = colleges
        self.config = config
        self.schedules = schedules
        self.classrooms = classrooms
        self.prerequisites = prerequisites

    # --- 학생 관리 ---
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
        if not (isinstance(student.grade, int) and 1 <= student.grade <= 4):
            return False, "!!! 오류: 학년은 1 이상 4 이하의 정수이어야 합니다."
        self.students[student.student_id] = student
        return True, "✓ 학생 등록 완료"

    def delete_student(self, student_id: str) -> tuple[bool, str]:
        student = self.students.get(student_id)
        if not student:
            return False, "!!! 오류: 해당 학번의 학생이 없습니다."
        if student.status == "inactive":
            return False, "!!! 안내: 이미 inactive 상태의 학생입니다."
        student.status = "inactive"
        return True, f"✓ 학생 삭제 완료: {student_id} (inactive 처리됨)"

    def activate_student(self, student_id: str) -> tuple[bool, str]:
        student = self.students.get(student_id)
        if not student:
            return False, "!!! 오류: 해당 학번의 학생이 없습니다."
        if student.status == "active":
            return False, "!!! 안내: 이미 active 상태의 학생입니다."
        student.status = "active"
        return True, f"✓ 학생 활성화 완료: {student_id}"

    # --- 강의 등록 ---
    def add_course(self, course: Course, new_schedules: list[Schedule]) -> tuple[bool, str]:
        valid, msg = self._validate_course_fields(course)
        if not valid:
            return False, msg
        if course.key() in self.courses:
            return False, "!!! 오류: 이미 존재하는 개설 강의입니다."
        if not new_schedules:
            return False, "!!! 오류: 스케줄을 1개 이상 등록해야 합니다."

        seen_days: set[str] = set()
        for sched in new_schedules:
            if sched.day not in VALID_DAYS:
                return False, "!!! 오류: 요일은 MON, TUE, WED, THU, FRI 중 하나여야 합니다."
            if sched.start_time % 30 != 0 or sched.end_time % 30 != 0:
                return False, "!!! 오류: 시각의 분은 00 또는 30만 허용됩니다."
            if sched.start_time >= sched.end_time:
                return False, "!!! 오류: 종료 시각은 시작 시각보다 이후여야 합니다."
            if sched.classroom_code not in self.classrooms:
                return False, "!!! 오류: 존재하지 않는 강의실코드입니다."
            if sched.day in seen_days:
                return False, "!!! 오류: 동일한 요일의 스케줄이 중복됩니다."
            seen_days.add(sched.day)

        min_seats = self._min_seats_for_schedules(new_schedules)
        if course.capacity > min_seats:
            room = self._smallest_room(new_schedules)
            return False, (
                f"!!! 오류: 정원은 가장 작은 강의실({room.display_name()}, {room.seats}석)의 "
                f"좌석 수를 초과할 수 없습니다."
            )

        self.courses[course.key()] = course
        self.schedules[course.key()] = list(new_schedules)
        return True, f"✓ 강의 등록 완료: {course.name} ({course.code}-{course.section}) | 스케줄 {len(new_schedules)}개"

    # --- 강의 수정 — 항목별 (설계 6.4) ---
    def update_course_name(self, code: str, section: str, name: str) -> tuple[bool, str]:
        course, msg = self._editable_course(code, section)
        if not course:
            return False, msg
        if self._period_started():
            return False, "!!! 오류: 수강신청 기간 시작 이후에는 과목명을 수정할 수 없습니다."
        if not name or "\t" in name:
            return False, "!!! 오류: 과목명은 1자 이상이어야 하며 탭/개행을 포함할 수 없습니다."
        course.name = name
        return True, f"✓ 강의 수정 완료: 과목명 → {name}"

    def update_course_credits(self, code: str, section: str, credits: int) -> tuple[bool, str]:
        course, msg = self._editable_course(code, section)
        if not course:
            return False, msg
        if self._period_started():
            return False, "!!! 오류: 수강신청 기간 시작 이후에는 학점을 수정할 수 없습니다."
        if not (1 <= credits <= 6):
            return False, "!!! 오류: 학점은 1 이상 6 이하의 정수여야 합니다."
        course.credits = credits
        return True, f"✓ 강의 수정 완료: 학점 → {credits}"

    def update_course_professor(self, code: str, section: str, professor: str) -> tuple[bool, str]:
        course, msg = self._editable_course(code, section)
        if not course:
            return False, msg
        if not professor or "\t" in professor:
            return False, "!!! 오류: 담당교수는 1자 이상이어야 하며 탭/개행을 포함할 수 없습니다."
        # 새 담당교수가 담당하는 타 강의의 스케줄과 충돌 검사
        my_schedules = self.schedules.get((code, section), [])
        for other in self.courses.values():
            if other.key() == (code, section):
                continue
            if other.professor != professor:
                continue
            other_schedules = self.schedules.get(other.key(), [])
            if self._schedules_overlap(my_schedules, other_schedules):
                return False, f"!!! 오류: 새 담당교수가 이미 담당하는 강의({other.name})와 요시가 충돌합니다."
        course.professor = professor
        return True, f"✓ 강의 수정 완료: 담당교수 → {professor}"

    def update_course_status(self, code: str, section: str, status: str) -> tuple[bool, str]:
        # 상태 변경은 수강신청 기간과 무관하게 가능 (강의 삭제·활성화와 일관)
        course = self.courses.get((code, section))
        if not course:
            return False, "!!! 오류: 존재하지 않는 개설 강의입니다."
        if status not in ("active", "inactive"):
            return False, "!!! 오류: 상태는 active 또는 inactive여야 합니다."
        course.status = status
        return True, f"✓ 강의 수정 완료: 상태 → {status}"

    def update_course_capacity(self, code: str, section: str, new_cap: int) -> tuple[bool, str]:
        course, msg = self._editable_course(code, section)
        if not course:
            return False, msg
        if new_cap < 1:
            return False, "!!! 오류: 정원은 1 이상의 정수여야 합니다."
        if new_cap > course.capacity:
            # 증가: 최소 강의실 좌석 수 이하
            min_seats = self._min_classroom_seats(code, section)
            if new_cap > min_seats:
                room = self._smallest_room(self.schedules.get((code, section), []))
                room_text = f"{room.display_name()}, {room.seats}석" if room else f"{min_seats}석"
                return False, f"!!! 오류: 정원은 가장 작은 강의실({room_text})의 좌석 수를 초과할 수 없습니다."
        else:
            # 감소: 현재 enrolled 인원 이상까지만
            enrolled = self._enrolled_count((code, section))
            if new_cap < enrolled:
                return False, f"!!! 오류: 정원은 현재 신청 인원({enrolled}명) 이상이어야 합니다."
        course.capacity = new_cap
        return True, f"✓ 강의 수정 완료: 정원 → {new_cap}"

    def update_schedule_classroom(self, code: str, section: str, day: str, new_classroom_code: str) -> tuple[bool, str]:
        course, msg = self._editable_course(code, section)
        if not course:
            return False, msg
        room = self.classrooms.get(new_classroom_code)
        if not room:
            return False, "!!! 오류: 존재하지 않는 강의실코드입니다."
        target = self._find_schedule(code, section, day)
        if not target:
            return False, "!!! 오류: 해당 요일의 스케줄이 없습니다."
        enrolled = self._enrolled_count((code, section))
        if room.seats < enrolled:
            return False, f"!!! 오류: 변경하려는 강의실({room.seats}석)이 현재 신청 인원({enrolled}명)보다 작습니다."
        target.classroom_code = new_classroom_code
        return True, f"✓ 강의실 변경 완료: {day} → {room.display_name()} ({room.seats}석)"

    def add_schedule(self, schedule: Schedule) -> tuple[bool, str]:
        course, msg = self._editable_course(schedule.course_code, schedule.section)
        if not course:
            return False, msg
        if self._period_started():
            return False, "!!! 오류: 수강신청 기간 시작 이후에는 스케줄을 추가할 수 없습니다."
        if schedule.day not in VALID_DAYS:
            return False, "!!! 오류: 요일은 MON, TUE, WED, THU, FRI 중 하나여야 합니다."
        if schedule.start_time % 30 != 0 or schedule.end_time % 30 != 0:
            return False, "!!! 오류: 시각의 분은 00 또는 30만 허용됩니다."
        if schedule.start_time >= schedule.end_time:
            return False, "!!! 오류: 종료 시각은 시작 시각보다 이후여야 합니다."
        if schedule.classroom_code not in self.classrooms:
            return False, "!!! 오류: 존재하지 않는 강의실코드입니다."
        bucket = self.schedules.setdefault((schedule.course_code, schedule.section), [])
        if any(s.day == schedule.day for s in bucket):
            return False, "!!! 오류: 이미 해당 요일의 스케줄이 존재합니다."
        bucket.append(schedule)
        room = self.classrooms[schedule.classroom_code]
        return True, f"✓ 스케줄 추가: {schedule.day} {schedule.time_text()} ({room.display_name()}, {room.seats}석)"

    def delete_schedule(self, code: str, section: str, day: str) -> tuple[bool, str]:
        course, msg = self._editable_course(code, section)
        if not course:
            return False, msg
        if self._period_started():
            return False, "!!! 오류: 수강신청 기간 시작 이후에는 스케줄을 삭제할 수 없습니다."
        bucket = self.schedules.get((code, section), [])
        target = self._find_schedule(code, section, day)
        if not target:
            return False, "!!! 오류: 해당 요일의 스케줄이 없습니다."
        if len(bucket) <= 1:
            return False, "!!! 오류: 스케줄은 최소 1개 이상 유지되어야 합니다."
        bucket.remove(target)
        return True, f"✓ 스케줄 삭제 완료: {day} {target.time_text()}"

    # --- 강의 삭제 / 활성화 (변경 없음) ---
    def delete_course(self, code: str, section: str) -> tuple[bool, str]:
        if not (code.isdigit() and len(code) == 4):
            return False, "!!! 오류: 과목코드는 숫자 4자리여야 합니다."
        if not (section.isdigit() and len(section) == 2):
            return False, "!!! 오류: 분반코드는 숫자 2자리여야 합니다."
        course = self.courses.get((code, section))
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
        course = self.courses.get((code, section))
        if not course:
            return False, "!!! 오류: 존재하지 않는 개설 강의입니다."
        if course.status == "active":
            return False, "!!! 안내: 이미 active 상태의 강의입니다."
        course.status = "active"
        return True, f"✓ 강의 활성화 완료: {course.name} ({code}-{section})"

    # --- 수강신청 기간 설정 (★학기 추가) ---
    def set_registration_period(self, start: date, end: date, semester: str) -> tuple[bool, str]:
        if not (date(2000, 1, 1) <= start <= date(2099, 12, 31)):
            return False, "!!! 오류: 날짜는 2000-01-01 ~ 2099-12-31 범위여야 합니다."
        if not (date(2000, 1, 1) <= end <= date(2099, 12, 31)):
            return False, "!!! 오류: 날짜는 2000-01-01 ~ 2099-12-31 범위여야 합니다."
        if end < start:
            return False, "!!! 오류: 종료일은 시작일과 같거나 이후여야 합니다."
        if not re.fullmatch(r"20\d{2}-[12]", semester):
            return False, "!!! 오류: 학기 형식이 올바르지 않습니다."
        self.config.reg_start = start
        self.config.reg_end = end
        self.config.semester = semester
        return True, f"✓ 수강신청 기간 설정 완료: {start.isoformat()} ~ {end.isoformat()} | 학기: {semester}"

    # --- 강의실 관리 (★2차 신규) ---
    def add_classroom(self, classroom: Classroom) -> tuple[bool, str]:
        if not (classroom.classroom_code.isdigit() and len(classroom.classroom_code) == 4):
            return False, "!!! 오류: 강의실코드는 숫자 4자리여야 합니다."
        if classroom.classroom_code in self.classrooms:
            return False, "!!! 오류: 이미 존재하는 강의실코드입니다."
        if not classroom.building or "\t" in classroom.building:
            return False, "!!! 오류: 건물명은 1자 이상이어야 합니다."
        if not classroom.room_number or "\t" in classroom.room_number:
            return False, "!!! 오류: 강의실번호는 1자 이상이어야 합니다."
        if classroom.seats < 1:
            return False, "!!! 오류: 좌석 수는 1 이상의 정수여야 합니다."
        self.classrooms[classroom.classroom_code] = classroom
        return True, f"✓ 강의실 등록 완료: {classroom.building} {classroom.room_number} (코드: {classroom.classroom_code})"

    def list_classrooms(self) -> list[Classroom]:
        return sorted(self.classrooms.values(), key=lambda x: x.classroom_code)

    # --- 전체 수강 현황 ---
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

    # --- 내부 유틸 ---
    def _validate_course_fields(self, course: Course) -> tuple[bool, str]:
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
        if course.status not in ("active", "inactive"):
            return False, "!!! 오류: 상태는 active 또는 inactive여야 합니다."
        if course.capacity < 1:
            return False, "!!! 오류: 정원은 1 이상의 정수여야 합니다."
        if not re.fullmatch(r"20\d{2}-[12]", course.semester):
            return False, "!!! 오류: 학기는 YYYY-S 형식이어야 합니다 (예: 2026-1)."
        if not (0 <= course.limit_grade <= 4):
            return False, "!!! 오류: 제한학년은 0 이상 4 이하의 정수여야 합니다."
        if course.limit_major != "전체" and course.limit_major not in self._all_majors():
            return False, "!!! 오류: 제한학과는 '전체' 또는 colleges.txt의 전공 중 하나여야 합니다."
        return True, "OK"

    def _all_majors(self) -> set[str]:
        majors: set[str] = set()
        for major_list in self.colleges.values():
            majors.update(major_list)
        return majors

    def _editable_course(self, code: str, section: str) -> tuple[Course | None, str]:
        course = self.courses.get((code, section))
        if not course:
            return None, "!!! 오류: 존재하지 않는 개설 강의입니다."
        if course.status == "inactive":
            return None, "!!! 오류: inactive 상태의 강의는 수정할 수 없습니다. 먼저 강의를 활성화하세요."
        return course, "OK"

    def _period_started(self) -> bool:
        # 수강신청 기간 시작 이후(시작일 포함 ~ 종료 후)면 True
        return self.config.current_date >= self.config.reg_start

    def _find_schedule(self, code: str, section: str, day: str) -> Schedule | None:
        for s in self.schedules.get((code, section), []):
            if s.day == day:
                return s
        return None

    def _min_classroom_seats(self, code: str, section: str) -> int:
        return self._min_seats_for_schedules(self.schedules.get((code, section), []))

    def _min_seats_for_schedules(self, scheds: list[Schedule]) -> int:
        seats = [self.classrooms[s.classroom_code].seats for s in scheds if s.classroom_code in self.classrooms]
        return min(seats) if seats else 0

    def _smallest_room(self, scheds: list[Schedule]) -> Classroom | None:
        rooms = [self.classrooms[s.classroom_code] for s in scheds if s.classroom_code in self.classrooms]
        return min(rooms, key=lambda r: r.seats) if rooms else None

    @staticmethod
    def _schedules_overlap(a_list: list[Schedule], b_list: list[Schedule]) -> bool:
        for a in a_list:
            for b in b_list:
                if a.day == b.day and a.start_time < b.end_time and b.start_time < a.end_time:
                    return True
        return False

    def _enrolled_count(self, key: tuple[str, str]) -> int:
        latest: dict[tuple[str, tuple[str, str]], str] = {}
        for enrollment in self.enrollments:
            latest[(enrollment.student_id, enrollment.key())] = enrollment.status
        count = 0
        for (_, course_key), status in latest.items():
            if course_key == key and status == "enrolled":
                count += 1
        return count
