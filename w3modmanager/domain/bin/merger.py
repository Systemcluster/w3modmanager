from loguru import logger

from typing import Optional
from pathlib import Path
import re


def findScriptMergerPath() -> Optional[Path]:
    try:
        from win32.win32gui import EnumWindows, GetWindow, GetWindowText
        from win32.win32process import GetWindowThreadProcessId, GetModuleFileNameEx
        from win32.win32api import OpenProcess
        existingPaths = []
        windowHandles = []
        EnumWindows(lambda windowHandle, _: windowHandles.append(windowHandle), None)
        for windowHandle in windowHandles:
            parentWindow = GetWindow(windowHandle, 4)
            if parentWindow:
                continue
            title = GetWindowText(windowHandle)
            if re.match(r'^Script Merger', title):
                processIds = GetWindowThreadProcessId(windowHandle)
                for processId in processIds:
                    try:
                        processHandle = OpenProcess(0x1000, False, processId)
                        fileName = GetModuleFileNameEx(processHandle, None)
                        existingPaths.append(fileName)
                    except Exception:  # noqa
                        continue
                existingPaths.append(windowHandle)
        for path in existingPaths:
            if verifyScriptMergerPath(Path(path)):
                return Path(path)
    except Exception as e:
        logger.bind().debug(f'Could not locate Script Merger: {e}')
    return None


def verifyScriptMergerPath(path: Optional[Path]) -> Optional[Path]:
    if not path:
        return None
    try:
        return path.resolve() \
            if path \
            and path.is_file() \
            and path.with_suffix('.exe.config').is_file() \
            else None
    except OSError:
        # check for errors here since this method is used with user input
        logger.bind(path=path).debug('Illegal path')
        return None
