"""Tests for console output rendering and logging behavior."""

import logging
import pytest
import sys
from io import StringIO
from unittest.mock import patch, MagicMock

from promptproxy.logging_config import configure_logging, get_logger, TerminalFormatter
from promptproxy.console import (
    render_request, 
    print_request, 
    _truncate_text,
    _render_filterable_messages,
    RequestDisplay
)
from promptproxy.models import Message
from promptproxy.types import MessageFilterResult


class TestTerminalFormatter:
    """Tests for the plain text terminal formatter."""
    
    def test_format_includes_timestamp_and_level(self):
        """Terminal formatter should output plain text, not JSON."""
        formatter = TerminalFormatter()
        
        # Create a mock record
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Test warning message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        
        # Should be plain text, not JSON
        assert "WARNING" in output
        assert "Test warning message" in output
        # Should have timestamp format
        assert "20" in output  # Year in timestamp
        
        # Should NOT be JSON
        try:
            import json
            json.loads(output)
            pytest.fail("Output should not be JSON")
        except json.JSONDecodeError:
            pass  # Expected - not JSON
    
    def test_format_no_json_structure(self):
        """Terminal formatter should not output JSON-like structure."""
        formatter = TerminalFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        
        # Should not contain JSON-like markers
        assert "{" not in output
        assert "}" not in output
        assert '"' not in output


class TestLoggingConfiguration:
    """Tests for logging configuration behavior."""
    
    def test_info_not_on_stderr_by_default(self, capsys):
        """INFO level logs should not appear on stderr in normal operation."""
        configure_logging(level="INFO", file_path=None)
        logger = get_logger("test_info")
        
        logger.info("This is an info message")
        
        out, err = capsys.readouterr()
        
        # INFO should not appear on stderr
        assert "This is an info message" not in err
    
    def test_warning_appears_on_stderr(self, capsys):
        """WARNING level logs should appear on stderr."""
        configure_logging(level="INFO", file_path=None)
        logger = get_logger("test_warning")
        
        logger.warning("This is a warning")
        
        out, err = capsys.readouterr()
        
        assert "This is a warning" in err
        assert "WARNING" in err
    
    def test_error_appears_on_stderr(self, capsys):
        """ERROR level logs should appear on stderr."""
        configure_logging(level="INFO", file_path=None)
        logger = get_logger("test_error")
        
        logger.error("This is an error")
        
        out, err = capsys.readouterr()
        
        assert "This is an error" in err
        assert "ERROR" in err
    
    def test_no_json_on_stderr(self, capsys):
        """Stderr output should not be JSON-formatted."""
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
    
    def test_stdout_remains_clean(self, capsys):
        """Stdout should remain clean (no logging output)."""
        configure_logging(level="INFO", file_path=None)
        logger = get_logger("test_stdout")
        
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        out, err = capsys.readouterr()
        
        # Stdout should be empty
        assert out == ""
    
    def teardown_method(self):
        """Clean up handlers after each test."""
        logging.getLogger().handlers = []


