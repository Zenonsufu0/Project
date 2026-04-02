from pathlib import Path

from major_basics.cli.app import CLIApp
from major_basics.data.repository import FileRepository


def main() -> None:
    data_dir = Path(__file__).resolve().parents[2] / "data" / "raw"
    repository = FileRepository(data_dir)
    app = CLIApp(repository)
    app.run()


if __name__ == "__main__":
    main()
