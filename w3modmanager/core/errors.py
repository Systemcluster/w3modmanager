from pathlib import Path


#
# util errors
#


class InvalidPathError(IOError):
    def __init__(self, path: Path, message: str = '') -> None:
        super().__init__(f'{f"{message}: " if message else ""}{str(path.resolve())}')
        self.path = path
        self.message = message


class UnexpectedInputError(IOError):
    def __init__(self, path: Path, message: str = '') -> None:
        super().__init__(f'{f"{message}: " if message else ""}{str(path.resolve())}')
        self.path = path
        self.message = message


#
# model errors
#


class ModelError(IOError):
    def __init__(self, path: Path, message: str = '') -> None:
        if message:
            self.message = message
        super().__init__(f'{self.message}: \'{str(path.resolve())}\'')
        self.path = path
    message = 'Model Error'


class OtherInstanceError(ModelError):
    message = 'Could not lock'


class InvalidGamePath(ModelError):
    message = 'Invalid game path'


class InvalidConfigPath(ModelError):
    message = 'Invalid config path'


class InvalidCachePath(ModelError):
    message = 'Invalid cache path'


class InvalidModsPath(ModelError):
    message = 'Invalid mods path'


class InvalidDlcsPath(ModelError):
    message = 'Invalid dlcs path'


class InvalidSourcePath(ModelError):
    message = 'Invalid source path'


#
# mod errors
#


class ModError(ValueError):
    pass


class ModExistsError(ModError):
    def __init__(self, filename: str, target: str) -> None:
        super().__init__(f'Mod already exists: {target}/{filename}')


class ModNotFoundError(ModError):
    def __init__(self, filename: str, target: str) -> None:
        super().__init__(f'Mod not found: {target}/{filename}')
