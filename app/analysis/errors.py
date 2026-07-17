from app.core.errors import DomainError


class ApiKeyInvalidError(DomainError):
    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__("API_KEY_INVALID", f"{provider} API 키가 더 이상 유효하지 않습니다.", status_code=422)


class LlmRequestError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)
