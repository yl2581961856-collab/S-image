from app.schemas.jobs import JobStatus


ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.queued: {JobStatus.running, JobStatus.cancelled},
    JobStatus.running: {
        JobStatus.postprocessing,
        JobStatus.failed,
        JobStatus.timeout,
        JobStatus.cancelled,
    },
    JobStatus.postprocessing: {
        JobStatus.succeeded,
        JobStatus.failed,
        JobStatus.timeout,
        JobStatus.cancelled,
    },
    JobStatus.succeeded: set(),
    JobStatus.failed: set(),
    JobStatus.timeout: set(),
    JobStatus.cancelled: set(),
}


def can_transition(current: JobStatus, target: JobStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def is_terminal(status: JobStatus) -> bool:
    return len(ALLOWED_TRANSITIONS[status]) == 0
