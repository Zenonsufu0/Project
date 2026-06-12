# -*- coding: utf-8 -*-
"""2차 검사보고서용 TC 스크린샷 생성기.

실제 main()을 인프로세스로 구동(입력 에코·비밀번호 마스킹 포함)해 세션 로그를 캡처하고,
TC별 구간을 잘라 1차 보고서와 동일한 다크 터미널 스타일 PNG로 렌더한다.
교수 안내에 따라 파일 생성·단일 메시지 등 자명한 TC는 제외하고
상호작용 화면 TC만 대상으로 한다.

실행: python _gen_tc_screenshots.py   →  _tc_shots/<tid>.png
"""
import builtins
import io
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import major_basics.main as M  # noqa: E402

DATA_DIR = ROOT / "data" / "raw"
SHOT_DIR = ROOT / "발표준비" / "_tc_shots"

# ------------------------------------------------------------------
# 세션 정의 (입력 시퀀스) — 순서대로 같은 data/raw 위에서 누적 실행
# ------------------------------------------------------------------
SESSIONS = [
    ("signup", [
        "2026-04-01",
        "2", "202512345", "Pass123", "김건국", "1", "1", "5", "2",   # 학년 5 오류 → 2 (6.3-14/15)
        "2", "202511111", "Pass123", "이신입", "1", "1", "1",        # 1학년 컴공
        "2", "202522222", "Pass123", "박전기", "1", "2", "2",        # 2학년 전기
        "2", "202544444", "Pass123", "최고참", "1", "1", "3",        # 3학년 컴공
        "0",
    ]),
    ("admin_setup", [
        "2026-04-01", "1", "admin01", "Admin@1234",
        # 강의 등록 3건 (충돌용 / 경계용 / 타학기)
        "4", "9999", "01", "충돌검증과목", "3", "김교수", "2026-1", "0", "전체",
        "MON", "13:00", "14:30", "1001", "0", "30",
        "4", "7002", "01", "경계검증과목", "3", "이교수", "2026-1", "0", "전체",
        "MON", "10:30", "12:00", "1002", "0", "30",
        "4", "8888", "01", "타학기과목", "3", "정교수", "2026-2", "0", "전체",
        "FRI", "13:00", "14:30", "1001", "0", "30",
        # 1001-02 삭제 (inactive 제외 셋업)
        "6", "1001", "02",
        # 학생 등록 (6.13-10)
        "1", "202533333", "Pass123", "정컴공", "1", "1", "2",
        # 기간 설정: 시작=종료 (6.15-9) → 2026-2 (6.15-8) → 복구
        "9", "2026-04-01", "2026-04-01", "2026-1",
        "9", "2026-09-01", "2026-09-07", "2026-2",
        "9", "2026-04-01", "2026-04-30", "2026-1",
        # 강의실 관리: 목록(6.17-1) / 등록(6.17-2) / 중복(6.17-3)
        "10", "1", "", "2", "1004", "과학관", "301", "50", "",
        "2", "1001", "공학관", "999", "10", "", "0",
        "0", "0",
    ]),
    ("stu2", [   # 2학년 컴퓨터공학부
        "2026-04-01", "1", "202512345", "Pass123",
        "1", "",                       # 조회 (6.7-7/8/9/10)
        "5", "1002 01", "1",           # 자료구조 신청 성공
        "5", "9999 01", "1",           # 스케줄 충돌 (6.9-20)
        "5", "8888 01", "1",           # 학기 불일치 (6.9-15)
        "5", "1001 01", "1",           # 프로그래밍기초 신청 성공
        "5", "7002 01", "1",           # 반열림 경계 성공 (6.9-21)
        "8", "",                       # 시간표 (6.12-4/5)
        "0", "0",
    ]),
    ("stu1", [   # 1학년 컴퓨터공학부
        "2026-04-01", "1", "202511111", "Pass123",
        "1", "",                       # [제한] 표시 (6.7-11)
        "5", "1002 01", "1",           # 학년 제한 (6.9-16)
        "0", "0",
    ]),
    ("stuE", [   # 2학년 전기공학부
        "2026-04-01", "1", "202522222", "Pass123",
        "5", "1002 01", "1",           # 학과 제한 (6.9-17)
        "0", "0",
    ]),
    ("stu3", [   # 3학년 컴퓨터공학부
        "2026-04-01", "1", "202544444", "Pass123",
        "5", "1003 01", "1",           # 선수과목 미이수 (6.9-18)
        "4", "자료구조", "1",          # 기이수 추가 (검색→선택)
        "5", "1003 01", "1",           # 이수 후 성공 (6.9-19)
        "0", "0",
    ]),
    ("stu533", [  # 2학년 컴공 — 1002 enrolled 2명 만들기
        "2026-04-01", "1", "202533333", "Pass123",
        "5", "1002 01", "1",
        "0", "0",
    ]),
    ("admin_after", [
        "2026-04-01", "1", "admin01", "Admin@1234",
        "5", "1002", "01", "5", "1",        # 정원 1 → 신청 인원(2명) 차단 (6.14-23)
        "5", "1001", "01", "1", "새과목명",  # 기간 후 과목명 차단 (6.14-19)
        "5", "1001", "01", "5", "50",       # 정원 증가 허용 (6.14-21)
        "5", "1001", "01", "5", "70",       # 최소 좌석 초과 (6.14-22)
        "0", "0",
    ]),
]

