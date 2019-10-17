"""
simple invoke task collection
"""


from pathlib import Path
from shutil import rmtree
from distutils.dir_util import copy_tree

from invoke import task


@task
def start(ctx, mock=False, clean=False):
    """start the w3modmanager application"""
    from tests.framework import _mockdata, _root
    from w3modmanager import __main__
    _testdata = _root.joinpath('testdata')
    if clean:
        print('cleaning up testdata...')
        rmtree(_testdata, ignore_errors=True)
    if mock:
        from qtpy.QtCore import QSettings
        print('setting up testdata...')
        copy_tree(str(_mockdata), str(_testdata))
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(_testdata.joinpath('settings')))
        __main__.main(_testdata.joinpath('programs'), _testdata.joinpath('documents'))
    else:
        __main__.main()


@task
def clean(ctx,):
    """delete the test and build files"""
    rmtree(Path(__file__).parent.joinpath('build'), ignore_errors=True)
    rmtree(Path(__file__).parent.joinpath('dist'), ignore_errors=True)
    rmtree(Path(__file__).parent.joinpath('testdata'), ignore_errors=True)


@task
def build(ctx, clean=False, spec='w3modmanager.spec'):
    """build the binary distribution"""
    if clean:
        return ctx.run(f'python -m PyInstaller --clean {spec}').exited
    else:
        return ctx.run(f'python -m PyInstaller {spec}').exited


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
