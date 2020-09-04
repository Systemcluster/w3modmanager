from w3modmanager.domain.mod.mod import Mod
from w3modmanager.util.util import detectEncoding

from pathlib import Path
from configparser import ConfigParser


def addSettings(mod: Mod, path: Path) -> int:
    encoding = detectEncoding(path)
    config = ConfigParser(strict=False)
    config.optionxform = str  # type: ignore
    config.read(path, encoding=encoding)
    modified = 0
    for settings in mod.settings:
        for section in settings.config.sections():
            if not config.has_section(section):
                config.add_section(section)
            for key, val in settings.config.items(section):
                config.set(section, key, val)
                modified += 1
    with open(path, 'w', encoding=encoding) as file:
        config.write(file, space_around_delimiters=False)
    return modified


def removeSettings(mod: Mod, path: Path) -> int:
    encoding = detectEncoding(path)
    config = ConfigParser(strict=False)
    config.optionxform = str  # type: ignore
    config.read(path, encoding=encoding)
    modified = 0
    for settings in mod.settings:
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
