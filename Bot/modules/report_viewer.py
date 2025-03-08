# ..\..\modules\report_viewer.py
# modules/report_viewer.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget,
                             QTreeWidgetItem, QTextEdit, QPushButton, QLabel,
                             QComboBox, QTabWidget, QSplitter, QMenu, QMessageBox)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QAction, QColor

import json
import logging
from pathlib import Path
from datetime import datetime
import markdown

logger = logging.getLogger(__name__)

class ReportViewer(QWidget):
    """Widget for viewing various reports and command responses"""
    
    # Define signals
    report_selected = Signal(str, dict)  # report_type, report_data
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        
        # Initialize state
        self.current_report = None
        self.report_cache = {}
        self.integrated_data_dir = Path(config.get("integrated_data_dir", "./nlp_bot_engine/data/integrated_data"))
        
        # Initialize UI
        self.init_ui()
        
        # Start periodic refresh
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_reports)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds
    
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        
        # Header with controls
        header_layout = QHBoxLayout()
        
        # Report type filter
        self.type_filter = QComboBox()
        self.type_filter.addItems([
            "Alla rapporter",
            "Kommandosvar",
            "Integrationsrapporter",
            "Valideringsrapporter",
            "Felrapporter"
        ])
        self.type_filter.currentTextChanged.connect(self.filter_reports)
        header_layout.addWidget(QLabel("Visa:"))
        header_layout.addWidget(self.type_filter)
        
        # Refresh button
        refresh_btn = QPushButton("Uppdatera")
        refresh_btn.clicked.connect(self.refresh_reports)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Main splitter
        splitter = QSplitter(Qt.Vertical)
        
        # Report tree
        self.report_tree = QTreeWidget()
        self.report_tree.setHeaderLabels(["Rapport", "Datum", "Typ"])
        self.report_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.report_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.report_tree.itemSelectionChanged.connect(self.on_report_selected)
        
        # Report content viewer (tabbed)
        self.content_tabs = QTabWidget()
        
        # HTML view tab
        self.html_view = QTextEdit()
        self.html_view.setReadOnly(True)
        self.content_tabs.addTab(self.html_view, "Formaterad vy")
        
        # Raw view tab
        self.raw_view = QTextEdit()
        self.raw_view.setReadOnly(True)
        self.content_tabs.addTab(self.raw_view, "Rådata")
        
        # Add widgets to splitter
        splitter.addWidget(self.report_tree)
        splitter.addWidget(self.content_tabs)
        
        # Set initial splitter sizes (40% tree, 60% content)
        splitter.setSizes([400, 600])
        
        layout.addWidget(splitter)
        
        # Initial report load
        self.refresh_reports()
    
    def refresh_reports(self):
        """Refresh the report list"""
        self.report_tree.clear()
        self.report_cache.clear()
        
        try:
            # Find all reports
            reports = []
            
            # Command responses
            for product_dir in self.integrated_data_dir.glob("products/*/command_responses"):
                for response_file in product_dir.glob("*.json"):
                    product_id = product_dir.parent.name
                    report_type = response_file.stem.replace("_response", "")
                    
                    try:
                        with open(response_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            timestamp = data.get("timestamp", "Unknown")
                            reports.append({
                                "type": "command",
                                "subtype": report_type,
                                "product_id": product_id,
                                "path": response_file,
                                "timestamp": timestamp,
                                "data": data
                            })
                    except Exception as e:
                        logger.error(f"Error reading command response {response_file}: {e}")
            
            # Integration reports
            for report_file in self.integrated_data_dir.glob("integration_report_*.json"):
                try:
                    with open(report_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        timestamp = data.get("timestamp", "Unknown")
                        reports.append({
                            "type": "integration",
                            "path": report_file,
                            "timestamp": timestamp,
                            "data": data
                        })
                except Exception as e:
                    logger.error(f"Error reading integration report {report_file}: {e}")
            
            # Validation reports
            for report_file in self.integrated_data_dir.glob("validation_report_*.json"):
                try:
                    with open(report_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        timestamp = data.get("timestamp", "Unknown")
                        reports.append({
                            "type": "validation",
                            "path": report_file,
                            "timestamp": timestamp,
                            "data": data
                        })
                except Exception as e:
                    logger.error(f"Error reading validation report {report_file}: {e}")
            
            # Sort reports by timestamp (newest first)
            reports.sort(key=lambda x: x["timestamp"], reverse=True)
            
            # Create tree items
            for report in reports:
                item = QTreeWidgetItem()
                
                # Set item text based on report type
                if report["type"] == "command":
                    item.setText(0, f"{report['product_id']} - {report['subtype']}")
                    item.setText(1, report["timestamp"])
                    item.setText(2, "Kommandosvar")
                else:
                    item.setText(0, report["path"].stem)
                    item.setText(1, report["timestamp"])
                    item.setText(2, "Integrationsrapport" if report["type"] == "integration" else "Valideringsrapport")
                
                # Store report data in cache
                cache_key = f"{report['type']}_{report['path']}"
                self.report_cache[cache_key] = report
                item.setData(0, Qt.UserRole, cache_key)
                
                self.report_tree.addTopLevelItem(item)
            
            # Resize columns to content
            for i in range(3):
                self.report_tree.resizeColumnToContents(i)
            
        except Exception as e:
            logger.error(f"Error refreshing reports: {e}")
            QMessageBox.warning(self, "Fel", f"Kunde inte uppdatera rapportlistan: {str(e)}")
    
    def filter_reports(self):
        """Filter reports based on selected type"""
        filter_text = self.type_filter.currentText()
        
        # Show all items first
        for i in range(self.report_tree.topLevelItemCount()):
            item = self.report_tree.topLevelItem(i)
            item.setHidden(False)
        
        # Apply filter if not "Alla rapporter"
        if filter_text != "Alla rapporter":
            for i in range(self.report_tree.topLevelItemCount()):
                item = self.report_tree.topLevelItem(i)
                if item.text(2) != filter_text:
                    item.setHidden(True)
    
    def on_report_selected(self):
        """Handle report selection"""
        items = self.report_tree.selectedItems()
        if not items:
            return
        
        item = items[0]
        cache_key = item.data(0, Qt.UserRole)
        report = self.report_cache.get(cache_key)
        
        if report:
            self.current_report = report
            self.display_report(report)
            self.report_selected.emit(report["type"], report["data"])
    
    def display_report(self, report):
        """Display the selected report"""
        if report["type"] == "command":
            # Display command response
            self.display_command_response(report)
        else:
            # Display integration or validation report
            self.display_general_report(report)
    
    def display_command_response(self, report):
        """Display a command response"""
        data = report["data"]
        
        # Format HTML view
        html = f"<h1>Kommandosvar: {report['subtype']}</h1>\n"
        html += f"<p><strong>Produkt:</strong> {report['product_id']}</p>\n"
        html += f"<p><strong>Tidpunkt:</strong> {report['timestamp']}</p>\n"
        
        # Add markdown response if available
        if "markdown_response" in data:
            html += "\n<hr>\n"
            html += markdown.markdown(data["markdown_response"])
        
        self.html_view.setHtml(html)
        
        # Raw view
        self.raw_view.setPlainText(
            json.dumps(data, ensure_ascii=False, indent=2)
        )
    
    def display_general_report(self, report):
        """Display a general report (integration or validation)"""
        data = report["data"]
        
        # Format HTML view
        html = f"<h1>{report['path'].stem}</h1>\n"
        html += f"<p><strong>Typ:</strong> {report['type'].title()}</p>\n"
        html += f"<p><strong>Tidpunkt:</strong> {report['timestamp']}</p>\n"
        
        # Add statistics if available
        if "statistics" in data:
            html += "\n<h2>Statistik</h2>\n<ul>\n"
            for key, value in data["statistics"].items():
                if isinstance(value, (int, float)):
                    html += f"<li><strong>{key}:</strong> {value}</li>\n"
            html += "</ul>\n"
        
        self.html_view.setHtml(html)
        
        # Raw view
        self.raw_view.setPlainText(
            json.dumps(data, ensure_ascii=False, indent=2)
        )
    
    def show_context_menu(self, position):
        """Show context menu for reports"""
        items = self.report_tree.selectedItems()
        if not items:
            return
        
        item = items[0]
        cache_key = item.data(0, Qt.UserRole)
        report = self.report_cache.get(cache_key)
        
        if report:
            menu = QMenu()
            
            # Add actions based on report type
            if report["type"] == "command":
                open_product = QAction("Öppna produkt", self)
                open_product.triggered.connect(
                    lambda: self.report_selected.emit("product", {"product_id": report["product_id"]})
                )
                menu.addAction(open_product)
            
            # Add general actions
            copy_action = QAction("Kopiera rådata", self)
            copy_action.triggered.connect(
                lambda: self.raw_view.copy()
            )
            menu.addAction(copy_action)
            
            menu.exec_(self.report_tree.viewport().mapToGlobal(position))
    
    def show_command_response(self, command, product_id, response):
        """Display a new command response"""
        # Create report data
        report = {
            "type": "command",
            "subtype": command.strip("-"),
            "product_id": product_id,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "command": command,
                "product_id": product_id,
                "markdown_response": response
            }
        }
        
        # Add to cache
        cache_key = f"command_{product_id}_{command}"
        self.report_cache[cache_key] = report
        
        # Create tree item
        item = QTreeWidgetItem()
        item.setText(0, f"{product_id} - {command}")
        item.setText(1, report["timestamp"])
        item.setText(2, "Kommandosvar")
        item.setData(0, Qt.UserRole, cache_key)
        
        # Add to tree and select
        self.report_tree.insertTopLevelItem(0, item)
        item.setSelected(True)
        
        # Display report
        self.display_report(report)
    
    def show_preview(self, preview_type, preview_data):
        """
        Handle preview updates from JsonEditor.
        
        :param preview_type: The type of preview (e.g., 'jsonl')
        :param preview_data: A dictionary containing the preview content
        """
        try:
            # Format the preview data as a pretty-printed JSON string
            formatted = json.dumps(preview_data, indent=2, ensure_ascii=False)
            # Update the raw view with the formatted JSON
            self.raw_view.setPlainText(formatted)
            # If the preview data contains a markdown response, convert it; otherwise, show the JSON string in the HTML view
            if "markdown_response" in preview_data:
                html_content = markdown.markdown(preview_data["markdown_response"])
                self.html_view.setHtml(html_content)
            else:
                self.html_view.setPlainText(formatted)
        except Exception as e:
            logger.error(f"Error in show_preview: {str(e)}")
