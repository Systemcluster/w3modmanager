import w3modmanager
from w3modmanager.core.model import Model
from w3modmanager.util.util import *
from w3modmanager.domain.mod.fetcher import *
from w3modmanager.ui.graphical.mainwidget import MainWidget
from w3modmanager.ui.graphical.settingswindow import SettingsWindow

from qtpy.QtCore import QSize, QSettings, Qt
from qtpy.QtWidgets import QMainWindow, QMenuBar, QAction, \
    QFileDialog, QInputDialog, QDialogButtonBox, QSizePolicy, \
    QMessageBox, QMenu
from qtpy.QtGui import QIcon


class MainWindow(QMainWindow):
    def __init__(self, model: Model):
        super().__init__()

        self.model = model

        self.setWindowTitle(getTitleString('Mod Manager'))
        self.setMinimumSize(QSize(750, 500))
        self.setupMenu()

        settings = QSettings()
        if settings.value('mainWindowGeometry'):
            self.restoreGeometry(settings.value('mainWindowGeometry'))
        if settings.value('mainWindowState'):
            self.restoreState(settings.value('mainWindowState'))

        # TODO: enhancement: add an url handler for 'nxm://' urls
        # see https://docs.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/platform-apis/aa767914(v=vs.85)  # noqa

        # TODO: enhancement: import settings from the witcher 3 mod manager

        self.mainwidget = MainWidget(self, model)
        self.setCentralWidget(self.mainwidget)
        self.show()
        self.raise_()
        self.activateWindow()

    def nxmUrlEvent(self, event):
        print(event)

    def closeEvent(self, _event):
        settings = QSettings()
        settings.setValue('mainWindowGeometry', self.saveGeometry())
        settings.setValue('mainWindowState', self.saveState())

    def setupMenu(self):
        self.menuBar = QMenuBar(self)
        self.setMenuBar(self.menuBar)
        settings = QSettings()

        # mods menu

        menuMods: QMenu = self.menuBar.addMenu('&Mods')

        downIcon = QIcon(str(getRuntimePath('resources/icons/down.ico')))
        gearIcon = QIcon(str(getRuntimePath('resources/icons/gear.ico')))

        actionAddModFromFile = QAction('&Add Mods', self)
        actionAddModFromFile.triggered.connect(self.showAddModFromFileDialog)
        menuMods.addAction(actionAddModFromFile)
        actionAddModFromFolder = QAction('Add u&npacked Mod', self)
        actionAddModFromFolder.triggered.connect(self.showAddModFromFolderDialog)
        menuMods.addAction(actionAddModFromFolder)
        actionDownloadMod = QAction('&Download Mod', self)
        actionDownloadMod.triggered.connect(self.showDownloadModDialog)
        actionDownloadMod.setIcon(downIcon)
        menuMods.addAction(actionDownloadMod)

        menuMods.addSeparator()
        actionGetInfo = QAction('Update mod de&tails', self)
        actionGetInfo.triggered.connect(self.showGetInfoDialog)
        actionGetInfo.setIcon(downIcon)
        menuMods.addAction(actionGetInfo)
        actionGetUpdates = QAction('Check for mod &updates', self)
        actionGetUpdates.triggered.connect(self.showGetUpdatesDialog)
        actionGetUpdates.setIcon(downIcon)
        menuMods.addAction(actionGetUpdates)

        menuMods.addSeparator()
        actionExport = QAction('&Export Modlist', self)
        actionExport.triggered.connect(self.showExportDialog)
        menuMods.addAction(actionExport)

        menuMods.aboutToShow.connect(lambda: [
            actionDownloadMod.setDisabled(not str(settings.value('nexusAPIKey'))),
            actionGetInfo.setDisabled(
                not str(settings.value('nexusAPIKey')) or not len(self.model)),
            actionGetUpdates.setDisabled(
                not str(settings.value('nexusAPIKey')) or not len(self.model)),
            actionExport.setDisabled(not len(self.model))
        ])

        # settings menu

        menuSettings: QMenu = self.menuBar.addMenu('&Tools')
        actionSettings = QAction('&Settings', self)
        actionSettings.triggered.connect(self.showSettingsDialog)
        actionSettings.setIcon(gearIcon)
        menuSettings.addAction(actionSettings)

        # info menu

        menuInfo: QMenu = self.menuBar.addMenu('&Info')
        actionAbout = QAction('&About', self)
        actionAbout.triggered.connect(self.showAboutDialog)
        actionAbout.setIcon(QIcon.fromTheme('document-open'))
        menuInfo.addAction(actionAbout)

    def showExportDialog(self):
        # TODO: incomplete: implement modlist export
        pass

    def showGetInfoDialog(self):
        # TODO: incomplete: implement mod info update
        pass

    def showGetUpdatesDialog(self):
        # TODO: incomplete: implement mod update download
        pass

    def showAddModFromFolderDialog(self):
        dialog: QFileDialog = QFileDialog(self, 'Select Mod to install')
        dialog.setOptions(QFileDialog.ReadOnly)
        dialog.setFileMode(QFileDialog.Directory)
        if (dialog.exec_()):
            self.mainwidget.modlist.checkInstallFromURLs(dialog.selectedUrls())

    def showAddModFromFileDialog(self):
        dialog: QFileDialog = QFileDialog(self, 'Select Mod(s) to install', '', 'Archives (*.zip *.rar *.7z)')
        dialog.setOptions(QFileDialog.ReadOnly)
        dialog.setFileMode(QFileDialog.ExistingFiles)
        if (dialog.exec_()):
            self.mainwidget.modlist.checkInstallFromURLs(dialog.selectedUrls())

    def showDownloadModDialog(self):
        dialog: QInputDialog = QInputDialog(self)
        dialog.setWindowTitle('Download Mod')
        dialog.setLabelText('''
            <p>Enter a Nexus Mods mod page URL:</p><p>
            <font color="#888">https://www.nexusmods.com/witcher3/mods/...</font>
            </p>
            ''')
        dialog.setInputMode(QInputDialog.TextInput)
        dialog.setOption(QInputDialog.NoButtons, True)
        dialog.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)

        buttonbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dialog.layout().addWidget(buttonbox)
        buttonbox.accepted.connect(dialog.accept)
        buttonbox.rejected.connect(dialog.reject)
        ok = buttonbox.button(QDialogButtonBox.Ok)
        ok.setDisabled(True)
        dialog.textValueChanged.connect(lambda x: ok.setDisabled(not isValidNexusModsUrl(x)))

        result = dialog.exec_()
        if not result:
            return
        # TODO: incomplete: show file selection etc.

    def showSettingsDialog(self, firstStart=False):
        settingswindow = SettingsWindow(self, firstStart)
        settingswindow.setAttribute(Qt.WA_DeleteOnClose)
        return settingswindow.exec_()

    def showAboutDialog(self):
        messagebox = QMessageBox(self)
        messagebox.setWindowTitle('About' if self else getTitleString('About'))
        messagebox.setText(f'''
            <p style="margin:0 15px 0 0;">
            <b>{w3modmanager.TITLE} {w3modmanager.VERSION}</b><br>
            {w3modmanager.SUBTITLE}<br>
            <br>
            For updates and information visit <br>
            <a href="{w3modmanager.URL_WEB}" style="text-decoration:none;">\
                {removeUrlScheme(w3modmanager.URL_WEB)}\
            </a><br>
            <br>
            Thank you for using {w3modmanager.TITLE}!
            </p>
            ''')
        # TODO: enhancement: check if new version is available
        messagebox.setTextFormat(Qt.RichText)
        messagebox.setIconPixmap(
            messagebox.windowIcon().pixmap(messagebox.windowIcon().actualSize(QSize(64, 64)))
        )
        messagebox.setMinimumSize(QSize(500, 500))
        messagebox.setStandardButtons(QMessageBox.Ok)
        messagebox.setAttribute(Qt.WA_DeleteOnClose)
        return messagebox.exec_()

    def showInvalidConfigDialog(self):
        messagebox = QMessageBox(self)
        messagebox.setWindowTitle('Invalid game path' if self else getTitleString('Invalid game path'))
        messagebox.setText(f'''
            <p style="margin:10px 15px 10px 5px;"><b>Invalid game or config path.</b><br>
                Please restart w3modmanager and enter the locations of witcher3.exe<br>
                and the game config folder (usually <code>User/Documents/The Witcher 3</code>).
            </p>
            <p style="margin:10px 15px 10px 5px;"><small>
                For updates and information visit <br>
                <a href="{w3modmanager.URL_WEB}" style="text-decoration:none;">\
                    {removeUrlScheme(w3modmanager.URL_WEB)}\
                </a>
            </small></p>
            ''')
        messagebox.setTextFormat(Qt.RichText)
        messagebox.setIconPixmap(
            messagebox.windowIcon().pixmap(messagebox.windowIcon().actualSize(QSize(64, 64)))
        )
        messagebox.setStandardButtons(QMessageBox.Ok)
        messagebox.setAttribute(Qt.WA_DeleteOnClose)
        return messagebox.exec_()

    def showInvalidPermissionsDialog(self, path: Path):
        messagebox = QMessageBox(self)
        messagebox.setWindowTitle('Invalid permissions' if self else getTitleString('Invalid permissions'))
        messagebox.setText(f'''
            <p style="margin:10px 15px 10px 5px;">
                <b>Invalid permissions for directory:</b>
            </p>
            <p style="margin:10px 15px 10px 5px;">
                <code>{path}</code>
            </p>
            <p style="margin:10px 15px 10px 5px;">
                Write permissions to this directory are required for mod management.<br>
                Automatically set the correct permissions?
            </p>
        ''')
        messagebox.setTextFormat(Qt.RichText)
        messagebox.setIconPixmap(
            messagebox.windowIcon().pixmap(messagebox.windowIcon().actualSize(QSize(64, 64)))
        )
        messagebox.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        return messagebox.exec_() == QMessageBox.Yes

    def showInvalidPermissionsErrorDialog(self):
        messagebox = QMessageBox(self)
        messagebox.setWindowTitle('Invalid permissions' if self else getTitleString('Invalid permissions'))
        messagebox.setText(f'''
            <p style="margin:10px 15px 10px 5px;">
                <b>Invalid permissions for the game directory.</b>
            </p>
            <p style="margin:10px 15px 10px 5px;">
                Please restart w3modmanager to try to automatically fix the permissions,
                or fix the permissions manually.
            </p>
        ''')
        messagebox.setTextFormat(Qt.RichText)
        messagebox.setIconPixmap(
            messagebox.windowIcon().pixmap(messagebox.windowIcon().actualSize(QSize(64, 64)))
        )
        messagebox.setStandardButtons(QMessageBox.Ok)
        return messagebox.exec_()

    def showCritcalErrorDialog(self, error: str):
        import traceback
        messagebox = QMessageBox(self)
        messagebox.setWindowTitle('Critical Error' if self else getTitleString('Critical Error'))
        messagebox.setText(f'''
            <p><strong>\
                Something unexpected happened. {'Detailed error message:' if error else ''}\
            </strong></p>
            {f'<p><code>{error}</code></p>' if error else ''}
            <p><small>
                Please check if this is a known issue or create a report \
                detailing the conditions of this error here:<br>
                <a href="{w3modmanager.URL_ISSUES}" style="text-decoration:none;">
                    {removeUrlScheme(w3modmanager.URL_ISSUES)}
                </a>
            </small></p>
            ''')
        if error:
            messagebox.setDetailedText(traceback.format_exc())
        messagebox.setIconPixmap(
            messagebox.windowIcon().pixmap(messagebox.windowIcon().actualSize(QSize(64, 64)))
        )
        messagebox.exec_()
