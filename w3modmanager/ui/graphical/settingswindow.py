from w3modmanager.util.util import getTitleString, debounce
from w3modmanager.domain.mod import fetcher
from w3modmanager.domain.web.nexus import RequestError, ResponseError, UnauthorizedError, getUserInformation
from w3modmanager.core.model import *

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QSize
from PySide6.QtWidgets import QLabel, QGroupBox, QVBoxLayout, QHBoxLayout, \
    QSizePolicy, QPushButton, QLineEdit, QCheckBox, QFileDialog, QDialog, QWidget


class SettingsWindow(QDialog):
    def __init__(self, parent: Optional[QWidget] = None, firstStart: bool = False) -> None:
        super().__init__(parent, )

        if parent:
            self.setWindowTitle('Settings')
        else:
            self.setWindowTitle(getTitleString('Settings'))
            self.setAttribute(Qt.WA_DeleteOnClose)

        settings = QSettings()
        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(5, 5, 5, 5)

        # First Start info

        if firstStart:
            firstStartInfo = QLabel('''
                <p><strong>Hello! It looks like this is your first time using w3modmanager,
                or the game installation path recently changed.</strong></p>
                <p>
                Please review the settings below.
                </p>
                ''', self)
            firstStartInfo.setWordWrap(True)
            firstStartInfo.setContentsMargins(10, 10, 10, 10)
            firstStartInfo.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
            mainLayout.addWidget(firstStartInfo)

        # Game

        gbGame = QGroupBox('Game Path', self)
        mainLayout.addWidget(gbGame)
        gbGameLayout = QVBoxLayout(gbGame)

        gamePathLayout = QHBoxLayout()
        self.gamePath = QLineEdit(self)
        self.gamePath.setPlaceholderText('Path to witcher3.exe...')
        if settings.value('gamePath'):
            self.gamePath.setText(str(settings.value('gamePath')))
        self.gamePath.textChanged.connect(lambda: self.validateGamePath(self.gamePath.text()))
        gamePathLayout.addWidget(self.gamePath)
        self.locateGame = QPushButton('Detect', self)
        self.locateGame.clicked.connect(self.locateGameEvent)
        self.locateGame.setToolTip('Automatically detect the game path if possible')
        gamePathLayout.addWidget(self.locateGame)
        selectGame = QPushButton('Browse', self)
        selectGame.clicked.connect(self.selectGameEvent)
        gamePathLayout.addWidget(selectGame)
        gbGameLayout.addLayout(gamePathLayout)

        gamePathInfoLayout = QHBoxLayout()
        self.gamePathInfo = QLabel('', self)
        self.gamePathInfo.setContentsMargins(4, 4, 4, 4)
        self.gamePathInfo.setMinimumHeight(36)
        self.gamePathInfo.setWordWrap(True)
        gamePathInfoLayout.addWidget(self.gamePathInfo)
        gbGameLayout.addLayout(gamePathInfoLayout)

        # Config

        gbConfig = QGroupBox('Game Config', self)
        mainLayout.addWidget(gbConfig)
        gbConfigLayout = QVBoxLayout(gbConfig)

        configPathLayout = QHBoxLayout()
        self.configPath = QLineEdit(self)
        self.configPath.setPlaceholderText('Path to config folder...')
        if settings.value('configPath'):
            self.configPath.setText(str(settings.value('configPath')))
        self.configPath.textChanged.connect(lambda: self.validateConfigPath(self.configPath.text()))
        configPathLayout.addWidget(self.configPath)
        self.locateConfig = QPushButton('Detect', self)
        self.locateConfig.clicked.connect(self.locateConfigEvent)
        self.locateConfig.setToolTip('Automatically detect the config folder if possible')
        configPathLayout.addWidget(self.locateConfig)
        selectConfig = QPushButton('Browse', self)
        selectConfig.clicked.connect(self.selectConfigEvent)
        configPathLayout.addWidget(selectConfig)
        gbConfigLayout.addLayout(configPathLayout)

        configPathInfoLayout = QHBoxLayout()
        self.configPathInfo = QLabel('', self)
        self.configPathInfo.setContentsMargins(4, 4, 4, 4)
        self.configPathInfo.setMinimumHeight(36)
        self.configPathInfo.setWordWrap(True)
        configPathInfoLayout.addWidget(self.configPathInfo)
        gbConfigLayout.addLayout(configPathInfoLayout)

        # Nexus Mods API

        gbNexusModsAPI = QGroupBox('Nexus Mods API', self)
        mainLayout.addWidget(gbNexusModsAPI)
        gbNexusModsAPILayout = QVBoxLayout(gbNexusModsAPI)

        self.nexusAPIKey = QLineEdit(self)
        self.nexusAPIKey.setPlaceholderText('Personal API Key...')
        if settings.value('nexusAPIKey'):
            self.nexusAPIKey.setText(str(settings.value('nexusAPIKey')))
        self.nexusAPIKey.textChanged.connect(lambda: self.validateApiKey(self.nexusAPIKey.text()))
        gbNexusModsAPILayout.addWidget(self.nexusAPIKey)

        self.nexusAPIKeyInfo = QLabel('🌐', self)
        self.nexusAPIKeyInfo.setOpenExternalLinks(True)
        self.nexusAPIKeyInfo.setWordWrap(True)
        self.nexusAPIKeyInfo.setContentsMargins(4, 4, 4, 4)
        self.nexusAPIKeyInfo.setMinimumHeight(48)
        gbNexusModsAPILayout.addWidget(self.nexusAPIKeyInfo)

        self.nexusGetInfo = QCheckBox('Get Mod details after adding a new mod', self)
        self.nexusGetInfo.setChecked(settings.value('nexusGetInfo', 'True') == 'True')
        self.nexusGetInfo.setDisabled(True)
        gbNexusModsAPILayout.addWidget(self.nexusGetInfo)

        self.nexusCheckUpdates = QCheckBox('Check for Mod updates on startup', self)
        self.nexusCheckUpdates.setChecked(settings.value('nexusCheckUpdates', 'False') == 'True')
        self.nexusCheckUpdates.setDisabled(True)
        gbNexusModsAPILayout.addWidget(self.nexusCheckUpdates)

        self.nexusCheckClipboard = QCheckBox('Monitor the Clipboard for Nexus Mods URLs', self)
        self.nexusCheckClipboard.setChecked(settings.value('nexusCheckClipboard', 'False') == 'True')
        self.nexusCheckClipboard.setDisabled(True)
        gbNexusModsAPILayout.addWidget(self.nexusCheckClipboard)

        # Output

        gbOutput = QGroupBox('Output Preferences', self)
        mainLayout.addWidget(gbOutput)
        gbOutputLayout = QVBoxLayout(gbOutput)
        self.unhideOutput = QCheckBox('Auto-show output panel', self)
        self.unhideOutput.setChecked(settings.value('unhideOutput', 'True') == 'True')
        gbOutputLayout.addWidget(self.unhideOutput)
        self.debugOutput = QCheckBox('Show debug output', self)
        self.debugOutput.setChecked(settings.value('debugOutput', 'False') == 'True')
        gbOutputLayout.addWidget(self.debugOutput)

        # Actions

        actionsLayout = QHBoxLayout()
        actionsLayout.setAlignment(Qt.AlignRight)
        self.save = QPushButton('Save', self)
        self.save.clicked.connect(self.saveEvent)
        self.save.setAutoDefault(True)
        self.save.setDefault(True)
        actionsLayout.addWidget(self.save)
        cancel = QPushButton('Cancel', self)
        cancel.clicked.connect(self.cancelEvent)
        actionsLayout.addWidget(cancel)
        mainLayout.addLayout(actionsLayout)

        # Setup

        if not settings.value('gamePath'):
            self.locateGameEvent()
        self.setMinimumSize(QSize(420, 420))
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)

        self.validGamePath = False
        self.validConfigPath = False
        self.validNexusAPIKey = False

        self.validateGamePath(self.gamePath.text())
        self.validateConfigPath(self.configPath.text())
        self.validateApiKey(self.nexusAPIKey.text())
        self.updateSaveButton()

        self.finished.connect(lambda: self.validateApiKey.cancel())  # type: ignore

    def saveEvent(self) -> None:
        settings = QSettings()
        settings.setValue('settingsWindowGeometry', self.saveGeometry())
        settings.setValue('gamePath', self.gamePath.text())
        settings.setValue('configPath', self.configPath.text())
        settings.setValue('nexusAPIKey', self.nexusAPIKey.text())
        settings.setValue('nexusGetInfo', str(self.nexusGetInfo.isChecked()))
        settings.setValue('nexusCheckUpdates', str(self.nexusCheckUpdates.isChecked()))
        settings.setValue('nexusCheckClipboard', str(self.nexusCheckClipboard.isChecked()))
        settings.setValue('debugOutput', str(self.debugOutput.isChecked()))
        settings.setValue('unhideOutput', str(self.unhideOutput.isChecked()))
        self.close()

    def cancelEvent(self) -> None:
        self.close()

    def selectGameEvent(self) -> None:
        dialog: QFileDialog = QFileDialog(self, 'Select witcher3.exe', '', 'The Witcher 3 (witcher3.exe)')
        dialog.setOptions(QFileDialog.ReadOnly)
        dialog.setFileMode(QFileDialog.ExistingFile)
        if (dialog.exec_()):
            if dialog.selectedFiles():
                self.gamePath.setText(dialog.selectedFiles()[0])

    def selectConfigEvent(self) -> None:
        dialog: QFileDialog = QFileDialog(self, 'Select config folder', '', 'The Witcher 3')
        dialog.setOptions(QFileDialog.ReadOnly)
        dialog.setFileMode(QFileDialog.Directory)
        if (dialog.exec_()):
            if dialog.selectedFiles():
                self.configPath.setText(dialog.selectedFiles()[0])

    def locateGameEvent(self) -> None:
        game = fetcher.findGamePath()
        if game:
            self.gamePath.setText(str(game))
        else:
            self.gamePathInfo.setText('''
                <font color="#888">
                Could not detect The Witcher 3!<br>
                Please make sure the game is installed, or set the path manually.
                </font>''')

    def locateConfigEvent(self) -> None:
        config = fetcher.findConfigPath()
        if config:
            self.configPath.setText(str(config))
        else:
            self.configPathInfo.setText('''
                <font color="#888">
                Could not detect a valid config path!
                Please make sure the The Witcher 3 was started at least once,
                or set the path manually.
                </font>''')

    def validateGamePath(self, text: str) -> bool:
        # validate game installation path
        if not verifyGamePath(Path(text)):
            self.gamePath.setStyleSheet('''
                *{
                    border: 1px solid #B22222;
                    padding: 1px 0px;
                }
                ''')
            self.gamePathInfo.setText('<font color="#888">Please enter a valid game path.</font>')
            self.validGamePath = False
            self.locateGame.setDisabled(False)
            self.updateSaveButton()
            return False
        else:
            self.gamePath.setStyleSheet('')
            self.gamePathInfo.setText('<font color="#888">Everything looks good!</font>')
            self.validGamePath = True
            self.locateGame.setDisabled(True)
            self.updateSaveButton()
            return True

    def validateConfigPath(self, text: str) -> bool:
        # validate game config path
        if not verifyConfigPath(Path(text)):
            self.configPath.setStyleSheet('''
                *{
                    border: 1px solid #B22222;
                    padding: 1px 0px;
                }
                ''')
            self.configPathInfo.setText('''<font color="#888">
                Please enter a valid config path.
                You need to start the The Witcher 3 at least once
                to generate the necessary user.settings and input.settings files.</font>
                ''')
            self.validConfigPath = False
            self.locateConfig.setDisabled(False)
            self.updateSaveButton()
            return False
        else:
            self.configPath.setStyleSheet('')
            self.configPathInfo.setText('<font color="#888">Everything looks good!</font>')
            self.validConfigPath = True
            self.locateConfig.setDisabled(True)
            self.updateSaveButton()
            return True

    @debounce(200, cancel_running=True)
    async def validateApiKey(self, text: str) -> bool:
        # validate neus mods api key
        self.nexusGetInfo.setDisabled(True)
        self.nexusCheckUpdates.setDisabled(True)
        self.nexusCheckClipboard.setDisabled(True)
        self.nexusAPIKey.setStyleSheet('')
        if not text:
            self.nexusAPIKeyInfo.setText('''
                <font color="#888">The API Key is used to check for mod updates, \
                to get mod details and to download mods. \
                Get your Personal API Key <a href="https://www.nexusmods.com/users/myaccount?tab=api">here</a>.</font>
                ''')
            self.validNexusAPIKey = True
            self.updateSaveButton()
            return True
        self.nexusAPIKeyInfo.setText('🌐')
        try:
            apiUser = await getUserInformation(text)
        except UnauthorizedError:
            self.nexusAPIKey.setStyleSheet('''
                *{
                    border: 1px solid #B22222;
                    padding: 1px 0px;
                }
                ''')
            self.nexusAPIKeyInfo.setText('''
                <font color="#888">Not a valid API Key. \
                Get your Personal API Key <a href="https://www.nexusmods.com/users/myaccount?tab=api">here</a>.</font>
                ''')
            self.validNexusAPIKey = False
            self.updateSaveButton()
            return False
        except (RequestError, ResponseError, Exception) as e:
            self.nexusAPIKey.setStyleSheet('''
                *{
                    border: 1px solid #B22222;
                    padding: 1px 0px;
                }
                ''')
            self.nexusAPIKeyInfo.setText(f'''
                <font color="#888">Could not validate API Key: {str(e) if str(e) else 'Request error'}.</font>
                ''')
            self.validNexusAPIKey = False
            self.updateSaveButton()
            return False
        self.nexusAPIKeyInfo.setText(f'<font color="#888">Valid API Key for {apiUser["name"]}!</font>')
        self.validNexusAPIKey = True
        self.nexusGetInfo.setDisabled(False)
        self.nexusCheckUpdates.setDisabled(False)
        self.nexusCheckClipboard.setDisabled(False)
        self.updateSaveButton()
        return True

    def updateSaveButton(self) -> None:
        # TODO: release: disable saving invalid settings
        # self.save.setDisabled(not all((
        #     self.validConfigPath,
        #     self.validGamePath,
        #     self.validNexusAPIKey,
        # )))  # noqa
        self.save.setDisabled(False)
