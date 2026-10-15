import logging
from logging.handlers import RotatingFileHandler

from shared import get_logger


def test_logger_writes_to_stderr_and_rotating_file(tmp_path, monkeypatch, capsys):
    log_path = tmp_path / "logs" / "backend.log"
    monkeypatch.setenv("LOG_FILE", str(log_path))
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    logger = get_logger("rotation-test")

    file_handler = next(
        handler
        for handler in logging.getLogger("mlai").handlers
        if isinstance(handler, RotatingFileHandler)
    )
    assert file_handler.maxBytes == 10 * 1024 * 1024
    assert file_handler.backupCount == 5
    file_handler.maxBytes = 150

    logger.info("first %s", "x" * 60)
    logger.info("second %s", "y" * 60)
    logger.info("third %s", "z" * 60)

    assert log_path.is_file()
    assert log_path.with_name("backend.log.1").is_file()
    assert "third" in log_path.read_text(encoding="utf-8")
    assert "third" in capsys.readouterr().err

    monkeypatch.delenv("LOG_FILE")
    get_logger("rotation-cleanup")


def test_render_uses_stderr_without_a_file_sink(tmp_path, monkeypatch, capsys):
    log_path = tmp_path / "should-not-exist.log"
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("LOG_FILE", str(log_path))

    get_logger("render-test").info("render dashboard stream")

    assert not log_path.exists()
    assert "render dashboard stream" in capsys.readouterr().err

    monkeypatch.delenv("LOG_FILE")
    monkeypatch.delenv("RENDER")
    get_logger("render-cleanup")
