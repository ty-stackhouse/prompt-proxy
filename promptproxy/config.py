"""Configuration loading and validation."""

import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator

class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    max_request_size: int = 1048576  # 1MB
    max_text_length: int = 100000

class BackendConfig(BaseModel):
    type: str = "stub"
    litellm: Dict[str, Any] = Field(default_factory=dict)

class LoggingConfig(BaseModel):
    level: str = "INFO"
    log_raw_prompt: bool = False

class FilterRule(BaseModel):
    name: str
    enabled: bool
    entities: Optional[List[str]] = None
    rules: Optional[List[Dict[str, Any]]] = None

class Config(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    backend: BackendConfig = Field(default_factory=BackendConfig)
    fail_open: bool = True
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    filters: List[FilterRule] = Field(default_factory=list)

    @validator('backend')
    def validate_backend(cls, v):
        if v.type not in ["stub", "litellm"]:
            raise ValueError(f"Unsupported backend type: {v.type}")
        return v

def load_config(config_path: str = "config.yaml") -> Config:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, 'r') as f:
        data = yaml.safe_load(f)

    return Config(**data)