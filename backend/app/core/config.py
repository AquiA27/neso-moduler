from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_list(val: Union[str, List[str], None]) -> List[str]:
    """
    CORS listesi hem JSON list (["...","..."]) hem de virgüllü string ("a,b") gelse de
    düzgün bir Python listesine çevir.
    """
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]

    s = str(val).strip()
    if not s:
        return []

    # Köşeli/normal parantezle gelmişse temizle
    if (s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")")):
        s = s.strip("[]()")

    parts = [p.strip().strip('"').strip("'") for p in s.split(",")]
    return [p for p in parts if p]


class Settings(BaseSettings):
    # ---------- Observability & Rate Limit ----------
    # Rate limit: 0 = disabled (dev), prod'da env'den ayarla
    # Önerilen: RATE_LIMIT_PER_MINUTE=60 (API), 120 (public), 30 (assistant)
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=0,  # 0 = disabled (for dev)
        description="Production'da 60 veya daha yüksek bir değer kullanın"
    )
    REQUEST_LOG_ENABLED: bool = True
    ADD_REQUEST_ID_HEADER: bool = True

    # ---------- Pydantic Settings v2 ----------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env'de fazladan anahtar olsa bile hata verme
    )

    # ---------- Uygulama ----------
    APP_NAME: str = "Neso Asistan API"
    VERSION: str = "0.1.0"
    ENV: str = "dev"  # dev | prod

    # ---------- Statik dosyalar ----------
    MEDIA_URL: str = "/media"
    MEDIA_ROOT: str = str(Path(__file__).resolve().parents[2] / "media")
    MAX_UPLOAD_SIZE_MB: int = 5

    # ---------- Auth/JWT ----------
    SECRET_KEY: str = Field(default="change-me", description="Production'da mutlaka güçlü bir değer kullanın")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ALGORITHM: str = "HS256"

    # ---------- Veritabanı ----------
    DATABASE_URL: str = "postgresql+asyncpg://neso:neso123@localhost:5432/neso"
    # Tek DB kullanıyorsan MENU_DATABASE_URL boş kalabilir.
    MENU_DATABASE_URL: Optional[str] = None
    
    # ---------- Database Connection Pool ----------
    # Cross-region latency için optimize edilmiş ayarlar
    DB_POOL_MIN_SIZE: int = 5  # Minimum connection sayısı (persistent connections)
    DB_POOL_MAX_SIZE: int = 20  # Maximum connection sayısı (traffic spikes için)
    DB_COMMAND_TIMEOUT: int = 10  # Query timeout (saniye) - cross-region için artırıldı
    DB_POOL_MAX_INACTIVE_CONNECTION_LIFETIME: float = 300.0  # Inactive connection lifetime (saniye)

    # ---------- CORS ----------
    CORS_ORIGINS: Union[str, List[str]] = ["http://localhost:5173", "http://localhost:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = Field(
        default=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        description="Production'da sadece gerekli method'lar"
    )
    CORS_ALLOW_HEADERS: List[str] = Field(
        default=["Content-Type", "Authorization", "X-Sube-Id", "X-Tenant-Id", "X-Request-ID"],
        description="Production'da sadece gerekli header'lar"
    )

    # ---------- Varsayılan admin (ilk kurulum) ----------
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"

    # ---------- Opsiyonel: OpenAI ----------
    OPENAI_MODEL: Optional[str] = "gpt-4o-mini"
    OPENAI_API_KEY: Optional[str] = None
    # Sesli asistan altyapısı için bayraklar
    ASSISTANT_ENABLE_LLM: bool = True
    ASSISTANT_ENABLE_TTS: bool = True   # Client-side tarayıcı SpeechSynthesis; sunucu TTS için ileride
    ASSISTANT_ENABLE_STT: bool = True   # Client-side tarayıcı SpeechRecognition; sunucu STT için ileride
     
    # ---------- TTS (Text-to-Speech) API Ayarları ----------
    # TTS Provider: 'system' (pyttsx3), 'google', 'azure', 'aws', 'openai'
    TTS_PROVIDER: str = "system"
    # Google Cloud Text-to-Speech
    GOOGLE_TTS_API_KEY: Optional[str] = None
    GOOGLE_TTS_PROJECT_ID: Optional[str] = None
    # Azure Speech Services
    AZURE_SPEECH_KEY: Optional[str] = None
    AZURE_SPEECH_REGION: Optional[str] = None
    # AWS Polly
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = None
    # OpenAI TTS (tts-1 veya tts-1-hd)
    OPENAI_TTS_MODEL: Optional[str] = "tts-1"

    # Data layer paths
    DATA_VIEWS_DIR: Path = Path(__file__).resolve().parents[2] / "app" / "db" / "views"
    BACKUP_DIR: str = str(Path(__file__).resolve().parents[2] / "backups")

    CACHE_TTL_SHORT: int = 60
    CACHE_TTL_MEDIUM: int = 300
    CACHE_TTL_LONG: int = 1800

    # ---------- Redis Cache ----------
    REDIS_ENABLED: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_POOL_SIZE: int = 20
    REDIS_SOCKET_TIMEOUT: int = 5

    # ---------- Backup / Scheduler ----------
    BACKUP_ENABLED: bool = False
    BACKUP_SCHEDULE_CRON: str = "0 2 * * *"  # Her gün 02:00

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _cors_list_parser(cls, v):
        return _parse_list(v)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()