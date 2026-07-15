class StaleStepExecution(Exception):
    """Raised when a recovered step rejects work from an older attempt."""
