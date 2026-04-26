import re
import sys
from datetime import date
from pathlib import Path

from major_basics.modules.admin_service import AdminService
from major_basics.modules.auth import AuthService
from major_basics.modules.models import Course, Student
from major_basics.modules.storage import DataStore
from major_basics.modules.student_service import StudentService


def _input_password(prompt: str = "비밀번호 > ") -> str:
    """비밀번호 입력 시 * 마스킹. Windows: msvcrt, 그 외: getpass 사용."""
    print(prompt, end="", flush=True)
    if sys.platform == "win32":
        import msvcrt
        chars = []
        while True:
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):      # Enter
                print()
                break
            elif ch == "\x03":          # Ctrl+C
                print()
                raise KeyboardInterrupt
            elif ch in ("\x08", "\x7f"):  # Backspace
                if chars:
                    chars.pop()
                    print("\b \b", end="", flush=True)
            elif ch == "\x00" or ch == "\xe0":  # 특수키 (방향키 등) 무시
                msvcrt.getwch()
            else:
                chars.append(ch)
                print("*", end="", flush=True)
        return "".join(chars)
    else:
        import getpass
        return getpass.getpass("")


def _parse_date(value: str) -> date | None:
    """기획서 6.1: 현행 그레고리력에 존재하는 날짜. 연도는 2000-2099 범위."""
    try:
        d = date.fromisoformat(value)
        if not (2000 <= d.year <= 2099):
            return None
        return d
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


def _search_and_select_course(student_service: StudentService) -> Course | None:
    """기획서 6.4.2: 과목명 검색 → 번호 선택 → Course 반환 (0: 돌아가기 → None)."""
    while True:
        keyword = input("과목명 검색어 > ").strip()
        results = student_service.search_courses(keyword)
        if not results:
            print("검색 결과가 없습니다.")
            retry = input("다시 검색하시겠습니까? (1: 재검색 / 0: 돌아가기) > ").strip()
            if retry != "1":
                return None
            continue
        _print_courses(results)
        print(f"총 {len(results)}건 검색됨.")
        while True:
            sel = input("선택 번호 입력 (0: 돌아가기) > ").strip()
            if sel == "0":
                return None
            if sel.isdigit() and 1 <= int(sel) <= len(results):
                return results[int(sel) - 1]
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


