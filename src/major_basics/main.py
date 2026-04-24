from datetime import date
from pathlib import Path

from major_basics.modules.admin_service import AdminService
from major_basics.modules.auth import AuthService
from major_basics.modules.models import Course, Student
from major_basics.modules.storage import DataStore
from major_basics.modules.student_service import StudentService


def _parse_date(value: str) -> date | None:
    """기획서 6.1: 현행 그레고리력에 존재하는 날짜."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_hhmm(value: str) -> int | None:
    """기획서 4.3.7~4.3.8: HH:MM, 분은 00 또는 30만 허용."""
    try:
        hour_s, minute_s = value.split(":")
        if len(hour_s) != 2 or len(minute_s) != 2:
            return None
        hour = int(hour_s)
        minute = int(minute_s)
        if hour < 0 or hour > 23:
            return None
        if minute not in (0, 30):
            return None
        return hour * 60 + minute
    except (ValueError, AttributeError):
        return None


def _save_all(store: DataStore, students, admins, courses, enrollments, completed, config) -> None:
    store.save_students(students)
    store.save_admins(admins)
    store.save_courses(courses)
    store.save_enrollments(enrollments)
    store.save_completed(completed)
    store.save_config(config)


def _choose_college_major(colleges: dict[str, list[str]]) -> tuple[str, str] | None:
    college_list = list(colleges.keys())

    while True:
        print("===== 단과대 선택 =====")
        for i, college in enumerate(college_list, 1):
            print(f"{i}. {college}")

        pick = input("선택 > ").strip()

        if not pick:
            continue

        if not pick.isdigit() or int(pick) < 1 or int(pick) > len(college_list):
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")
            continue

        selected_college = college_list[int(pick) - 1]
        break

    majors = colleges[selected_college]
    while True:
        print(f"===== 전공 선택 ({selected_college}) =====")
        for i, major in enumerate(majors, 1):
            print(f"{i}. {major}")

        mpick = input("선택 > ").strip()

        if not mpick:
            continue

        if not mpick.isdigit() or int(mpick) < 1 or int(mpick) > len(majors):
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")
            continue

        selected_major = majors[int(mpick) - 1]
        break

    return selected_college, selected_major


def _print_courses(courses, current_counts: dict[tuple[str, str], int] | None = None) -> None:
    if not courses:
        print("조회 결과가 없습니다.")
        return
    print("번호 | 과목코드 | 분반코드 | 과목명 | 학점 | 요일 | 시간 | 담당교수 | 정원")
    for i, course in enumerate(courses, 1):
        now = current_counts[course.key()] if current_counts and course.key() in current_counts else 0
        print(
            f"{i} | {course.code} | {course.section} | {course.name} | {course.credits} | "
            f"{course.day} | {course.time_text()} | {course.professor} | {course.capacity} (현재 {now})"
        )


def _student_menu(student_service: StudentService, courses: dict, enrollments: list, config) -> None:
    while True:
        print("\n----------------------------------------")
        print(f"[학생 메뉴] {student_service.student.name} ({student_service.student.student_id})")
        print(
            f"현재 신청 학점: {student_service.current_credits()} / {StudentService.MAX_CREDITS}"
            f" | 수강신청 기간: {config.reg_start.isoformat()} ~ {config.reg_end.isoformat()}"
        )
        print("----------------------------------------")
        print("1. 개설 과목 전체 조회")
        print("2. 과목 검색")
        print("3. 기이수 과목 조회")
        print("4. 기이수 과목 추가")
        print("5. 수강신청")
        print("6. 수강취소")
        print("7. 신청 내역 조회")
        print("8. 내 시간표 조회")
        print("0. 로그아웃")
        print("----------------------------------------")
        choice = input("선택 > ").strip()

        if choice == "1":
            counts = {}
            latest = {}
            for enrollment in enrollments:
                latest[(enrollment.student_id, enrollment.key())] = enrollment.status
            for (_, key), status in latest.items():
                if status == "enrolled":
                    counts[key] = counts.get(key, 0) + 1
            _print_courses(student_service.list_courses(), counts)
        elif choice == "2":
            keyword = input("과목명 검색어 > ").strip()
            results = student_service.search_courses(keyword)
            if not results:
                print("검색 결과가 없습니다.")
            else:
                _print_courses(results)
                print(f"총 {len(results)}건 검색됨.")
        elif choice == "3":
            print("===== 기이수 과목 목록 =====")
            completed = student_service.list_completed()
            if not completed:
                print("등록된 기이수 과목이 없습니다.")
            else:
                print("번호 | 과목코드")
                for i, code in enumerate(completed, 1):
                    print(f"{i} | {code}")
                print(f"총 {len(completed)}개 과목 이수 완료.")
        elif choice == "4":
            code = input("기이수 추가 과목코드 > ").strip()
            _, msg = student_service.add_completed(code)
            print(msg)
        elif choice == "5":
            if not student_service.is_registration_open():
                print("!!! 안내: 현재 수강신청 기간이 아닙니다.")
                continue
            code = input("신청 과목코드(4자리) > ").strip()
            section = input("분반코드(2자리) > ").strip()
            _, msg, _ = student_service.register(code, section)
            print(msg)
            print(f"현재 총 신청 학점: {student_service.current_credits()} / {StudentService.MAX_CREDITS}")
        elif choice == "6":
            if not student_service.is_registration_open():
                print("!!! 안내: 현재 수강신청 기간이 아닙니다.")
                continue
            code = input("취소 과목코드(4자리) > ").strip()
            section = input("분반코드(2자리) > ").strip()
            _, msg = student_service.cancel(code, section)
            print(msg)
            print(f"현재 총 신청 학점: {student_service.current_credits()} / {StudentService.MAX_CREDITS}")
        elif choice == "7":
            history = student_service.enrollment_history()
            if not history:
                print("신청 내역이 없습니다.")
            else:
                print("번호 | 과목코드 | 분반코드 | 과목명 | 학점 | 상태 | 재수강")
                for i, enrollment in enumerate(history, 1):
                    course = courses.get(enrollment.key())
                    name = course.name if course else "(삭제된 강의)"
                    credits = course.credits if course else 0
                    retake = "Y" if student_service.is_retake(enrollment.course_code) else "N"
                    print(
                        f"{i} | {enrollment.course_code} | {enrollment.section} | {name} | "
                        f"{credits} | {enrollment.status} | {retake}"
                    )
                print(
                    f"총 신청 학점 (enrolled): {student_service.current_credits()} / {StudentService.MAX_CREDITS}"
                )
        elif choice == "8":
            timetable = student_service.timetable()
            by_day = {"MON": [], "TUE": [], "WED": [], "THU": [], "FRI": []}
            for course in timetable:
                by_day.setdefault(course.day, []).append(course)
            print("===== 내 시간표 =====")
            for day in ("MON", "TUE", "WED", "THU", "FRI"):
                items = by_day.get(day, [])
                if not items:
                    print(f"[{day}] 없음")
                else:
                    for course in items:
                        name = course.name if len(course.name) <= 15 else course.name[:15] + "..."
                        print(
                            f"[{day}] {course.time_text()} {name} ({course.code}-{course.section}) | "
                            f"{course.credits}학점 | {course.professor}"
                        )
            print(f"총 신청 학점: {student_service.current_credits()} / {StudentService.MAX_CREDITS}")
        elif choice == "0":
            print("로그아웃합니다.")
            break
        else:
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


def _input_course() -> Course | None:
    code = input("과목코드 (숫자 4자리) > ").strip()
    section = input("분반코드 (숫자 2자리) > ").strip()
    name = input("과목명 > ").strip()
    credits_s = input("학점 (1~6 정수) > ").strip()
    professor = input("담당교수 > ").strip()
    day = input("요일 (MON/TUE/WED/THU/FRI) > ").strip().upper()
    start_s = input("시작 시각 (HH:MM) > ").strip()
    end_s = input("종료 시각 (HH:MM) > ").strip()
    capacity_s = input("정원 (1 이상의 정수) > ").strip()

    if not credits_s.isdigit() or not (1 <= int(credits_s) <= 6):
        print("!!! 오류: 학점은 1~6 사이의 정수여야 합니다.")
        return None
    if not capacity_s.isdigit() or int(capacity_s) < 1:
        print("!!! 오류: 정원은 1 이상의 정수여야 합니다.")
        return None

    start = _parse_hhmm(start_s)
    end = _parse_hhmm(end_s)
    if start is None or end is None:
        print("!!! 오류: 시각 형식이 올바르지 않습니다. 분은 00 또는 30만 허용됩니다.")
        return None

    return Course(code, section, name, int(credits_s), professor, day, start, end, "active", int(capacity_s))


def _admin_menu(admin_service: AdminService, colleges, store, students, admins, courses, enrollments, completed, config) -> None:
    while True:
        print("\n----------------------------------------")
        print(f"[관리자 메뉴] 관리자")
        print(
            f"오늘 날짜: {config.current_date.isoformat()} | "
            f"수강신청 기간: {config.reg_start.isoformat()} ~ {config.reg_end.isoformat()}"
        )
        print("----------------------------------------")
        print("1. 학생 등록")
        print("2. 학생 삭제")
        print("3. 학생 활성화")
        print("4. 강의 등록")
        print("5. 강의 수정 (수강신청 기간 시작 전에만 가능)")
        print("6. 강의 삭제")
        print("7. 강의 활성화")
        print("8. 전체 수강 현황 조회")
        print("9. 수강신청 기간 설정")
        print("0. 로그아웃")
        print("----------------------------------------")
        choice = input("선택 > ").strip()

        if choice == "1":
            sid = input("학번 (숫자 9자리) > ").strip()
            pw = input("비밀번호 > ").strip()
            name = input("이름 (한국어 완성형) > ").strip()
            selected = _choose_college_major(colleges)
            if selected is None:
                continue
            college, major = selected
            _, msg = admin_service.register_student(Student(sid, pw, name, college, major, "active"))
            print(msg)
            _save_all(store, students, admins, courses, enrollments, completed, config)
        elif choice == "2":
            print("===== 학생 삭제 =====")
            sid = input("삭제할 학생의 학번 입력 (0: 돌아가기) > ").strip()
            if sid == "0":
                continue
            _, msg = admin_service.delete_student(sid)
            print(msg)
            _save_all(store, students, admins, courses, enrollments, completed, config)
        elif choice == "3":
            print("===== 학생 활성화 =====")
            sid = input("활성화할 학생의 학번 입력 (0: 돌아가기) > ").strip()
            if sid == "0":
                continue
            _, msg = admin_service.activate_student(sid)
            print(msg)
            _save_all(store, students, admins, courses, enrollments, completed, config)
        elif choice == "4":
            print("===== 강의 등록 =====")
            course = _input_course()
            if course is None:
                continue
            _, msg = admin_service.add_course(course)
            print(msg)
            _save_all(store, students, admins, courses, enrollments, completed, config)
        elif choice == "5":
            print("===== 강의 수정 =====")
            course = _input_course()
            if course is None:
                continue
            _, msg = admin_service.update_course(course)
            print(msg)
            _save_all(store, students, admins, courses, enrollments, completed, config)
        elif choice == "6":
            print("===== 강의 삭제 =====")
            code = input("삭제할 과목코드 입력 (0: 돌아가기) > ").strip()
            if code == "0":
                continue
            section = input("삭제할 분반코드 입력 > ").strip()
            _, msg = admin_service.delete_course(code, section)
            print(msg)
            _save_all(store, students, admins, courses, enrollments, completed, config)
        elif choice == "7":
            print("===== 강의 활성화 =====")
            code = input("활성화할 과목코드 입력 (0: 돌아가기) > ").strip()
            if code == "0":
                continue
            section = input("활성화할 분반코드 입력 > ").strip()
            _, msg = admin_service.activate_course(code, section)
            print(msg)
            _save_all(store, students, admins, courses, enrollments, completed, config)
        elif choice == "8":
            print("===== 전체 수강 현황 =====")
            print("과목코드 | 분반코드 | 과목명 | 정원 | 신청 인원")
            for course, count in admin_service.enrollment_summary():
                print(f"{course.code} | {course.section} | {course.name} | {course.capacity} | {count}")
        elif choice == "9":
            print("===== 수강신청 기간 설정 =====")
            print(f"현재 설정: {config.reg_start.isoformat()} ~ {config.reg_end.isoformat()}")
            while True:
                start_s = input("새로운 시작일 (YYYY-MM-DD) > ").strip()
                start = _parse_date(start_s)
                if start is None:
                    print("!!! 오류: 날짜 형식이 올바르지 않습니다.")
                    continue
                break
            while True:
                end_s = input("새로운 종료일 (YYYY-MM-DD) > ").strip()
                end = _parse_date(end_s)
                if end is None:
                    print("!!! 오류: 날짜 형식이 올바르지 않습니다.")
                    continue
                break
            _, msg = admin_service.set_registration_period(start, end)
            print(msg)
            _save_all(store, students, admins, courses, enrollments, completed, config)
        elif choice == "0":
            print("로그아웃합니다.")
            break
        else:
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    data_dir = project_root / "data" / "raw"

    while True:
        entered = input("오늘 날짜를 입력하세요 (YYYY-MM-DD) > ").strip()
        current_date = _parse_date(entered)
        if current_date is not None:
            break
        print("!!! 오류: 날짜 형식이 올바르지 않습니다.")

    store = DataStore(data_dir)
    store.ensure_defaults(current_date)

    # 기획서 5.5절: 무결성 검사
    errors = store.validate_integrity()
    if errors:
        for err in errors:
            print(f"!!! 오류: {err}")
        print("프로그램을 종료합니다.")
        return

    students = store.load_students()
    admins = store.load_admins()
    courses = store.load_courses()
    enrollments = store.load_enrollments()
    completed = store.load_completed()
    colleges = store.load_colleges()
    config = store.load_config(current_date)
    config.current_date = current_date

    auth_service = AuthService(students, admins, colleges)

    while True:
        print("\n========================================")
        print("   건국 수강신청 시뮬레이터")
        print("========================================")
        print("1. 로그인")
        print("2. 회원가입")
        print("0. 종료")
        print("----------------------------------------")
        choice = input("선택 > ").strip()

        if choice == "1":
            print("----------------------------------------")
            user_id = input("ID (학번 또는 관리자 ID) > ").strip()
            password = input("비밀번호 > ").strip()
            role, user, msg = auth_service.login(user_id, password)
            print(msg)

            if role == "student":
                student_service = StudentService(user, courses, enrollments, completed, config)
                _student_menu(student_service, courses, enrollments, config)
                _save_all(store, students, admins, courses, enrollments, completed, config)
            elif role == "admin":
                admin_service = AdminService(students, courses, enrollments, completed, colleges, config)
                _admin_menu(admin_service, colleges, store, students, admins, courses, enrollments, completed, config)
                _save_all(store, students, admins, courses, enrollments, completed, config)

        elif choice == "2":
            print("\n===== 회원가입 =====")

            # 1. 학번 즉시 검증 루프
            while True:
                student_id = input("학번 (숫자 9자리) > ").strip()
                is_valid, msg = auth_service.validate_student_id(student_id)
                if is_valid:
                    break
                print(f"!!! 오류: {msg}")

            # 2. 비밀번호 입력 (형식 검사)
            while True:
                password = input("비밀번호 > ").strip()
                is_valid, msg = auth_service.validate_password_format(password, user_type="student")
                if is_valid:
                    break
                print(f"!!! 오류: {msg}")

            # 3. 이름 입력 루프
            while True:
                name = input("이름 (한국어 완성형) > ").strip()
                if not name:
                    continue
                is_valid, msg = auth_service.validate_name(name)
                if is_valid:
                    break
                print(f"!!! 오류: {msg}")

            # 4. 단과대 및 전공 선택
            selected = _choose_college_major(colleges)
            if selected is None:
                continue
            college, major = selected

            # 5. 최종 등록 및 저장
            ok, _msg, _ = auth_service.signup_student(
                student_id=student_id,
                password=password,
                password_check=password,
                name=name,
                college=college,
                major=major,
            )
            if ok:
                print(f"✓ 회원가입 완료: {name} ({student_id})")
                print("로그인 화면으로 돌아갑니다.")
                _save_all(store, students, admins, courses, enrollments, completed, config)

        elif choice == "0":
            _save_all(store, students, admins, courses, enrollments, completed, config)
            print("프로그램을 종료합니다.")
            break
        else:
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


if __name__ == "__main__":
    main()
