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

    # [추가] 실시간 학번 검사
    def validate_student_id(self, student_id: str) -> tuple[bool, str]:
        if not student_id.isdigit() or len(student_id) != 9:
            return False, "학번은 숫자 9자리이어야 합니다."
        if student_id in self.students or student_id in self.admins:
            return False, "이미 존재하는 학번입니다."
        return True, "사용 가능한 학번입니다."

   # 1단계: 사용자 타입에 따른 비밀번호 형식 체크
    def validate_password_format(self, password: str, user_type: str = "student") -> tuple[bool, str]:
        # 학생: 영문 대소문자와 숫자, 6~12자, 영문자와 숫자 각 최소 1자 이상 포함
        if user_type == "student":
            if not re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]{6,12}", password):
                return False, "비밀번호는 영문자와 숫자를 각각 1자 이상 포함한 6~12자이어야 합니다."

        # 관리자: 영문 대소문자, 숫자, 특수문자(!@#$%^&*), 8~16자, 세 종류 각 최소 1자 이상
        else:
            if not self._is_valid_admin_password(password):
                return False, "관리자 비밀번호는 영문자, 숫자, 특수문자(!@#$%^&*)를 각각 1자 이상 포함한 8~16자이어야 합니다."

        return True, "사용 가능한 형식입니다."

    # [추가] 2단계: 비밀번호 일치 여부만 체크
    def validate_password_match(self, password: str, password_check: str) -> tuple[bool, str]:
        if password != password_check:
            return False, "비밀번호 확인이 일치하지 않습니다."
        return True, "비밀번호가 일치합니다."
   
    # [추가] 실시간 이름 형식 검사 (6.3-11, 12 대응)
    def validate_name(self, name: str) -> tuple[bool, str]:
        # re.fullmatch를 사용하여 '가'부터 '힣'까지 완성형 한글만 허용
        if not re.fullmatch(r"[가-힣]+", name):
            return False, "이름은 한국어 완성형 글자로만 이루어져야 합니다."
        return True, "사용 가능한 이름입니다."

    # 기존 함수 유지 (매개변수 password_check는 내부 로직용으로 남겨둠)
    def signup_student(self, student_id, password, password_check, name, college, major):
        student = Student(student_id, password, name, college, major, "active")
        self.students[student.student_id] = student
        return True, "회원가입 완료", student

    def check_user_id(self, user_id: str) -> tuple[bool, str]:
        """기획서 6.4: ID 존재·활성 여부만 확인 (비밀번호 미검증)."""
        student = self.students.get(user_id)
        if student:
            if student.status != "active":
                return False, "!!! 오류: 비활성화된 계정입니다."
            return True, ""
        if user_id in self.admins:
            return True, ""
        return False, "!!! 오류: 존재하지 않는 계정입니다."

    def login(self, user_id: str, password: str) -> tuple[str, object | None, str]:
        student = self.students.get(user_id)
        if student:
            if student.status != "active":
                return "none", None, "!!! 오류: 비활성화된 계정입니다."
            if student.password != password:
                return "none", None, "!!! 오류: 비밀번호가 틀렸습니다."
            return "student", student, "학생 로그인 성공"

        admin = self.admins.get(user_id)
        if admin:
            if admin.password != password:
                return "none", None, "!!! 오류: 비밀번호가 틀렸습니다."
            return "admin", admin, "관리자 로그인 성공"

        return "none", None, "!!! 오류: 존재하지 않는 계정입니다."

    @staticmethod
    def _is_valid_admin_password(value: str) -> bool:
        if not re.fullmatch(r"[A-Za-z0-9!@#$%^&*]{8,16}", value):
            return False
        patterns = [r"[A-Za-z]", r"\d", r"[!@#$%^&*]"]
        return all(re.search(pat, value) for pat in patterns)
