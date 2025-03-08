# modules/product_explorer.py
# modules/product_explorer.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                             QTreeWidgetItem, QLabel, QLineEdit, QPushButton,
                             QMenu, QInputDialog, QMessageBox, QTabWidget,
                             QSplitter, QFrame, QFileDialog, QSpinBox,
                             QTextEdit, QPlainTextEdit)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon, QAction, QFont, QSyntaxHighlighter, QTextCharFormat

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class JsonlHighlighter(QSyntaxHighlighter):
    """Syntaxmarkering för JSONL-filer"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.json_format = QTextCharFormat()
        self.json_format.setForeground(Qt.darkBlue)
        
        self.key_format = QTextCharFormat()
        self.key_format.setForeground(Qt.darkRed)
        
        self.value_format = QTextCharFormat()
        self.value_format.setForeground(Qt.darkGreen)
        
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(Qt.blue)

    def highlightBlock(self, text):
        """Markera JSON-syntax"""
        import re
        
        # Markera nycklar
        for match in re.finditer(r'"([^"]+)"\s*:', text):
            self.setFormat(match.start(), match.end() - match.start(), self.key_format)
        
        # Markera strängar
        for match in re.finditer(r':\s*"([^"]+)"', text):
            self.setFormat(match.start(1)-1, match.end(1)-match.start(1)+2, self.value_format)
        
        # Markera nummer
        for match in re.finditer(r':\s*(-?\d+(?:\.\d+)?)', text):
            self.setFormat(match.start(1), match.end(1)-match.start(1), self.number_format)

class JsonlEditor(QWidget):
    """Editor för JSONL-filer med syntaxmarkering"""
    
    data_changed = Signal(str)  # Signal när data ändras
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Editor med syntaxmarkering
        self.editor = QPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFont("Consolas", 10)
        self.editor.setFont(font)
        
        # Skapa och sätt syntax highlighter
        self.highlighter = JsonlHighlighter(self.editor.document())
        
        # Lägg till editor i layouten
        layout.addWidget(self.editor)
        
        # Verktygsfält
        toolbar = QHBoxLayout()
        
        # Spara-knapp
        self.save_btn = QPushButton("Spara")
        self.save_btn.clicked.connect(self.save_data)
        toolbar.addWidget(self.save_btn)
        
        # Formattera-knapp
        self.format_btn = QPushButton("Formattera")
        self.format_btn.clicked.connect(self.format_json)
        toolbar.addWidget(self.format_btn)
        
        # Validera-knapp
        self.validate_btn = QPushButton("Validera")
        self.validate_btn.clicked.connect(self.validate_json)
        toolbar.addWidget(self.validate_btn)
        
        layout.addLayout(toolbar)
    
    def load_file(self, file_path: Path):
        """Ladda en JSONL-fil"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.editor.setPlainText(f.read())
        except Exception as e:
            QMessageBox.warning(self, "Fel", f"Kunde inte ladda fil: {str(e)}")
    
    def save_data(self):
        """Spara ändringar"""
        try:
            # Validera först
            if not self.validate_json():
                return
                
            # Signalera att data har ändrats
            self.data_changed.emit(self.editor.toPlainText())
            QMessageBox.information(self, "Sparat", "Ändringarna har sparats")
        except Exception as e:
            QMessageBox.warning(self, "Fel", f"Kunde inte spara: {str(e)}")
    
    def format_json(self):
        """Formattera JSONL för bättre läsbarhet"""
        try:
            text = self.editor.toPlainText()
            formatted_lines = []
            
            for line in text.split('\n'):
                if line.strip():
                    # Parse och formattera varje JSON-objekt
                    data = json.loads(line)
                    formatted = json.dumps(data, ensure_ascii=False, indent=2)
                    # Konvertera till en rad
                    formatted_line = formatted.replace('\n', '')
                    formatted_lines.append(formatted_line)
            
            self.editor.setPlainText('\n'.join(formatted_lines))
        except Exception as e:
            QMessageBox.warning(self, "Fel", f"Kunde inte formattera: {str(e)}")
    
    def validate_json(self) -> bool:
        """Validera JSONL-syntax"""
        text = self.editor.toPlainText()
        try:
            for line in text.split('\n'):
                if line.strip():
                    json.loads(line)
            return True
        except Exception as e:
            QMessageBox.warning(self, "Valideringsfel", f"Ogiltig JSONL: {str(e)}")
            return False