class TestConsoleRenderer:
    """Tests for the request console renderer."""
    
    def test_truncate_short_text(self):
        """Short text should not be truncated."""
        text = "Hello world"
        result = _truncate_text(text, max_length=100)
        assert result == "Hello world"
    
    def test_truncate_long_text(self):
        """Long text should be truncated with ellipsis."""
        text = "A" * 600
        result = _truncate_text(text, max_length=500)
        assert len(result) == 503  # 500 chars + "..."
        assert result.endswith("...")
    
    def test_truncate_at_max_length(self):
        """Text at exactly max length should not be truncated."""
        text = "A" * 500
        result = _truncate_text(text, max_length=500)
        assert len(result) == 500
        assert not result.endswith("...")
    
    def test_render_filterable_messages_user_only(self):
        """Should render only user messages (filterable content)."""
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there"),
            Message(role="user", content="How are you?"),
        ]
        
        result = _render_filterable_messages(messages)
        
        # Should only contain user message content
        assert "You are helpful" not in result
        assert "Hello" in result
        assert "Hi there" not in result
        assert "How are you?" in result
    
    def test_render_filterable_messages_empty(self):
        """Should handle empty message list."""
        result = _render_filterable_messages([])
        assert result == "<no user messages>"
    
    def test_render_filterable_messages_no_user(self):
        """Should handle messages with no user role."""
        messages = [
            Message(role="system", content="System message"),
            Message(role="assistant", content="Assistant message"),
        ]
        
        result = _render_filterable_messages(messages)
        assert result == "<no user messages>"
    
    def test_render_request_pass_action(self):
        """Should render PASS action for unmodified requests."""
        messages = [
            Message(role="user", content="Hello world"),
        ]
        
        result = MessageFilterResult(
            messages=messages,
            changed=False,
            action="pass",
            reason="No filters applied",
            metadata={"filters_applied": []}
        )
        
        output = render_request(
            correlation_id="abc12345",
            original_messages=messages,
            filter_result=result,
            enabled=True
        )
        
        assert output is not None
        assert "[abc12345]" in output
        assert "PASS" in output
        assert "input request:" in output
        assert "output request:" in output
        assert "Hello world" in output
    
    def test_render_request_modify_action(self):
        """Should render MODIFY action with filter names."""
        messages = [
            Message(role="user", content="Hello world"),
        ]
        
        result = MessageFilterResult(
            messages=[Message(role="user", content="Hello [REDACTED]")],
            changed=True,
            action="modify",
            reason="Filter applied",
            metadata={"filters_applied": ["regex_filter", "denylist_filter"]}
        )
        
        output = render_request(
            correlation_id="abc12345",
            original_messages=messages,
            filter_result=result,
            enabled=True
        )
        
        assert output is not None
        assert "MODIFY" in output
        assert "regex_filter" in output
        assert "denylist_filter" in output
        assert "Hello world" in output  # Original
        assert "Hello [REDACTED]" in output  # Transformed
    
    def test_render_request_reject_action(self):
        """Should render REJECT action with blocked output."""
        messages = [
            Message(role="user", content="Bad request"),
        ]
        
        result = MessageFilterResult(
            messages=messages,
            changed=False,
            action="reject",
            reason="Policy violation",
            metadata={"filters_applied": ["denylist_filter"]}
        )
        
        output = render_request(
            correlation_id="abc12345",
            original_messages=messages,
            filter_result=result,
            enabled=True
        )
        
        assert output is not None
        assert "REJECT" in output
        assert "denylist_filter" in output
        assert "<blocked>" in output
    
    def test_render_request_disabled(self):
        """Should return None when disabled."""
        messages = [
            Message(role="user", content="Hello"),
        ]
        
        result = MessageFilterResult(
            messages=messages,
            changed=False,
            action="pass",
            reason="",
            metadata={}
        )
        
        output = render_request(
            correlation_id="abc12345",
            original_messages=messages,
            filter_result=result,
            enabled=False
        )
        
        assert output is None
    
    def test_render_request_truncation(self):
        """Should truncate long request text."""
        messages = [
            Message(role="user", content="A" * 1000),
        ]
        
        result = MessageFilterResult(
            messages=messages,
            changed=False,
            action="pass",
            reason="",
            metadata={}
        )
        
        output = render_request(
            correlation_id="abc12345",
            original_messages=messages,
            filter_result=result,
            max_length=100,
            enabled=True
        )
        
        assert output is not None
        assert "..." in output
        # Should not contain full 1000 character string
        assert "A" * 1000 not in output
    
    def test_print_request_writes_to_stdout(self, capsys):
        """print_request should write to stdout."""
        messages = [
            Message(role="user", content="Hello"),
        ]
        
        result = MessageFilterResult(
            messages=messages,
            changed=False,
            action="pass",
            reason="",
            metadata={}
        )
        
        print_request(
            correlation_id="abc12345",
            original_messages=messages,
            filter_result=result,
            enabled=True
        )
        
        out, err = capsys.readouterr()
        
        assert "PASS" in out
        assert "Hello" in out
    
    def test_print_request_fails_safely(self, capsys):
        """print_request should not crash on errors."""
        messages = [
            Message(role="user", content="Hello"),
        ]
        
        result = MessageFilterResult(
            messages=messages,
            changed=False,
            action="pass",
            reason="",
            metadata={}
        )
        
        # Should not raise even if stdout fails
        with patch.object(sys.stdout, 'write', side_effect=OSError("stdout error")):
            print_request(
                correlation_id="abc12345",
                original_messages=messages,
                filter_result=result,
                enabled=True
            )
    
    def test_request_display_format_structure(self):
        """RequestDisplay should format correctly."""
        display = RequestDisplay(
            correlation_id="test1234",
            action="modify",
            filters=["regex_filter"],
            input_text="original text",
            output_text="transformed text"
        )
        
        output = display.format()
        
        lines = output.split("\n")
        assert len(lines) == 3
        assert "[test1234]" in lines[0]
        assert "MODIFY" in lines[0]
        assert "regex_filter" in lines[0]
        assert "input request:" in lines[1]
        assert "original text" in lines[1]
        assert "output request:" in lines[2]
        assert "transformed text" in lines[2]
    
    def test_request_display_reject_format(self):
        """RequestDisplay should show <blocked> for rejected requests."""
        display = RequestDisplay(
            correlation_id="test1234",
            action="reject",
            filters=["denylist_filter"],
            input_text="bad content",
            output_text="<blocked>"
        )
        
        output = display.format()
        
        assert "REJECT" in output
        assert "<blocked>" in output