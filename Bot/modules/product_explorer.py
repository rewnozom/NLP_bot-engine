# modules/product_explorer.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                             QTreeWidgetItem, QLabel, QLineEdit, QPushButton,
                             QMenu, QInputDialog, QMessageBox, QTabWidget,
                             QSplitter, QFrame, QFileDialog, QSpinBox,
                             QTextEdit, QPlainTextEdit, QProgressBar, QComboBox,
                             QToolBar, QStatusBar, QHeaderView )
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtGui import QIcon, QAction, QFont, QSyntaxHighlighter, QTextCharFormat, QColor

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import shutil


# Försök importera avancerad botmotor, fallback till standard om den inte finns
try:
    from nlp_bot_engine.core.engine import AdvancedBotEngine
    NLP_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("Använder avancerad NLP-botmotor")
except ImportError:
    from .bot_engine import BotEngine
    NLP_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("NLP-botmotor inte tillgänglig, använder standardmotor")

class JsonlHighlighter(QSyntaxHighlighter):
    """Syntaxmarkering för JSONL-filer"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Definiera formateringar för olika syntaxdelar
        self.json_format = QTextCharFormat()
        self.json_format.setForeground(QColor("#2980b9"))  # Blå
        
        self.key_format = QTextCharFormat()
        self.key_format.setForeground(QColor("#c0392b"))  # Röd
        self.key_format.setFontWeight(QFont.Bold)
        
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#27ae60"))  # Grön
        
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#8e44ad"))  # Lila
        
        self.boolean_format = QTextCharFormat()
        self.boolean_format.setForeground(QColor("#d35400"))  # Orange
        self.boolean_format.setFontWeight(QFont.Bold)
        
        self.null_format = QTextCharFormat()
        self.null_format.setForeground(QColor("#7f8c8d"))  # Grå
        self.null_format.setFontWeight(QFont.Bold)
        
        self.bracket_format = QTextCharFormat()
        self.bracket_format.setForeground(QColor("#34495e"))  # Mörkgrå
        self.bracket_format.setFontWeight(QFont.Bold)

    def highlightBlock(self, text):
        """Markera JSON-syntax"""
        import re
        
        # Markera nycklar - "key":
        for match in re.finditer(r'"([^"]+)"\s*:', text):
            self.setFormat(match.start(), match.end() - match.start(), self.key_format)
        
        # Markera strängar - "value"
        for match in re.finditer(r':\s*"([^"]*)"', text):
            value_start = match.start(1) - 1
            value_len = len(match.group(1)) + 2  # +2 för citattecken
            self.setFormat(value_start, value_len, self.string_format)
        
        # Markera strängar utan föregående kolon (t.ex. i arrayer)
        for match in re.finditer(r'(?<!:)\s*"([^"]*)"', text):
            # Undvik att markera nycklar igen
            if not re.search(r'"[^"]+"\s*:', match.group(0)):
                self.setFormat(match.start(), match.end() - match.start(), self.string_format)
        
        # Markera nummer
        for match in re.finditer(r':\s*(-?\d+(?:\.\d+)?)', text):
            self.setFormat(match.start(1), match.end(1) - match.start(1), self.number_format)
        
        # Markera booleska värden
        for match in re.finditer(r':\s*(true|false)', text, re.IGNORECASE):
            self.setFormat(match.start(1), match.end(1) - match.start(1), self.boolean_format)
        
        # Markera null
        for match in re.finditer(r':\s*(null)', text, re.IGNORECASE):
            self.setFormat(match.start(1), match.end(1) - match.start(1), self.null_format)
        
        # Markera hakparenteser och klammerparenteser
        for match in re.finditer(r'[[\]{}]', text):
            self.setFormat(match.start(), 1, self.bracket_format)

class JsonlEditor(QWidget):
    """Editor för JSONL-filer med syntaxmarkering och avancerade funktioner"""
    
    data_changed = Signal(str)  # Signal när data ändras
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file = None
        self.init_ui()
        
    def init_ui(self):
        """Skapa och konfigurera användargränssnittet"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar med åtgärder
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(16, 16))
        
        # Spara-knapp
        self.save_action = QAction(QIcon.fromTheme("document-save", QIcon(":/icons/save.png")), "Spara", self)
        self.save_action.triggered.connect(self.save_data)
        self.save_action.setShortcut("Ctrl+S")
        toolbar.addAction(self.save_action)
        
        # Formattera-knapp
        self.format_action = QAction(QIcon.fromTheme("format-indent-more", QIcon(":/icons/format.png")), "Formattera", self)
        self.format_action.triggered.connect(self.format_json)
        toolbar.addAction(self.format_action)
        
        # Validera-knapp
        self.validate_action = QAction(QIcon.fromTheme("dialog-ok", QIcon(":/icons/validate.png")), "Validera", self)
        self.validate_action.triggered.connect(self.validate_json)
        toolbar.addAction(self.validate_action)
        
        # Sök-funktion
        toolbar.addSeparator()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Sök i JSON...")
        self.search_input.returnPressed.connect(self.find_text)
        toolbar.addWidget(self.search_input)
        
        self.find_next_action = QAction(QIcon.fromTheme("go-down", QIcon(":/icons/next.png")), "Nästa", self)
        self.find_next_action.triggered.connect(self.find_next)
        self.find_next_action.setShortcut("F3")
        toolbar.addAction(self.find_next_action)
        
        layout.addWidget(toolbar)
        
        # Editor med syntaxmarkering
        self.editor = QPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        
        # Använd monospace-font för bättre läsbarhet
        available_fonts = QFont().families()  # Anropa families() på en instans av QFont
        font = QFont("Consolas", 10) if "Consolas" in available_fonts else QFont("Monospace", 10)
        self.editor.setFont(font)
        
        # Aktivera radnummer och syntaxmarkering
        self.highlighter = JsonlHighlighter(self.editor.document())
        
        # Lägg till editor i layouten
        layout.addWidget(self.editor)
        
        # Statusrad med information
        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        layout.addWidget(self.status_bar)
        
        # Sätt standardmeddelande i statusraden
        self.status_bar.showMessage("Klar")
    
    def load_file(self, file_path: Path):
        """Ladda en JSONL-fil och visa i editorn"""
        try:
            self.current_file = file_path
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            self.editor.setPlainText(text)
            self.status_bar.showMessage(f"Laddade {file_path.name}")
            
            # Uppdatera fönsterrubrik med filnamn
            self.window().setWindowTitle(f"Editor - {file_path.name}")
            
        except Exception as e:
            QMessageBox.warning(self, "Fel", f"Kunde inte ladda fil: {str(e)}")
            self.status_bar.showMessage("Fel vid laddning av fil")
    
    def save_data(self):
        """Spara ändringar till fil"""
        if not self.current_file:
            self.status_bar.showMessage("Ingen fil laddad")
            return
        
        try:
            # Validera först
            if not self.validate_json():
                return
            
            # Spara till fil
            with open(self.current_file, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
                
            # Signalera att data har ändrats
            self.data_changed.emit(self.editor.toPlainText())
            self.status_bar.showMessage(f"Sparad: {self.current_file.name}")
            
        except Exception as e:
            QMessageBox.warning(self, "Fel", f"Kunde inte spara: {str(e)}")
            self.status_bar.showMessage(f"Fel vid sparning: {str(e)}")
    
    def format_json(self):
        """Formattera JSONL för bättre läsbarhet"""
        try:
            text = self.editor.toPlainText()
            formatted_lines = []
            
            # Bearbeta rad för rad
            for i, line in enumerate(text.split('\n')):
                if line.strip():
                    try:
                        # Parse och formattera varje JSON-objekt
                        data = json.loads(line)
                        # Skapa en snygg indenterad version
                        formatted = json.dumps(data, ensure_ascii=False, indent=2)
                        # Konvertera till en rad igen
                        formatted_line = json.dumps(data, ensure_ascii=False)
                        formatted_lines.append(formatted_line)
                    except json.JSONDecodeError as e:
                        # Visa exakt vilken rad som är felaktig
                        QMessageBox.warning(
                            self, 
                            "Formatteringsfel", 
                            f"Fel på rad {i+1}: {str(e)}\n\nRad: {line[:50]}..."
                        )
                        return
            
            self.editor.setPlainText('\n'.join(formatted_lines))
            self.status_bar.showMessage("JSON formaterad")
            
        except Exception as e:
            QMessageBox.warning(self, "Fel", f"Kunde inte formattera: {str(e)}")
            self.status_bar.showMessage(f"Fel vid formatering: {str(e)}")
    
    def validate_json(self) -> bool:
        """Validera JSONL-syntax, rad för rad"""
        text = self.editor.toPlainText()
        valid = True
        
        for i, line in enumerate(text.split('\n')):
            if line.strip():
                try:
                    json.loads(line)
                except json.JSONDecodeError as e:
                    QMessageBox.warning(
                        self, 
                        "Valideringsfel", 
                        f"Fel på rad {i+1}: {str(e)}\n\nRad: {line[:50]}..."
                    )
                    # Markera raden med felet
                    cursor = self.editor.textCursor()
                    cursor.movePosition(cursor.Start)
                    for _ in range(i):
                        cursor.movePosition(cursor.Down)
                    cursor.movePosition(cursor.EndOfLine, cursor.KeepAnchor)
                    self.editor.setTextCursor(cursor)
                    valid = False
                    break
        
        if valid:
            self.status_bar.showMessage("JSON validerad - OK")
        
        return valid
    
    def find_text(self):
        """Sök efter text i editorn"""
        text = self.search_input.text()
        if not text:
            return
        
        cursor = self.editor.textCursor()
        # Starta från början om vi är i slutet
        if cursor.atEnd():
            cursor.movePosition(cursor.Start)
            self.editor.setTextCursor(cursor)
        
        self.find_next()
    
    def find_next(self):
        """Hitta nästa förekomst av söktexten"""
        text = self.search_input.text()
        if not text:
            return
        
        # Sök med hänsyn till skiftläge
        options = QTextEdit.FindCaseSensitively
        found = self.editor.find(text, options)
        
        if not found:
            # Om inte hittat, börja om från början
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.Start)
            self.editor.setTextCursor(cursor)
            self.editor.find(text, options)

