# app/config.py

from pydantic_settings import BaseSettings
from pydantic import computed_field
from aiocache import caches
import os

from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    keycloak_server_url: str = os.getenv("KEYCLOAK_SERVER_URL")
    keycloak_public_key: str = os.getenv("KEYCLOAK_PUBLIC_KEY")
    keycloak_audience: str = os.getenv("KEYCLOAK_AUDIENCE")
    keycloak_realm: str = os.getenv("REALM_NAME")
    keycloak_client_id: str = os.getenv("CLIENT_ID")
    keycloak_admin_username: str = os.getenv("ADMIN_USERNAME")
    keycloak_admin_password: str = os.getenv("ADMIN_PASSWORD")
    keycloak_client_secret: str = os.getenv("CLIENT_SECRET")
    keycloak_redirect_uri: str = os.getenv(
        "REDIRECT_URI", "http://localhost:8000")
    # auth_service_url: str = os.getenv(
    # "AUTH_SERVICE_URL", "https://core.schoolmate.co.tz")
    core_service_url: str = os.getenv(
        "CORE_SERVICE_URL", "http://localhost:8084")
    # core_token_secret: str = os.getenv(
    #     "CORE_TOKEN_SECRET",)
    pg_user: str
    pg_password: str
    pg_db: str
    pg_host: str
    pg_port: str
    database_url: str
    session_key: str

    @computed_field(return_type=str)
    @property
    def keycloak_openid_config_url(self):
        return f"{self.keycloak_server_url}realms/{self.keycloak_realm}/.well-known/openid-configuration"

    @computed_field(return_type=str)
    @property
    def keycloak_token_url(self):
        return f"{self.keycloak_server_url}realms/{self.keycloak_realm}/protocol/openid-connect/token"

    @computed_field(return_type=str)
    @property
    def keycloak_userinfo_url(self):
        return f"{self.keycloak_server_url}realms/{self.keycloak_realm}/protocol/openid-connect/userinfo"

    # Update model configurations for Pydantic v2
    model_config = {
        "env_file": ".env",
        "extra": "ignore",  # Optional: To ignore extra fields instead of raising errors
    }


# Configure Redis Cache
caches.set_config({
    "default": {
        "cache": "aiocache.RedisCache",
        "endpoint": "localhost",
        "port": 6379,
        "timeout": 1,
        "namespace": "mala_cache",
    }
})

settings = Settings()


# TODO CACHING LRU
