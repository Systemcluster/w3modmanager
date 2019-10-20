"""
simple invoke task collection
"""


from pathlib import Path
from shutil import rmtree, which
from distutils.dir_util import copy_tree
import subprocess

from invoke import task


@task
def start(ctx, mock=False, clean=False):
    """start the w3modmanager application"""
    from tests.framework import _mockdata, _root
    import w3modmanager
    import w3modmanager.__main__
    _testdata = _root.joinpath('testdata')
    if clean:
        print('cleaning up testdata...')
        rmtree(_testdata, ignore_errors=True)
    git = which('git')
    if git:
        hash = subprocess.run([git, 'rev-parse', '--short=auto', 'HEAD'], capture_output=True).stdout
        if hash:
            w3modmanager.VERSION_HASH = str(hash, 'utf-8').strip()
        date = subprocess.run([git, 'show', '-s', '--format=%cI', 'HEAD'], capture_output=True).stdout
        if date:
            w3modmanager.VERSION = str(date, 'utf-8').strip()[:10].replace('-', '.')
    if mock:
        from qtpy.QtCore import QSettings
        print('setting up testdata...')
        copy_tree(str(_mockdata), str(_testdata))
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(_testdata.joinpath('settings')))
        w3modmanager.__main__.main(_testdata.joinpath('programs'), _testdata.joinpath('documents'))
    else:
        w3modmanager.__main__.main()


@task
def clean(ctx,):
    """delete the test and build files"""
    rmtree(Path(__file__).parent.joinpath('build'), ignore_errors=True)
    rmtree(Path(__file__).parent.joinpath('dist'), ignore_errors=True)
    rmtree(Path(__file__).parent.joinpath('testdata'), ignore_errors=True)


@task
def build(ctx, clean=False, spec='w3modmanager.spec', version=''):
    """build the binary distribution"""
    runtime = Path(__file__).parent.joinpath('runtime.py')
    with open(runtime, 'w') as rt:
        hook = ['import w3modmanager']
        if version:
            hook.append(f'w3modmanager.VERSION = \'{version}\'')
        git = which('git')
        if git:
            hash = subprocess.run([git, 'rev-parse', '--short=auto', 'HEAD'], capture_output=True).stdout
            if hash:
                hash = str(hash, 'utf-8').strip()
                hook.append(f'w3modmanager.VERSION_HASH = \'{hash}\'')
            if not version:
                date = subprocess.run([git, 'show', '-s', '--format=%cI', 'HEAD'], capture_output=True).stdout
                if date:
                    date = str(date, 'utf-8').strip()
                    date = date[:10].replace('-', '.')
                    hook.append(f'w3modmanager.VERSION = \'{date}\'')
        rt.write('\n'.join(hook))
    if clean:
        result = ctx.run(f'python -m PyInstaller --clean {spec}').exited
    else:
        result = ctx.run(f'python -m PyInstaller {spec}').exited
    if runtime.is_file():
        runtime.unlink()
    return result


@task
def mypy(ctx,):
    """check the project files for correctness with mypy"""
    return ctx.run('python -m mypy -p w3modmanager').exited


@task
def flake8(ctx, noerror=False):
    """check the project files for correctness with flake8"""
    return ctx.run(f'python -m flake8 w3modmanager{" --exit-zero" if noerror else ""}').exited


@task
def check(ctx,):
    """check the project files for correctness"""
    results = [flake8(ctx), mypy(ctx)]
    successes = results.count(0)
    result = not any(results)
    if result:
        print(f'\npassed {successes} checks')
    else:
        print(f'\nfailed {len(results) - successes} checks ({successes} passed)')
    return result


@task
def test(ctx,):
    """runs the test suite"""
    return ctx.run('python -m pytest')
