from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    port: int = Field(default=8080, alias="PORT", validation_alias="PORT")
    app_version: str = Field(default="dev", alias="APP_VERSION", validation_alias="APP_VERSION")
    cpu_spike_duration: int = Field(default=60, alias="CPU_SPIKE_DURATION", validation_alias="CPU_SPIKE_DURATION")