class ProductExplorer(QWidget):
    """
    Avancerad produktutforskare med stöd för:
    - Trädvy av produkter
    - JSONL-redigering
    - Bot-svar preview
    - Direktredigering av data
    """
    
    # Signaler
    product_selected = Signal(str, str)  # product_id, file_path
    data_modified = Signal(str, str)  # product_id, modification_type
    
    def __init__(self, config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.config = config
        
        # Grundläggande sökvägar
        self.base_dir = Path(config.get("base_dir", "./converted_docs"))
        self.integrated_dir = Path(config.get("integrated_data_dir", "./nlp_bot_engine/data/integrated_data"))
        
        # Initiera UI
        self.init_ui()
        
        # Ladda produktdata
        self.load_products()
    
    def init_ui(self):
        """Initiera användargränssnittet"""
        # Huvudlayout
        layout = QHBoxLayout(self)
        
        # Vänster panel: Produktträd
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Sökfält
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Sök produkter...")
        self.search_input.textChanged.connect(self.filter_products)
        left_layout.addWidget(self.search_input)
        
        # Produktträd
        self.product_tree = QTreeWidget()
        self.product_tree.setHeaderLabels(["Produkt", "Typ"])
        self.product_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.product_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.product_tree.customContextMenuRequested.connect(self.show_context_menu)
        left_layout.addWidget(self.product_tree)
        
        # Höger panel: Editor och förhandsgranskning
        right_panel = QTabWidget()
        
        # JSONL-editor
        self.jsonl_editor = JsonlEditor()
        self.jsonl_editor.data_changed.connect(self.on_data_changed)
        right_panel.addTab(self.jsonl_editor, "JSONL Editor")
        
        # Bot-svar preview
        self.bot_preview = QTextEdit()
        self.bot_preview.setReadOnly(True)
        right_panel.addTab(self.bot_preview, "Bot Preview")
        
        # Lägg till paneler i splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        
        # Sätt standardbredd på panelerna
        splitter.setSizes([int(self.width() * 0.3), int(self.width() * 0.7)])
        
        layout.addWidget(splitter)
    
    def load_products(self):
        """Ladda produkter från integrerad data"""
        self.product_tree.clear()
        
        try:
            # Läs in alla produktkataloger
            product_dirs = list(self.integrated_dir.glob("products/*"))
            
            # Skapa rot-items för olika kategorier
            self.tech_root = QTreeWidgetItem(self.product_tree, ["Teknisk Data"])
            self.compat_root = QTreeWidgetItem(self.product_tree, ["Kompatibilitet"])
            self.article_root = QTreeWidgetItem(self.product_tree, ["Artikeldata"])
            self.summary_root = QTreeWidgetItem(self.product_tree, ["Sammanfattningar"])
            
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
            
        except Exception as e:
            QMessageBox.warning(self, "Fel", f"Kunde inte ladda produkter: {str(e)}")
    
    def filter_products(self, text: str):
        """Filtrera produkter baserat på söktext"""
        search_text = text.lower().strip()
        
        if not search_text:
            for i in range(self.product_tree.topLevelItemCount()):
                category = self.product_tree.topLevelItem(i)
                category.setHidden(False)
                for j in range(category.childCount()):
                    category.child(j).setHidden(False)
            return
        
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
            
            category.setHidden(not visible_children)
    
    def on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Hantera dubbelklick på produkt"""
        if item.parent() is None:
            return
        
        file_path = item.data(0, Qt.UserRole)
        if file_path:
            self.jsonl_editor.load_file(Path(file_path))
            
            product_id = item.text(0)
            self.product_selected.emit(product_id, file_path)
            self.update_bot_preview(product_id, Path(file_path))
    
    def on_data_changed(self, data: str):
        """Hantera ändrad data i editorn"""
        items = self.product_tree.selectedItems()
        if not items:
            return
        
        item = items[0]
        product_id = item.text(0)
        file_path = item.data(0, Qt.UserRole)
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(data)
                
                self.data_modified.emit(product_id, item.text(1))
                self.update_bot_preview(product_id, Path(file_path))
                
            except Exception as e:
                QMessageBox.warning(self, "Fel", f"Kunde inte spara ändringar: {str(e)}")
    
    def show_context_menu(self, position):
        """Visa kontext-meny för produkter"""
        items = self.product_tree.selectedItems()
        if not items:
            return
        
        item = items[0]
        if item.parent() is None:
            return
        
        menu = QMenu()
        
        open_action = QAction("Öppna i editor", self)
        open_action.triggered.connect(lambda: self.on_item_double_clicked(item, 0))
        menu.addAction(open_action)
        
        bot_menu = menu.addMenu("Bot-kommandon")
        
        tech_action = QAction("-t (Teknisk info)", self)
        tech_action.triggered.connect(lambda: self.execute_bot_command("-t", item.text(0)))
        bot_menu.addAction(tech_action)
        
        compat_action = QAction("-c (Kompatibilitet)", self)
        compat_action.triggered.connect(lambda: self.execute_bot_command("-c", item.text(0)))
        bot_menu.addAction(compat_action)
        
        summary_action = QAction("-s (Sammanfattning)", self)
        summary_action.triggered.connect(lambda: self.execute_bot_command("-s", item.text(0)))
        bot_menu.addAction(summary_action)
        
        menu.exec_(self.product_tree.viewport().mapToGlobal(position))
    
    def execute_bot_command(self, command: str, product_id: str):
        """Exekvera ett bot-kommando och visa resultatet"""
        try:
            from .bot_engine import BotEngine
            bot = BotEngine(self.config)
            result = bot.execute_command(command, product_id)
            
            if result["status"] == "success":
                self.bot_preview.setMarkdown(result.get("formatted_text", ""))
            else:
                self.bot_preview.setMarkdown(f"# Fel\n\n{result.get('message', 'Okänt fel')}")
            
        except Exception as e:
            self.bot_preview.setMarkdown(f"# Fel\n\nKunde inte köra kommando: {str(e)}")
    
    def update_bot_preview(self, product_id: str, file_path: Path):
        """Uppdatera bot-preview baserat på filtyp"""
        try:
            command = None
            if "technical_specs.jsonl" in str(file_path):
                command = "-t"
            elif "compatibility.jsonl" in str(file_path):
                command = "-c"
            elif "summary.jsonl" in str(file_path):
                command = "-s"
            
            if command:
                self.execute_bot_command(command, product_id)
                
        except Exception as e:
            self.bot_preview.setMarkdown(f"# Fel\n\nKunde inte uppdatera preview: {str(e)}")
    
    def select_product(self, product_id: str):
        """
        Programmatisk markering av en produkt i trädet baserat på produkt-ID.
        Detta gör att andra moduler (t.ex. report_viewer) kan be om att en viss produkt
        väljs i produktutforskaren.
        """
        for i in range(self.product_tree.topLevelItemCount()):
            category = self.product_tree.topLevelItem(i)
            for j in range(category.childCount()):
                item = category.child(j)
                if item.text(0) == product_id:
                    self.product_tree.setCurrentItem(item)
                    self.product_tree.scrollToItem(item)
                    return
