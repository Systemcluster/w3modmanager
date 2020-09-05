from w3modmanager.domain.mod.mod import Settings
from w3modmanager.util.util import detectEncoding

from typing import Sequence, Optional
from pathlib import Path
from configparser import ConfigParser


def addSettings(settingslist: Sequence[Settings], path: Path) -> int:
    encoding = detectEncoding(path)
    config = ConfigParser(strict=False)
    config.optionxform = str  # type: ignore
    config.read(path, encoding=encoding)
    modified = 0
    for settings in settingslist:
        for section in settings.config.sections():
            if not config.has_section(section):
                config.add_section(section)
            for key, val in settings.config.items(section):
                config.set(section, key, val)
                modified += 1
    with open(path, 'w', encoding=encoding) as file:
        config.write(file, space_around_delimiters=False)
    return modified


def removeSettings(settingslist: Sequence[Settings], path: Path) -> int:
    encoding = detectEncoding(path)
    config = ConfigParser(strict=False)
    config.optionxform = str  # type: ignore
    config.read(path, encoding=encoding)
    modified = 0
    for settings in settingslist:
        for section in settings.config.sections():
            if not config.has_section(section):
                continue
            for key, _ in settings.config.items(section):
                config.remove_option(section, key)
                modified += 1
            if not config.items(section):
                config.remove_section(section)
    with open(path, 'w', encoding=encoding) as file:
        config.write(file, space_around_delimiters=False)
    return modified


def removeSettingsSection(section: str, path: Path) -> None:
    encoding = detectEncoding(path)
    config = ConfigParser(strict=False)
    config.optionxform = str  # type: ignore
    config.read(path, encoding=encoding)
    if config.has_section(section):
        config.remove_section(section)
    with open(path, 'w', encoding=encoding) as file:
        config.write(file, space_around_delimiters=False)


def renameSettingsSection(section: str, to: str, path: Path) -> None:
    if section == to:
        return
    encoding = detectEncoding(path)
    config = ConfigParser(strict=False)
    config.optionxform = str  # type: ignore
    config.read(path, encoding=encoding)
    if not config.has_section(section):
        return
    items = config.items(section)
    if not config.has_section(to):
        config.add_section(to)
    for key, val in items:
        config.set(to, key, val)
    config.remove_section(section)
    with open(path, 'w', encoding=encoding) as file:
        config.write(file, space_around_delimiters=False)


def setSettingsValue(section: str, key: str, val: str, path: Path) -> None:
    encoding = detectEncoding(path)
    config = ConfigParser(strict=False)
    config.optionxform = str  # type: ignore
    config.read(path, encoding=encoding)
    if not config.has_section(section):
        config.add_section(section)
    if val:
        config.set(section, key, val)
    else:
        config.remove_option(section, key)
    if not config.items(section):
        config.remove_section(section)
    with open(path, 'w', encoding=encoding) as file:
        config.write(file, space_around_delimiters=False)


def getSettingsValue(section: str, key: str, path: Path) -> Optional[str]:
    encoding = detectEncoding(path)
    config = ConfigParser(strict=False)
    config.optionxform = str  # type: ignore
    config.read(path, encoding=encoding)
    if not config.has_section(section):
        return None
    if not config.has_option(section, key):
        return None
    return config.get(section, key)