class ProductExplorer(QWidget):
    """
    Avancerad produktutforskare med stöd för:
    - Trädvy av produkter organiserade efter kategori
    - JSONL-redigering med syntaxmarkering
    - Förhandsgranskning av bot-svar med NLP-stöd 
    - Direktåtkomst till vanliga kommandon
    - Sökfunktion för att hitta specifika produkter
    """
    
    # Signaler för kommunikation med andra moduler
    product_selected = Signal(str, str)  # product_id, file_path
    data_modified = Signal(str, str)     # product_id, modification_type
    
    def __init__(self, config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.config = config
        
        # Grundläggande sökvägar, med stöd för både standard och NLP-struktur
        self.base_dir = Path(config.get("base_dir", "./converted_docs"))
        
        # Använd NLP-struktur om tillgänglig
        if NLP_AVAILABLE:
            # För NLP-motorn, check om vi har rätt sökvägsstruktur i config
            nlp_data_dir = Path(config.get("nlp_data_dir", "./nlp_bot_engine/data"))
            self.integrated_dir = Path(config.get("integrated_data_dir", nlp_data_dir / "integrated_data"))
        else:
            # För standardmotorn
            self.integrated_dir = Path(config.get("integrated_data_dir", "./integrated_data"))
        
        # Initiera botmotor
        self.init_bot_engine()
        
        # Initiera UI
        self.init_ui()
        
        # Ladda produktdata
        self.load_products()
    
    def init_bot_engine(self):
        """Initiera botmotor baserat på tillgänglighet"""
        try:
            if NLP_AVAILABLE:
                self.bot_engine = AdvancedBotEngine(self.config)
                logger.info("NLP-botmotor initierad i ProductExplorer")
            else:
                self.bot_engine = BotEngine(self.config)
                logger.info("Standardbotmotor initierad i ProductExplorer")
        except Exception as e:
            logger.error(f"Fel vid initiering av botmotor: {str(e)}")
            QMessageBox.warning(self, "Motorfel", f"Kunde inte initiera botmotor: {str(e)}")
    
    def init_ui(self):
        """Initiera användargränssnittet med alla komponenter"""
        # Huvudlayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Verktygsfält
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(16, 16))
        
        # Uppdatera-knapp
        refresh_action = QAction(QIcon.fromTheme("view-refresh", QIcon(":/icons/refresh.png")), "Uppdatera", self)
        refresh_action.triggered.connect(self.load_products)
        toolbar.addAction(refresh_action)
        
        # Exportera-knapp
        export_action = QAction(QIcon.fromTheme("document-save-as", QIcon(":/icons/export.png")), "Exportera", self)
        export_action.triggered.connect(self.export_data)
        toolbar.addAction(export_action)
        
        # Bot test-knapp
        test_action = QAction(QIcon.fromTheme("system-run", QIcon(":/icons/test.png")), "Testa bot", self)
        test_action.triggered.connect(self.open_bot_test)
        toolbar.addAction(test_action)
        
        layout.addWidget(toolbar)
        
        # Splitter för att dela skärmen
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Vänster panel: Produktträd
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # Sökfält med ikon
        search_layout = QHBoxLayout()
        search_icon = QLabel()
        search_icon.setPixmap(QIcon.fromTheme("system-search", QIcon(":/icons/search.png")).pixmap(16, 16))
        search_layout.addWidget(search_icon)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Sök produkter...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.filter_products)
        search_layout.addWidget(self.search_input)
        
        left_layout.addLayout(search_layout)
        
        # Produktträd med förbättrad utseende
        self.product_tree = QTreeWidget()
        self.product_tree.setHeaderLabels(["Produkt", "Typ"])
        self.product_tree.setAlternatingRowColors(True)
        self.product_tree.setAnimated(True)
        self.product_tree.header().setStretchLastSection(False)
        self.product_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.product_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.product_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.product_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.product_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #FAFAFA;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #E3F2FD;
                color: #0D47A1;
            }
        """)
        
        left_layout.addWidget(self.product_tree)
        
        # Höger panel: Flikar med editor och förhandsgranskning
        right_panel = QTabWidget()
        right_panel.setDocumentMode(True)
        right_panel.setTabPosition(QTabWidget.North)
        
        # JSONL-editor
        self.jsonl_editor = JsonlEditor()
        self.jsonl_editor.data_changed.connect(self.on_data_changed)
        right_panel.addTab(self.jsonl_editor, "JSONL Editor")
        
        # Bot-svar preview med förbättrad formatering
        self.bot_preview = QTextEdit()
        self.bot_preview.setReadOnly(True)
        self.bot_preview.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
            }
        """)
        
        # Preview-kontroller
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        preview_controls = QToolBar()
        preview_controls.setIconSize(QSize(16, 16))
        
        # Välj kommando för preview
        self.preview_command = QComboBox()
        self.preview_command.addItem("Tekniska detaljer (-t)", "-t")
        self.preview_command.addItem("Kompatibilitet (-c)", "-c")
        self.preview_command.addItem("Sammanfattning (-s)", "-s")
        self.preview_command.addItem("Fullständig info (-f)", "-f")
        self.preview_command.currentIndexChanged.connect(self.update_preview_for_current)
        preview_controls.addWidget(QLabel("Kommando:"))
        preview_controls.addWidget(self.preview_command)
        
        # Uppdatera preview-knapp
        refresh_preview = QAction(QIcon.fromTheme("view-refresh", QIcon(":/icons/refresh.png")), "Uppdatera", self)
        refresh_preview.triggered.connect(self.update_preview_for_current)
        preview_controls.addAction(refresh_preview)
        
        preview_layout.addWidget(preview_controls)
        preview_layout.addWidget(self.bot_preview)
        
        right_panel.addTab(preview_container, "Bot Preview")
        
        # Lägg till paneler i splitter
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        
        # Sätt standardbredd på panelerna (30/70)
        main_splitter.setSizes([int(self.width() * 0.3), int(self.width() * 0.7)])
        
        layout.addWidget(main_splitter)
        
        # Statusrad
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Redo")
        layout.addWidget(self.status_bar)
    
    def load_products(self):
        """Ladda produkter från integrerad data och organisera i trädvy"""
        self.product_tree.clear()
        self.status_bar.showMessage("Laddar produkter...")
        
        try:
            # Läs in alla produktkataloger
            product_dirs = list(self.integrated_dir.glob("products/*"))
            
            if not product_dirs:
                self.status_bar.showMessage("Inga produkter hittades i " + str(self.integrated_dir))
                return
            
            # Skapa rot-items för olika kategorier med ikoner
            self.tech_root = QTreeWidgetItem(self.product_tree, ["Teknisk Data"])
            self.tech_root.setIcon(0, QIcon.fromTheme("applications-system", QIcon(":/icons/tech.png")))
            
            self.compat_root = QTreeWidgetItem(self.product_tree, ["Kompatibilitet"])
            self.compat_root.setIcon(0, QIcon.fromTheme("network-wired", QIcon(":/icons/compat.png")))
            
            self.article_root = QTreeWidgetItem(self.product_tree, ["Artikeldata"])
            self.article_root.setIcon(0, QIcon.fromTheme("text-x-generic", QIcon(":/icons/article.png")))
            
            self.summary_root = QTreeWidgetItem(self.product_tree, ["Sammanfattningar"])
            self.summary_root.setIcon(0, QIcon.fromTheme("help-about", QIcon(":/icons/summary.png")))
            
            # Processa varje produktkatalog
            for product_dir in product_dirs:
                product_id = product_dir.name
                
                # Kolla vilka filer som finns för produkten
                files = {
                    "tech": (product_dir / "technical_specs.jsonl").exists(),
                    "compat": (product_dir / "compatibility.jsonl").exists(),
                    "article": (product_dir / "article_info.jsonl").exists(),
                    "summary": (product_dir / "summary.jsonl").exists()
                }
                
                # Lägg till under respektive kategori
                if files["tech"]:
                    item = QTreeWidgetItem(self.tech_root, [product_id, "Teknisk"])
                    item.setData(0, Qt.UserRole, str(product_dir / "technical_specs.jsonl"))
                
                if files["compat"]:
                    item = QTreeWidgetItem(self.compat_root, [product_id, "Kompatibilitet"])
                    item.setData(0, Qt.UserRole, str(product_dir / "compatibility.jsonl"))
                
                if files["article"]:
                    item = QTreeWidgetItem(self.article_root, [product_id, "Artikel"])
                    item.setData(0, Qt.UserRole, str(product_dir / "article_info.jsonl"))
                
                if files["summary"]:
                    item = QTreeWidgetItem(self.summary_root, [product_id, "Sammanfattning"])
                    item.setData(0, Qt.UserRole, str(product_dir / "summary.jsonl"))
            
            # Expandera alla kategorier
            self.product_tree.expandAll()
            
            # Uppdatera statusrad
            self.status_bar.showMessage(f"Laddade {len(product_dirs)} produkter")
            
        except Exception as e:
            logger.error(f"Fel vid laddning av produkter: {str(e)}")
            QMessageBox.warning(self, "Fel", f"Kunde inte ladda produkter: {str(e)}")
            self.status_bar.showMessage("Fel vid laddning av produkter")
    
    def filter_products(self, text: str):
        """Filtrera produkter baserat på söktext med förbättrad användarupplevelse"""
        search_text = text.lower().strip()
        
        # Om söktext är tom, visa alla produkter
        if not search_text:
            for i in range(self.product_tree.topLevelItemCount()):
                category = self.product_tree.topLevelItem(i)
                category.setHidden(False)
                for j in range(category.childCount()):
                    category.child(j).setHidden(False)
            
            self.status_bar.showMessage("Visar alla produkter")
            return
        
        # Leta efter matchande produkter i trädet
        match_count = 0
        for i in range(self.product_tree.topLevelItemCount()):
            category = self.product_tree.topLevelItem(i)
            visible_children = False
            
            for j in range(category.childCount()):
                item = category.child(j)
                product_id = item.text(0).lower()
                matches = search_text in product_id
                item.setHidden(not matches)
                
                if matches:
                    visible_children = True
                    match_count += 1
            
            category.setHidden(not visible_children)
        
        # Uppdatera statusrad med sökresultat
        self.status_bar.showMessage(f"Hittade {match_count} matchande produkter")
    
    def on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Hantera dubbelklick på en produkt i trädet"""
        if item.parent() is None:
            return  # Klick på kategori, inte på produkt
        
        file_path = item.data(0, Qt.UserRole)
        if not file_path:
            return
        
        # Ladda filen i editorn
        self.jsonl_editor.load_file(Path(file_path))
        
        # Extrahera produkt-ID och filtyp
        product_id = item.text(0)
        file_type = item.text(1)
        
        # Emitta signal för produktval
        self.product_selected.emit(product_id, file_path)
        
        # Uppdatera förhandsgranskning baserat på filtyp
        self.update_bot_preview(product_id, Path(file_path))
        
        # Uppdatera statusrad
        self.status_bar.showMessage(f"Laddade {file_type}-data för produkt {product_id}")
    
    def on_data_changed(self, data: str):
       """Hantera ändrad data i editorn, spara och uppdatera gränssnitt"""
       items = self.product_tree.selectedItems()
       if not items:
           return
       
       item = items[0]
       if item.parent() is None:
           return  # Kategori, inte produkt
       
       product_id = item.text(0)
       file_type = item.text(1)
       file_path = item.data(0, Qt.UserRole)
       
       if file_path:
           try:
               # Spara data till fil
               with open(file_path, 'w', encoding='utf-8') as f:
                   f.write(data)
               
               # Emitta signal om dataändring
               self.data_modified.emit(product_id, file_type)
               
               # Uppdatera förhandsgranskning
               self.update_bot_preview(product_id, Path(file_path))
               
               # Uppdatera statusrad
               self.status_bar.showMessage(f"Sparade ändringar för {product_id} ({file_type})")
               
           except Exception as e:
               logger.error(f"Fel vid sparning av data: {str(e)}")
               QMessageBox.warning(self, "Fel", f"Kunde inte spara ändringar: {str(e)}")
               self.status_bar.showMessage("Fel vid sparning av ändringar")
   
    def show_context_menu(self, position):
        
        """Visa kontextmeny med avancerade åtgärder för valda produkter"""
        items = self.product_tree.selectedItems()
        if not items:
            return
        
        item = items[0]
        if item.parent() is None:
            # Kontextmeny för kategorier
            menu = QMenu()
            expand_all = QAction("Expandera alla", self)
            expand_all.triggered.connect(lambda: self.product_tree.expandAll())
            menu.addAction(expand_all)
            
            collapse_all = QAction("Kollapsa alla", self)
            collapse_all.triggered.connect(lambda: self.product_tree.collapseAll())
            menu.addAction(collapse_all)
            
            menu.exec_(self.product_tree.viewport().mapToGlobal(position))
            return
        
        # Kontextmeny för produkter
        menu = QMenu()
        
        # Grundläggande åtgärder
        open_action = QAction(QIcon.fromTheme("document-open", QIcon(":/icons/open.png")), "Öppna i editor", self)
        open_action.triggered.connect(lambda: self.on_item_double_clicked(item, 0))
        menu.addAction(open_action)
        
        # Bot-kommandon undermeny
        bot_menu = menu.addMenu(QIcon.fromTheme("system-run", QIcon(":/icons/bot.png")), "Bot-kommandon")
        
        tech_action = QAction(QIcon.fromTheme("applications-system", QIcon(":/icons/tech.png")), "-t (Teknisk info)", self)
        tech_action.triggered.connect(lambda: self.execute_bot_command("-t", item.text(0)))
        bot_menu.addAction(tech_action)
        
        compat_action = QAction(QIcon.fromTheme("network-wired", QIcon(":/icons/compat.png")), "-c (Kompatibilitet)", self)
        compat_action.triggered.connect(lambda: self.execute_bot_command("-c", item.text(0)))
        bot_menu.addAction(compat_action)
        
        summary_action = QAction(QIcon.fromTheme("help-about", QIcon(":/icons/summary.png")), "-s (Sammanfattning)", self)
        summary_action.triggered.connect(lambda: self.execute_bot_command("-s", item.text(0)))
        bot_menu.addAction(summary_action)
        
        full_action = QAction(QIcon.fromTheme("text-x-generic", QIcon(":/icons/full.png")), "-f (Fullständig info)", self)
        full_action.triggered.connect(lambda: self.execute_bot_command("-f", item.text(0)))
        bot_menu.addAction(full_action)
        
        menu.addSeparator()
        
        # Avancerade åtgärder
        export_action = QAction(QIcon.fromTheme("document-save-as", QIcon(":/icons/export.png")), "Exportera data", self)
        export_action.triggered.connect(lambda: self.export_product_data(item.text(0)))
        menu.addAction(export_action)
        
        menu.exec_(self.product_tree.viewport().mapToGlobal(position))
    
    def execute_bot_command(self, command: str, product_id: str):
        """Exekvera ett bot-kommando och visa resultatet i förhandsgranskningen"""
        self.status_bar.showMessage(f"Kör kommando {command} för produkt {product_id}...")
        
        try:
            # Olika anrop beroende på motortyp
            if NLP_AVAILABLE:
                # För NLP-motorn
                text = f"{command} {product_id}"
                context = {}
                result = self.bot_engine.process_input(text, context)
                
                if result["status"] == "success":
                    self.bot_preview.setMarkdown(result.get("formatted_text", ""))
                    self.status_bar.showMessage(f"Kommando {command} utfört")
                else:
                    error_msg = result.get("message", "Okänt fel")
                    self.bot_preview.setMarkdown(f"# Fel\n\n{error_msg}")
                    self.status_bar.showMessage(f"Fel vid körning av kommando")
            else:
                # För standardmotorn
                result = self.bot_engine.execute_command(command, product_id)
                
                if result["status"] == "success":
                    self.bot_preview.setMarkdown(result.get("formatted_text", ""))
                    self.status_bar.showMessage(f"Kommando {command} utfört")
                else:
                    error_msg = result.get("message", "Okänt fel")
                    self.bot_preview.setMarkdown(f"# Fel\n\n{error_msg}")
                    self.status_bar.showMessage(f"Fel vid körning av kommando")
            
        except Exception as e:
            logger.error(f"Fel vid körning av botkommando: {str(e)}")
            self.bot_preview.setMarkdown(f"# Fel\n\nKunde inte köra kommando: {str(e)}")
            self.status_bar.showMessage(f"Fel vid körning av kommando: {str(e)}")
    
    def update_bot_preview(self, product_id: str, file_path: Path):
        """Uppdatera förhandsgranskning baserat på filtyp och aktuellt valt kommando"""
        file_str = str(file_path)
        
        # Välj lämpligt kommando baserat på filtypen
        if "technical_specs.jsonl" in file_str:
            command_index = self.preview_command.findData("-t")
            if command_index >= 0:
                self.preview_command.setCurrentIndex(command_index)
        elif "compatibility.jsonl" in file_str:
            command_index = self.preview_command.findData("-c")
            if command_index >= 0:
                self.preview_command.setCurrentIndex(command_index)
        elif "summary.jsonl" in file_str:
            command_index = self.preview_command.findData("-s")
            if command_index >= 0:
                self.preview_command.setCurrentIndex(command_index)
        
        # Kör kommandot för förhandsgranskning
        command = self.preview_command.currentData()
        if command:
            self.execute_bot_command(command, product_id)
    
    def update_preview_for_current(self):
        """Uppdatera förhandsgranskning för aktuellt valt kommando och produkt"""
        items = self.product_tree.selectedItems()
        if not items or items[0].parent() is None:
            return
        
        item = items[0]
        product_id = item.text(0)
        command = self.preview_command.currentData()
        
        if product_id and command:
            self.execute_bot_command(command, product_id)
    
    def export_data(self):
        """Exportera all data för en produkt eller kategori"""
        items = self.product_tree.selectedItems()
        if not items:
            QMessageBox.information(self, "Info", "Välj en produkt eller kategori först")
            return
        
        item = items[0]
        
        if item.parent() is None:
            # Exportera alla produkter i en kategori
            category_name = item.text(0)
            export_dir = QFileDialog.getExistingDirectory(
                self, f"Välj mapp för export av {category_name}",
                str(Path.home())
            )
            
            if not export_dir:
                return
            
            try:
                export_count = 0
                for i in range(item.childCount()):
                    child = item.child(i)
                    product_id = child.text(0)
                    file_path = child.data(0, Qt.UserRole)
                    
                    if file_path:
                        target_path = os.path.join(export_dir, f"{product_id}_{item.text(0)}.jsonl")
                        shutil.copy2(file_path, target_path)
                        export_count += 1
                
                QMessageBox.information(
                    self, 
                    "Export klar", 
                    f"Exporterade {export_count} filer till {export_dir}"
                )
                self.status_bar.showMessage(f"Exporterade {export_count} filer")
                
            except Exception as e:
                logger.error(f"Fel vid export: {str(e)}")
                QMessageBox.warning(self, "Fel", f"Kunde inte exportera data: {str(e)}")
                self.status_bar.showMessage("Fel vid export")
        else:
            # Exportera en specifik produkt
            self.export_product_data(item.text(0))
    
    def export_product_data(self, product_id: str):
        """Exportera alla data för en specifik produkt"""
        export_path, _ = QFileDialog.getSaveFileName(
            self, 
            f"Exportera data för {product_id}",
            str(Path.home() / f"{product_id}_export.json"),
            "JSON files (*.json)"
        )
        
        if not export_path:
            return
        
        try:
            # Samla all data för produkten
            product_dir = self.integrated_dir / "products" / product_id
            
            export_data = {
                "product_id": product_id,
                "exported_at": datetime.now().isoformat(),
                "technical_specs": [],
                "compatibility": [],
                "article_info": [],
                "summary": {}
            }
            
            # Ladda tekniska specifikationer
            tech_path = product_dir / "technical_specs.jsonl"
            if tech_path.exists():
                with open(tech_path, 'r', encoding='utf-8') as f:
                    export_data["technical_specs"] = [json.loads(line) for line in f if line.strip()]
            
            # Ladda kompatibilitetsinformation
            compat_path = product_dir / "compatibility.jsonl"
            if compat_path.exists():
                with open(compat_path, 'r', encoding='utf-8') as f:
                    export_data["compatibility"] = [json.loads(line) for line in f if line.strip()]
            
            # Ladda artikeldata
            article_path = product_dir / "article_info.jsonl"
            if article_path.exists():
                with open(article_path, 'r', encoding='utf-8') as f:
                    export_data["article_info"] = [json.loads(line) for line in f if line.strip()]
            
            # Ladda sammanfattning
            summary_path = product_dir / "summary.jsonl"
            if summary_path.exists():
                with open(summary_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    if first_line:
                        export_data["summary"] = json.loads(first_line)
            
            # Spara exportdata till JSON-fil
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(
                self, 
                "Export klar", 
                f"Data för produkt {product_id} exporterad till {export_path}"
            )
            self.status_bar.showMessage(f"Exporterade data för {product_id}")
            
        except Exception as e:
            logger.error(f"Fel vid export av produktdata: {str(e)}")
            QMessageBox.warning(self, "Fel", f"Kunde inte exportera produktdata: {str(e)}")
            self.status_bar.showMessage("Fel vid export av produktdata")
    
    def open_bot_test(self):
        """Öppna ett testfönster för botinteraktion"""
        try:
            from .chat_frame import ChatFrame
            
            # Skapa ett nytt fönster
            test_window = QWidget()
            test_window.setWindowTitle("Bot Test")
            test_window.resize(800, 600)
            
            layout = QVBoxLayout(test_window)
            
            # Skapa chat frame
            chat_frame = ChatFrame(self.config)
            layout.addWidget(chat_frame)
            
            # Visa fönstret
            test_window.show()
            
            # Spara referens för att förhindra att skräpsamlaren tar bort objektet
            self._test_window = test_window
            
        except Exception as e:
            logger.error(f"Fel vid öppning av testfönster: {str(e)}")
            QMessageBox.warning(self, "Fel", f"Kunde inte öppna testfönster: {str(e)}")
    
    def select_product(self, product_id: str):
        """
        Programmatisk markering av en produkt i trädet baserat på produkt-ID.
        Söker igenom alla kategorier och väljer första förekomsten.
        """
        for i in range(self.product_tree.topLevelItemCount()):
            category = self.product_tree.topLevelItem(i)
            for j in range(category.childCount()):
                item = category.child(j)
                if item.text(0) == product_id:
                    self.product_tree.setCurrentItem(item)
                    self.product_tree.scrollToItem(item)
                    # Simulera dubbelklick för att ladda produkt
                    self.on_item_double_clicked(item, 0)
                    return
        
        # Om produkten inte hittades
        self.status_bar.showMessage(f"Produkt {product_id} hittades inte")