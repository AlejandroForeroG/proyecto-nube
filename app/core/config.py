from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str
    REDIS_URL: str
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
settings = Settings()