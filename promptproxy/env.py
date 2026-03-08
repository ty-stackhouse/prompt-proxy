"""Environment validation utilities for PromptProxy.

This module provides checks to ensure the project is running in the
expected uv-managed environment and helps users recover from common
environment issues.
"""

import os
import sys
from pathlib import Path


def get_project_venv_path() -> Path:
    """Get the expected project-local .venv path."""
    # Navigate from promptproxy/env.py up to project root (promptproxy/)
    # and then to .venv
    return Path(__file__).parent.parent / ".venv"


def get_active_venv() -> str | None:
    """Get the path of the currently active virtualenv, if any."""
    # Check VIRTUAL_ENV environment variable
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        return venv
    
    # Check for conda environments
    conda_env = os.environ.get("CONDA_DEFAULT_ENV")
    if conda_env:
        return conda_env
    
    return None


def is_in_project_venv() -> bool:
    """Check if we're running in the project-local .venv.
    
    This checks if either:
    1. The Python executable is within the project .venv, OR
    2. VIRTUAL_ENV is set to the project .venv (uv run behavior)
    """
    project_venv = get_project_venv_path()
    
    # Check if VIRTUAL_ENV points to project .venv (uv run sets this)
    active_venv = os.environ.get("VIRTUAL_ENV")
    if active_venv:
        try:
            if Path(active_venv).resolve() == project_venv.resolve():
                return True
        except OSError:
            pass
    
    # Check if the Python executable is within the project .venv
    python_path = Path(sys.executable)
    
    # Normalize paths for comparison
    try:
        return python_path.resolve().is_relative_to(project_venv.resolve())
    except (ValueError, OSError):
        # Fallback for platforms that don't support is_relative_to
        return str(python_path.resolve()).startswith(str(project_venv.resolve()))


def check_environment() -> bool:
    """Check if the environment is properly configured.
    
    Returns:
        True if environment is correct, False otherwise.
        
    Prints guidance if there's a mismatch.
    """
    project_venv = get_project_venv_path()
    active_venv = get_active_venv()
    in_project = is_in_project_venv()
    
    # Check if .venv exists
    if not project_venv.exists():
        print("⚠️  Project .venv not found.")
        print()
        print("To set up the development environment:")
        print("  1. Run: uv sync --group dev --group test")
        print("  2. Or use: make bootstrap")
        print()
        print("This will create the project-local .venv and install all dependencies.")
        return False
    
    # Check if we're in the wrong virtualenv (active venv that isn't project venv)
    if active_venv and not in_project:
        print("⚠️  External virtualenv is active.")
        print()
        print(f"  Active: {active_venv}")
        print(f"  Expected: {project_venv}")
        print()
        print("Using an external virtualenv may cause unexpected behavior.")
        print()
        print("To fix this:")
        print("  1. Deactivate the current environment: deactivate")
        print("  2. Use uv run to execute commands: uv run promptproxy")
        print("  3. Or use make targets: make run, make cli, make test")
        print()
        print("The project uses uv-managed .venv - no manual activation needed!")
        return False
    
    # Check if we're not in any virtualenv but .venv exists
    if not active_venv and not in_project:
        # This might be a system Python - check if .venv exists
        if project_venv.exists():
            print("⚠️  Not running in project .venv.")
            print()
            print("To run commands in the correct environment:")
            print("  - Use: uv run <command>")
            print("  - Or: make <target>")
            print()
            print("Example: uv run promptproxy")
            print("         make run")
            return False
    
    # Environment is correct (either using project venv via uv run, or no external venv active)
    return True


def ensure_environment() -> None:
    """Ensure we're in the correct environment before running.
    
    This is called at startup to validate the environment.
    Raises SystemExit if environment is misconfigured.
    """
    if not check_environment():
        print()
        print("Environment check failed. Please resolve the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    check_environment()