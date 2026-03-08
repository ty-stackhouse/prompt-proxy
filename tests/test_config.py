"""Tests for configuration loading."""

import pytest
from promptproxy.config import Config, load_config
from pathlib import Path

def test_default_config():
    config = Config()
    assert config.server.host == "127.0.0.1"
    assert config.fail_open is True

def test_load_config(tmp_path):
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text("""
server:
  host: "0.0.0.0"
  port: 9000
fail_open: false
""")
    config = load_config(str(config_file))
    assert config.server.host == "0.0.0.0"
    assert config.server.port == 9000
    assert config.fail_open is False