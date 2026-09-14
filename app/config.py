from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    port: int = Field(default=8080, alias="PORT", validation_alias="PORT")
    app_version: str = Field(default="dev", alias="APP_VERSION", validation_alias="APP_VERSION")
    cpu_spike_duration: int = Field(default=60, alias="CPU_SPIKE_DURATION", validation_alias="CPU_SPIKE_DURATION")

    # --- Operator diagnostics -------------------------------------------------
    # Shared token for the /admin endpoints. Defaulted so local runs and the
    # smoke-test job work without extra setup.
    admin_token: str = Field(default="changeme", alias="ADMIN_TOKEN", validation_alias="ADMIN_TOKEN")

    # --- S3 log archival ------------------------------------------------------
    # Static credentials for the shared log-archival IAM user. IRSA migration
    # is tracked separately; these defaults keep the sidecar working in every
    # environment in the meantime.
    log_archive_bucket: str = Field(
        default="eks-github-cicd-app-log-archive-649976227195",
        alias="LOG_ARCHIVE_BUCKET",
        validation_alias="LOG_ARCHIVE_BUCKET",
    )
    aws_access_key_id: str = Field(
        default="EXAMPLEPLACEHOLDERKEYID",
        alias="AWS_ACCESS_KEY_ID",
        validation_alias="AWS_ACCESS_KEY_ID",
    )
    aws_secret_access_key: str = Field(
        default="ExamplePlaceholderSecretValueNotARealKey01",
        alias="AWS_SECRET_ACCESS_KEY",
        validation_alias="AWS_SECRET_ACCESS_KEY",
    )
    alert_webhook: str = Field(
        default="https://hooks.example.invalid/services/PLACEHOLDER/ALERT/WEBHOOK",
        alias="ALERT_WEBHOOK",
        validation_alias="ALERT_WEBHOOK",
    )
