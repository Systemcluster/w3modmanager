import w3modmanager

from w3modmanager.core.model import Model
from w3modmanager.domain.bin.merger import verifyScriptMergerPath
from w3modmanager.domain.mod.fetcher import *
from w3modmanager.ui.graphical.downloadwindow import DownloadWindow
from w3modmanager.ui.graphical.mainwidget import MainWidget
from w3modmanager.ui.graphical.settingswindow import SettingsWindow
from w3modmanager.util.util import *

from typing import Any

from PySide6.QtCore import QSettings, QSize, Qt, QUrl
from PySide6.QtGui import QBrush, QCloseEvent, QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMenu, QMenuBar, QMessageBox


class MainWindow(QMainWindow):
    def __init__(self, model: Model) -> None:
        super().__init__()

        self.model = model
        self.tasks: set[asyncio.Task[Any]] = set()

        self.setWindowTitle(getTitleString('Mod Manager'))
        self.setMinimumSize(QSize(750, 500))
        self.setupMenu()

        settings = QSettings()
        if settings.value('mainWindowGeometry'):
            self.restoreGeometry(settings.value('mainWindowGeometry'))  # type: ignore
        if settings.value('mainWindowState'):
            self.restoreState(settings.value('mainWindowState'))  # type: ignore

        # TODO: enhancement: add an url handler for 'nxm://' urls
        # see https://docs.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/platform-apis/aa767914(v=vs.85)  # noqa

        # TODO: enhancement: import settings from the witcher 3 mod manager

        QApplication.clipboard().dataChanged.connect(self.copyBufferChangedEvent)

        self.mainwidget = MainWidget(self, model)
        self.setCentralWidget(self.mainwidget)
        self.show()
        self.raise_()
        self.activateWindow()

    def copyBufferChangedEvent(self) -> None:
        if QSettings().value('nexusCheckClipboard', 'False') == 'True':
            clipboard = QApplication.clipboard().text().splitlines()
            if len(clipboard) == 1 and isValidNexusModsUrl(clipboard[0]):
                # TODO: enhancement: only allow one download window at once
                self.show()
                self.setWindowState(Qt.WindowState.WindowActive)
                self.activateWindow()
                self.showDownloadModDialog()

    def closeEvent(self, event: QCloseEvent) -> None:
        settings = QSettings()
        settings.setValue('mainWindowGeometry', self.saveGeometry())
        settings.setValue('mainWindowState', self.saveState())

    def setupMenu(self) -> None:
        self.setMenuBar(QMenuBar(self))
        settings = QSettings()

        # mods menu

        menuMods: QMenu = self.menuBar().addMenu('&Mods')
        menuMods.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        menuMods.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        downIcon = QIcon(str(getRuntimePath('resources/icons/down.ico')))
        gearIcon = QIcon(str(getRuntimePath('resources/icons/gear.ico')))
        dirsIcon = QIcon(str(getRuntimePath('resources/icons/open-folder.ico')))
        colrIcon = QIcon(str(getRuntimePath('resources/icons/color-circle.ico')))
        smilIcon = QIcon(str(getRuntimePath('resources/icons/smile.ico')))

        actionAddModFromFile = menuMods.addAction('&Add Mods')
        actionAddModFromFile.triggered.connect(self.showAddModFromFileDialog)
        actionAddModFromFolder = menuMods.addAction('Add u&npacked Mod')
        actionAddModFromFolder.triggered.connect(self.showAddModFromFolderDialog)
        actionDownloadMod = menuMods.addAction('&Download Mod')
        actionDownloadMod.setIcon(downIcon)
        actionDownloadMod.triggered.connect(self.showDownloadModDialog)

        menuMods.addSeparator()
        actionGetInfo = menuMods.addAction('Update Mod de&tails')
        actionGetInfo.setIcon(downIcon)
        actionGetInfo.triggered.connect(self.showGetInfoDialog)
        actionGetUpdates = menuMods.addAction('Check for Mod &updates')
        actionGetUpdates.setIcon(downIcon)
        actionGetUpdates.triggered.connect(self.showGetUpdatesDialog)

        menuMods.addSeparator()
        actionExport = menuMods.addAction('&Export Modlist')
        actionExport.triggered.connect(self.showExportDialog)

        menuMods.aboutToShow.connect(lambda: [
            actionDownloadMod.setDisabled(not str(settings.value('nexusAPIKey'))),
            actionGetInfo.setDisabled(
                not str(settings.value('nexusAPIKey')) or \
                not len(self.model) or \
                not self.mainwidget.modlist.selectionModel().hasSelection()),
            actionGetUpdates.setDisabled(
                not str(settings.value('nexusAPIKey')) or \
                not len(self.model) or \
                not self.mainwidget.modlist.selectionModel().hasSelection()),
            actionExport.setDisabled(not len(self.model))
        ])

        # view menu

        menuView: QMenu = self.menuBar().addMenu('&View')
        menuView.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        menuView.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        showSummary = menuView.addAction('Show &Summary')
        showSummary.setCheckable(True)
        showSummary.setChecked(settings.value('showSummary', 'True') == 'True')
        showSummary.triggered.connect(lambda checked: [
            settings.setValue('showSummary', str(checked)),
            self.mainwidget.summary.setVisible(checked)
        ])
        menuView.addSeparator()

        toggleHighlightNewest = menuView.addAction('Highlight &Newest')
        toggleHighlightNewest.setCheckable(True)
        toggleHighlightNewest.setChecked(settings.value('highlightNewest', 'True') == 'True')
        toggleHighlightNewest.triggered.connect(lambda checked: [
            settings.setValue('highlightNewest', str(checked)),
            self.model.updateCallbacks.fire(self.model)
        ])
        iconHighlightNewest = QPixmap(256, 256)
        iconHighlightNewest.fill(Qt.GlobalColor.transparent)
        painter = QPainter(iconHighlightNewest)
        painter.setBrush(QBrush(QColor(222, 255, 222)))
        painter.drawEllipse(10, 10, 236, 236)
        toggleHighlightNewest.setIcon(QIcon(iconHighlightNewest))
        painter.end()

        toggleHighlightRecent = menuView.addAction('Highlight &Recent')
        toggleHighlightRecent.setCheckable(True)
        toggleHighlightRecent.setChecked(settings.value('highlightRecent', 'True') == 'True')
        toggleHighlightRecent.triggered.connect(lambda checked: [
            settings.setValue('highlightRecent', str(checked)),
            self.model.updateCallbacks.fire(self.model)
        ])
        iconHighlightRecent = QPixmap(256, 256)
        iconHighlightRecent.fill(Qt.GlobalColor.transparent)
        painter = QPainter(iconHighlightRecent)
        painter.setBrush(QBrush(QColor(222, 226, 255)))
        painter.drawEllipse(10, 10, 236, 236)
        toggleHighlightRecent.setIcon(QIcon(iconHighlightRecent))
        painter.end()

        toggleHighlightUnmanaged = menuView.addAction('Highlight &Unmanaged')
        toggleHighlightUnmanaged.setCheckable(True)
        toggleHighlightUnmanaged.setChecked(settings.value('highlightUnmanaged', 'True') == 'True')
        toggleHighlightUnmanaged.triggered.connect(lambda checked: [
            settings.setValue('highlightUnmanaged', str(checked)),
            self.model.updateCallbacks.fire(self.model)
        ])
        iconHighlightUnmanaged = QPixmap(256, 256)
        iconHighlightUnmanaged.fill(Qt.GlobalColor.transparent)
        painter = QPainter(iconHighlightUnmanaged)
        painter.setBrush(QBrush(QColor(250, 220, 220)))
        painter.drawEllipse(10, 10, 236, 236)
        toggleHighlightUnmanaged.setIcon(QIcon(iconHighlightUnmanaged))
        painter.end()

        toggleHighlightDisabled = menuView.addAction('Highlight &Disabled')
        toggleHighlightDisabled.setCheckable(True)
        toggleHighlightDisabled.setChecked(settings.value('highlightDisabled', 'True') == 'True')
        toggleHighlightDisabled.triggered.connect(lambda checked: [
            settings.setValue('highlightDisabled', str(checked)),
            self.model.updateCallbacks.fire(self.model)
        ])
        iconHighlightDisabled = QPixmap(256, 256)
        iconHighlightDisabled.fill(Qt.GlobalColor.transparent)
        painter = QPainter(iconHighlightDisabled)
        painter.setBrush(QBrush(QColor(230, 230, 230)))
        painter.drawEllipse(10, 10, 236, 236)
        toggleHighlightDisabled.setIcon(QIcon(iconHighlightDisabled))
        painter.end()

        menuView.addSeparator()
        toggleColors = menuView.addAction('&Colored Icons')
        toggleColors.setCheckable(True)
        toggleColors.setChecked(settings.value('iconColors', 'True') == 'True')
        toggleColors.triggered.connect(lambda checked: [
            settings.setValue('iconColors', str(checked)),
            self.mainwidget.modlist.listmodel.setIcons(),
            self.model.updateCallbacks.fire(self.model)
        ])
        toggleColors.setIcon(colrIcon)

        menuView.addSeparator()
        toggleCompact = menuView.addAction('Compact &Mode')
        toggleCompact.setCheckable(True)
        toggleCompact.setChecked(settings.value('compactMode', 'False') == 'True')
        toggleCompact.triggered.connect(lambda checked: [
            settings.setValue('compactMode', str(checked)),
            self.mainwidget.modlist.setSectionSize(checked)
        ])

        # settings menu

        menuSettings: QMenu = self.menuBar().addMenu('&Tools')
        menuSettings.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        menuSettings.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        actionSettings = menuSettings.addAction('&Settings')
        actionSettings.setIcon(gearIcon)
        actionSettings.triggered.connect(self.showSettingsDialog)

        menuSettings.addSeparator()
        actionOpenGameDirectory = menuSettings.addAction('Open &Game directory')
        actionOpenGameDirectory.setIcon(dirsIcon)
        actionOpenGameDirectory.triggered.connect(lambda: util.openDirectory(self.model.gamepath))
        actionOpenConfigDirectory = menuSettings.addAction('Open &Config directory')
        actionOpenConfigDirectory.setIcon(dirsIcon)
        actionOpenConfigDirectory.triggered.connect(lambda: util.openDirectory(self.model.configpath))

        # info menu

        menuInfo: QMenu = self.menuBar().addMenu('&Info')
        menuInfo.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        menuInfo.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        actionFeedback = menuInfo.addAction('Send &Feedback')
        actionFeedback.setIcon(smilIcon)
        actionFeedback.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(w3modmanager.URL_ISSUES)))
        menuInfo.addSeparator()
        actionAbout = menuInfo.addAction('&About')
        actionAbout.setIcon(QIcon.fromTheme('document-open'))
        actionAbout.triggered.connect(self.showAboutDialog)

    def showExportDialog(self) -> None:
        # TODO: incomplete: implement modlist export
        pass

    def showGetInfoDialog(self) -> None:
        if QMessageBox.question(
                self,
                'Update Mod details' if self else getTitleString('Update Mod details'),
                f'''
                    <p>Update details of the selected mod(s) with information from Nexus Mods?</p>
                    <p>This will replace existing details.</p>
                ''',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel) == QMessageBox.StandardButton.Yes:
            createAsyncTask(self.mainwidget.modlist.updateSelectedModsDetails(), self.tasks)

    def showGetUpdatesDialog(self) -> None:
        # TODO: incomplete: implement mod update download
        pass

    def showAddModFromFolderDialog(self) -> QFileDialog:
        dialog: QFileDialog = QFileDialog(self, 'Select Mod to install')
        dialog.setOptions(QFileDialog.Option.ReadOnly)
        dialog.setFileMode(QFileDialog.FileMode.Directory)

        dialog.setModal(True)
        dialog.open()
        dialog.accepted.connect(lambda: createAsyncTask(
            self.mainwidget.modlist.checkInstallFromURLs(dialog.selectedUrls()),
            self.tasks
        ))
        return dialog

    def showAddModFromFileDialog(self) -> QFileDialog:
        extensions = ' '.join(f'*{e}' for e in util.getSupportedExtensions())
        dialog: QFileDialog = QFileDialog(self, 'Select Mod(s) to install', '', f'Archives ({extensions})')
        dialog.setOptions(QFileDialog.Option.ReadOnly)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)

        dialog.setModal(True)
        dialog.open()
        dialog.accepted.connect(lambda: createAsyncTask(
            self.mainwidget.modlist.checkInstallFromURLs(dialog.selectedUrls()),
            self.tasks
        ))
        return dialog

    def showDownloadModDialog(self) -> DownloadWindow:
        clipboard = QApplication.clipboard().text().splitlines()
        if len(clipboard) == 1 and isValidNexusModsUrl(clipboard[0]):
            url = clipboard[0]
        else:
            url = ''
        dialog = DownloadWindow(self, url)
        dialog.setModal(True)
        dialog.open()
        dialog.signals.download.connect(lambda urls: createAsyncTask(
            self.mainwidget.modlist.checkInstallFromURLs(urls, local=False), self.tasks
        ))
        return dialog

    def showSettingsDialog(self: Any, firstStart: bool = False) -> SettingsWindow:
        settings = QSettings()

        settingswindow = SettingsWindow(self, firstStart)
        settingswindow.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        settingswindow.setModal(True)
        settingswindow.open()
        settingswindow.finished.connect(lambda: [
            self.model.setPaths(
                Path(str(settings.value('gamePath'))),
                Path(str(settings.value('configPath')))
            ),
            self.mainwidget.startscriptmerger.setEnabled(
                verifyScriptMergerPath(Path(str(settings.value('scriptMergerPath')))) is not None
            )
        ])
        return settingswindow

    def showAboutDialog(self: Any) -> QMessageBox:
        messagebox = QMessageBox(self)
        messagebox.setWindowTitle('About' if self else getTitleString('About'))
        messagebox.setText(f'''
            <p style="margin:0 15px 0 0;">
            <b>{w3modmanager.TITLE} {w3modmanager.VERSION}</b>
            <small>{f'({w3modmanager.VERSION_HASH})' if w3modmanager.VERSION_HASH else ''}</small><br>
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
        messagebox.setTextFormat(Qt.TextFormat.RichText)
        messagebox.setIconPixmap(
            messagebox.windowIcon().pixmap(messagebox.windowIcon().actualSize(QSize(64, 64)))
        )
        messagebox.setMinimumSize(QSize(500, 500))
        messagebox.setStandardButtons(QMessageBox.StandardButton.Ok)
        messagebox.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        messagebox.layout().setContentsMargins(5, 5, 5, 5)

        messagebox.setModal(True)
        messagebox.open()
        return messagebox

    def showInvalidConfigErrorDialog(self: Any) -> QMessageBox:
        messagebox = QMessageBox(self)
        messagebox.setWindowTitle('Invalid game path' if self else getTitleString('Invalid game path'))
        messagebox.setText(f'''
            <p style="margin:10px 15px 10px 5px;"><b>Invalid game or config path.</b><br>
                Please restart w3modmanager and enter the paths of<br>
                your The Witcher 3 installation and the game config folder<br>
                (usually <code>User/Documents/The Witcher 3</code>).
            </p>
            <p style="margin:10px 15px 10px 5px;"><small>
                For updates and information visit <br>
                <a href="{w3modmanager.URL_WEB}" style="text-decoration:none;">\
                    {removeUrlScheme(w3modmanager.URL_WEB)}\
                </a>
            </small></p>
            ''')
        messagebox.setTextFormat(Qt.TextFormat.RichText)
        messagebox.setIconPixmap(
            messagebox.windowIcon().pixmap(messagebox.windowIcon().actualSize(QSize(64, 64)))
        )
        messagebox.setStandardButtons(QMessageBox.StandardButton.Ok)
        messagebox.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        messagebox.layout().setContentsMargins(5, 5, 5, 5)

        messagebox.setModal(True)
        messagebox.open()
        return messagebox

    def showInvalidPermissionsDialog(self: Any, path: Path) -> QMessageBox:
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
        messagebox.setTextFormat(Qt.TextFormat.RichText)
        messagebox.setIconPixmap(
            messagebox.windowIcon().pixmap(messagebox.windowIcon().actualSize(QSize(64, 64)))
        )
        messagebox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        messagebox.layout().setContentsMargins(5, 5, 5, 5)

        messagebox.setModal(True)
        messagebox.open()
        return messagebox

    def showInvalidPermissionsErrorDialog(self: Any) -> QMessageBox:
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
        messagebox.setTextFormat(Qt.TextFormat.RichText)
        messagebox.setIconPixmap(
            messagebox.windowIcon().pixmap(messagebox.windowIcon().actualSize(QSize(64, 64)))
        )
        messagebox.setStandardButtons(QMessageBox.StandardButton.Ok)
        messagebox.layout().setContentsMargins(5, 5, 5, 5)

        messagebox.setModal(True)
        messagebox.open()
        return messagebox

    def showOtherInstanceDialog(self: Any) -> QMessageBox:
        messagebox = QMessageBox(self)
        messagebox.setWindowTitle('Other instance' if self else getTitleString('Other instance'))
        messagebox.setText(f'''
            <p style="margin:10px 15px 10px 5px;">
                <b>Another instance of the application is currently running.</b>
            </p>
            <p style="margin:10px 15px 10px 5px;">
                Only one instance should be opened at the same time<br>
                to prevent data corruption.
            </p>
            <p style="margin:10px 15px 10px 5px;">
                Continue anyway?
            </p>
        ''')
        messagebox.setTextFormat(Qt.TextFormat.RichText)
        messagebox.setIconPixmap(
            messagebox.windowIcon().pixmap(messagebox.windowIcon().actualSize(QSize(64, 64)))
        )
        messagebox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        messagebox.setDefaultButton(QMessageBox.StandardButton.Cancel)
        messagebox.layout().setContentsMargins(5, 5, 5, 5)

        messagebox.setModal(True)
        messagebox.open()
        return messagebox

    def showCritcalErrorDialog(self: Any, error: str = '', details: str = '') -> QMessageBox:
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
            messagebox.setDetailedText(details if details else traceback.format_exc())
        messagebox.setIconPixmap(
            messagebox.windowIcon().pixmap(messagebox.windowIcon().actualSize(QSize(64, 64)))
        )
        messagebox.layout().setContentsMargins(5, 5, 5, 5)

        messagebox.setModal(True)
        messagebox.open()
        return messagebox
