class StaleStepExecution(Exception):
    """Raised when a recovered step rejects work from an older attempt."""


class WorkerShutdownRequested(Exception):
    """Raised after active RAG items drain during worker shutdown."""
