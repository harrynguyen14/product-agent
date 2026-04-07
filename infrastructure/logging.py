from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO", fmt: str = "console") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        formatter = logging.Formatter(
            '{"time":"%(asctime)s","level":"%(levelname)s","name":"%(name)s","msg":"%(message)s"}'
        )
    else:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)


class _StructLogger:
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _log(self, level: int, event: str, **kwargs) -> None:
        extra = " ".join(f"{k}={v!r}" for k, v in kwargs.items())
        self._logger.log(level, f"{event} {extra}".strip())

    def debug(self, event: str, **kw) -> None:   self._log(logging.DEBUG,   event, **kw)
    def info(self, event: str, **kw) -> None:    self._log(logging.INFO,    event, **kw)
    def warning(self, event: str, **kw) -> None: self._log(logging.WARNING, event, **kw)
    def error(self, event: str, **kw) -> None:   self._log(logging.ERROR,   event, **kw)

    def exception(self, event: str, **kw) -> None:
        extra = " ".join(f"{k}={v!r}" for k, v in kw.items())
        self._logger.exception(f"{event} {extra}".strip())


def get_logger(name: str) -> _StructLogger:
    return _StructLogger(name)
