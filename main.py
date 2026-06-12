# 실행 진입점 — 프로젝트 루트에서 python main.py 로 실행

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from major_basics.main import main


if __name__ == "__main__":
    main()
