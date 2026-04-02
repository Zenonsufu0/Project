from major_basics.models.course import Course


def is_time_overlap(first: Course, second: Course) -> bool:
    if first.day != second.day:
        return False
    return first.start_time < second.end_time and second.start_time < first.end_time
