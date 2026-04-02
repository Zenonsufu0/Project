from dataclasses import dataclass


@dataclass
class EnrollmentRecord:
    student_id: str
    course_code: str
    status: str
    is_retake: bool
