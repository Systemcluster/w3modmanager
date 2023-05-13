from w3modmanager.core.model import Model
from w3modmanager.domain.mod.mod import Mod

from dataclasses import fields

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QDialog, QFrame, QGroupBox, QScrollArea, QSizePolicy, QTextEdit, QVBoxLayout, QWidget


class DetailsWindow(QDialog):
    def __init__(self, parent: QWidget, mod: Mod, model: Model) -> None:
        super().__init__(parent,)

        self.setWindowTitle(f'Details: {mod.uploadname if mod.uploadname else mod.filename}')

        # Widgets

        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(5, 5, 5, 5)

        scrollArea = QScrollArea(self)
        scrollArea.setWidgetResizable(True)
        mainLayout.addWidget(scrollArea)

        scrollFrame = QFrame(scrollArea)
        scrollArea.setWidget(scrollFrame)

        innerLayout = QVBoxLayout(scrollFrame)
        innerLayout.setContentsMargins(0, 0, 5, 0)
        innerLayout.setSpacing(5)

        gbInfo = QGroupBox('Info')
        gbInfo.setMinimumHeight(160)
        innerLayout.addWidget(gbInfo)
        gbInfoLayout = QVBoxLayout(gbInfo)

        self.info = QTextEdit(gbInfo)
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.info.setReadOnly(True)
        self.info.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        for field in fields(mod):
            if field.name in ['files', 'contents', 'settings', 'inputs', 'bundled', 'readmes']:
                continue
            self.info.append(f'<strong>{field.name}</strong>: {getattr(mod, field.name)}')
        self.info.moveCursor(QTextCursor.MoveOperation.Start)
        self.info.verticalScrollBar().setValue(self.info.verticalScrollBar().minimum())
        self.info.setSizeAdjustPolicy(QTextEdit.SizeAdjustPolicy.AdjustToContents)
        gbInfoLayout.addWidget(self.info)

        contentFiles = mod.contentFiles
        if contentFiles:
            gbContents = QGroupBox('Content')
            gbContents.setMinimumHeight(160)
            gbContents.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
            innerLayout.addWidget(gbContents)
            gbContentsLayout = QVBoxLayout(gbContents)

            self.contents = QTextEdit(gbContents)
            self.contents.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.contents.setReadOnly(True)
            self.contents.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            for contentFile in contentFiles:
                self.contents.append(f'{contentFile.source}')
            self.contents.moveCursor(QTextCursor.MoveOperation.Start)
            self.contents.setSizeAdjustPolicy(QTextEdit.SizeAdjustPolicy.AdjustToContents)
            self.contents.verticalScrollBar().setValue(self.contents.verticalScrollBar().minimum())
            gbContentsLayout.addWidget(self.contents)

        scriptFiles = mod.scriptFiles
        if scriptFiles:
            gbScripts = QGroupBox('Scripts')
            gbScripts.setMinimumHeight(160)
            innerLayout.addWidget(gbScripts)
            innerLayout.setStretchFactor(gbScripts, 2)
            gbScriptsLayout = QVBoxLayout(gbScripts)

            self.scripts = QTextEdit(gbScripts)
            self.scripts.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.scripts.setReadOnly(True)
            self.scripts.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            conflicting = mod.filename in model.conflicts.scripts
            if conflicting:
                scriptFiles = sorted(scriptFiles, key=lambda file: file not in model.conflicts.scripts[mod.filename])
            for scriptFile in scriptFiles:
                if conflicting and scriptFile in model.conflicts.scripts[mod.filename]:
                    conflict = model.conflicts.scripts[mod.filename][scriptFile]
                    self.scripts.append(f'{scriptFile} <span style="color: #E55934;">conflicting with \
                                        <strong>{conflict}</strong></span>')
                else:
                    self.scripts.append(f'{scriptFile}')
            self.scripts.moveCursor(QTextCursor.MoveOperation.Start)
            self.scripts.setSizeAdjustPolicy(QTextEdit.SizeAdjustPolicy.AdjustToContents)
            self.scripts.verticalScrollBar().setValue(self.scripts.verticalScrollBar().minimum())
            gbScriptsLayout.addWidget(self.scripts)

        menuFiles = mod.menuFiles
        if menuFiles:
            gbMenus = QGroupBox('Menus')
            gbMenus.setMinimumHeight(160)
            innerLayout.addWidget(gbMenus)
            gbMenusLayout = QVBoxLayout(gbMenus)

            self.menus = QTextEdit(gbMenus)
            self.menus.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.menus.setReadOnly(True)
            self.menus.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            for menuFile in menuFiles:
                self.menus.append(f'{menuFile.target} <span style="color: #888">({menuFile.source})</span>')
            self.menus.moveCursor(QTextCursor.MoveOperation.Start)
            self.menus.setSizeAdjustPolicy(QTextEdit.SizeAdjustPolicy.AdjustToContents)
            self.menus.verticalScrollBar().setValue(self.menus.verticalScrollBar().minimum())
            gbMenusLayout.addWidget(self.menus)

        binFiles = mod.binFiles
        if binFiles:
            gbFiles = QGroupBox('Bins')
            gbFiles.setMinimumHeight(160)
            innerLayout.addWidget(gbFiles)
            gbFilesLayout = QVBoxLayout(gbFiles)

            self.files = QTextEdit(gbFiles)
            self.files.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.files.setReadOnly(True)
            self.files.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            for binFile in binFiles:
                self.files.append(f'{binFile.target} <span style="color: #888">({binFile.source})</span>')
            self.files.moveCursor(QTextCursor.MoveOperation.Start)
            self.files.setSizeAdjustPolicy(QTextEdit.SizeAdjustPolicy.AdjustToContents)
            self.files.verticalScrollBar().setValue(self.files.verticalScrollBar().minimum())
            gbFilesLayout.addWidget(self.files)

        settings = mod.settings
        if settings:
            gbSettings = QGroupBox('Settings')
            gbSettings.setMinimumHeight(160)
            innerLayout.addWidget(gbSettings)
            innerLayout.setStretchFactor(gbSettings, 2)
            gbSettingsLayout = QVBoxLayout(gbSettings)

            self.settings = QTextEdit(gbSettings)
            self.settings.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.settings.setReadOnly(True)
            self.settings.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            for settingLine in settings:
                self.settings.append(f'<strong>{settingLine.source}</strong>:')
                for section in settingLine.config.sections():
                    self.settings.append(f'&nbsp;&nbsp;<span style="color: #888"><strong>[{section}]</strong></span>')
                    for key, value in settingLine.config[section].items():
                        self.settings.append(f'&nbsp;&nbsp;&nbsp;&nbsp;\
                                             {key} <span style="color: #888">= {value} </span>')
            self.settings.moveCursor(QTextCursor.MoveOperation.Start)
            self.settings.setSizeAdjustPolicy(QTextEdit.SizeAdjustPolicy.AdjustToContents)
            self.settings.verticalScrollBar().setValue(self.settings.verticalScrollBar().minimum())
            gbSettingsLayout.addWidget(self.settings)

        inputs = mod.inputs
        if inputs:
            gbInputs = QGroupBox('Inputs')
            gbInputs.setMinimumHeight(160)
            innerLayout.addWidget(gbInputs)
            innerLayout.setStretchFactor(gbInputs, 2)
            gbInputsLayout = QVBoxLayout(gbInputs)

            self.inputs = QTextEdit(gbInputs)
            self.inputs.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.inputs.setReadOnly(True)
            self.inputs.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            for inputLine in inputs:
                self.inputs.append(f'<strong>{inputLine.source}</strong>:')
                for section in inputLine.config.sections():
                    self.inputs.append(f'&nbsp;&nbsp;<span style="color: #888"><strong>[{section}]</strong></span>')
                    for key, value in inputLine.config[section].items():
                        self.inputs.append(f'&nbsp;&nbsp;&nbsp;&nbsp;\
                                             {key} <span style="color: #888">= {value} </span>')
            self.inputs.moveCursor(QTextCursor.MoveOperation.Start)
            self.inputs.setSizeAdjustPolicy(QTextEdit.SizeAdjustPolicy.AdjustToContents)
            self.inputs.verticalScrollBar().setValue(self.inputs.verticalScrollBar().minimum())
            gbInputsLayout.addWidget(self.inputs)

        bundled = mod.bundledFiles
        if bundled:
            gbBundled = QGroupBox('Bundled')
            gbBundled.setMinimumHeight(160)
            innerLayout.addWidget(gbBundled)
            innerLayout.setStretchFactor(gbBundled, 2)
            gbBundledLayout = QVBoxLayout(gbBundled)

            self.bundled = QTextEdit(gbBundled)
            self.bundled.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.bundled.setReadOnly(True)
            self.bundled.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            conflicting = mod.filename in model.conflicts.bundled
            if conflicting:
                bundled = sorted(bundled, key=lambda file: file not in model.conflicts.bundled[mod.filename])
            for bundledFile in bundled:
                if conflicting and bundledFile in model.conflicts.bundled[mod.filename]:
                    conflict = model.conflicts.bundled[mod.filename][bundledFile]
                    self.bundled.append(f'<span style="color: #888">{bundledFile.source}:</span> {bundledFile.bundled}\
                        </span> <span style="color: #b08968;">overridden by <strong>{conflict}</strong></span>')
                else:
                    self.bundled.append(f'<span style="color: #888">{bundledFile.source}:</span> \
                        <span>{bundledFile.bundled}</span>')
            self.bundled.moveCursor(QTextCursor.MoveOperation.Start)
            self.bundled.setSizeAdjustPolicy(QTextEdit.SizeAdjustPolicy.AdjustToContents)
            self.bundled.verticalScrollBar().setValue(self.bundled.verticalScrollBar().minimum())
            gbBundledLayout.addWidget(self.bundled)

        readmes = mod.readmeFiles
        if readmes:
            gbReadmes = QGroupBox('Readmes')
            gbReadmes.setMinimumHeight(160)
            innerLayout.addWidget(gbReadmes)
            innerLayout.setStretchFactor(gbReadmes, 2)
            gbReadmesLayout = QVBoxLayout(gbReadmes)

            self.readmes = QTextEdit(gbReadmes)
            self.readmes.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            self.readmes.setReadOnly(True)
            self.readmes.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            for readmeFile in readmes:
                self.readmes.append(f'<p><pre>{readmeFile.content}</pre></p>')
            self.readmes.moveCursor(QTextCursor.MoveOperation.Start)
            self.readmes.setSizeAdjustPolicy(QTextEdit.SizeAdjustPolicy.AdjustToContents)
            self.readmes.verticalScrollBar().setValue(self.readmes.verticalScrollBar().minimum())
            gbReadmesLayout.addWidget(self.readmes)

        # Setup

        self.setMinimumSize(QSize(800, 600))
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.resize(QSize(1000, 800))

        self.setStyleSheet('''
            QScrollArea {border: none; background: transparent;}
            QFrame {border: none; background: transparent;}
        ''')
