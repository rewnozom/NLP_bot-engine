# modules/settings_panel.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLabel, QLineEdit, QSpinBox, QComboBox, QPushButton,
                             QGroupBox, QCheckBox, QScrollArea, QTabWidget,
                             QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, Signal, QSize
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class SettingsPanel(QWidget):
    """A comprehensive settings panel for configuring the application"""
    
    # Signal emitted when any setting changes
    settings_changed = Signal(str, object)  # setting_name, new_value
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.init_ui()
        
    def init_ui(self):
        """Initialize the settings panel UI"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Create a scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        # Create the content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        
        # Create tabs for different setting categories
        tabs = QTabWidget()
        
        # General Settings Tab
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        
        # Directory Settings
        dir_group = QGroupBox("Kataloger")
        dir_layout = QFormLayout()
        
        # Base Directory
        self.base_dir_edit = QLineEdit(self.config.get("base_dir", ""))
        self.base_dir_edit.setReadOnly(True)
        browse_base_btn = QPushButton("Bläddra...")
        browse_base_btn.clicked.connect(lambda: self.browse_directory("base_dir"))
        base_dir_layout = QHBoxLayout()
        base_dir_layout.addWidget(self.base_dir_edit)
        base_dir_layout.addWidget(browse_base_btn)
        dir_layout.addRow("Grundkatalog:", base_dir_layout)
        
        # Integrated Data Directory
        self.integrated_dir_edit = QLineEdit(self.config.get("integrated_data_dir", ""))
        self.integrated_dir_edit.setReadOnly(True)
        browse_integrated_btn = QPushButton("Bläddra...")
        browse_integrated_btn.clicked.connect(lambda: self.browse_directory("integrated_data_dir"))
        integrated_dir_layout = QHBoxLayout()
        integrated_dir_layout.addWidget(self.integrated_dir_edit)
        integrated_dir_layout.addWidget(browse_integrated_btn)
        dir_layout.addRow("Integrerad data:", integrated_dir_layout)
        
        dir_group.setLayout(dir_layout)
        general_layout.addWidget(dir_group)
        
        # Interface Settings
        ui_group = QGroupBox("Gränssnitt")
        ui_layout = QFormLayout()
        
        # Theme Selection
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["light", "dark"])
        self.theme_combo.setCurrentText(self.config.get("theme", "light"))
        self.theme_combo.currentTextChanged.connect(
            lambda v: self.settings_changed.emit("theme", v)
        )
        ui_layout.addRow("Tema:", self.theme_combo)
        
        # Font Size
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(self.config.get("font_size", 12))
        self.font_size_spin.valueChanged.connect(
            lambda v: self.settings_changed.emit("font_size", v)
        )
        ui_layout.addRow("Textstorlek:", self.font_size_spin)
        
        ui_group.setLayout(ui_layout)
        general_layout.addWidget(ui_group)
        
        # Add general tab
        tabs.addTab(general_tab, "Allmänt")
        
        # Bot Settings Tab
        bot_tab = QWidget()
        bot_layout = QVBoxLayout(bot_tab)
        
        # Bot Response Templates
        template_group = QGroupBox("Svarsmallar")
        template_layout = QVBoxLayout()
        
        # Technical Response Template
        tech_label = QLabel("Mall för tekniska specifikationer:")
        self.tech_template_edit = QLineEdit(
            self.config.get("bot_settings", {}).get(
                "response_template_tech",
                "# Tekniska specifikationer för {product_name}\n\n**Artikelnummer:** {product_id}\n\n{specifications}"
            )
        )
        self.tech_template_edit.textChanged.connect(
            lambda v: self.settings_changed.emit("bot_settings.response_template_tech", v)
        )
        template_layout.addWidget(tech_label)
        template_layout.addWidget(self.tech_template_edit)
        
        # Compatibility Response Template
        compat_label = QLabel("Mall för kompatibilitetsinformation:")
        self.compat_template_edit = QLineEdit(
            self.config.get("bot_settings", {}).get(
                "response_template_compat",
                "# Kompatibilitetsinformation för {product_name}\n\n**Artikelnummer:** {product_id}\n\n{compatibility}"
            )
        )
        self.compat_template_edit.textChanged.connect(
            lambda v: self.settings_changed.emit("bot_settings.response_template_compat", v)
        )
        template_layout.addWidget(compat_label)
        template_layout.addWidget(self.compat_template_edit)
        
        # Summary Response Template
        summary_label = QLabel("Mall för produktsammanfattning:")
        self.summary_template_edit = QLineEdit(
            self.config.get("bot_settings", {}).get(
                "response_template_summary",
                "# {product_name}\n\n**Artikelnummer:** {product_id}\n\n{description}\n\n{specifications}\n\n{compatibility}"
            )
        )
        self.summary_template_edit.textChanged.connect(
            lambda v: self.settings_changed.emit("bot_settings.response_template_summary", v)
        )
        template_layout.addWidget(summary_label)
        template_layout.addWidget(self.summary_template_edit)
        
        template_group.setLayout(template_layout)
        bot_layout.addWidget(template_group)
        
        # Performance Settings
        perf_group = QGroupBox("Prestanda")
        perf_layout = QFormLayout()
        
        # Max Workers
        self.max_workers_spin = QSpinBox()
        self.max_workers_spin.setRange(1, 32)
        self.max_workers_spin.setValue(self.config.get("max_workers", 4))
        self.max_workers_spin.valueChanged.connect(
            lambda v: self.settings_changed.emit("max_workers", v)
        )
        perf_layout.addRow("Max antal arbetare:", self.max_workers_spin)
        
        perf_group.setLayout(perf_layout)
        bot_layout.addWidget(perf_group)
        
        # Add bot tab
        tabs.addTab(bot_tab, "Bot")
        
        # Add tabs to content layout
        content_layout.addWidget(tabs)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Spara")
        save_btn.clicked.connect(self.save_settings)
        
        reset_btn = QPushButton("Återställ")
        reset_btn.clicked.connect(self.reset_settings)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(reset_btn)
        content_layout.addLayout(button_layout)
        
        # Set the content widget to the scroll area
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def browse_directory(self, setting_name):
        """Open a directory browser dialog"""
        current_dir = self.config.get(setting_name, "")
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Välj katalog",
            current_dir
        )
        if dir_path:
            if setting_name == "base_dir":
                self.base_dir_edit.setText(dir_path)
            elif setting_name == "integrated_data_dir":
                self.integrated_dir_edit.setText(dir_path)
            self.settings_changed.emit(setting_name, dir_path)
    
    def save_settings(self):
        """Save current settings to config file"""
        try:
            # Update config with current values
            self.config["base_dir"] = self.base_dir_edit.text()
            self.config["integrated_data_dir"] = self.integrated_dir_edit.text()
            self.config["theme"] = self.theme_combo.currentText()
            self.config["font_size"] = self.font_size_spin.value()
            self.config["max_workers"] = self.max_workers_spin.value()
            
            if "bot_settings" not in self.config:
                self.config["bot_settings"] = {}
            
            self.config["bot_settings"]["response_template_tech"] = self.tech_template_edit.text()
            self.config["bot_settings"]["response_template_compat"] = self.compat_template_edit.text()
            self.config["bot_settings"]["response_template_summary"] = self.summary_template_edit.text()
            
            # Save to file
            config_file = Path("config/app_config.json")
            config_file.parent.mkdir(exist_ok=True)
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            
            QMessageBox.information(self, "Framgång", "Inställningarna har sparats!")
            
        except Exception as e:
            logger.error(f"Failed to save settings: {str(e)}")
            QMessageBox.critical(self, "Fel", f"Kunde inte spara inställningar: {str(e)}")
    
    def reset_settings(self):
        """Reset settings to default values"""
        if QMessageBox.question(
            self,
            "Återställ inställningar",
            "Är du säker på att du vill återställa alla inställningar till standardvärden?"
        ) == QMessageBox.Yes:
            # Reset to defaults
            default_config = {
                "base_dir": str(Path("./converted_docs")),
                "integrated_data_dir": str(Path("./nlp_bot_engine/data/integrated_data")),
                "theme": "light",
                "font_size": 12,
                "max_workers": 4,
                "bot_settings": {
                    "response_template_tech": "# Tekniska specifikationer för {product_name}\n\n**Artikelnummer:** {product_id}\n\n{specifications}",
                    "response_template_compat": "# Kompatibilitetsinformation för {product_name}\n\n**Artikelnummer:** {product_id}\n\n{compatibility}",
                    "response_template_summary": "# {product_name}\n\n**Artikelnummer:** {product_id}\n\n{description}\n\n{specifications}\n\n{compatibility}"
                }
            }
            
            # Update UI
            self.base_dir_edit.setText(default_config["base_dir"])
            self.integrated_dir_edit.setText(default_config["integrated_data_dir"])
            self.theme_combo.setCurrentText(default_config["theme"])
            self.font_size_spin.setValue(default_config["font_size"])
            self.max_workers_spin.setValue(default_config["max_workers"])
            self.tech_template_edit.setText(default_config["bot_settings"]["response_template_tech"])
            self.compat_template_edit.setText(default_config["bot_settings"]["response_template_compat"])
            self.summary_template_edit.setText(default_config["bot_settings"]["response_template_summary"])
            
            # Update config
            self.config.update(default_config)
            
            # Emit changes
            for key, value in default_config.items():
                if key != "bot_settings":
                    self.settings_changed.emit(key, value)
            
            for key, value in default_config["bot_settings"].items():
                self.settings_changed.emit(f"bot_settings.{key}", value)