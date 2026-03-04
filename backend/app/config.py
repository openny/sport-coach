from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENV: str = "local"

    DATABASE_URL: str
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    MINIO_ENDPOINT: str
    MINIO_PUBLIC_ENDPOINT: str
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_BUCKET: str

    # ✅ 추가
    EMBED_BASE_URL: str
    EMBED_API_KEY: str
    EMBED_MODEL: str = "intfloat/multilingual-e5-large"

    # LLM
    LLM_PROVIDER: str = "ollama"  # ollama | openai_compatible
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "qwen2.5:14b-instruct-q4_K_M"
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""

settings = Settings()