import logging
import os
import pytest
from promptproxy.logging_config import configure_logging, get_logger, TerminalFormatter


def test_configure_logging_stderr(capsys, tmp_path):
    """Test that logging writes to stderr with plain text format."""
    configure_logging(level="DEBUG", file_path=None)
    logger = get_logger("test")
    logger.warning("test warning message")
    out, err = capsys.readouterr()
    assert "test warning message" in err
    assert "WARNING" in err
    # ensure nothing on stdout
    assert out == ""
    # clear handlers so later tests can reconfigure independently
    logging.getLogger().handlers = []


def test_configure_logging_file(tmp_path):
    log_file = tmp_path / "out.log"
    configure_logging(level="INFO", file_path=str(log_file))
    logger = get_logger("test2")
    logger.setLevel(logging.INFO)  # Ensure child logger accepts INFO
    logger.info("hello file")
    # flush handlers
    for h in logger.handlers:
        h.flush()
    contents = log_file.read_text()
    assert "hello file" in contents
    # cleanup handlers and level for other tests
    logger.handlers = []
    logger.setLevel(logging.NOTSET)
    logging.getLogger().handlers = []


def test_info_not_on_stderr(capsys):
    """INFO level should not appear on stderr in normal operation."""
    configure_logging(level="INFO", file_path=None)
    logger = get_logger("test_info")
    logger.info("This is info")
    out, err = capsys.readouterr()
    # INFO should not appear on stderr
    assert "This is info" not in err
    logging.getLogger().handlers = []


def test_warning_on_stderr(capsys):
    """WARNING level should appear on stderr."""
    configure_logging(level="INFO", file_path=None)
    logger = get_logger("test_warning")
    logger.warning("This is a warning")
    out, err = capsys.readouterr()
    assert "This is a warning" in err
    assert "WARNING" in err
    logging.getLogger().handlers = []


def test_error_on_stderr(capsys):
    """ERROR level should appear on stderr."""
    configure_logging(level="INFO", file_path=None)
    logger = get_logger("test_error")
    logger.error("This is an error")
    out, err = capsys.readouterr()
    assert "This is an error" in err
    assert "ERROR" in err
    logging.getLogger().handlers = []


def test_stderr_not_json(capsys):
    """Stderr output should be plain text, not JSON."""
    configure_logging(level="INFO", file_path=None)
    logger = get_logger("test_json")
    logger.warning("Test message")
    out, err = capsys.readouterr()
    
    # Try to parse as JSON - should fail
    try:
        import json
        json.loads(err)
        pytest.fail("Stderr should not contain JSON")
    except json.JSONDecodeError:
        pass  # Expected - not JSON
    logging.getLogger().handlers = []


def test_terminal_formatter_format():
    """Test TerminalFormatter produces correct format."""
    formatter = TerminalFormatter()
    
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="test.py",
        lineno=1,
        msg="Test warning",
        args=(),
        exc_info=None
    )
    
    output = formatter.format(record)
    
    # Should be plain text with timestamp, level, message
    assert "WARNING" in output
    assert "Test warning" in output
    # Should have timestamp format (YYYY-MM-DD HH:MM:SS)
    assert "20" in output  # Year
    assert "-" in output  # Date separator
    assert ":" in output  # Time separator
    # Should NOT be JSON
    assert "{" not in output
    assert "}" not in output
