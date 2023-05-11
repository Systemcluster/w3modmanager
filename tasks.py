"""
simple invoke task collection
"""


import subprocess

from datetime import datetime, timezone
from distutils.dir_util import copy_tree
from os import environ
from pathlib import Path
from shutil import rmtree, which
from typing import Any

from invoke.tasks import task


@task
def start(ctx: Any, mock=False, clean=False, configured=True):
    """start the w3modmanager application"""
    import w3modmanager
    import w3modmanager.__main__

    from tests.framework import _mockdata, _root  # type: ignore

    testdata = _root.joinpath('testdata')
    if clean:
        print('cleaning up testdata...')
        rmtree(testdata, ignore_errors=True)
    git = which('git')
    if git:
        hash = subprocess.run([git, 'rev-parse', '--short=7', 'HEAD'], capture_output=True).stdout
        if hash:
            w3modmanager.VERSION_HASH = str(hash, 'utf-8').strip()
        date = subprocess.run([git, 'show', '-s', '--format=%cI', 'HEAD'], capture_output=True).stdout
        if date:
            date = datetime.fromisoformat(str(date, 'utf-8').strip()).astimezone(timezone.utc).isoformat()
            date = date[:10].replace('-', '.')
            w3modmanager.VERSION = date
    if mock:
        from PySide6.QtCore import QSettings
        print('setting up testdata...')
        copy_tree(str(_mockdata), str(testdata))
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(testdata.joinpath('settings')))
        if configured:
            w3modmanager.__main__.main(str(testdata.joinpath('programs')), str(testdata.joinpath('documents')))
        else:
            w3modmanager.__main__.main()
    else:
        w3modmanager.__main__.main()


@task
def clean(ctx: Any):
    """delete the test and build files"""
    rmtree(Path(__file__).parent.joinpath('build'), ignore_errors=True)
    rmtree(Path(__file__).parent.joinpath('dist'), ignore_errors=True)
    rmtree(Path(__file__).parent.joinpath('testdata'), ignore_errors=True)


@task
def build(ctx: Any, clean=False, spec='w3modmanager.spec', version=''):
    """build the binary distribution"""
    runtime = Path(__file__).parent.joinpath('runtime.py')
    with open(runtime, 'w', encoding='utf-8') as rt:
        hook = ['import w3modmanager']
        if version:
            hook.append(f'w3modmanager.VERSION = \'{version}\'')
        git = which('git')
        if git:
            hash = subprocess.run([git, 'rev-parse', '--short=7', 'HEAD'], capture_output=True).stdout
            if hash:
                hash = str(hash, 'utf-8').strip()
                hook.append(f'w3modmanager.VERSION_HASH = \'{hash}\'')
            if not version:
                date = subprocess.run([git, 'show', '-s', '--format=%cI', 'HEAD'], capture_output=True).stdout
                if date:
                    date = datetime.fromisoformat(str(date, 'utf-8').strip()).astimezone(timezone.utc).isoformat()
                    date = date[:10].replace('-', '.')
                    hook.append(f'w3modmanager.VERSION = \'{date}\'')
        rt.write('\n'.join(hook))
    dist = Path(__file__).parent.joinpath('dist/w3modmanager')
    if dist.is_dir():
        rmtree(dist)
    if clean:
        result = subprocess.run(
            f'python -m PyInstaller --clean {spec}', env={**environ.copy(), 'PYTHONOPTIMIZE': '2'}, shell=True
        ).returncode
    else:
        result = subprocess.run(
            f'python -m PyInstaller {spec}', env={**environ.copy(), 'PYTHONOPTIMIZE': '2'}, shell=True
        ).returncode
    if runtime.is_file():
        runtime.unlink()
    return result


@task
def pyright(ctx: Any):
    """check the project files for correctness with pyright"""
    return subprocess.run('python -m pyright -p pyproject.toml', shell=True).returncode


@task
def flake8(ctx: Any):
    """check the project files for correctness with ruff"""
    return subprocess.run('python -m ruff w3modmanager', shell=True).returncode


@task
def check(ctx: Any):
    """check the project files for correctness"""
    results = [
        subprocess.run('python -m pyright -p pyproject.toml', shell=True).returncode,
        subprocess.run('python -m ruff w3modmanager', shell=True).returncode
    ]
    successes = results.count(0)
    result = not any(results)
    if result:
        print(f'\npassed {successes} checks')
    else:
        print(f'\nfailed {len(results) - successes} checks ({successes} passed)')
    return result


@task
def test(ctx: Any, changes=False):
    """runs the test suite"""
    return subprocess.run(f'python -m pytest --verbose {"--picked --mode=branch" if changes else ""}', shell=True).returncode