# ------------------------------------------------------------------
# 컷 정의: (tid, session, (start_substr, occurrence), end_substr, pad_before, after_lines)
# ------------------------------------------------------------------
CUTS = [
    ("6.3-14", "signup", ("학년 입력 (1~4) > 5", 1), "이상 4 이하의 정수", 1, 1),
    ("6.3-15", "signup", ("===== 회원가입", 1), "로그인 화면으로 돌아갑니다.", 0, 0),
    ("6.13-10", "admin_setup", ("===== 학생 등록", 1), "학생 등록 완료", 0, 0),
    ("6.15-9", "admin_setup", ("새로운 시작일 (YYYY-MM-DD) > 2026-04-01", 1), "2026-04-01 ~ 2026-04-01 | 학기: 2026-1", 2, 0),
    ("6.15-8", "admin_setup", ("새로운 시작일 (YYYY-MM-DD) > 2026-09-01", 1), "학기: 2026-2", 2, 0),
    ("6.17-1", "admin_setup", ("===== 강의실 목록", 1), "엔터를 누르면 메뉴로 돌아갑니다. > ", 0, 0),
    ("6.17-2", "admin_setup", ("강의실코드 (숫자 4자리) > 1004", 1), "강의실 등록 완료", 1, 0),
    ("6.17-3", "admin_setup", ("강의실코드 (숫자 4자리) > 1001", 1), "이미 존재하는 강의실코드", 1, 0),
    ("6.7-7", "stu2", ("===== 개설 과목 목록", 1), "엔터를 누르면 메뉴로 돌아갑니다. > ", 0, 0),
    ("6.9-20", "stu2", ("> 9999 01", 1), "스케줄 충돌", 0, 0),
    ("6.9-15", "stu2", ("> 8888 01", 1), "개설된 과목이 아닙니다", 0, 0),
    ("6.9-21", "stu2", ("> 7002 01", 1), "현재 총 신청 학점", 0, 0),
    ("6.12-4", "stu2", ("===== 내 시간표", 1), "총 신청 학점", 0, 0),
    ("6.7-11", "stu1", ("===== 개설 과목 목록", 1), "엔터를 누르면 메뉴로 돌아갑니다. > ", 0, 0),
    ("6.9-16", "stu1", ("> 1002 01", 1), "학생만 수강신청할 수 있습니다", 0, 0),
    ("6.9-17", "stuE", ("> 1002 01", 1), "학생만 수강신청할 수 있습니다", 0, 0),
    ("6.9-18", "stu3", ("> 1003 01", 1), "미이수 선수과목", 0, 0),
    ("6.9-19", "stu3", ("> 1003 01", 2), "현재 총 신청 학점", 0, 0),
    ("6.14-23", "admin_after", ("새 정원 (1 이상의 정수) > 1", 1), "이상이어야 합니다", 4, 0),
    ("6.14-19", "admin_after", ("새 과목명 > 새과목명", 1), "과목명을 수정할 수 없습니다", 4, 0),
    ("6.14-21", "admin_after", ("새 정원 (1 이상의 정수) > 50", 1), "정원 → 50", 4, 0),
    ("6.14-22", "admin_after", ("새 정원 (1 이상의 정수) > 70", 1), "좌석 수를 초과할 수 없습니다", 4, 0),
]

# 같은 화면을 공유하는 TC (빌더에서 사용)
SHOT_SHARE = {"6.7-8": "6.7-7", "6.7-9": "6.7-7", "6.7-10": "6.7-7", "6.12-5": "6.12-4"}


