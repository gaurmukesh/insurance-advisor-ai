from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me"

    DATABASE_URL: str
    SYNC_DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379"

    OPENAI_API_KEY: str

    SENDGRID_API_KEY: str
    SENDGRID_FROM_EMAIL: str = "naukritoolmg@gmail.com"

    META_WHATSAPP_TOKEN: str = ""
    META_PHONE_NUMBER_ID: str = ""
    META_VERIFY_TOKEN: str = ""

    AWS_REGION: str = ""
    POLICIES_S3_BUCKET: str = ""
    POLICIES_S3_PREFIX: str = ""
    POLICIES_SQS_QUEUE_URL: str = ""
    CLOUDWATCH_LOG_GROUP: str = ""

    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    SENTRY_DSN: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
