from dataclasses import dataclass


@dataclass
class Student:
    student_id: str
    password: str
    name: str
    college: str
    major: str
    status: str = "active"
