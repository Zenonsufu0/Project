# main.py — CLI 진입점: 메뉴 흐름·입출력만 담당, 규칙은 서비스 모듈에 위임 (구현: 이강준)
import sys
import unicodedata
from datetime import date
from pathlib import Path

from major_basics.modules.admin_service import AdminService
from major_basics.modules.auth import AuthService
from major_basics.modules.models import (
    Classroom,
    Course,
    Schedule,
    Student,
    VALID_DAYS,
    to_hhmm,
)
from major_basics.modules.storage import DataStore, IntegrityError
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
    """기획서 6.1: 현행 그레고리력에 존재하는 날짜."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_hhmm(value: str) -> int | None:
    """기획서: HH:MM, 분은 00 또는 30만 허용."""
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


def _header_sep(header: str) -> str:
    """헤더 문자열 → '-+-' 구분선 생성 (CJK 2열 너비 계산)."""
    def _vis(s: str) -> int:
        return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)
    return "-+-".join("-" * _vis(col) for col in header.split(" | "))


def _save_all(store, students, admins, courses, enrollments, completed, config,
              schedules, classrooms, prerequisites) -> None:
    store.save_students(students)
    store.save_admins(admins)
    store.save_courses(courses)
    store.save_enrollments(enrollments)
    store.save_completed(completed)
    store.save_config(config)
    store.save_schedules(schedules)
    store.save_classrooms(classrooms)
    store.save_prerequisites(prerequisites)


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


def _input_grade() -> int:
    print("===== 학년 선택 =====")
    while True:
        g = input("학년 입력 (1~4) > ").strip()
        if g in ("1", "2", "3", "4"):
            return int(g)
        print("!!! 오류: 학년은 1 이상 4 이하의 정수이어야 합니다.")


def _collect_student_fields(auth_service, colleges):
    """기획서 6.3 / 6.13.1: 학번·비번·이름·단과대·전공·학년을 항목별 재대기로 입력받아 반환.
    학번은 형식·중복 위반 시, 비밀번호·이름은 형식 위반 시 해당 항목 재대기. (취소 시 None)"""
    while True:
        student_id = input("학번 (숫자 9자리) > ").strip()
        ok, msg = auth_service.validate_student_id(student_id)
        if ok:
            break
        print(f"!!! 오류: {msg}")
    while True:
        password = input("비밀번호 > ").strip()
        ok, msg = auth_service.validate_password_format(password, user_type="student")
        if ok:
            break
        print(f"!!! 오류: {msg}")
    while True:
        name = input("이름 (한국어 완성형) > ").strip()
        if not name:
            continue
        ok, msg = auth_service.validate_name(name)
        if ok:
            break
        print(f"!!! 오류: {msg}")
    selected = _choose_college_major(colleges)
    if selected is None:
        return None
    college, major = selected
    grade = _input_grade()
    return student_id, password, name, college, major, grade


def _schedule_text(key, schedules) -> str:
    scheds = schedules.get(key, [])
    if not scheds:
        return "-"
    return " / ".join(f"{s.day} {s.time_text()}" for s in scheds)


def _room_text(key, schedules, classrooms) -> str:
    scheds = schedules.get(key, [])
    names = []
    for s in scheds:
        room = classrooms.get(s.classroom_code)
        disp = room.display_name() if room else s.classroom_code
        if disp not in names:
            names.append(disp)
    return " / ".join(names) if names else "-"


def _limit_text(course) -> str:
    parts = []
    if course.limit_grade != 0:
        parts.append(f"{course.limit_grade}학년")
    if course.limit_major != "전체":
        parts.append(course.limit_major)
    return "/".join(parts) if parts else "없음"


def _print_courses(courses, schedules, classrooms, student=None) -> None:
    """기획서 6.7.1/6.7.2 표 출력. student가 주어지면 학년·학과 제한 위반 과목에 [제한] 표시 (기획서 7절)."""
    if not courses:
        print("조회 결과가 없습니다.")
        return
    hdr = "번호 | 과목코드 | 분반코드 | 과목명 | 학점 | 스케줄 | 담당교수 | 강의실 | 정원 | 제한"
    print(hdr)
    print(_header_sep(hdr))
    for i, course in enumerate(courses, 1):
        sched_t = _schedule_text(course.key(), schedules)
        room_t = _room_text(course.key(), schedules, classrooms)
        limit_t = _limit_text(course)
        if student is not None:
            grade_ok = course.limit_grade == 0 or course.limit_grade == student.grade
            major_ok = course.limit_major == "전체" or course.limit_major == student.major
            if not (grade_ok and major_ok):
                limit_t += " [제한]"
        print(
            f"{i} | {course.code} | {course.section} | {course.name} | {course.credits} | "
            f"{sched_t} | {course.professor} | {room_t} | {course.capacity} | {limit_t}"
        )


def _student_menu(student_service, courses, enrollments, config, schedules, classrooms, prerequisites,
                  store, students, admins, completed) -> None:
    def save():
        # 기획서 2.3 '즉시 반영' / 설계 7.15: 상태 변경 직후 즉시 저장
        _save_all(store, students, admins, courses, enrollments, completed, config,
                  schedules, classrooms, prerequisites)

    while True:
        print("\n----------------------------------------")
        print(
            f"[학생 메뉴] {student_service.student.name} ({student_service.student.student_id})"
            f" | {student_service.student.grade}학년 | {config.semester}학기"
        )
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
            print(f"===== 개설 과목 목록 ({config.semester}) =====")
            _print_courses(student_service.list_courses(), schedules, classrooms, student_service.student)
            input("엔터를 누르면 메뉴로 돌아갑니다. > ")
        elif choice == "2":
            # 기획서 6.7.2: 과목 검색 → (선택) 번호. 단독 조회이므로 선택 결과는 사용하지 않음
            _search_and_select_course(student_service, schedules, classrooms)
        elif choice == "3":
            print("===== 기이수 과목 목록 =====")
            completed = student_service.list_completed()
            if not completed:
                print("등록된 기이수 과목이 없습니다.")
            else:
                hdr = "번호 | 과목코드 | 과목명"
                print(hdr)
                print(_header_sep(hdr))
                for i, code in enumerate(completed, 1):
                    name = next((c.name for c in courses.values() if c.code == code), "(삭제된 강의)")
                    print(f"{i} | {code} | {name}")
                print(f"총 {len(completed)}개 과목 이수 완료.")
            input("엔터를 누르면 메뉴로 돌아갑니다. > ")
        elif choice == "4":
            course = _search_and_select_course(student_service, schedules, classrooms)
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
            else:
                print(msg)
            save()
        elif choice == "5":
            if not student_service.is_registration_open():
                print("!!! 안내: 현재 수강신청 기간이 아닙니다.")
                continue
            _do_register(student_service, schedules, classrooms, prerequisites)
            save()
        elif choice == "6":
            if not student_service.is_registration_open():
                print("!!! 안내: 현재 수강신청 기간이 아닙니다.")
                continue
            _do_cancel(student_service)
            save()
        elif choice == "7":
            history = student_service.enrollment_history()
            if not history:
                print("신청 내역이 없습니다.")
            else:
                hdr = "번호 | 과목코드 | 분반코드 | 과목명 | 학점 | 상태 | 재수강"
                print(hdr)
                print(_header_sep(hdr))
                for i, enrollment in enumerate(history, 1):
                    course = courses.get(enrollment.key())
                    name = course.name if course else "(삭제된 강의)"
                    credits = course.credits if course else 0
                    retake = "Y" if student_service.is_retake(enrollment.course_code) else "N"
                    print(
                        f"{i} | {enrollment.course_code} | {enrollment.section} | {name} | "
                        f"{credits} | {enrollment.status} | {retake}"
                    )
                print(f"총 신청 학점 (enrolled): {student_service.current_credits()} / {StudentService.MAX_CREDITS}")
            input("엔터를 누르면 메뉴로 돌아갑니다. > ")
        elif choice == "8":
            _print_timetable(student_service, classrooms)
            input("엔터를 누르면 메뉴로 돌아갑니다. > ")
        elif choice == "0":
            print("로그아웃합니다.")
            break
        else:
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


def _search_and_select_course(student_service, schedules, classrooms):
    """기획서 6.7.2: 과목명 검색 → 번호 선택 → Course 반환 (0/재검색 거부 → None)."""
    while True:
        keyword = input("과목명 검색어 > ").strip()
        results = student_service.search_courses(keyword)
        if not results:
            print("검색 결과가 없습니다.")
            retry = input("다시 검색하시겠습니까? (1: 재검색 / 0: 돌아가기) > ").strip()
            if retry != "1":
                return None
            continue
        _print_courses(results, schedules, classrooms, student_service.student)
        print(f"총 {len(results)}건 검색됨.")
        while True:
            sel = input("선택 번호 입력 (0: 돌아가기) > ").strip()
            if sel == "0":
                return None
            if sel.isdigit() and 1 <= int(sel) <= len(results):
                return results[int(sel) - 1]
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


def _print_course_detail(selected, schedules, classrooms, prerequisites, courses) -> None:
    key = (selected.code, selected.section)
    sched_t = _schedule_text(key, schedules)
    room_t = _room_text(key, schedules, classrooms)
    print("\n[선택된 과목]")
    print(f"과목코드: {selected.code} | 분반코드: {selected.section} | 과목명: {selected.name} | 학점: {selected.credits}")
    print(f"스케줄: {sched_t} | 강의실: {room_t} | 담당교수: {selected.professor}")
    prereq_codes = sorted(prerequisites.get(selected.code, set()))
    if prereq_codes:
        names = ", ".join(
            next((c.name for c in courses.values() if c.code == pc), pc)
            for pc in prereq_codes
        )
        print(f"선수과목: {names}")
    else:
        print("선수과목: 없음")


def _do_register(student_service, schedules, classrooms, prerequisites) -> None:
    print("===== 수강신청 =====")
    raw = input("과목명 또는 과목코드와 분반코드 입력 (0: 돌아가기) > ").strip()
    if raw == "0":
        return
    parts = raw.split()
    if (len(parts) == 2 and parts[0].isdigit() and len(parts[0]) == 4
            and parts[1].isdigit() and len(parts[1]) == 2):
        # 과목코드+분반코드 직접 입력
        code, section = parts[0], parts[1]
        selected = student_service.courses.get((code, section))
        if not selected or selected.status != "active":
            # 존재하지 않는 과목코드/분반 또는 inactive → register()가 설계 6.9 1~3단계 메시지 출력
            _, msg, _ = student_service.register(code, section)
            print(msg)
            return
    else:
        # 과목명 검색 분기 (기획서 6.9 형식)
        results = student_service.search_courses(raw)
        if not results:
            print("검색 결과가 없습니다.")
            return
        _print_courses(results, schedules, classrooms, student_service.student)
        print(f"총 {len(results)}건 검색됨.")
        pick = input("번호 선택 (0: 돌아가기) > ").strip()
        if pick == "0":
            return
        if not pick.isdigit() or int(pick) < 1 or int(pick) > len(results):
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")
            return
        selected = results[int(pick) - 1]
    _print_course_detail(selected, schedules, classrooms, prerequisites, student_service.courses)
    confirm = input("신청하시겠습니까? (1: 예 / 0: 아니오) > ").strip()
    if confirm != "1":
        return
    _, msg, _ = student_service.register(selected.code, selected.section)
    print(msg)
    print(f"현재 총 신청 학점: {student_service.current_credits()} / {StudentService.MAX_CREDITS}")


def _do_cancel(student_service) -> None:
    print("===== 수강취소 =====")
    active = student_service._active_enrolled_map()
    if not active:
        print("!!! 안내: 취소 가능한 과목이 없습니다.")
        return
    items = []
    hdr = "번호 | 과목코드 | 분반코드 | 과목명 | 학점 | 재수강"
    print(hdr)
    print(_header_sep(hdr))
    for i, key in enumerate(sorted(active.keys()), 1):
        course = student_service.courses.get(key)
        name = course.name if course else f"{key[0]}-{key[1]}"
        credits = course.credits if course else 0
        retake = "Y" if student_service.is_retake(key[0]) else "N"
        items.append(key)
        print(f"{i} | {key[0]} | {key[1]} | {name} | {credits} | {retake}")
    while True:
        pick = input("취소할 과목 번호 입력 (0: 돌아가기) > ").strip()
        if pick == "0":
            return
        if pick.isdigit() and 1 <= int(pick) <= len(items):
            break
        print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")
    code, section = items[int(pick) - 1]
    course = student_service.courses.get((code, section))
    name = course.name if course else f"{code}-{section}"
    confirm = input(f"수강취소하시겠습니까? {name} (1: 예 / 0: 아니오) > ").strip()
    if confirm != "1":
        print("!!! 안내: 수강취소가 취소되었습니다.")
        return
    _, msg = student_service.cancel(code, section)
    print(msg)
    print(f"현재 총 신청 학점: {student_service.current_credits()} / {StudentService.MAX_CREDITS}")


def _print_timetable(student_service, classrooms) -> None:
    timetable = student_service.timetable()
    by_day = {"MON": [], "TUE": [], "WED": [], "THU": [], "FRI": []}
    for course, schedule in timetable:
        by_day.setdefault(schedule.day, []).append((course, schedule))
    print("===== 내 시간표 =====")
    for day in ("MON", "TUE", "WED", "THU", "FRI"):
        items = by_day.get(day, [])
        if not items:
            print(f"[{day}] 없음")
        else:
            for idx, (course, schedule) in enumerate(items):
                name = course.name if len(course.name) <= 15 else course.name[:15] + "..."
                room = classrooms.get(schedule.classroom_code)
                room_t = room.display_name() if room else schedule.classroom_code
                # 같은 요일 두 번째 줄부터는 요일 라벨 대신 들여쓰기 (기획서 6.12 목업)
                prefix = f"[{day}]" if idx == 0 else " " * (len(day) + 2)
                print(
                    f"{prefix} {to_hhmm(schedule.start_time)} ~ {to_hhmm(schedule.end_time)} "
                    f"{name} ({course.code}-{course.section}) | {room_t} | {course.credits}학점 | {course.professor}"
                )
    print(f"총 신청 학점: {student_service.current_credits()} / {StudentService.MAX_CREDITS}")


def _input_course_basic(courses) -> dict | None:
    """강의 등록 기본 필드 입력 (정원은 스케줄 등록 후 입력 — 설계 7.11).
    과목코드+분반코드가 이미 존재하면 과목코드 입력 프롬프트로 복귀 (기획서 6.14.1)."""
    print("===== 강의 등록 =====")
    while True:
        code = input("과목코드 (숫자 4자리) > ").strip()
        section = input("분반코드 (숫자 2자리) > ").strip()
        if (code, section) in courses:
            print("!!! 오류: 이미 존재하는 개설 강의입니다.")
            continue
        break
    name = input("과목명 > ").strip()
    credits_s = input("학점 (1~6 정수) > ").strip()
    professor = input("담당교수 > ").strip()
    semester = input("학기 (YYYY-S 형식, 예: 2026-1) > ").strip()
    limit_grade_s = input("제한학년 (0: 제한없음 / 1~4: 해당학년만) > ").strip()
    limit_major = input("제한학과 (전체 / 특정 전공명 입력) > ").strip()

    if not credits_s.isdigit() or not (1 <= int(credits_s) <= 6):
        print("!!! 오류: 학점은 1~6 사이의 정수여야 합니다.")
        return None
    if not (limit_grade_s.isdigit() and 0 <= int(limit_grade_s) <= 4):
        print("!!! 오류: 제한학년은 0 이상 4 이하의 정수여야 합니다.")
        return None
    if not limit_major:
        print("!!! 오류: 제한학과를 입력해야 합니다.")
        return None

    return {
        "code": code, "section": section, "name": name, "credits": int(credits_s),
        "professor": professor, "semester": semester,
        "limit_grade": int(limit_grade_s), "limit_major": limit_major,
    }


def _input_capacity(new_schedules, classrooms) -> int:
    """정원 입력 (설계 7.11: 스케줄 등록 후). 최소 좌석 초과 시 재입력 대기."""
    rooms = [classrooms[s.classroom_code] for s in new_schedules if s.classroom_code in classrooms]
    smallest = min(rooms, key=lambda r: r.seats) if rooms else None
    while True:
        capacity_s = input("정원 (1 이상의 정수) > ").strip()
        if not capacity_s.isdigit() or int(capacity_s) < 1:
            print("!!! 오류: 정원은 1 이상의 정수여야 합니다.")
            continue
        capacity = int(capacity_s)
        if smallest and capacity > smallest.seats:
            print(
                f"!!! 오류: 정원은 가장 작은 강의실({smallest.display_name()}, {smallest.seats}석)의 "
                f"좌석 수를 초과할 수 없습니다."
            )
            continue
        return capacity


def _input_schedules(code: str, section: str, classrooms) -> list[Schedule]:
    schedules: list[Schedule] = []
    days_used: set[str] = set()
    print("===== 스케줄 등록 =====")
    while True:
        day = input("요일 (MON/TUE/WED/THU/FRI) > ").strip().upper()
        if day not in VALID_DAYS:
            print("!!! 오류: 요일은 MON, TUE, WED, THU, FRI 중 하나여야 합니다.")
            continue
        if day in days_used:
            print("!!! 오류: 이미 해당 요일의 스케줄이 등록되었습니다.")
            continue
        start = _parse_hhmm(input("시작 시각 (HH:MM) > ").strip())
        end = _parse_hhmm(input("종료 시각 (HH:MM) > ").strip())
        if start is None or end is None:
            print("!!! 오류: 시각 형식이 올바르지 않습니다. 분은 00 또는 30만 허용됩니다.")
            continue
        if start >= end:
            print("!!! 오류: 종료 시각은 시작 시각보다 이후여야 합니다.")
            continue
        room_code = input("강의실코드 (숫자 4자리) > ").strip()
        room = classrooms.get(room_code)
        if not room:
            print("!!! 오류: 존재하지 않는 강의실코드입니다.")
            continue
        schedules.append(Schedule(code, section, day, start, end, room_code))
        days_used.add(day)
        print(f"✓ 스케줄 추가: {day} {to_hhmm(start)}~{to_hhmm(end)} ({room.display_name()}, {room.seats}석)")
        more = input("추가 스케줄이 있습니까? (1: 예 / 0: 아니오) > ").strip()
        if more != "1":
            break
    return schedules


def _manage_schedules(admin_service, code: str, section: str, classrooms) -> None:
    while True:
        scheds = admin_service.schedules.get((code, section), [])
        course = admin_service.courses.get((code, section))
        print(f"\n===== 스케줄 관리: {course.name} ({code}-{section}) =====")
        print("현재 스케줄:")
        for i, s in enumerate(scheds, 1):
            room = classrooms.get(s.classroom_code)
            room_t = f"{room.display_name()}, {room.seats}석" if room else s.classroom_code
            print(f"  {i}. {s.day} {s.time_text()} ({room_t})")
        sub = input("선택 (1:스케줄 추가 / 2:스케줄 삭제 / 3:강의실 변경 / 0:취소) > ").strip()
        if sub == "0":
            return
        elif sub == "1":
            day = input("요일 (MON/TUE/WED/THU/FRI) > ").strip().upper()
            start = _parse_hhmm(input("시작 시각 (HH:MM) > ").strip())
            end = _parse_hhmm(input("종료 시각 (HH:MM) > ").strip())
            room_code = input("강의실코드 (숫자 4자리) > ").strip()
            if start is None or end is None:
                print("!!! 오류: 시각 형식이 올바르지 않습니다. 분은 00 또는 30만 허용됩니다.")
                continue
            ok, msg = admin_service.add_schedule(Schedule(code, section, day, start, end, room_code))
            print(msg)
            return
        elif sub == "2":
            pick = input("삭제할 스케줄 번호 입력 > ").strip()
            if not pick.isdigit() or int(pick) < 1 or int(pick) > len(scheds):
                print("!!! 오류: 잘못된 번호입니다.")
                continue
            day = scheds[int(pick) - 1].day
            ok, msg = admin_service.delete_schedule(code, section, day)
            print(msg)
            return
        elif sub == "3":
            pick = input("변경할 스케줄 번호 입력 > ").strip()
            if not pick.isdigit() or int(pick) < 1 or int(pick) > len(scheds):
                print("!!! 오류: 잘못된 번호입니다.")
                continue
            day = scheds[int(pick) - 1].day
            new_code = input("새 강의실코드 (숫자 4자리) > ").strip()
            ok, msg = admin_service.update_schedule_classroom(code, section, day, new_code)
            print(msg)
            return
        else:
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


def _update_course_flow(admin_service, classrooms) -> None:
    print("===== 강의 수정 =====")
    code = input("수정할 과목코드 입력 (0: 돌아가기) > ").strip()
    if code == "0":
        return
    section = input("수정할 분반코드 입력 > ").strip()
    course = admin_service.courses.get((code, section))
    if not course:
        print("!!! 오류: 존재하지 않는 개설 강의입니다.")
        return
    if course.status == "inactive":
        print("!!! 오류: inactive 상태의 강의는 수정할 수 없습니다. 먼저 강의를 활성화하세요.")
        return
    print("[대상 강의 정보]")
    print(f"과목코드: {course.code} | 분반코드: {course.section} | 과목명: {course.name} | "
          f"학점: {course.credits} | 담당교수: {course.professor} | 정원: {course.capacity} | 상태: {course.status}")
    item = input("변경할 항목 선택 (1:과목명 2:학점 3:담당교수 4:상태 5:정원 6:스케줄 관리 0:취소) > ").strip()

    def _confirm_edit() -> bool:
        # 기획서 6.14.2 목업: 항목 값 입력 후 최종 확인
        if input("수정하시겠습니까? (1: 예 / 0: 아니오) > ").strip() == "1":
            return True
        print("!!! 안내: 강의 수정이 취소되었습니다.")
        return False

    if item == "0":
        return
    elif item == "1":
        name = input("새 과목명 > ").strip()
        if not _confirm_edit():
            return
        _, msg = admin_service.update_course_name(code, section, name)
        print(msg)
    elif item == "2":
        c = input("새 학점 (1~6) > ").strip()
        if not c.isdigit():
            print("!!! 오류: 학점은 1 이상 6 이하의 정수여야 합니다.")
            return
        if not _confirm_edit():
            return
        _, msg = admin_service.update_course_credits(code, section, int(c))
        print(msg)
    elif item == "3":
        prof = input("새 담당교수 > ").strip()
        if not _confirm_edit():
            return
        _, msg = admin_service.update_course_professor(code, section, prof)
        print(msg)
    elif item == "4":
        st = input("새 상태 (active / inactive) > ").strip()
        if not _confirm_edit():
            return
        _, msg = admin_service.update_course_status(code, section, st)
        print(msg)
    elif item == "5":
        c = input("새 정원 (1 이상의 정수) > ").strip()
        if not c.isdigit():
            print("!!! 오류: 정원은 1 이상의 정수여야 합니다.")
            return
        if not _confirm_edit():
            return
        _, msg = admin_service.update_course_capacity(code, section, int(c))
        print(msg)
    elif item == "6":
        _manage_schedules(admin_service, code, section, classrooms)
    else:
        print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


def _classroom_menu(admin_service) -> None:
    while True:
        print("\n===== 강의실 관리 =====")
        print("1. 강의실 목록 조회")
        print("2. 강의실 등록")
        print("0. 돌아가기")
        sub = input("선택 > ").strip()
        if sub == "0":
            return
        elif sub == "1":
            print("===== 강의실 목록 =====")
            hdr = "강의실코드 | 건물명 | 강의실번호 | 좌석수"
            print(hdr)
            print(_header_sep(hdr))
            for room in admin_service.list_classrooms():
                print(f"{room.classroom_code} | {room.building} | {room.room_number} | {room.seats}")
            input("엔터를 누르면 메뉴로 돌아갑니다. > ")
        elif sub == "2":
            print("===== 강의실 등록 =====")
            rcode = input("강의실코드 (숫자 4자리) > ").strip()
            building = input("건물명 > ").strip()
            room_no = input("강의실번호 > ").strip()
            seats_s = input("좌석 수 (1 이상의 정수) > ").strip()
            if not seats_s.isdigit() or int(seats_s) < 1:
                print("!!! 오류: 좌석 수는 1 이상의 정수여야 합니다.")
                continue
            _, msg = admin_service.add_classroom(Classroom(rcode, building, room_no, int(seats_s)))
            print(msg)
            input("엔터를 누르면 메뉴로 돌아갑니다. > ")
        else:
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


def _admin_menu(admin_service, auth_service, colleges, store, students, admins, courses, enrollments,
                completed, config, schedules, classrooms, prerequisites) -> None:
    def save():
        _save_all(store, students, admins, courses, enrollments, completed, config,
                  schedules, classrooms, prerequisites)

    while True:
        print("\n----------------------------------------")
        print("[관리자 메뉴] 관리자")
        print(
            f"오늘 날짜: {config.current_date.isoformat()} | "
            f"수강신청 기간: {config.reg_start.isoformat()} ~ {config.reg_end.isoformat()}"
        )
        print("----------------------------------------")
        print("1. 학생 등록")
        print("2. 학생 삭제")
        print("3. 학생 활성화")
        print("4. 강의 등록")
        print("5. 강의 수정")
        print("6. 강의 삭제")
        print("7. 강의 활성화")
        print("8. 전체 수강 현황 조회")
        print("9. 수강신청 기간 설정")
        print("10. 강의실 관리 (등록 / 조회)")
        print("0. 로그아웃")
        print("----------------------------------------")
        choice = input("선택 > ").strip()

        if choice == "1":
            print("===== 학생 등록 =====")
            fields = _collect_student_fields(auth_service, colleges)
            if fields is None:
                continue
            sid, pw, name, college, major, grade = fields
            _, msg = admin_service.register_student(Student(sid, pw, name, college, major, "active", grade))
            print(msg)
            save()
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
                print(f"학번: {target.student_id} | 이름: {target.name} | 단과대: {target.college} | "
                      f"전공: {target.major} | 상태: {target.status}")
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
                save()
                input("엔터를 누르면 메뉴로 돌아갑니다. > ")
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
                print(f"학번: {target.student_id} | 이름: {target.name} | 단과대: {target.college} | "
                      f"전공: {target.major} | 상태: {target.status}")
                if target.status == "active":
                    print("!!! 안내: 이미 active 상태의 학생입니다.")
                    break
                confirm = input("해당 학생을 활성화하시겠습니까? (1: 예 / 0: 아니오) > ").strip()
                if confirm != "1":
                    break
                _, msg = admin_service.activate_student(sid)
                print(msg)
                save()
                input("엔터를 누르면 메뉴로 돌아갑니다. > ")
                break
        elif choice == "4":
            fields = _input_course_basic(courses)
            if fields is None:
                continue
            new_schedules = _input_schedules(fields["code"], fields["section"], classrooms)
            capacity = _input_capacity(new_schedules, classrooms)
            course = Course(
                code=fields["code"], section=fields["section"], name=fields["name"],
                credits=fields["credits"], professor=fields["professor"], status="active",
                capacity=capacity, semester=fields["semester"],
                limit_grade=fields["limit_grade"], limit_major=fields["limit_major"],
            )
            _, msg = admin_service.add_course(course, new_schedules)
            print(msg)
            save()
        elif choice == "5":
            _update_course_flow(admin_service, classrooms)
            save()
        elif choice == "6":
            print("===== 강의 삭제 =====")
            while True:
                code = input("삭제할 과목코드 입력 (0: 돌아가기) > ").strip()
                if code == "0":
                    break
                section = input("삭제할 분반코드 입력 > ").strip()
                target_course = courses.get((code, section))
                if not target_course:
                    print("!!! 오류: 존재하지 않는 과목코드입니다.")
                    continue
                print("[대상 강의 정보]")
                print(f"과목코드: {target_course.code} | 분반코드: {target_course.section} | "
                      f"과목명: {target_course.name} | 스케줄: {_schedule_text(target_course.key(), schedules)} | "
                      f"상태: {target_course.status}")
                if target_course.status == "inactive":
                    print("!!! 안내: 이미 inactive 상태의 강의입니다.")
                    break
                confirm = input("해당 강의를 삭제(비활성화)하시겠습니까? (1: 예 / 0: 아니오) > ").strip()
                if confirm != "1":
                    print("!!! 안내: 강의 삭제가 취소되었습니다.")
                    break
                print("!!! 경고: 삭제된 강의는 inactive 상태로 전환됩니다.")
                _, msg = admin_service.delete_course(code, section)
                print(msg)
                save()
                input("엔터를 누르면 메뉴로 돌아갑니다. > ")
                break
        elif choice == "7":
            print("===== 강의 활성화 =====")
            while True:
                code = input("활성화할 과목코드 입력 (0: 돌아가기) > ").strip()
                if code == "0":
                    break
                section = input("활성화할 분반코드 입력 > ").strip()
                target_course = courses.get((code, section))
                if not target_course:
                    print("!!! 오류: 존재하지 않는 개설 강의입니다.")
                    continue
                print("[대상 강의 정보]")
                print(f"과목코드: {target_course.code} | 분반코드: {target_course.section} | "
                      f"과목명: {target_course.name} | 스케줄: {_schedule_text(target_course.key(), schedules)} | "
                      f"상태: {target_course.status}")
                if target_course.status == "active":
                    print("!!! 안내: 이미 active 상태의 강의입니다.")
                    break
                confirm = input("해당 강의를 활성화하시겠습니까? (1: 예 / 0: 아니오) > ").strip()
                if confirm != "1":
                    break
                _, msg = admin_service.activate_course(code, section)
                print(msg)
                save()
                input("엔터를 누르면 메뉴로 돌아갑니다. > ")
                break
        elif choice == "8":
            print("===== 전체 수강 현황 =====")
            hdr = "과목코드 | 분반코드 | 과목명 | 정원 | 신청 인원"
            print(hdr)
            print(_header_sep(hdr))
            for course, count in admin_service.enrollment_summary():
                print(f"{course.code} | {course.section} | {course.name} | {course.capacity} | {count}")
        elif choice == "9":
            print("===== 수강신청 기간 설정 =====")
            print(f"현재 설정: {config.reg_start.isoformat()} ~ {config.reg_end.isoformat()} | 학기: {config.semester}")
            while True:
                start = _parse_date(input("새로운 시작일 (YYYY-MM-DD) > ").strip())
                if start is None:
                    print("!!! 오류: 날짜 형식이 올바르지 않습니다.")
                    continue
                break
            while True:
                end = _parse_date(input("새로운 종료일 (YYYY-MM-DD) > ").strip())
                if end is None:
                    print("!!! 오류: 날짜 형식이 올바르지 않습니다.")
                    continue
                break
            new_sem = input("새로운 학기 (YYYY-S 형식, 예: 2026-1) > ").strip()
            _, msg = admin_service.set_registration_period(start, end, new_sem)
            print(msg)
            save()
        elif choice == "10":
            _classroom_menu(admin_service)
            save()
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
    # 기획서 5.5절: 파일 존재 및 읽기 권한 확인 — 생성/읽기 실패 시 오류 출력 후 종료
    try:
        store.ensure_defaults(current_date)
        errors = store.validate_integrity()
    except OSError as e:
        fname = Path(getattr(e, "filename", "") or "").name or "(알 수 없음)"
        print(f"!!! 오류: 데이터 파일 {fname}을 생성할 수 없거나 읽을 권한이 없습니다.")
        print("프로그램을 종료합니다.")
        return

    # 기획서 5.5절: 무결성 검사 (설계 7.2: 첫 번째 오류 메시지 출력 후 종료)
    if errors:
        print(f"!!! 오류: {errors[0]}")
        print("프로그램을 종료합니다.")
        return

    students = store.load_students()
    admins = store.load_admins()
    courses = store.load_courses()
    enrollments = store.load_enrollments()
    completed = store.load_completed()
    try:
        colleges = store.load_colleges()
    except IntegrityError as e:
        print(f"!!! 오류: {e}")
        print("프로그램을 종료합니다.")
        return
    config = store.load_config(current_date)
    config.current_date = current_date
    schedules = store.load_schedules()
    classrooms = store.load_classrooms()
    prerequisites = store.load_prerequisites()

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
            password = _input_password("비밀번호 > ")
            role, user, msg = auth_service.login(user_id, password)
            print(msg)

            if role == "student":
                student_service = StudentService(
                    user, courses, enrollments, completed, config, schedules, classrooms, prerequisites
                )
                _student_menu(student_service, courses, enrollments, config, schedules, classrooms, prerequisites,
                              store, students, admins, completed)
                _save_all(store, students, admins, courses, enrollments, completed, config,
                          schedules, classrooms, prerequisites)
            elif role == "admin":
                admin_service = AdminService(
                    students, courses, enrollments, completed, colleges, config,
                    schedules, classrooms, prerequisites
                )
                _admin_menu(admin_service, auth_service, colleges, store, students, admins, courses, enrollments,
                            completed, config, schedules, classrooms, prerequisites)
                _save_all(store, students, admins, courses, enrollments, completed, config,
                          schedules, classrooms, prerequisites)

        elif choice == "2":
            print("\n===== 회원가입 =====")
            fields = _collect_student_fields(auth_service, colleges)
            if fields is None:
                continue
            student_id, password, name, college, major, grade = fields

            ok, _msg, _ = auth_service.signup_student(
                student_id=student_id,
                password=password,
                password_check=password,
                name=name,
                college=college,
                major=major,
                grade=grade,
            )
            if ok:
                print(f"✓ 회원가입 완료: {name} ({student_id})")
                print("로그인 화면으로 돌아갑니다.")
                _save_all(store, students, admins, courses, enrollments, completed, config,
                          schedules, classrooms, prerequisites)

        elif choice == "0":
            _save_all(store, students, admins, courses, enrollments, completed, config,
                      schedules, classrooms, prerequisites)
            print("프로그램을 종료합니다.")
            break
        else:
            print("!!! 오류: 잘못된 입력입니다. 다시 선택하세요.")


if __name__ == "__main__":
    main()