def _student_menu(student_service: StudentService, courses: dict, enrollments: list, config, store, students, admins, completed) -> None:
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
        if student_service.is_registration_open():
            print("5. 수강신청")
            print("6. 수강취소")
        else:
            print("5. 수강신청 [기간 외]")
            print("6. 수강취소 [기간 외]")
        print("7. 신청 내역 조회")
        print("8. 내 시간표 조회")
        print("0. 로그아웃")
        print("----------------------------------------")
        choice = input("선택 > ").strip()

        if choice == "1":
            print("===== 개설 과목 목록 =====")
            counts = {}
            latest = {}
            for enrollment in enrollments:
                latest[(enrollment.student_id, enrollment.key())] = enrollment.status
            for (_, key), status in latest.items():
                if status == "enrolled":
                    counts[key] = counts.get(key, 0) + 1
            _print_courses(student_service.list_courses(), counts)
            input("엔터를 누르면 메뉴로 돌아갑니다. >")
        elif choice == "2":
            while True:
                keyword = input("과목명 검색어 > ").strip()
                results = student_service.search_courses(keyword)
                if not results:
                    print("검색 결과가 없습니다.")
                    retry = input("다시 검색하시겠습니까? (1: 재검색 / 0: 돌아가기) > ").strip()
                    if retry != "1":
                        break
                else:
                    _print_courses(results)
                    print(f"총 {len(results)}건 검색됨.")
                    break
        elif choice == "3":
            print("===== 기이수 과목 목록 =====")
            completed_list = student_service.list_completed()
            if not completed_list:
                print("등록된 기이수 과목이 없습니다.")
            else:
                print("번호 | 과목코드 | 과목명")
                for i, code in enumerate(completed_list, 1):
                    course_obj = next((c for c in courses.values() if c.code == code), None)
                    name_str = course_obj.name if course_obj else "(삭제된 강의)"
                    print(f"{i} | {code} | {name_str}")
                print(f"총 {len(completed_list)}개 과목 이수 완료.")
            input("엔터를 누르면 메뉴로 돌아갑니다. >")
        elif choice == "4":
            course = _search_and_select_course(student_service)
            if course is None:
                continue
            code = course.code
            if student_service.is_currently_enrolled(code):
                confirm = input(
                    "이 과목은 현재 수강신청 중입니다. 기이수로 추가하시겠습니까? (1: 예 / 0: 아니오) > "
                ).strip()
                if confirm != "1":
                    print("기이수 처리가 취소되었습니다.")
                    continue
                student_service.force_cancel_enrollment(code)
                print("수강신청이 취소 처리되었습니다.")
            ok, msg = student_service.add_completed(code)
            if ok:
                print(f"기이수 과목으로 추가되었습니다: {course.name}")
                _save_all(store, students, admins, courses, enrollments, completed, config)
            else:
                print(msg)
        elif choice == "5":
            if not student_service.is_registration_open():
                print("!!! 안내: 현재 수강신청 기간이 아닙니다.")
                continue
            print("===== 수강신청 =====")
            raw = input("과목명 또는 과목코드와 분반코드 입력 (0: 돌아가기) > ").strip()
            if raw == "0":
                continue
            # "1001 01" 형식 → 과목코드+분반코드 직접 조회
            parts = raw.split()
            if (len(parts) == 2
                    and parts[0].isdigit() and len(parts[0]) == 4
                    and parts[1].isdigit() and len(parts[1]) == 2):
                key = (parts[0], parts[1])
                course_obj = student_service.courses.get(key)
                if not course_obj or course_obj.status != "active":
                    print("검색 결과가 없습니다.")
                    continue
                selected = course_obj
            else:
                # 과목명 검색어
                results = student_service.search_courses(raw)
                if not results:
                    print("검색 결과가 없습니다.")
                    continue
                _print_courses(results)
                print(f"총 {len(results)}건 검색됨.")
                pick = input("번호 선택 (0: 돌아가기) > ").strip()
                if pick == "0":
                    continue
                if not pick.isdigit() or int(pick) < 1 or int(pick) > len(results):
                    print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")
                    continue
                selected = results[int(pick) - 1]
            print("\n[선택된 과목]")
            print(f"과목코드: {selected.code} | 분반코드: {selected.section} | 과목명: {selected.name} | "
                  f"학점: {selected.credits} | {selected.day} {selected.time_text()} | {selected.professor}")
            confirm = input("신청하시겠습니까? (1: 예 / 0: 아니오) > ").strip()
            if confirm != "1":
                continue
            _, msg, _ = student_service.register(selected.code, selected.section)
            print(msg)
            print(f"현재 총 신청 학점: {student_service.current_credits()} / {StudentService.MAX_CREDITS}")
            _save_all(store, students, admins, courses, enrollments, completed, config)
        elif choice == "6":
            if not student_service.is_registration_open():
                print("!!! 안내: 현재 수강신청 기간이 아닙니다.")
                continue
            timetable = student_service.timetable()
            if not timetable:
                print("!!! 안내: 취소 가능한 과목이 없습니다.")
                continue
            print("===== 수강취소 =====")
            print("번호 | 과목코드 | 분반코드 | 과목명 | 학점 | 재수강")
            for i, course in enumerate(timetable, 1):
                retake = "Y" if student_service.is_retake(course.code) else "N"
                print(f"{i} | {course.code} | {course.section} | {course.name} | {course.credits} | {retake}")
            while True:
                num_str = input("취소할 과목 번호 입력 (0: 돌아가기) > ").strip()
                if num_str == "0":
                    break
                if not num_str.isdigit() or int(num_str) < 1 or int(num_str) > len(timetable):
                    print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")
                    continue
                selected = timetable[int(num_str) - 1]
                confirm = input(f"수강취소하시겠습니까? {selected.name} (1: 예 / 0: 아니오) > ").strip()
                if confirm != "1":
                    break
                _, msg = student_service.cancel(selected.code, selected.section)
                print(msg)
                print(f"현재 총 신청 학점: {student_service.current_credits()} / {StudentService.MAX_CREDITS}")
                _save_all(store, students, admins, courses, enrollments, completed, config)
                break
        elif choice == "7":
            print("===== 신청 내역 조회 =====")
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
            input("엔터를 누르면 메뉴로 돌아갑니다. >")
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
            input("엔터를 누르면 메뉴로 돌아갑니다. >")
        elif choice == "0":
            print("로그아웃합니다.")
            break
        else:
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


