import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    app_name: str = "AstronClaw Backend"
    api_prefix: str = "/api/v1/astron-claw"
    access_token_ttl_seconds: int = 7200
    database_url: str = "mysql+pymysql://astronclaw:astronclaw@127.0.0.1:3306/astronclaw?charset=utf8mb4"
    claw_proxy_base_url: str = "http://localhost:18080"
    claw_proxy_auth_token: str = "dev-claw-proxy-token"
    bridge_base_url: str = "http://localhost:18081"
    mock_external_services: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings(
        access_token_ttl_seconds=int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "7200")),
        database_url=os.getenv(
            "DATABASE_URL",
            "mysql+pymysql://astronclaw:astronclaw@127.0.0.1:3306/astronclaw?charset=utf8mb4",
        ),
        claw_proxy_base_url=os.getenv("CLAW_PROXY_BASE_URL", "http://localhost:18080"),
        claw_proxy_auth_token=os.getenv("CLAW_PROXY_AUTH_TOKEN", "dev-claw-proxy-token"),
        bridge_base_url=os.getenv("BRIDGE_BASE_URL", "http://localhost:18081"),
        mock_external_services=os.getenv("MOCK_EXTERNAL_SERVICES", "true").lower() == "true",
    )
