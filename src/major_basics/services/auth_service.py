from major_basics.models.admin import Admin
from major_basics.models.student import Student


class AuthService:
    def __init__(self, students: dict[str, Student], admins: dict[str, Admin]) -> None:
        self.students = students
        self.admins = admins

    def login_student(self, student_id: str, password: str) -> Student | None:
        user = self.students.get(student_id)
        if user and user.password == password:
            return user
        return None

    def login_admin(self, admin_id: str, password: str) -> Admin | None:
        admin = self.admins.get(admin_id)
        if admin and admin.password == password:
            return admin
        return None

    def register_student(self, student: Student) -> tuple[bool, str]:
        if student.student_id in self.students:
            return False, "이미 존재하는 학번입니다."
        self.students[student.student_id] = student
        return True, "회원가입이 완료되었습니다."
