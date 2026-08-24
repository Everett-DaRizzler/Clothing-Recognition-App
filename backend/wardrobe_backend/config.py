from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    model_id: str = "HelloWorld0204/Classification-StyleWell-model"
    model_revision: str = "main"
    data_dir: Path = Path("./data")
    host: str = "0.0.0.0"
    port: int = 8000
    max_upload_bytes: int = 15 * 1024 * 1024
    inference_timeout_seconds: int = 180
    device: str = "auto"
    @property
    def model_is_allowed(self): return self.model_id == "HelloWorld0204/Classification-StyleWell-model"
    @property
    def images_dir(self): return self.data_dir / "images"
    @property
    def db_path(self): return self.data_dir / "wardrobe.sqlite3"
