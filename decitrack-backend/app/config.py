from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_uri: str
    database_name: str = "decitrack"
    frontend_url: str = "http://localhost:3000"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()
