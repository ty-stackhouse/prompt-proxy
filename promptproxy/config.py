"""Configuration loading and validation."""

import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator, root_validator

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
    # Optional path to write structured logs (JSON). Logs will still go to stderr.
    file_path: Optional[str] = None


class UIConfig(BaseModel):
    """Settings controlling CLI/demo behavior.
    
    Attributes:
        demo_mode: When true, CLI minimizes non-chat output (legacy, prefer stdout_display_requests)
        stdout_display_requests: When true, show input/output request text on stdout
        stdout_max_display_length: Maximum characters to display for request text on stdout
    """
    demo_mode: bool = False
    stdout_display_requests: bool = False  # Security: disabled by default
    stdout_max_display_length: int = 500   # Truncate long requests

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
    ui: UIConfig = Field(default_factory=UIConfig)

    # ---- new staged filters ----
    request_filters: List[FilterRule] = Field(default_factory=list)
    response_filters: List[FilterRule] = Field(default_factory=list)
    # legacy field for backwards compatibility; migrated to request_filters
    filters: List[FilterRule] = Field(default_factory=list)

    @validator('backend')
    def validate_backend(cls, v):
        if v.type not in ["stub", "litellm"]:
            raise ValueError(f"Unsupported backend type: {v.type}")
        return v

    @classmethod
    def __get_validators__(cls):
        # preserve default pydantic behaviour
        yield from super().__get_validators__()

    @root_validator(pre=True)
    def migrate_old_filters(cls, values):
        # Support old 'filters' key by copying its value into request_filters
        if 'filters' in values and 'request_filters' not in values:
            values['request_filters'] = values.pop('filters')
        return values

def load_config(config_path: str = "config.yaml") -> Config:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, 'r') as f:
        data = yaml.safe_load(f)

    return Config(**data)