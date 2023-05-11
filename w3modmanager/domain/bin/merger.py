import re

from pathlib import Path

from loguru import logger


def findScriptMergerPath() -> Path | None:
    try:
        from win32.win32api import OpenProcess
        from win32.win32gui import EnumWindows, GetWindow, GetWindowText
        from win32.win32process import GetModuleFileNameEx, GetWindowThreadProcessId
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
                        fileName = GetModuleFileNameEx(processHandle, 0)
                        existingPaths.append(Path(fileName))
                    except Exception:  # noqa
                        continue
        for path in existingPaths:
            if verifyScriptMergerPath(path):
                return path
    except Exception as e:
        logger.bind().debug(f'Could not locate Script Merger: {e}')
    return None


def verifyScriptMergerPath(path: Path | None) -> Path | None:
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
