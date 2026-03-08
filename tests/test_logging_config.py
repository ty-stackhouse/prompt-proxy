import logging
import os
from promptproxy.logging_config import configure_logging, get_logger


def test_configure_logging_stderr(capsys, tmp_path):
    # make sure basic configuration writes to stderr
    configure_logging(level="DEBUG", file_path=None)
    logger = get_logger("test")
    logger.debug("debugging")
    out, err = capsys.readouterr()
    assert "debugging" in err
    # ensure nothing on stdout
    assert out == ""
    # clear handlers so later tests can reconfigure independently
    logging.getLogger().handlers = []


def test_configure_logging_file(tmp_path):
    log_file = tmp_path / "out.log"
    configure_logging(level="INFO", file_path=str(log_file))
    logger = get_logger("test2")
    logger.info("hello file")
    # flush handlers
    for h in logger.handlers:
        h.flush()
    contents = log_file.read_text()
    assert "hello file" in contents
    # cleanup handlers for other tests
    logging.getLogger().handlers = []
