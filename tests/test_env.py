"""Tests for environment validation utilities."""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestGetProjectVenvPath:
    """Tests for get_project_venv_path()."""

    def test_returns_path_to_venv_in_project_root(self):
        """Should return .venv path relative to project root."""
        from promptproxy.env import get_project_venv_path
        
        result = get_project_venv_path()
        
        # Should be a Path object
        assert isinstance(result, Path)
        # Should end with .venv
        assert result.name == ".venv"
        # Should be a parent of the promptproxy package directory
        assert result.parent.exists()
        assert (result.parent / "promptproxy").exists()


class TestGetActiveVenv:
    """Tests for get_active_venv()."""

    def test_returns_none_when_no_venv_active(self):
        """Should return None when VIRTUAL_ENV is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove VIRTUAL_ENV if it exists
            env = os.environ.copy()
            env.pop("VIRTUAL_ENV", None)
            env.pop("CONDA_DEFAULT_ENV", None)
            with patch.dict(os.environ, env, clear=True):
                from promptproxy.env import get_active_venv
                result = get_active_venv()
                assert result is None

    def test_returns_virtual_env_path_when_set(self):
        """Should return VIRTUAL_ENV value when set."""
        with patch.dict(os.environ, {"VIRTUAL_ENV": "/some/path/to/venv"}):
            from promptproxy.env import get_active_venv
            result = get_active_venv()
            assert result == "/some/path/to/venv"

    def test_returns_conda_env_when_set(self):
        """Should return CONDA_DEFAULT_ENV when VIRTUAL_ENV is not set."""
        env = {
            "CONDA_DEFAULT_ENV": "my_conda_env",
        }
        with patch.dict(os.environ, env, clear=True):
            from promptproxy.env import get_active_venv
            result = get_active_venv()
            assert result == "my_conda_env"

    def test_prefers_virtual_env_over_conda(self):
        """VIRTUAL_ENV should take precedence over CONDA_DEFAULT_ENV."""
        env = {
            "VIRTUAL_ENV": "/venv/path",
            "CONDA_DEFAULT_ENV": "conda_env",
        }
        with patch.dict(os.environ, env, clear=True):
            from promptproxy.env import get_active_venv
            result = get_active_venv()
            assert result == "/venv/path"


class TestIsInProjectVenv:
    """Tests for is_in_project_venv()."""

    def test_returns_true_when_python_in_project_venv(self):
        """Should return True when sys.executable is in project .venv."""
        project_venv = Path("/project/.venv")
        
        with patch("promptproxy.env.get_project_venv_path", return_value=project_venv):
            with patch.object(sys, "executable", "/project/.venv/bin/python"):
                from promptproxy.env import is_in_project_venv
                result = is_in_project_venv()
                assert result is True

    def test_returns_false_when_python_outside_project_venv(self):
        """Should return False when sys.executable is outside project .venv."""
        project_venv = Path("/project/.venv")
        
        with patch("promptproxy.env.get_project_venv_path", return_value=project_venv):
            with patch.object(sys, "executable", "/usr/bin/python3"):
                from promptproxy.env import is_in_project_venv
                result = is_in_project_venv()
                assert result is False


class TestCheckEnvironment:
    """Tests for check_environment()."""

    def test_returns_true_when_venv_exists_and_correct(self):
        """Should return True when .venv exists and we're using it."""
        project_venv = Path("/project/.venv")
        
        with patch("promptproxy.env.get_project_venv_path", return_value=project_venv):
            with patch("promptproxy.env.get_active_venv", return_value=None):
                with patch("promptproxy.env.is_in_project_venv", return_value=True):
                    with patch.object(Path, "exists", return_value=True):
                        from promptproxy.env import check_environment
                        result = check_environment()
                        assert result is True

    def test_warns_when_external_venv_active(self):
        """Should return False and warn when external venv is active."""
        project_venv = Path("/project/.venv")
        
        with patch("promptproxy.env.get_project_venv_path", return_value=project_venv):
            with patch("promptproxy.env.get_active_venv", return_value="/external/venv"):
                with patch("promptproxy.env.is_in_project_venv", return_value=False):
                    with patch.object(Path, "exists", return_value=True):
                        with patch("builtins.print") as mock_print:
                            from promptproxy.env import check_environment
                            result = check_environment()
                            assert result is False
                            # Should print a warning about external venv
                            assert any("External virtualenv" in str(call) 
                                      for call in mock_print.call_args_list)

    def test_warns_when_venv_not_found(self):
        """Should return False and warn when .venv doesn't exist."""
        with patch("promptproxy.env.get_project_venv_path") as mock_path:
            mock_path.return_value = Path("/project/.venv")
            with patch.object(Path, "exists", return_value=False):
                with patch("builtins.print") as mock_print:
                    from promptproxy.env import check_environment
                    result = check_environment()
                    assert result is False
                    # Should print a warning about missing .venv
                    assert any(".venv not found" in str(call) 
                              for call in mock_print.call_args_list)


class TestEnsureEnvironment:
    """Tests for ensure_environment()."""

    def test_exits_when_environment_invalid(self):
        """Should exit with error code when environment check fails."""
        with patch("promptproxy.env.check_environment", return_value=False):
            from promptproxy.env import ensure_environment
            with pytest.raises(SystemExit) as exc_info:
                ensure_environment()
            assert exc_info.value.code == 1

    def test_does_not_exit_when_environment_valid(self):
        """Should not exit when environment check passes."""
        with patch("promptproxy.env.check_environment", return_value=True):
            from promptproxy.env import ensure_environment
            # Should not raise
            ensure_environment()