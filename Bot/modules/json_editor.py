# modules/json_editor.py

import re
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, 
                             QPushButton, QLabel, QComboBox, QTabWidget, QSplitter,
                             QMessageBox, QToolBar, QStatusBar, QMenu, QTreeWidget,
                             QTreeWidgetItem, QLineEdit, QFileDialog, QFrame
                             )
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QSize
from PySide6.QtGui import (QTextCharFormat, QSyntaxHighlighter, QFont, QColor, 
                          QAction, QKeySequence, QShortcut)

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class JsonSyntaxHighlighter(QSyntaxHighlighter):
    """Syntaxmarkering för JSON med stöd för JSONL-format"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Formatdefinitioner
        self.formats = {
            'key': self._create_format(QColor("#C2185B")),     # Nycklar i mörkt rosa
            'string': self._create_format(QColor("#2E7D32")),  # Strängar i grönt
            'number': self._create_format(QColor("#1976D2")),  # Nummer i blått
            'boolean': self._create_format(QColor("#E64A19")), # Boolean i orange
            'null': self._create_format(QColor("#757575")),    # Null i grått
            'error': self._create_format(QColor("#D32F2F"), background=QColor("#FFEBEE")) # Fel i rött
        }
        
        # Regler för syntaxmarkering
        self.rules = [
            # Nycklar
            (r'"[^"]*"\s*:', self.formats['key']),
            # Strängar
            (r':\s*"[^"]*"', self.formats['string']),
            # Nummer
            (r':\s*-?\d+\.?\d*', self.formats['number']),
            # Boolean
            (r':\s*(true|false)', self.formats['boolean']),
            # Null
            (r':\s*null', self.formats['null'])
        ]
    
    def _create_format(self, color, background=None):
        """Skapa ett textformat med given färg"""
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        if background:
            fmt.setBackground(background)
        return fmt
    
    def highlightBlock(self, text: str):
        """Markera ett textblock med JSON-syntax"""
        for pattern, format in self.rules:
            for match in re.finditer(pattern, text):
                # För strängar, markera bara värdet
                if format == self.formats['string']:
                    # Hitta start av strängvärdet
                    start = match.group().find('"', match.group().find(':'))
                    if start != -1:
                        self.setFormat(match.start() + start, 
                                     len(match.group()) - start, format)
                # För andra typer, markera hela matchningen
                else:
                    self.setFormat(match.start(), len(match.group()), format)

class JsonlPreview(QPlainTextEdit):
    """Widget för att visa formaterad JSONL-data"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setup_ui()
    
    def setup_ui(self):
        """Konfigurera utseende"""
        # Använd monospace font för bättre läsbarhet
        font = QFont("Consolas", 10)
        self.setFont(font)
        
        # Aktivera syntaxmarkering
        self.highlighter = JsonSyntaxHighlighter(self.document())
        
        # Konfigurera visning
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(40)  # 40 pixlar per tab

