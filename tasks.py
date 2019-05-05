"""
simple invoke task collection
"""


from pathlib import Path
from shutil import rmtree, copytree

from invoke import task


@task
def start(ctx, cleancopy=False):
    """start the w3modmanager application"""
    from w3modmanager import __main__


@task
def clean(ctx,):
    """delete the test and build files"""
    rmtree(Path(__file__).parent.joinpath('build'), ignore_errors=True)
    rmtree(Path(__file__).parent.joinpath('dist'), ignore_errors=True)


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
