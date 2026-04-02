from major_basics.models.course import Course
from major_basics.models.enrollment import EnrollmentRecord
from major_basics.models.student import Student


class AdminManager:
    def __init__(
        self,
        students: dict[str, Student],
        courses: dict[str, Course],
        enrollments: list[EnrollmentRecord],
    ) -> None:
        self.students = students
        self.courses = courses
        self.enrollments = enrollments

    def add_student(self, student: Student) -> tuple[bool, str]:
        if student.student_id in self.students:
            return False, "이미 존재하는 학번입니다."
        self.students[student.student_id] = student
        return True, "학생 등록 완료."

    def delete_student(self, student_id: str) -> tuple[bool, str]:
        if student_id not in self.students:
            return False, "존재하지 않는 학번입니다."
        del self.students[student_id]
        return True, "학생 삭제 완료."

    def add_course(self, course: Course) -> tuple[bool, str]:
        if course.code in self.courses:
            return False, "이미 존재하는 과목코드입니다."
        self.courses[course.code] = course
        return True, "강의 등록 완료."

    def update_course(self, course: Course) -> tuple[bool, str]:
        if course.code not in self.courses:
            return False, "존재하지 않는 과목코드입니다."
        self.courses[course.code] = course
        return True, "강의 수정 완료."

    def delete_course(self, code: str) -> tuple[bool, str]:
        if code not in self.courses:
            return False, "존재하지 않는 과목코드입니다."
        del self.courses[code]
        return True, "강의 삭제 완료."

    def enrollment_counts(self) -> list[tuple[str, str, int]]:
        latest: dict[tuple[str, str], str] = {}
        for rec in self.enrollments:
            latest[(rec.student_id, rec.course_code)] = rec.status

        counts: dict[str, int] = {}
        for (_, code), status in latest.items():
            if status == "enrolled":
                counts[code] = counts.get(code, 0) + 1

        result = []
        for code, course in sorted(self.courses.items()):
            result.append((code, course.name, counts.get(code, 0)))
        return result