def _input_course() -> Course:
    """각 항목을 입력받고 즉시 검증. 오류 시 해당 항목만 재입력."""
    while True:
        code = input("과목코드 (숫자 4자리) > ").strip()
        if code.isdigit() and len(code) == 4:
            break
        print("!!! 오류: 과목코드는 숫자 4자리여야 합니다.")

    while True:
        section = input("분반코드 (숫자 2자리) > ").strip()
        if section.isdigit() and len(section) == 2:
            break
        print("!!! 오류: 분반코드는 숫자 2자리여야 합니다.")

    while True:
        name = input("과목명 > ").strip()
        if name and "\t" not in name and "\n" not in name:
            break
        print("!!! 오류: 과목명은 1자 이상이어야 하며 탭/개행을 포함할 수 없습니다.")

    while True:
        credits_s = input("학점 (1~6 정수) > ").strip()
        if credits_s.isdigit() and 1 <= int(credits_s) <= 6:
            break
        print("!!! 오류: 학점은 1 이상 6 이하의 정수여야 합니다.")

    while True:
        professor = input("담당교수 > ").strip()
        if professor and "\t" not in professor and "\n" not in professor:
            break
        print("!!! 오류: 담당교수는 1자 이상이어야 하며 탭/개행을 포함할 수 없습니다.")

    while True:
        day = input("요일 (MON/TUE/WED/THU/FRI) > ").strip().upper()
        if day in ("MON", "TUE", "WED", "THU", "FRI"):
            break
        print("!!! 오류: 요일은 MON, TUE, WED, THU, FRI 중 하나여야 합니다.")

    while True:
        start_s = input("시작 시각 (HH:MM) > ").strip()
        start = _parse_hhmm(start_s)
        if start is not None:
            break
        print("!!! 오류: 시각 형식이 올바르지 않습니다. HH:MM, 분은 00 또는 30만 허용됩니다.")

    while True:
        end_s = input("종료 시각 (HH:MM) > ").strip()
        end = _parse_hhmm(end_s)
        if end is None:
            print("!!! 오류: 시각 형식이 올바르지 않습니다. HH:MM, 분은 00 또는 30만 허용됩니다.")
            continue
        if end <= start:
            print("!!! 오류: 종료 시각은 시작 시각보다 이후여야 합니다.")
            continue
        break

    while True:
        capacity_s = input("정원 (1 이상의 정수) > ").strip()
        if capacity_s.isdigit() and int(capacity_s) >= 1:
            break
        print("!!! 오류: 정원은 1 이상의 정수여야 합니다.")

    return Course(code, section, name, int(credits_s), professor, day, start, end, "active", int(capacity_s))


