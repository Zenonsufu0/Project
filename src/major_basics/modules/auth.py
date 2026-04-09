import re

from major_basics.modules.models import Admin, Student


class AuthService:
    def __init__(
        self,
        students: dict[str, Student],
        admins: dict[str, Admin],
        colleges: dict[str, list[str]],
    ) -> None:
        self.students = students
        self.admins = admins
        self.colleges = colleges

    def signup_student(
        self,
        student_id: str,
        password: str,
        password_check: str,
        name: str,
        college: str,
        major: str,
    ) -> tuple[bool, str, Student | None]:
        if not student_id.isdigit() or len(student_id) != 9:
            return False, "학번은 숫자 9자리여야 합니다.", None
        if student_id in self.students or student_id in self.admins:
            return False, "이미 존재하는 ID입니다.", None
        if not self._is_valid_password(password):
            return False, "비밀번호는 8~16자, 영문 대/소문자, 숫자, 특수문자를 포함해야 합니다.", None
        if password != password_check:
            return False, "비밀번호 확인이 일치하지 않습니다.", None
        if not name:
            return False, "이름을 입력해야 합니다.", None
        if college not in self.colleges:
            return False, "존재하지 않는 단과대학입니다.", None
        if major not in self.colleges[college]:
            return False, "선택한 단과대학에 없는 전공입니다.", None

        student = Student(student_id, password, name, college, major, "active")
        self.students[student.student_id] = student
        return True, "회원가입 완료", student

    def login(self, user_id: str, password: str) -> tuple[str, object | None, str]:
        student = self.students.get(user_id)
        if student:
            if student.password != password:
                return "none", None, "비밀번호가 올바르지 않습니다."
            if student.status != "active":
                return "none", None, "비활성 학생 계정입니다. 관리자에게 문의하세요."
            return "student", student, "학생 로그인 성공"

        admin = self.admins.get(user_id)
        if admin:
            if admin.password != password:
                return "none", None, "비밀번호가 올바르지 않습니다."
            return "admin", admin, "관리자 로그인 성공"

        return "none", None, "존재하지 않는 ID입니다."

    @staticmethod
    def _is_valid_password(value: str) -> bool:
        if len(value) < 8 or len(value) > 16:
            return False
        patterns = [r"[A-Z]", r"[a-z]", r"\d", r"[^A-Za-z0-9]"]
        return all(re.search(pat, value) for pat in patterns)
