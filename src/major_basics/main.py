import getpass
from datetime import date
from pathlib import Path

from major_basics.modules.admin_service import AdminService
from major_basics.modules.auth import AuthService
from major_basics.modules.models import Course, Student
from major_basics.modules.storage import DataStore
from major_basics.modules.student_service import StudentService


def _parse_date(value: str) -> date | None:
    try:
        parsed_date = date.fromisoformat(value)
        if not (date(2000, 1, 1) <= parsed_date <= date(2099, 12, 31)):
            return None
        return parsed_date
    except ValueError:
        return None


def _parse_hhmm(value: str) -> int | None:
    try:
        hour_s, minute_s = value.split(":")
        hour = int(hour_s)
        minute = int(minute_s)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
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
    
    # 1. 단과대학 선택 루프
    while True:
        print("단과대학 선택")
        for i, college in enumerate(college_list, 1):
            print(f"{i}. {college}")
        
        pick = input("번호 선택 > ").strip()
        
        if not pick:
            continue
            
        if not pick.isdigit() or int(pick) < 1 or int(pick) > len(college_list):
            # 6.3-13 요구 메시지
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")
            continue 
        
        selected_college = college_list[int(pick) - 1]
        break 

    # 2. 전공 선택 루프
    majors = colleges[selected_college]
    while True:
        print(f"전공 선택")
        for i, major in enumerate(majors, 1):
            print(f"{i}. {major}")
            
        mpick = input("번호 선택 > ").strip()
        
        if not mpick:
            continue
            
        if not mpick.isdigit() or int(mpick) < 1 or int(mpick) > len(majors):
            # 6.3-13 요구 메시지
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")
            continue # 다시 목록 출력 및 입력 대기
            
        selected_major = majors[int(mpick) - 1]
        break

    return selected_college, selected_major


def _print_courses(courses, current_counts: dict[tuple[str, str], int] | None = None) -> None:
    if not courses:
        print("조회 결과가 없습니다.")
        return
    for i, course in enumerate(courses, 1):
        now = current_counts[course.key()] if current_counts and course.key() in current_counts else "-"
        print(
            f"{i} | {course.code} | {course.section} | {course.name} | {course.credits} | "
            f"{course.day} | {course.time_text()} | {course.professor} | {course.capacity} | {now}"
        )

def _format_date(d):
    return d.isoformat()


def _student_header(student_service: StudentService) -> None:
    student = student_service.student
    config = student_service.config

    print("-" * 45)
    print(f"[학생 메뉴] {student.name} ({student.student_id})")
    print(
        f"현재 신청 학점: {student_service.current_credits()} / 18"
        f"  |  수강신청 기간: {_format_date(config.reg_start)} ~ {_format_date(config.reg_end)}"
    )
    print("-" * 45)


def _admin_header(admin_id: str, config) -> None:
    print("-" * 45)
    print(f"[관리자 메뉴] 관리자 ({admin_id})")
    print(
        f"오늘 날짜: {_format_date(config.current_date)}"
        f"  |  수강신청 기간: {_format_date(config.reg_start)} ~ {_format_date(config.reg_end)}"
    )
    print("-" * 45)


def _student_menu(student_service: StudentService, courses: dict, enrollments: list) -> None:
    while True:
        _student_header(student_service)

        print("1. 개설 과목 전체 조회")
        print("2. 과목 검색")
        print("3. 기이수 과목 조회")
        print("4. 기이수 과목 추가")
        print("5. 수강신청")
        print("6. 수강취소")
        print("7. 신청 내역 조회")
        print("8. 내 시간표 조회")
        print("0. 로그아웃")
        choice = input("선택: ").strip()

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
            keyword = input("검색어(과목코드/분반/과목명): ").strip()
            _print_courses(student_service.search_courses(keyword))
        elif choice == "3":
            print("[기이수 과목]")
            completed = student_service.list_completed()
            if not completed:
                print("등록된 기이수 과목이 없습니다.")
            for i, code in enumerate(completed, 1):
                print(f"{i} | {code}")
        elif choice == "4":
            code = input("기이수 추가 과목코드: ").strip()
            _, msg = student_service.add_completed(code)
            print(msg)
        elif choice == "5":
            code = input("신청 과목코드(4자리): ").strip()
            section = input("분반코드(2자리): ").strip()
            _, msg = student_service.register(code, section)
            print(msg)
            print(f"현재 신청 학점: {student_service.current_credits()}학점")
        elif choice == "6":
            code = input("취소 과목코드(4자리): ").strip()
            section = input("분반코드(2자리): ").strip()
            _, msg = student_service.cancel(code, section)
            print(msg)
            print(f"현재 신청 학점: {student_service.current_credits()}학점")
        elif choice == "7":
            history = student_service.enrollment_history()
            if not history:
                print("신청 내역이 없습니다.")
            for i, enrollment in enumerate(history, 1):
                course = courses.get(enrollment.key())
                name = course.name if course else "(삭제된 강의)"
                credits = course.credits if course else 0
                retake = "Y" if enrollment.is_retake else "N"
                print(
                    f"{i} | {enrollment.course_code} | {enrollment.section} | {name} | "
                    f"{credits} | {enrollment.status} | {retake}"
                )
            print(f"총 신청 학점: {student_service.current_credits()}학점")
        elif choice == "8":
            timetable = student_service.timetable()
            if not timetable:
                print("신청된 과목이 없습니다.")
            for course in timetable:
                print(f"{course.day} {course.time_text()} | {course.code}-{course.section} | {course.name}")
        elif choice == "0":
            print("로그아웃합니다.")
            break
        else:
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


