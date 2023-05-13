from w3modmanager.util.util import debounce, detectEncoding

import asyncio

from collections.abc import Callable
from configparser import ConfigParser
from pathlib import Path
from typing import Any, TypeVar

from loguru import logger
from PySide6.QtCore import QObject, Signal
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer


class CallbackList(list[Callable[..., Any]]):
    def __init__(self) -> None:
        self.fireLock = asyncio.Lock()
        self._skip = 0
        super().__init__()

    def skip(self, count: int) -> None:
        self._skip += count

    @debounce(25)
    async def fire(self, *args: Any, **kwargs: Any) -> None:
        async with self.fireLock:
            if self._skip == 0:
                for listener in self:
                    listener(*args, **kwargs)
            else:
                self._skip = max(0, self._skip - 1)


class FileWatcher(QObject):
    _signal = Signal(Path)

    def __init__(self, path: Path | str, files: list[str]) -> None:
        super().__init__()

        self.path = path
        self.callbacks = CallbackList()

        self._signal.connect(self._callback)
        self._paused = False

        self._observer = Observer()
        self._handler = PatternMatchingEventHandler(
            patterns=files, ignore_patterns=[], ignore_directories=True, case_sensitive=False)
        self._handler.on_modified = lambda event: self._signal.emit(Path(event.src_path))
        self._handler.on_created = lambda event: self._signal.emit(Path(event.src_path))
        self._handler.on_deleted = lambda event: self._signal.emit(Path(event.src_path))
        self._observer.schedule(self._handler, str(path), recursive=False)
        self._observer.start()

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def _callback(self, path: Path) -> None:
        if not self._paused:
            self.callbacks.fire(path)

    def __del__(self) -> None:
        self._observer.stop()


class WatchedConfigFile:
    _SectionGet = TypeVar('_SectionGet', str, int, None)

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.watcher = FileWatcher(self.path.parent, [self.path.name])
        self.watcher.callbacks.append(lambda _: self._onFileChanged())
        self.config = ConfigParser(strict=False)
        self.config.optionxform = str  # type: ignore
        self.encoding = 'utf-8'
        self.read()

    def setValue(self, section: str, key: str, value: str) -> None:
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, value)

    def getValue(self, section: str, key: str, fallback: _SectionGet = None) -> str | _SectionGet:
        if fallback is not None:
            return self.config.get(section, key, fallback=fallback)
        if self.config.has_section(section) and self.config.has_option(section, key):
            return self.config.get(section, key)
        return fallback

    def renameSection(self, section: str, to: str) -> None:
        if self.config.has_section(section):
            items = self.config.items(section)
            if not self.config.has_section(to):
                self.config.add_section(to)
            for key, val in items:
                self.config.set(to, key, val)
            self.config.remove_section(section)

    def removeSection(self, section: str) -> None:
        if self.config.has_section(section):
            self.config.remove_section(section)

    def read(self) -> None:
        if self.path.is_file():
            encoding = detectEncoding(self.path)
            self.encoding = encoding
            self.config.read(self.path, encoding=encoding)
        else:
            self.config.clear()

    @debounce(25)
    async def write(self) -> None:
        # skip callbacks for the next modification event
        self.watcher.callbacks.skip(1)
        try:
            if not self.path.parent.is_dir():
                self.path.parent.mkdir(parents=True)
            with open(self.path, 'w', encoding=self.encoding) as file:  # noqa: ASYNC101
                self.config.write(file, space_around_delimiters=False)
        except Exception as e:
            logger.bind(path=self.path).exception(f'Could not write settings file: {e}')

    def _onFileChanged(self) -> None:
        self.read()
