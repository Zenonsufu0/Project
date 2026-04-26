"""Root entry point.

Allows running the project with: python main.py
"""

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from major_basics.main import main


if __name__ == "__main__":
    main()