def _input_course() -> Course | None:
    code = input("과목코드(숫자 4자리): ").strip()
    section = input("분반코드(숫자 2자리): ").strip()
    name = input("과목명: ").strip()
    credits_s = input("학점: ").strip()
    professor = input("담당교수: ").strip()
    day = input("요일(MON/TUE/WED/THU/FRI): ").strip().upper()
    start_s = input("시작시각(HH:MM): ").strip()
    end_s = input("종료시각(HH:MM): ").strip()
    status = input("상태(active/inactive, 기본 active): ").strip() or "active"
    capacity_s = input("정원(숫자, 기본 30): ").strip() or "30"

    if not credits_s.isdigit() or not capacity_s.isdigit():
        print("학점/정원은 숫자여야 합니다.")
        return None

    start = _parse_hhmm(start_s)
    end = _parse_hhmm(end_s)
    if start is None or end is None:
        print("시각 형식이 올바르지 않습니다. 예: 09:00")
        return None

    return Course(code, section, name, int(credits_s), professor, day, start, end, status, int(capacity_s))


def _admin_menu(admin_service: AdminService, admin_id: str) -> None:
    while True:
        _admin_header(admin_id, admin_service.config)

        print("1. 학생 등록")
        print("2. 학생 삭제")
        print("3. 학생 활성화")
        print("4. 강의 등록")
        print("5. 강의 수정 (수강신청 시작 전만 가능)")
        print("6. 강의 삭제")
        print("7. 강의 활성화")
        print("8. 전체 수강 현황 조회")
        print("9. 수강신청 기간 설정")
        print("0. 로그아웃")
        choice = input("선택: ").strip()

        if choice == "1":
            print("===== 학생 등록 ===== ")
            sid = input("학번(9자리): ").strip()
            pw = input("비밀번호: ").strip()
            name = input("이름: ").strip()
            selected = _choose_college_major(admin_service.colleges)
            if selected is None:
                continue
            college, major = selected
            _, msg = admin_service.register_student(Student(sid, pw, name, college, major, "active"))
            print(msg)
        elif choice == "2":
            print("===== 학생 삭제 ===== ")
            sid = input("삭제할 학생의 학번 입력 (0: 돌아가기) > ").strip()
            _, msg = admin_service.delete_student(sid)
            print(msg)
        elif choice == "3":
            print("===== 학생 활성화 =====")
            sid = input("활성화할 학생의 학번 입력 (0: 돌아가기) > ").strip()
            _, msg = admin_service.activate_student(sid)
            print(msg)
        elif choice == "4":
            print("===== 강의 등록 =====")
            course = _input_course()
            if course is None:
                continue
            _, msg = admin_service.add_course(course)
            print(msg)
        elif choice == "5":
            print("===== 강의 수정 =====")
            course = _input_course()
            if course is None:
                continue
            _, msg = admin_service.update_course(course)
            print(msg)
        elif choice == "6":
            print("===== 강의 삭제 =====")
            code = input("삭제할 과목코드 입력 (0: 돌아가기) > ").strip()
            section = input("삭제할 분반코드 입력 > ").strip()
            _, msg = admin_service.delete_course(code, section)
            print(msg)
        elif choice == "7":
            print("===== 강의 활성화 =====")
            code = input("활성화할 과목코드 입력 (0: 돌아가기) > ").strip()
            section = input("활성화할 분반코드 입력 > ").strip()
            _, msg = admin_service.activate_course(code, section)
            print(msg)
        elif choice == "8":
            print("===== 전체 수강 현황 =====\n과목코드 | 분반 | 과목명 | 정원 | 신청인원")
            for course, count in admin_service.enrollment_summary():
                print(f"{course.code} | {course.section} | {course.name} | {course.capacity} | {count}")
        elif choice == "9":
            print("===== 수강신청 기간 설정 =====")
            start_s = input("수강신청 시작일(YYYY-MM-DD): ").strip()
            end_s = input("수강신청 종료일(YYYY-MM-DD): ").strip()
            start = _parse_date(start_s)
            end = _parse_date(end_s)
            if start is None or end is None:
                print("날짜 형식이 올바르지 않습니다.")
                continue
            _, msg = admin_service.set_registration_period(start, end)
            print(msg)
        elif choice == "0":
            print("로그아웃합니다.")
            break
        else:
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    data_dir = project_root / "data" / "raw"

    while True:
        entered = input("프로그램 시작 날짜를 입력하세요 (YYYY-MM-DD): ").strip()
        current_date = _parse_date(entered)
        if current_date is not None:
            break
        print("날짜 형식이 올바르지 않습니다.")

    store = DataStore(data_dir)
    store.ensure_defaults(current_date)

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
        print("\n========================================\n   건국 수강신청 시뮬레이터\n========================================")
        print("1. 로그인")
        print("2. 회원가입")
        print("0. 종료")
        print("----------------------------------------")
        choice = input("선택 > ").strip()

        if choice == "1":
            first = True 
            while True:
                while True:
                    prompt = "\n---------------------------------------- \nID(학번 또는 관리자ID) > " if first else "ID(학번 또는 관리자ID) > "
                    user_id = input(prompt).strip()
                    first = False
                    if user_id in students or user_id in admins:
                        break
                    print("!!! 오류: 존재하지 않는 계정입니다.")

                go_back = False
                while True:
                    password = input("비밀번호 > ").strip()
                    role, user, msg = auth_service.login(user_id, password)

                    if role == "student":
                        print(msg)
                        student_service = StudentService(user, courses, enrollments, completed, config)
                        _student_menu(student_service, courses, enrollments)
                        _save_all(store, students, admins, courses, enrollments, completed, config)
                        break
                    elif role == "admin":
                        print(msg)
                        admin_service = AdminService(students, courses, enrollments, completed, colleges, config)
                        _admin_menu(admin_service, user_id)
                        _save_all(store, students, admins, courses, enrollments, completed, config)
                        break
                    else:
                        print(f"!!! 오류: {msg}")
                        if "비활성" in msg:
                            go_back = True
                            break

                if not go_back:
                    break

        elif choice == "2":
            print("\n===== 회원가입 =====")
            
            # 1. 학번 즉시 검증 루프
            while True:
                student_id = input("학번 (숫자 9자리) > ").strip()
                is_valid, msg = auth_service.validate_student_id(student_id)
                if is_valid:
                    break
                print(f"!!! 오류: {msg}")

            # 2. 비밀번호 입력 (형식 검사 후 바로 통과)
            while True:
                password = input("비밀번호 > ").strip()
                is_valid, msg = auth_service.validate_password_format(password, user_type="student")
                
                if is_valid:
                    break 

                print(f"!!! 오류: {msg}")

           # 3. 이름 입력 루프
            while True:
                name = input("이름 (한국어 완성형) > ").strip()
                
                # 아무것도 입력하지 않았을 때 (공백 포함)
                if not name:
                    continue
                
                # 한글 완성형 형식 검사
                is_valid, msg = auth_service.validate_name(name)
                
                if is_valid:
                    break
                else:
                    # "Kim", "ㄱㄴㄷ" 등 형식이 틀렸을 때만 오류 메시지 출력
                    print(f"!!! 오류: {msg}")

            # 4. 단과대 및 전공 선택
            selected = _choose_college_major(colleges)
            if selected is None:
                continue
            college, major = selected

            # 5. 최종 등록 및 저장
            ok, msg, _ = auth_service.signup_student(
                student_id=student_id,
                password=password,
                name=name,
                college=college,
                major=major,
            )
            print(msg)
            if ok:
                _save_all(store, students, admins, courses, enrollments, completed, config)

        elif choice == "0":
            _save_all(store, students, admins, courses, enrollments, completed, config)
            print("프로그램을 종료합니다.")
            break
        else:
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


if __name__ == "__main__":
    main()
