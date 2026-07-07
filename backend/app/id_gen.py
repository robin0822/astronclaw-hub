import secrets


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def new_bot_id() -> str:
    return f"agt_{secrets.token_hex(6)}"