def _admin_menu(admin_service: AdminService, admin_id: str, colleges, store, students, admins, courses, enrollments, completed, config) -> None:
    while True:
        print("\n----------------------------------------")
        print(f"[관리자 메뉴] 관리자 ({admin_id})")
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
            print("===== 학생 등록 =====")
            while True:
                sid = input("학번 (숫자 9자리) > ").strip()
                if not (sid.isdigit() and len(sid) == 9):
                    print("!!! 오류: 학번은 숫자 9자리이어야 합니다.")
                    continue
                if sid in students:
                    print("!!! 오류: 이미 존재하는 학번입니다.")
                    continue
                break
            while True:
                pw = input("비밀번호 > ").strip()
                if re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]{6,12}", pw):
                    break
                print("!!! 오류: 비밀번호는 영문자와 숫자를 각각 1자 이상 포함한 6~12자이어야 합니다.")
            while True:
                name = input("이름 (한국어 완성형) > ").strip()
                if re.fullmatch(r"[가-힣]+", name):
                    break
                print("!!! 오류: 이름은 한국어 완성형 글자로만 이루어져야 합니다.")
            selected = _choose_college_major(colleges)
            if selected is None:
                continue
            college, major = selected
            _, msg = admin_service.register_student(Student(sid, pw, name, college, major, "active"))
            print(msg)
            _save_all(store, students, admins, courses, enrollments, completed, config)
            input("엔터를 누르면 메뉴로 돌아갑니다. >")
        elif choice == "2":
            print("===== 학생 삭제 =====")
            while True:
                sid = input("삭제할 학생의 학번 입력 (0: 돌아가기) > ").strip()
                if sid == "0":
                    break
                target = students.get(sid)
                if not target:
                    print("!!! 오류: 해당 학번의 학생이 없습니다.")
                    continue
                print("[대상 학생 정보]")
                print(f"학번: {target.student_id} | 이름: {target.name} | 단과대: {target.college} | 전공: {target.major} | 상태: {target.status}")
                if target.status == "inactive":
                    print("!!! 안내: 이미 inactive 상태의 학생입니다.")
                    break
                confirm = input("해당 학생을 삭제(비활성화)하시겠습니까? (1: 예 / 0: 아니오) > ").strip()
                if confirm != "1":
                    print("!!! 안내: 학생 삭제가 취소되었습니다.")
                    break
                print("!!! 경고: 삭제된 학생은 inactive 상태로 전환됩니다.")
                _, msg = admin_service.delete_student(sid)
                print(msg)
                _save_all(store, students, admins, courses, enrollments, completed, config)
                input("엔터를 누르면 메뉴로 돌아갑니다. >")
                break
        elif choice == "3":
            print("===== 학생 활성화 =====")
            while True:
                sid = input("활성화할 학생의 학번 입력 (0: 돌아가기) > ").strip()
                if sid == "0":
                    break
                target = students.get(sid)
                if not target:
                    print("!!! 오류: 해당 학번의 학생이 없습니다.")
                    continue
                print("[대상 학생 정보]")
                print(f"학번: {target.student_id} | 이름: {target.name} | 단과대: {target.college} | 전공: {target.major} | 상태: {target.status}")
                if target.status == "active":
                    print("!!! 안내: 이미 active 상태의 학생입니다.")
                    break
                confirm = input("해당 학생을 활성화하시겠습니까? (1: 예 / 0: 아니오) > ").strip()
                if confirm != "1":
                    break
                _, msg = admin_service.activate_student(sid)
                print(msg)
                _save_all(store, students, admins, courses, enrollments, completed, config)
                input("엔터를 누르면 메뉴로 돌아갑니다. >")
                break
        elif choice == "4":
            print("===== 강의 등록 =====")
            while True:
                course = _input_course()
                ok, msg = admin_service.add_course(course)
                print(msg)
                if ok:
                    _save_all(store, students, admins, courses, enrollments, completed, config)
                    input("엔터를 누르면 메뉴로 돌아갑니다. >")
                    break
                # 중복 강의인 경우 과목코드 입력부터 재시작
        elif choice == "5":
            if config.reg_start <= config.current_date <= config.reg_end:
                print("!!! 오류: 수강신청 기간 중에는 강의를 수정할 수 없습니다.")
                continue
            print("===== 강의 수정 =====")
            _update_found = False
            while True:
                code = input("수정할 과목코드 입력 (0: 돌아가기) > ").strip()
                if code == "0":
                    break
                section = input("수정할 분반코드 입력 > ").strip()
                target_c = courses.get((code, section))
                if not target_c:
                    print("!!! 오류: 존재하지 않는 개설 강의입니다.")
                    continue
                if target_c.status == "inactive":
                    print("!!! 오류: inactive 상태의 강의는 수정할 수 없습니다. 먼저 강의를 활성화하세요.")
                    break
                _update_found = True
                break
            if not _update_found:
                continue
            print("[대상 강의 정보]")
            print(f"과목코드: {target_c.code} | 분반코드: {target_c.section} | 과목명: {target_c.name} | "
                  f"시간: {target_c.day} {target_c.time_text()} | 정원: {target_c.capacity}")
            field = input("변경할 항목 선택 (1:과목명 2:학점 3:담당교수 4:요일 5:시간 6:상태 7:정원 0:취소) > ").strip()
            if field == "0":
                continue
            n_name = target_c.name
            n_credits = target_c.credits
            n_professor = target_c.professor
            n_day = target_c.day
            n_start = target_c.start_time
            n_end = target_c.end_time
            n_status = target_c.status
            n_capacity = target_c.capacity
            if field == "1":
                while True:
                    v = input("새로운 과목명 > ").strip()
                    if v and "\t" not in v and "\n" not in v:
                        n_name = v; break
                    print("!!! 오류: 과목명은 1자 이상이어야 하며 탭/개행을 포함할 수 없습니다.")
            elif field == "2":
                while True:
                    v = input("새로운 학점 (1~6 정수) > ").strip()
                    if v.isdigit() and 1 <= int(v) <= 6:
                        n_credits = int(v); break
                    print("!!! 오류: 학점은 1 이상 6 이하의 정수여야 합니다.")
            elif field == "3":
                while True:
                    v = input("새로운 담당교수 > ").strip()
                    if v and "\t" not in v and "\n" not in v:
                        n_professor = v; break
                    print("!!! 오류: 담당교수는 1자 이상이어야 하며 탭/개행을 포함할 수 없습니다.")
            elif field == "4":
                while True:
                    v = input("새로운 요일 (MON/TUE/WED/THU/FRI) > ").strip().upper()
                    if v in ("MON", "TUE", "WED", "THU", "FRI"):
                        n_day = v; break
                    print("!!! 오류: 요일은 MON, TUE, WED, THU, FRI 중 하나여야 합니다.")
            elif field == "5":
                while True:
                    v = input("새로운 요일 (MON/TUE/WED/THU/FRI) > ").strip().upper()
                    if v in ("MON", "TUE", "WED", "THU", "FRI"):
                        n_day = v; break
                    print("!!! 오류: 요일은 MON, TUE, WED, THU, FRI 중 하나여야 합니다.")
                while True:
                    v = input("새로운 시작 시각 (HH:MM) > ").strip()
                    t = _parse_hhmm(v)
                    if t is not None:
                        n_start = t; break
                    print("!!! 오류: 시각 형식이 올바르지 않습니다. HH:MM, 분은 00 또는 30만 허용됩니다.")
                while True:
                    v = input("새로운 종료 시각 (HH:MM) > ").strip()
                    t = _parse_hhmm(v)
                    if t is None:
                        print("!!! 오류: 시각 형식이 올바르지 않습니다. HH:MM, 분은 00 또는 30만 허용됩니다.")
                        continue
                    if t <= n_start:
                        print("!!! 오류: 종료 시각은 시작 시각보다 이후여야 합니다.")
                        continue
                    n_end = t; break
            elif field == "6":
                while True:
                    v = input("새로운 상태 (active/inactive) > ").strip()
                    if v in ("active", "inactive"):
                        n_status = v; break
                    print("!!! 오류: 상태는 active 또는 inactive여야 합니다.")
            elif field == "7":
                while True:
                    v = input("새로운 정원 (1 이상의 정수) > ").strip()
                    if v.isdigit() and int(v) >= 1:
                        n_capacity = int(v); break
                    print("!!! 오류: 정원은 1 이상의 정수여야 합니다.")
            else:
                print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")
                continue
            confirm = input("수정하시겠습니까? (1: 예 / 0: 아니오) > ").strip()
            if confirm != "1":
                continue
            updated = Course(code, section, n_name, n_credits, n_professor, n_day, n_start, n_end, n_status, n_capacity)
            _, msg = admin_service.update_course(updated)
            print(msg)
            _save_all(store, students, admins, courses, enrollments, completed, config)
            input("엔터를 누르면 메뉴로 돌아갑니다. >")
        elif choice == "6":
            print("===== 강의 삭제 =====")
            while True:
                code = input("삭제할 과목코드 입력 (0: 돌아가기) > ").strip()
                if code == "0":
                    break
                if not (code.isdigit() and len(code) == 4):
                    print("!!! 오류: 과목코드는 숫자 4자리여야 합니다.")
                    continue
                section = input("삭제할 분반코드 입력 > ").strip()
                target_course = courses.get((code, section))
                if not target_course:
                    print("!!! 오류: 존재하지 않는 과목코드입니다.")
                    continue
                print("[대상 강의 정보]")
                print(f"과목코드: {target_course.code} | 분반코드: {target_course.section} | "
                      f"과목명: {target_course.name} | 시간: {target_course.day} {target_course.time_text()} | 상태: {target_course.status}")
                if target_course.status == "inactive":
                    print("!!! 안내: 이미 inactive 상태의 강의입니다.")
                    break
                confirm = input("해당 강의를 삭제(비활성화)하시겠습니까? (1: 예 / 0: 아니오) > ").strip()
                if confirm != "1":
                    print("!!! 안내: 강의 삭제가 취소되었습니다.")
                    break
                print("!!! 경고: 삭제된 강의는 inactive 상태로 전환됩니다.")
                _, msg = admin_service.delete_course(target_course.code, target_course.section)
                print(msg)
                _save_all(store, students, admins, courses, enrollments, completed, config)
                input("엔터를 누르면 메뉴로 돌아갑니다. >")
                break
        elif choice == "7":
            print("===== 강의 활성화 =====")
            while True:
                code = input("활성화할 과목코드 입력 (0: 돌아가기) > ").strip()
                if code == "0":
                    break
                section = input("활성화할 분반코드 입력 > ").strip()
                target_c = courses.get((code, section))
                if not target_c:
                    print("!!! 오류: 존재하지 않는 개설 강의입니다.")
                    continue
                print("[대상 강의 정보]")
                print(f"과목코드: {target_c.code} | 분반코드: {target_c.section} | "
                      f"과목명: {target_c.name} | 시간: {target_c.day} {target_c.time_text()} | 상태: {target_c.status}")
                if target_c.status == "active":
                    print("!!! 안내: 이미 active 상태의 강의입니다.")
                    break
                confirm = input("해당 강의를 활성화하시겠습니까? (1: 예 / 0: 아니오) > ").strip()
                if confirm != "1":
                    break
                _, msg = admin_service.activate_course(code, section)
                print(msg)
                _save_all(store, students, admins, courses, enrollments, completed, config)
                input("엔터를 누르면 메뉴로 돌아갑니다. >")
                break
        elif choice == "8":
            print("===== 전체 수강 현황 =====")
            print("과목코드 | 분반코드 | 과목명 | 정원 | 신청 인원")
            for course, count in admin_service.enrollment_summary():
                print(f"{course.code} | {course.section} | {course.name} | {course.capacity} | {count}")
            input("엔터를 누르면 메뉴로 돌아갑니다. >")
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
                if end < start:
                    print("!!! 오류: 종료일은 시작일과 같거나 이후여야 합니다.")
                    continue
                break
            _, msg = admin_service.set_registration_period(start, end)
            print(msg)
            _save_all(store, students, admins, courses, enrollments, completed, config)
            input("엔터를 누르면 메뉴로 돌아갑니다. >")
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
            # 기획서 6.4: ID 오류 → ID 재입력, 비밀번호 오류 → 비밀번호만 재입력
            role, user, msg = "none", None, ""
            while True:
                user_id = input("ID (학번 또는 관리자 ID) > ").strip()
                id_ok, id_err = auth_service.check_user_id(user_id)
                if not id_ok:
                    print(id_err)
                    continue
                while True:
                    password = _input_password("비밀번호 > ")
                    role, user, msg = auth_service.login(user_id, password)
                    if role == "none":
                        print(msg)
                        continue
                    break
                break

            if role == "student":
                student_service = StudentService(user, courses, enrollments, completed, config)
                _student_menu(student_service, courses, enrollments, config, store, students, admins, completed)
                _save_all(store, students, admins, courses, enrollments, completed, config)
            elif role == "admin":
                admin_service = AdminService(students, courses, enrollments, completed, colleges, config)
                _admin_menu(admin_service, user_id, colleges, store, students, admins, courses, enrollments, completed, config)
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
