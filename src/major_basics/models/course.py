from dataclasses import dataclass


@dataclass(frozen=True)
class Course:
    code: str
    name: str
    credits: int
    professor: str
    day: str
    start_time: int  # HHMM
    end_time: int    # HHMM
    category: str
    status: str = "active"

    def schedule_text(self) -> str:
        return f"{self.day} {self.start_time:04d}-{self.end_time:04d}"
