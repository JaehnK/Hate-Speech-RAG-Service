import logging


SENSITIVE_KEYS = ("api_key", "token", "secret", "authorization")


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")


def mask_sensitive(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: "***" if any(part in key.lower() for part in SENSITIVE_KEYS) else mask_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [mask_sensitive(item) for item in value]
    return value
