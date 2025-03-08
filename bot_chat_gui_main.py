# main.py
import sys
import os
from pathlib import Path
import logging
from datetime import datetime

from PySide6.QtWidgets import (QApplication, QMainWindow, QSplitter, QVBoxLayout, 
                               QWidget, QMessageBox)
from PySide6.QtCore import Qt, QSize

# Importera våra egna moduler
from Bot.modules.chat_frame import ChatFrame
from Bot.modules.product_explorer import ProductExplorer
from Bot.modules.json_editor import JsonEditor
from Bot.modules.settings_panel import SettingsPanel
from Bot.modules.report_viewer import ReportViewer

# Importera temafunktioner
from Bot.modules.theme import apply_theme, apply_font_size

# Konfigurera loggning
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("dev_bot_chat.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """Huvudfönster för Developer Bot-Chat applikationen"""
    
    def __init__(self):
        super().__init__()
        
        # Grundläggande fönsterinställningar
        self.setWindowTitle("Developer Bot-Chat")
        self.setMinimumSize(QSize(1200, 800))
        
        # Läs in konfiguration och skapa kataloger om de inte finns
        self.setup_data_directories()
        
        # Skapa huvudwidget och layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # Skapa huvudsplitter för att dela fönstret
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.layout.addWidget(self.main_splitter)
        
        # Vänster panel: Produktutforskare + Inställningar
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        
        # Produktutforskare
        self.product_explorer = ProductExplorer(self.config)
        self.left_layout.addWidget(self.product_explorer)
        
        # Inställningspanel
        self.settings_panel = SettingsPanel(self.config)
        self.left_layout.addWidget(self.settings_panel)
        
        # Höger panel: Chat + JSONL-editor + Report Viewer
        self.right_panel = QSplitter(Qt.Vertical)
        
        # Chat-gränssnitt
        self.chat_frame = ChatFrame(self.config)
        
        # JSONL-editor
        self.json_editor = JsonEditor(self.config)
        
        # Rapport-visning
        self.report_viewer = ReportViewer(self.config)
        
        # Lägg till paneler i rätt splitters
        self.right_panel.addWidget(self.chat_frame)
        self.right_panel.addWidget(self.json_editor)
        
        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.right_panel)
        self.main_splitter.addWidget(self.report_viewer)
        
        # Ställ in relativ storlek på panelerna (i procent)
        self.main_splitter.setSizes([
            int(self.width() * 0.2),  # Left panel
            int(self.width() * 0.6),  # Right panel
            int(self.width() * 0.2)   # Report viewer
        ])
        self.right_panel.setSizes([
            int(self.height() * 0.6),  # Chat frame
            int(self.height() * 0.4)   # JSON editor
        ])
        
        # Anslut signaler
        self.setup_signal_connections()
        
        # Visa välkomstmeddelande i chatten
        self.welcome_message()
    
    def setup_data_directories(self):
        """Skapar datakataloger om de inte finns och läser in konfiguration"""
        # Grundläggande sökvägar
        self.app_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.config_file = self.app_dir / "config" / "app_config.json"
        
        # Skapa katalogstruktur
        (self.app_dir / "config").mkdir(exist_ok=True)
        (self.app_dir / "logs").mkdir(exist_ok=True)
        (self.app_dir / "temp").mkdir(exist_ok=True)
        
        # Läs in eller skapa konfiguration
        self.config = self.load_config()
    
    def load_config(self):
        """Läser in konfiguration från fil eller skapar standard om den inte finns"""
        import json
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Kunde inte läsa konfigurationsfil: {str(e)}")
        
        # Standardkonfiguration
        config = {
            "base_dir": str(Path("./converted_docs")),
            "integrated_data_dir": str(Path("./nlp_bot_engine/data/integrated_data")),
            "technical_data_dir": str(Path("./nlp_bot_engine/data/extracted_data/technical")),
            "compatibility_data_dir": str(Path("./nlp_bot_engine/data/extracted_data/compatibility")),
            "article_data_dir": str(Path("./nlp_bot_engine/data/extracted_data/artikel")),
            "max_workers": os.cpu_count(),
            "theme": "dark",
            "font_size": 12,
            "bot_settings": {
                "response_template_tech": "# Tekniska specifikationer för {product_name}\n\n**Artikelnummer:** {product_id}\n\n{specifications}",
                "response_template_compat": "# Kompatibilitetsinformation för {product_name}\n\n**Artikelnummer:** {product_id}\n\n{compatibility}",
                "response_template_summary": "# {product_name}\n\n**Artikelnummer:** {product_id}\n\n{description}\n\n{specifications}\n\n{compatibility}"
            },
            "supported_file_types": [
                "_pro", "_produktblad", "_TEK", "_sak", "_man", "_ins", 
                "_CERT", "_BRO", "_INs", "_cert", "_prodblad", "_PRE", 
                "_bro", "_mdek", "_tek", "_MAN", "_PRO"
            ]
        }
        
        # Spara standardkonfiguration
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Kunde inte spara standardkonfiguration: {str(e)}")
        
        return config
    
    def setup_signal_connections(self):
        """Konfigurerar signaler och anslutningar mellan komponenter"""
        self.product_explorer.product_selected.connect(self.on_product_selected)
        self.chat_frame.command_executed.connect(self.on_command_executed)
        self.json_editor.data_changed.connect(self.on_data_changed)
        self.json_editor.preview_updated.connect(self.report_viewer.show_preview)
        self.settings_panel.settings_changed.connect(self.on_settings_changed)
        self.report_viewer.report_selected.connect(self.on_report_selected)
    
    def on_product_selected(self, product_id, file_path):
        """Hantera val av produkt i utforskaren"""
        self.json_editor.load_product(product_id)
        self.chat_frame.update_active_product(product_id) 
        logger.info(f"Vald produkt: {product_id} ({file_path})")
    
    def on_command_executed(self, command, product_id, response):
        """Hantera utförande av ett bot-kommando"""
        self.report_viewer.show_command_response(command, product_id, response)
        logger.info(f"Utfört kommando: {command} för {product_id}")
    
    def on_data_changed(self, product_id, data_type, data):
        """Hantera ändring av data i editorn"""
        self.product_explorer.refresh_product(product_id)
        logger.info(f"Uppdaterade {data_type} för {product_id}")
    
    def on_settings_changed(self, setting_name, value):
        """Hantera ändring av inställningar"""
        if setting_name in self.config:
            self.config[setting_name] = value
        elif "." in setting_name:
            parts = setting_name.split(".")
            parent = self.config
            for part in parts[:-1]:
                if part not in parent:
                    parent[part] = {}
                parent = parent[part]
            parent[parts[-1]] = value
        self.save_config()
        self.update_ui_from_settings()
        logger.info(f"Ändrade inställning: {setting_name} = {value}")
    
    def save_config(self):
        """Sparar nuvarande konfiguration till fil"""
        import json
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Kunde inte spara konfiguration: {str(e)}")
    
    def update_ui_from_settings(self):
        """Uppdaterar UI-element baserat på inställningar"""
        if "theme" in self.config:
            # Använder theme.py för att applicera temat
            apply_theme(self, self.config["theme"])
        if "font_size" in self.config:
            apply_font_size(self, self.config["font_size"])
    
    def on_report_selected(self, report_type, report_data):
        """Hantera val av rapport i report viewer"""
        if "product_id" in report_data:
            self.product_explorer.select_product(report_data["product_id"])
        logger.info(f"Vald rapport: {report_type}")
    
    def welcome_message(self):
        """Visar ett välkomstmeddelande i chat-rutan"""
        welcome_html = """
        <h2>Välkommen till Developer Bot-Chat!</h2>
        <p>Detta är ett avancerat gränssnitt för att arbeta med produktdata och bot-kommandon.</p>
        <ul>
            <li>Använd produktutforskaren till vänster för att bläddra bland produkter</li>
            <li>Skriv kommandon eller frågor i chat-rutan</li>
            <li>Se och redigera raw data i JSONL-editorn</li>
            <li>Konfigurera inställningar för bot och app i inställningspanelen</li>
        </ul>
        <p>Exempel på kommandon:</p>
        <ul>
            <li><code>-t 50091812</code> - Visa tekniska specifikationer för en produkt</li>
            <li><code>-c 50091812</code> - Visa kompatibilitetsinformation för en produkt</li>
            <li><code>-s 50091812</code> - Visa en sammanfattning av produkten</li>
            <li><code>-f 50091812</code> - Visa fullständig produktinformation</li>
        </ul>
        <p>Du kan också ställa naturliga frågor som:</p>
        <ul>
            <li>"Vilka trycken passar assa Låshus 310-50 hö?"</li>
            <li>"Vilken monteringsstolpe ska jag använda med Elslutbleck-150-24?"</li>
            <li>"Visa kompatibla produkter för artikelnummer 50091812"</li>
        </ul>
        """
        self.chat_frame.display_system_message(welcome_html)

def main():
    app = QApplication(sys.argv)

    # Skapa och visa huvudfönstret
    window = MainWindow()

    # Applicera tema och fontstorlek på hela applikationen via theme.py
    apply_theme(app, window.config.get("theme", "dark"))
    apply_font_size(app, window.config.get("font_size", 12))

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