# ------------------------------------------------------------------
# 세션 실행 (입력 에코 + 비밀번호 마스킹)
# ------------------------------------------------------------------
def run_session(inputs: list[str]) -> str:
    it = iter(inputs)
    buf = io.StringIO()

    def fake_input(prompt: str = "") -> str:
        try:
            value = next(it)
        except StopIteration:
            raise SystemExit("입력 소진")
        print(f"{prompt}{value}")
        return value

    def fake_password(prompt: str = "비밀번호 > ") -> str:
        try:
            value = next(it)
        except StopIteration:
            raise SystemExit("입력 소진")
        print(f"{prompt}{'*' * len(value)}")
        return value

    orig_input, orig_pw = builtins.input, M._input_password
    builtins.input, M._input_password = fake_input, fake_password
    try:
        with redirect_stdout(buf):
            try:
                M.main()
            except SystemExit:
                pass
    finally:
        builtins.input, M._input_password = orig_input, orig_pw
    return buf.getvalue()


def cut_lines(log: str, start: tuple[str, int], end: str, pad_before: int, after: int) -> list[str]:
    lines = log.splitlines()
    sub, occ = start
    idxs = [i for i, l in enumerate(lines) if sub in l]
    if len(idxs) < occ:
        raise RuntimeError(f"start 마커 미발견: {sub!r} (occ {occ}, 발견 {len(idxs)})")
    s = idxs[occ - 1]
    e = next((i for i in range(s, len(lines)) if end in lines[i]), None)
    if e is None:
        raise RuntimeError(f"end 마커 미발견: {end!r} (start {sub!r} 이후)")
    s = max(0, s - pad_before)
    e = min(len(lines) - 1, e + after)
    return [l.rstrip() for l in lines[s:e + 1]]


# ------------------------------------------------------------------
# PNG 렌더 (1차 보고서 다크 터미널 스타일)
# ------------------------------------------------------------------
BG = (12, 12, 12)
BAR = (45, 45, 45)
FG = (230, 230, 230)
RED = (255, 85, 85)
GREEN = (78, 201, 78)
GRAY = (150, 150, 150)
OKGREEN = (107, 203, 119)
TITLE = "건국 수강신청 시뮬레이터 - 실행 결과"


def line_color(line: str):
    t = line.strip()
    if t.startswith("!!! 오류") or t.startswith("!!! 경고"):
        return RED
    if t.startswith("✓"):
        return OKGREEN
    if t and set(t) <= {"="}:
        return GREEN
    if t and set(t) <= {"-"}:
        return GRAY
    return FG


def render(lines: list[str], out_path: Path) -> None:
    font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 16)
    pad, lh, bar_h = 14, 22, 28
    probe = Image.new("RGB", (8, 8))
    dr = ImageDraw.Draw(probe)
    width = max([int(dr.textlength(l, font=font)) for l in lines] + [int(dr.textlength(TITLE, font=font)) + 70, 540])
    img = Image.new("RGB", (width + pad * 2, bar_h + pad * 2 + lh * len(lines)), BG)
    d = ImageDraw.Draw(img)
    # 타이틀바
    d.rectangle([0, 0, img.width, bar_h], fill=BAR)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([10 + i * 18, bar_h // 2 - 5, 20 + i * 18, bar_h // 2 + 5], fill=c)
    d.text((66, bar_h // 2 - 9), TITLE, font=font, fill=(210, 210, 210))
    # 본문
    y = bar_h + pad
    for l in lines:
        d.text((pad, y), l, font=font, fill=line_color(l))
        y += lh
    img.save(out_path)


def main() -> None:
    SHOT_DIR.mkdir(exist_ok=True)
    backup = Path(tempfile.mkdtemp()) / "raw_backup"
    shutil.copytree(DATA_DIR, backup)
    try:
        # 깨끗한 기본 데이터에서 시작
        for f in DATA_DIR.glob("*.txt"):
            f.unlink()
        from datetime import date
        from major_basics.modules.storage import DataStore
        DataStore(DATA_DIR).ensure_defaults(date(2026, 4, 1))

        logs: dict[str, str] = {}
        for name, inputs in SESSIONS:
            logs[name] = run_session(inputs)
            print(f"[세션 {name}] {len(logs[name].splitlines())}줄 캡처")

        made = []
        for tid, session, start, end, before, after in CUTS:
            lines = cut_lines(logs[session], start, end, before, after)
            out = SHOT_DIR / f"{tid}.png"
            render(lines, out)
            made.append(tid)
        print(f"PNG {len(made)}개 생성: {', '.join(made)}")
    finally:
        # data/raw 원복
        for f in DATA_DIR.glob("*.txt"):
            f.unlink()
        for f in backup.glob("*.txt"):
            shutil.copy(f, DATA_DIR / f.name)
        print("data/raw 원복 완료")


if __name__ == "__main__":
    main()
