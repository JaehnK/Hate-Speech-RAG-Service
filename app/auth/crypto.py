from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import DomainError


class KeyEncryptionService:
    def __init__(self, key: str | bytes) -> None:
        self.fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, value: str) -> bytes:
        return self.fernet.encrypt(value.encode())

    def decrypt(self, value: bytes) -> str:
        try:
            return self.fernet.decrypt(value).decode()
        except InvalidToken as exc:
            raise DomainError("API_KEY_DECRYPTION_FAILED", "저장된 API 키를 복호화할 수 없습니다.", status_code=500) from exc
