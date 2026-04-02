from major_basics.data.repository import FileRepository
from major_basics.models.course import Course
from major_basics.models.student import Student
from major_basics.services.admin_manager import AdminManager
from major_basics.services.auth_service import AuthService
from major_basics.services.registration_manager import RegistrationManager


class CLIApp:
    def __init__(self, repository: FileRepository) -> None:
        self.repository = repository
        self.repository.bootstrap_if_missing()

        self.students = repository.load_students()
        self.admins = repository.load_admins()
        self.courses = repository.load_courses()
        self.completed = repository.load_completed()
        self.enrollments = repository.load_enrollments()

        self.auth = AuthService(self.students, self.admins)

    def run(self) -> None:
        while True:
            print("\n=== 로그인 프롬프트 ===")
            print("1. 학생 로그인")
            print("2. 관리자 로그인")
            print("3. 학생 회원가입")
            print("0. 종료")
            choice = input("선택: ").strip()

            if choice == "1":
                self._student_login_flow()
            elif choice == "2":
                self._admin_login_flow()
            elif choice == "3":
                self._student_signup_flow()
            elif choice == "0":
                self._save_all()
                print("프로그램을 종료합니다.")
                break
            else:
                print("올바른 번호를 입력하세요.")

    def _student_login_flow(self) -> None:
        student_id = input("학번: ").strip()
        password = input("비밀번호: ").strip()
        student = self.auth.login_student(student_id, password)
        if student is None:
            print("로그인 실패")
            return

        print(f"로그인 성공: {student.name}")
        manager = RegistrationManager(student, self.courses, self.completed, self.enrollments)
        self._student_menu(manager)

    def _student_menu(self, manager: RegistrationManager) -> None:
        while True:
            print("\n=== 학생 메인 메뉴 ===")
            print("1. 개설 과목 전체 조회")
            print("2. 과목 검색")
            print("3. 기이수 과목 조회")
            print("4. 기이수 과목 추가")
            print("5. 수강신청")
            print("6. 수강취소")
            print("7. 신청 내역 조회")
            print("8. 내 시간표 조회")
            print("9. 신청 학점 확인")
            print("0. 로그아웃")
            choice = input("선택: ").strip()

            if choice == "1":
                self._print_courses(manager.list_active_courses())
            elif choice == "2":
                keyword = input("검색어(과목코드/과목명): ").strip()
                self._print_courses(manager.search_courses(keyword))
            elif choice == "3":
                self._print_completed(manager)
            elif choice == "4":
                code = input("기이수 등록 과목코드: ").strip()
                _, message = manager.add_completed_course(code)
                print(message)
                self._save_all()
            elif choice == "5":
                code = input("신청 과목코드: ").strip()
                _, message = manager.register_course(code)
                print(message)
                self._save_all()
            elif choice == "6":
                code = input("취소 과목코드: ").strip()
                _, message = manager.cancel_course(code)
                print(message)
                self._save_all()
            elif choice == "7":
                self._print_enrollment_history(manager)
            elif choice == "8":
                self._print_timetable(manager)
            elif choice == "9":
                print(f"현재 신청 학점: {manager.current_credits()}학점")
            elif choice == "0":
                print("로그아웃합니다.")
                break
            else:
                print("올바른 번호를 입력하세요.")

    def _admin_login_flow(self) -> None:
        admin_id = input("관리자 ID: ").strip()
        password = input("비밀번호: ").strip()
        admin = self.auth.login_admin(admin_id, password)
        if admin is None:
            print("로그인 실패")
            return

        print(f"관리자 로그인 성공: {admin.name}")
        manager = AdminManager(self.students, self.courses, self.enrollments)
        self._admin_menu(manager)

    def _student_signup_flow(self) -> None:
        print("\n=== 학생 회원가입 ===")
        student_id = input("학번: ").strip()
        password = input("비밀번호: ").strip()
        password_check = input("비밀번호 확인: ").strip()
        name = input("이름: ").strip()
        college = input("단과대: ").strip()
        major = input("전공: ").strip()

        if not all([student_id, password, password_check, name, college, major]):
            print("모든 항목을 입력해야 합니다.")
            return
        if password != password_check:
            print("비밀번호가 일치하지 않습니다.")
            return

        student = Student(student_id, password, name, college, major, "active")
        ok, message = self.auth.register_student(student)
        print(message)
        if ok:
            self._save_all()

    def _admin_menu(self, manager: AdminManager) -> None:
        while True:
            print("\n=== 관리자 메인 메뉴 ===")
            print("1. 학생 등록")
            print("2. 학생 삭제")
            print("3. 강의 등록")
            print("4. 강의 수정")
            print("5. 강의 삭제")
            print("6. 전체 수강 현황 조회")
            print("0. 로그아웃")
            choice = input("선택: ").strip()

            if choice == "1":
                student = self._input_student()
                ok, msg = manager.add_student(student)
                print(msg)
                if ok:
                    self._save_all()
            elif choice == "2":
                sid = input("삭제할 학번: ").strip()
                ok, msg = manager.delete_student(sid)
                print(msg)
                if ok:
                    self._save_all()
            elif choice == "3":
                course = self._input_course()
                ok, msg = manager.add_course(course)
                print(msg)
                if ok:
                    self._save_all()
            elif choice == "4":
                course = self._input_course()
                ok, msg = manager.update_course(course)
                print(msg)
                if ok:
                    self._save_all()
            elif choice == "5":
                code = input("삭제할 과목코드: ").strip()
                ok, msg = manager.delete_course(code)
                print(msg)
                if ok:
                    self._save_all()
            elif choice == "6":
                print("\n[전체 수강 현황]")
                for code, name, count in manager.enrollment_counts():
                    print(f"{code} | {name} | {count}명")
            elif choice == "0":
                print("로그아웃합니다.")
                break
            else:
                print("올바른 번호를 입력하세요.")

    def _print_courses(self, courses: list[Course]) -> None:
        print("\n[개설 과목 목록]")
        if not courses:
            print("조회 결과가 없습니다.")
            return
        for idx, c in enumerate(courses, 1):
            print(
                f"{idx} | {c.code} | {c.name} | {c.credits} | "
                f"{c.day} {c.start_time:04d}-{c.end_time:04d} | {c.professor}"
            )

    def _print_completed(self, manager: RegistrationManager) -> None:
        print("\n[기이수 과목]")
        completed = manager.get_completed_courses()
        if not completed:
            print("등록된 기이수 과목이 없습니다.")
            return
        for idx, code in enumerate(completed, 1):
            name = self.courses[code].name if code in self.courses else "(과목정보 없음)"
            print(f"{idx} | {code} | {name}")

    def _print_enrollment_history(self, manager: RegistrationManager) -> None:
        print("\n[신청 내역]")
        history = manager.enrollment_history()
        if not history:
            print("신청 내역이 없습니다.")
            return
        for idx, rec in enumerate(history, 1):
            course = self.courses.get(rec.course_code)
            name = course.name if course else "(과목정보 없음)"
            credits = course.credits if course else 0
            retake = "Y" if rec.is_retake else "N"
            print(f"{idx} | {rec.course_code} | {name} | {credits} | {rec.status} | {retake}")

    def _print_timetable(self, manager: RegistrationManager) -> None:
        print("\n[내 시간표]")
        courses = manager.timetable_courses()
        if not courses:
            print("신청된 과목이 없습니다.")
            return
        for c in courses:
            print(f"{c.day} {c.start_time:04d}-{c.end_time:04d} | {c.code} | {c.name}")

    def _input_student(self) -> Student:
        student_id = input("학번: ").strip()
        password = input("비밀번호: ").strip()
        name = input("이름: ").strip()
        college = input("단과대: ").strip()
        major = input("전공: ").strip()
        return Student(student_id, password, name, college, major, "active")

    def _input_course(self) -> Course:
        code = input("과목코드(숫자4자리): ").strip()
        name = input("과목명: ").strip()
        credits = int(input("학점: ").strip())
        professor = input("담당교수: ").strip()
        day = input("요일(MON/TUE/WED/THU/FRI): ").strip().upper()
        start = int(input("시작시각(HHMM): ").strip())
        end = int(input("종료시각(HHMM): ").strip())
        category = input("이수구분: ").strip() or "major_elective"
        status = input("상태(active/inactive): ").strip() or "active"
        return Course(code, name, credits, professor, day, start, end, category, status)

    def _save_all(self) -> None:
        self.repository.save_students(self.students)
        self.repository.save_courses(self.courses)
        self.repository.save_completed(self.completed)
        self.repository.save_enrollments(self.enrollments)
