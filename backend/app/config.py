"""
Loads settings from .env. Never hardcode secrets — everything sensitive
comes from environment variables so .env (gitignored) is the only place
real values live.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    item_bank_encryption_key: str
    ntp_servers: str = "pool.ntp.org,time.google.com"

    class Config:
        env_file = ".env"

    @property
    def ntp_server_list(self) -> list[str]:
        return [s.strip() for s in self.ntp_servers.split(",")]


settings = Settings()