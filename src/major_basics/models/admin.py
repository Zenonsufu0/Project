from dataclasses import dataclass


@dataclass
class Admin:
    admin_id: str
    password: str
    name: str
