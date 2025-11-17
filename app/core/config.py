from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str
    REDIS_URL: str | None = None
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 3600
    UPLOAD_PATH: str = "my-app/uploads"
    PROCESSED_PATH: str = "my-app/processed"
    PROCESSED_DIR: str = "processed"
    MAX_FILE_SIZE: int = 100 * 1024 * 1024
    TESTING: bool = False
    CELERY_EAGER: bool = False
    ASSETS_DIR: str = "assets"
    STORAGE_BACKEND: str = "s3"  # options: s3 | nfs | local
    AWS_REGION: str | None = None
    AWS_S3_BUCKET: str | None = None
    S3_UPLOAD_PREFIX: str = "uploads"
    S3_PROCESSED_PREFIX: str = "processed"
    S3_URL_EXPIRE_SECONDS: int = 3600
    SQS_QUEUE_NAME: str = "cola-nube"
    SQS_VISIBILITY_TIMEOUT: int = 1500
    SQS_WAIT_TIME_SECONDS: int = 20
settings = Settings()