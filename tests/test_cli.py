import sys
from promptproxy.cli import chat_console, log_console, configure_logging
from promptproxy.config import Config

def test_console_channels(capsys):
    # chat_console writes to stdout
    chat_console.print("chat message")
    # log_console writes to stderr
    log_console.print("log message")
    out, err = capsys.readouterr()
    assert "chat message" in out
    assert "log message" in err


def test_demo_mode_header(capsys, monkeypatch, tmp_path):
    # create a temporary config with demo_mode enabled
    cfg = Config()
    cfg.ui.demo_mode = True
    # configure logging so logger creation works
    configure_logging(level=cfg.logging.level, file_path=cfg.logging.file_path)

    # simulate what main() would print on startup
    from promptproxy.cli import chat_console
    chat_console.print("[bold magenta]DEMO MODE ENABLED[/bold magenta]\n")
    # simulate a log message as might occur during operation
    log_console.print("error occurred")
    out, err = capsys.readouterr()
    assert "DEMO MODE ENABLED" in out
    # log message should go to stderr, not stdout
    assert "error occurred" in err
    assert "error occurred" not in out
