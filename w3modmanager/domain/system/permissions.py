"""System permission queries and modifications"""

from w3modmanager.util.util import getWindowsPath

from pathlib import Path
import pywintypes  # noqa
import win32api  # noqa
import win32security  # noqa
import subprocess
import shutil

from loguru import logger


def getWritePermissions(path: Path, children: bool = True) -> bool:
    """Check user write permissions to directory"""
    try:
        if children:
            # only check the top level directories for performance reasons
            # this should be enough in most cases
            dirs = [path.resolve(strict=True), *list(path.glob('*'))]
        else:
            dirs = [path.resolve(strict=True)]
        for file in dirs:
            user = win32api.GetUserName()
            usid = win32security.ConvertSidToStringSid(win32security.LookupAccountName(None, user)[0])
            info = win32security.GetFileSecurity(str(file), win32security.DACL_SECURITY_INFORMATION)
            dacl = info.GetSecurityDescriptorDacl()
            expl = dacl.GetExplicitEntriesFromAcl()
            # if no explicit access is set, assume inherited access
            if not expl:
                if file.parent not in dirs:
                    dirs.append(file.parent)
                continue
            # search for a permission set with full access or modify access
            # for the current user or for authenticated users
            good = False
            for perm in expl:
                dsid = win32security.ConvertSidToStringSid(perm['Trustee']['Identifier'])
                dacc = perm['AccessPermissions']
                if dsid in (usid, 'S-1-5-11',) and dacc in (0x1f01ff, 0x1301bf,):
                    good = True
                    break
            if not good:
                return False
        return True
    except Exception as e:
        logger.exception(str(e))
        return False


def setWritePermissions(path: Path) -> bool:
    """Set write permissions to directory for current user"""
    try:
        # get the paths to the required system executables
        icacls = shutil.which('icacls.exe') \
            or getWindowsPath().joinpath('system32/icacls.exe')
        powershell = shutil.which('powershell.exe') or shutil.which('pwsh.exe') \
            or getWindowsPath().joinpath('WindowsPowerShell/v1.0/powershell.exe')
        # add modify access permissions for the current user
        # the indirection through powershell allows access through the uac screen
        user = win32api.GetUserName()
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        CREATE_NO_WINDOW = 0x08000000
        result = subprocess.run([  # noqa
            f'{str(Path(powershell).resolve(strict=True))}', '-Command',
            f'Start-Process \
                -FilePath "{str(Path(icacls).resolve(strict=True))}" \
                -ArgumentList \'"{str(path.resolve(strict=True))}" "/grant" "{user}:(OI)(CI)M" "/T"\' \
                -Verb RunAs -WindowStyle Hidden'],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW, startupinfo=si)
        return result.returncode == 0
    except Exception as e:
        logger.exception(str(e))
        return False