class JsonEditor(QWidget):
    """
    Avancerad JSON-editor med stöd för:
    - JSONL-format
    - Syntaxmarkering
    - Live validering
    - Formattering
    - Sökfunktion
    """
    
    # Signaler
    data_changed = Signal(str, str)  # fil_id, ny_data
    validation_error = Signal(str)    # felmeddelande
    preview_updated = Signal(str, dict)  # preview_type, preview_data
    
    def __init__(self, config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.config = config
        
        # Intern state
        self.current_file = None
        self.is_modified = False
        self.validation_timer = QTimer()
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self.validate_current)
        
        # Initiera UI
        self.init_ui()
        self.setup_shortcuts()
    
    def init_ui(self):
        """Initiera användargränssnittet"""
        layout = QVBoxLayout(self)
        
        # Skapa toolbar
        toolbar = QToolBar()
        layout.addWidget(toolbar)
        
        # Lägg till verktygsåtgärder
        self.create_actions()
        
        # Lägg till actions i toolbar
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.save_action)
        toolbar.addSeparator()
        toolbar.addAction(self.format_action)
        toolbar.addAction(self.validate_action)
        toolbar.addSeparator()
        toolbar.addAction(self.find_action)
        
        # Split view between editor and preview
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Left side: Editor
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        
        # Editor with syntax highlighting
        self.editor = QPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.editor.textChanged.connect(self.on_text_changed)
        
        # Set font and syntax highlighter
        font = QFont("Consolas", 10)
        self.editor.setFont(font)
        self.highlighter = JsonSyntaxHighlighter(self.editor.document())
        
        editor_layout.addWidget(self.editor)
        splitter.addWidget(editor_widget)
        
        # Right side: Preview
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        
        # Preview title
        preview_label = QLabel("Formatted Preview")
        preview_layout.addWidget(preview_label)
        
        # Preview with syntax highlighting
        self.preview = JsonlPreview()
        preview_layout.addWidget(self.preview)
        
        splitter.addWidget(preview_widget)
        
        # Set equal sizes for editor and preview
        splitter.setSizes([int(self.width() * 0.5), int(self.width() * 0.5)])
        
        # Statusrad
        self.status_bar = QStatusBar()
        layout.addWidget(self.status_bar)
        
        # Sökwidget (gömd som standard)
        self.search_widget = QWidget()
        search_layout = QHBoxLayout(self.search_widget)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Sök...")
        self.search_input.textChanged.connect(self.search_text)
        search_layout.addWidget(self.search_input)
        
        self.search_next = QPushButton("Nästa")
        self.search_next.clicked.connect(self.find_next)
        search_layout.addWidget(self.search_next)
        
        self.search_prev = QPushButton("Föregående")
        self.search_prev.clicked.connect(self.find_previous)
        search_layout.addWidget(self.search_prev)
        
        self.close_search = QPushButton("✕")
        self.close_search.clicked.connect(self.hide_search)
        search_layout.addWidget(self.close_search)
        
        self.search_widget.hide()
        layout.addWidget(self.search_widget)
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Save
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.save_current_file)
        
        # Find
        find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        find_shortcut.activated.connect(self.show_search)
        
        # Format
        format_shortcut = QShortcut(QKeySequence("Ctrl+Shift+F"), self)
        format_shortcut.activated.connect(self.format_json)
    
    def create_actions(self):
        """Skapa actions för toolbar"""
        # Öppna fil
        self.open_action = QAction("Öppna", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_file)
        
        # Spara fil
        self.save_action = QAction("Spara", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_current_file)
        
        # Formattera
        self.format_action = QAction("Formattera", self)
        self.format_action.setShortcut("Ctrl+Shift+F")
        self.format_action.triggered.connect(self.format_json)
        
        # Validera
        self.validate_action = QAction("Validera", self)
        self.validate_action.setShortcut("Ctrl+Shift+V")
        self.validate_action.triggered.connect(self.validate_current)
        
        # Sök
        self.find_action = QAction("Sök", self)
        self.find_action.setShortcut("Ctrl+F")
        self.find_action.triggered.connect(self.show_search)
    
    def load_product(self, product_id: str):
        """Load a product's JSONL files for editing"""
        try:
            # Build path to product directory
            product_dir = Path(self.config.get("integrated_data_dir", "./nlp_bot_engine/data/integrated_data")) / "products" / product_id
            
            # Find the latest modified JSONL file for this product
            jsonl_files = list(product_dir.glob("*.jsonl"))
            if not jsonl_files:
                self.status_bar.showMessage(f"No JSONL files found for product {product_id}", 5000)
                return
            
            # Sort by modification time to get the latest
            latest_file = max(jsonl_files, key=lambda p: p.stat().st_mtime)
            
            # Load the file content
            with open(latest_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update editor content
            self.editor.setPlainText(content)
            self.current_file = latest_file
            
            # Update status
            self.status_bar.showMessage(f"Loaded {latest_file.name}", 3000)
            self.is_modified = False
            
            # Update preview
            self.update_preview()
            
        except Exception as e:
            self.status_bar.showMessage(f"Error loading product {product_id}: {str(e)}", 5000)
            logger.error(f"Error loading product {product_id}: {str(e)}")
    
    def open_file(self, file_path: Optional[Path] = None):
        """Öppna en JSONL-fil för redigering"""
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Öppna JSONL-fil", 
                str(self.config.get("integrated_data_dir", ".")),
                "JSONL-filer (*.jsonl);;Alla filer (*.*)"
            )
            if not file_path:
                return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.current_file = Path(file_path)
            self.editor.setPlainText(content)
            self.update_preview()
            self.is_modified = False
            self.status_bar.showMessage(f"Öppnade {self.current_file.name}")
            
        except Exception as e:
            QMessageBox.warning(self, "Fel", f"Kunde inte öppna fil: {str(e)}")
    
    def save_current_file(self):
        """Save current file if it exists"""
        try:
            if self.current_file and self.is_modified:
                with open(self.current_file, 'w', encoding='utf-8') as f:
                    f.write(self.editor.toPlainText())
                self.is_modified = False
                self.status_bar.showMessage(f"Saved {self.current_file.name}", 3000)
                return True
            return False
        except Exception as e:
            self.status_bar.showMessage(f"Error saving file: {str(e)}", 5000)
            return False
    
    def format_json(self):
        """Formattera JSON/JSONL för bättre läsbarhet"""
        try:
            text = self.editor.toPlainText()
            formatted_lines = []
            
            for line in text.splitlines():
                if line.strip():
                    # Parse och formattera varje JSON-objekt
                    data = json.loads(line)
                    formatted = json.dumps(data, ensure_ascii=False, indent=2)
                    # Konvertera till en rad
                    formatted_line = formatted.replace('\n', '')
                    formatted_lines.append(formatted_line)
            
            self.editor.setPlainText('\n'.join(formatted_lines))
            self.status_bar.showMessage("JSON formaterad")
            
        except Exception as e:
            QMessageBox.warning(self, "Fel", f"Kunde inte formattera: {str(e)}")


    def validate_current(self) -> bool:
        """Validera aktuell JSON/JSONL"""
        text = self.editor.toPlainText()
        try:
            for line in text.splitlines():
                if line.strip():
                    json.loads(line)
            self.status_bar.showMessage("Validation OK", 3000)
            return True
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON on line {e.lineno}: {e.msg}"
            self.validation_error.emit(error_msg)
            self.status_bar.showMessage("Validation failed", 5000)
            return False
        
        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            self.validation_error.emit(error_msg)
            self.status_bar.showMessage("Validation failed", 5000)
            return False

    def show_search(self):
        """Visa sökfältet"""
        self.search_widget.show()
        self.search_input.setFocus()
    
    def hide_search(self):
        """Göm sökfältet"""
        self.search_widget.hide()
        self.editor.setFocus()
    
    def search_text(self):
        """Sök efter text och markera första träffen"""
        search_text = self.search_input.text()
        if not search_text:
            return
        
        # Markera tidigare sökresultat
        cursor = self.editor.textCursor()
        cursor.clearSelection()
        self.editor.setTextCursor(cursor)
        
        # Sök från nuvarande position
        self.find_next()
    
    def find_next(self):
        """Hitta nästa träff på söktexten"""
        if not self.search_input.text():
            return
        
        found = self.editor.find(self.search_input.text())
        if not found:
            # Om vi inte hittar något, börja från början
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.Start)
            self.editor.setTextCursor(cursor)
            # Försök hitta igen från början
            found = self.editor.find(self.search_input.text())
            if found:
                self.status_bar.showMessage("Sökningen fortsätter från början", 3000)
            else:
                self.status_bar.showMessage("Ingen träff hittad", 3000)

    def find_previous(self):
        """Hitta föregående träff på söktexten"""
        if not self.search_input.text():
            return
        
        found = self.editor.find(self.search_input.text(), self.editor.FindBackward)
        if not found:
            # Om vi inte hittar något, börja från slutet
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.End)
            self.editor.setTextCursor(cursor)
            # Försök hitta igen från slutet
            found = self.editor.find(self.search_input.text(), self.editor.FindBackward)
            if found:
                self.status_bar.showMessage("Sökningen fortsätter från slutet", 3000)
            else:
                self.status_bar.showMessage("Ingen träff hittad", 3000)

    def on_text_changed(self):
        """Handle text changes in the editor"""
        # Set modified flag
        self.is_modified = True
        
        # Start validation timer to avoid validating on every keystroke
        self.validation_timer.start(1000)  # Validate after 1 second of no typing
        
        # Update preview
        self.update_preview()
        
        # Emit preview signal
        self.emit_preview()
    
    def update_preview(self):
        """Update the preview with formatted content"""
        try:
            text = self.editor.toPlainText()
            formatted_lines = []
            
            for line in text.splitlines():
                if line.strip():
                    # Parse and format each JSON object
                    try:
                        data = json.loads(line)
                        formatted = json.dumps(data, ensure_ascii=False, indent=2)
                        formatted_lines.append(formatted)
                    except json.JSONDecodeError:
                        # If line isn't valid JSON, show it as-is
                        formatted_lines.append(line)
            
            # Join formatted lines with double newlines for spacing
            preview_text = '\n\n'.join(formatted_lines)
            self.preview.setPlainText(preview_text)
            self.status_bar.showMessage("Preview updated", 3000)
            
        except Exception as e:
            self.status_bar.showMessage(f"Preview error: {str(e)}", 3000)
            logger.error(f"Error updating preview: {str(e)}")

    def emit_preview(self):
        """Emit preview data to connected viewers"""
        try:
            text = self.editor.toPlainText()
            data = []
            
            # Parse each line as JSON
            for line in text.splitlines():
                if line.strip():
                    try:
                        json_obj = json.loads(line)
                        data.append(json_obj)
                    except json.JSONDecodeError:
                        continue
            
            # Emit preview signal with parsed data
            self.preview_updated.emit("jsonl", {"content": data})
            
        except Exception as e:
            logger.error(f"Error emitting preview: {str(e)}")











