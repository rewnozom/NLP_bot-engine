# modules/chat_frame.py

import os
import re
import logging
import markdown
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

from PySide6.QtCore import Qt, Signal, QSize, QTimer, QEvent
from PySide6.QtGui import QIcon, QFont, QColor, QPalette, QKeyEvent, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser, QLineEdit, QPushButton,
    QLabel, QComboBox, QScrollArea, QFrame, QSizePolicy, QMenu, 
    QSplitter, QToolButton, QMessageBox, QApplication
)

# Importera avancerad botmotor om tillgänglig, annars använd standard
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

class ChatBubble(QFrame):
    """
    Widget som representerar en chatbubbla för att visa meddelanden.
    
    Visar avsändare, meddelandetext och tidsstämpel med korrekt formatering
    och dynamisk storleksanpassning.
    """
    def __init__(self, message: Union[str, Dict[str, Any]], is_user: bool = False, 
                parent: Optional[QWidget] = None):
        """
        Initierar en ChatBubble.
        
        Args:
            message: Meddelandetexten eller ett objekt med nycklarna 'formatted_text' eller 'message'
            is_user: True om meddelandet kommer från användaren, annars False
            parent: Föräldrawidget
        """
        super().__init__(parent)
        
        # Extrahera texten om 'message' inte är en sträng
        if not isinstance(message, str):
            message = message.get("formatted_text", message.get("message", str(message)))
        
        # Ställ in stil för bubblans bakgrund och kant
        if is_user:
            self.setStyleSheet("""
                QFrame {
                    background-color: #DCF8C6;
                    border-radius: 10px;
                    border: 1px solid #c7e5b4;
                }
                QTextBrowser {
                    background-color: transparent;
                    color: #333333;
                }
            """)
            alignment = Qt.AlignRight
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #333333;
                    border-radius: 10px;
                    border: 1px solid #444444;
                }
                QTextBrowser {
                    background-color: transparent;
                    color: #FFFFFF;
                }
            """)
            alignment = Qt.AlignLeft
        
        # Skapa huvudlayout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        main_layout.setSpacing(5)
        
        # Lägg till etikett för avsändare med bättre formatering
        sender_text = "Du" if is_user else "Bot"
        sender_label = QLabel(sender_text)
        sender_label.setStyleSheet(f"""
            font-weight: bold;
            font-size: 13px;
            color: {'#1E8C3A' if is_user else '#7E7EFF'};
        """)
        sender_label.setAlignment(alignment)
        main_layout.addWidget(sender_label)
        
        # Omvandla text med markdown för bot-meddelanden om det inte redan är HTML
        # och säkerställ korrekt kodning/hantering av specialtecken
        if not is_user and not message.lstrip().startswith("<"):
            try:
                message = markdown.markdown(message)
            except Exception as e:
                logger.error(f"Fel vid markdown-omvandling: {str(e)}")
                # Fortsätt med originaltexten om omvandling misslyckas
        
        # Skapa och konfigurera meddelandewidget
        msg_widget = QTextBrowser()
        msg_widget.setReadOnly(True)
        msg_widget.setOpenExternalLinks(True)
        msg_widget.setFrameStyle(QFrame.NoFrame)
        msg_widget.document().setDocumentMargin(0)
        msg_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        msg_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Ställ in detaljerad formatering för rik text
        msg_widget.setStyleSheet("""
            QTextBrowser {
                border: none;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                line-height: 1.4;
            }
        """)
        
        # Använd setHtml för korrekt hantering av HTML-innehåll
        msg_widget.setHtml(message)
        
        # Justera höjden baserat på innehållet
        # Tvinga dokumentets layout att uppdateras först för korrekt beräkning
        msg_widget.document().setTextWidth(msg_widget.viewport().width())
        msg_widget.document().adjustSize()
        text_height = int(msg_widget.document().size().height())
        msg_widget.setMinimumHeight(text_height + 10)  # Lägg till marginal
        
        # Lägg till widget i huvudlayouten
        main_layout.addWidget(msg_widget)
        
        # Lägg till tidsstämpel
        timestamp = datetime.now().strftime("%H:%M")
        time_label = QLabel(timestamp)
        time_label.setStyleSheet("""
            color: #888888;
            font-size: 10px;
        """)
        time_label.setAlignment(Qt.AlignRight if is_user else Qt.AlignLeft)
        main_layout.addWidget(time_label)
        
        # Anpassa bubblan till innehållet
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.adjustSize()
    
    def resizeEvent(self, event):
        """Hantera storleksändringar för att säkerställa korrekt layoutuppdatering"""
        super().resizeEvent(event)
        # Leta efter QTextBrowser-widget och uppdatera dess layout
        for child in self.children():
            if isinstance(child, QTextBrowser):
                child.document().setTextWidth(child.viewport().width())
                child.setMinimumHeight(int(child.document().size().height()) + 10)
                break


class ChatFrame(QWidget):
    """
    Huvudwidget för chat-gränssnittet.
    
    Hanterar chat-historik, meddelandeinmatning och interaktion med bot-motorn.
    Stödjer både standard och avancerad NLP-botmotor.
    """
    # Signaler
    command_executed = Signal(str, str, object)  # kommando, produkt_id, svarsdata
    active_product_changed = Signal(str)  # product_id
    
    def __init__(self, config: Dict[str, Any], parent: Optional[QWidget] = None):
        """
        Initierar ChatFrame med konfiguration.
        
        Args:
            config: Konfigurationsparametrar för bot-motorn
            parent: Föräldrawidget
        """
        super().__init__(parent)
        self.config = config
        
        # Initiera botmotor - använd avancerad om tillgänglig
        if NLP_AVAILABLE:
            self.bot_engine = AdvancedBotEngine(config)
            logger.info("Avancerad NLP-botmotor initierad")
        else:
            self.bot_engine = BotEngine(config)
            logger.info("Standard-botmotor initierad")
        
        # Konversationskontext
        self.context = {
            "active_product_id": None,
            "query_history": [],
            "session_started": datetime.now().isoformat()
        }
        
        # Skapa användargränssnittet
        self.init_ui()
        
        # Visa välkomstmeddelande
        self.show_welcome_message()
    
    def init_ui(self):
        """Konstruera och konfigurera gränssnittets layout och komponenter."""
        # Konfigurera huvudlayout med marginaler
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Informationsrad (valfri) - visar aktiv produkt
        self.info_bar = QFrame()
        info_layout = QHBoxLayout(self.info_bar)
        info_layout.setContentsMargins(5, 3, 5, 3)
        
        self.active_product_label = QLabel("Ingen aktiv produkt")
        self.active_product_label.setStyleSheet("""
            background-color: #444444;
            color: #CCCCCC;
            border-radius: 4px;
            padding: 3px 8px;
            font-size: 12px;
        """)
        info_layout.addWidget(self.active_product_label)
        
        # Rensa chatt-knapp
        clear_button = QToolButton()
        clear_button.setIcon(QIcon.fromTheme("edit-clear", QIcon(":/icons/clear.png")))
        clear_button.setToolTip("Rensa chatt")
        clear_button.clicked.connect(self.clear_chat)
        info_layout.addWidget(clear_button)
        
        # Dölj informationsraden initialt
        self.info_bar.setVisible(False)
        main_layout.addWidget(self.info_bar)
        
        # Skapa chattområde med förbättrad scrollning
        self.create_chat_area()
        main_layout.addWidget(self.chat_area, 1)  # Ger växande vertikal plats
        
        # Inmatningsområde med förbättrad layout
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #2D2D30;
                border-radius: 8px;
                border: 1px solid #3E3E42;
            }
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 8, 8, 8)
        input_layout.setSpacing(8)
        
        # Kommandoval
        self.command_combo = QComboBox()
        self.command_combo.addItem("Chat", "")
        self.command_combo.addItem("Tekniska detaljer (-t)", "-t")
        self.command_combo.addItem("Kompatibilitet (-c)", "-c")
        self.command_combo.addItem("Sammanfattning (-s)", "-s")
        self.command_combo.addItem("Fullständig info (-f)", "-f")
        self.command_combo.setStyleSheet("""
            QComboBox {
                background-color: #3E3E42;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px;
                min-width: 150px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #3E3E42;
                color: #FFFFFF;
                selection-background-color: #007ACC;
            }
        """)
        input_layout.addWidget(self.command_combo)
        
        # Textfält för användarinmatning
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Skriv kommando eller fråga här...")
        self.input_field.returnPressed.connect(self.send_message)
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #3E3E42;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
        """)
        input_layout.addWidget(self.input_field, 1)  # Ger växande horisontell plats
        
        # Skicka-knapp
        self.send_button = QPushButton("Skicka")
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1C86E0;
            }
            QPushButton:pressed {
                background-color: #0067C0;
            }
        """)
        input_layout.addWidget(self.send_button)
        
        main_layout.addWidget(input_frame)
        
        # Statusrad (valfri)
        self.status_bar = QLabel("Redo")
        self.status_bar.setStyleSheet("""
            color: #888888;
            font-size: 11px;
            padding: 2px;
        """)
        self.status_bar.setAlignment(Qt.AlignRight)
        main_layout.addWidget(self.status_bar)
        
        # Fokusera på inmatningsfältet
        self.input_field.setFocus()
    
    def create_chat_area(self):
        """Skapa och konfigurera chattområdet med förbättrad scrollning."""
        # Huvudcontainer för chattområdet
        self.chat_area = QScrollArea()
        self.chat_area.setWidgetResizable(True)
        self.chat_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.chat_area.setFrameShape(QFrame.NoFrame)
        self.chat_area.setStyleSheet("""
            QScrollArea {
                background-color: #1E1E1E;
                border-radius: 8px;
                border: 1px solid #3E3E42;
            }
            QScrollBar:vertical {
                border: none;
                background: #3E3E42;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #686868;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        # Container för chatbubblor med förbättrad layout
        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background-color: #1E1E1E;")
        
        # Använd QVBoxLayout med förbättrade layoutegenskaper
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_layout.setSpacing(15)  # Mer utrymme mellan bubblor
        self.chat_layout.setContentsMargins(15, 15, 15, 15)  # Marginaler på alla sidor
        
        self.chat_area.setWidget(self.chat_container)
    
    def show_welcome_message(self):
        """Visa välkomstmeddelande när chatten startar."""
        welcome_message = """
# Välkommen till Produktbotten!

Jag kan hjälpa dig med information om våra produkter. Du kan:

- Söka efter produkter genom att beskriva vad du letar efter
- Ställa frågor om tekniska specifikationer
- Få information om kompatibilitet med andra produkter
- Använda kommandon för specifik information

**Tips:** Välj ett kommando i rullgardinsmenyn eller skriv direkt i chattrutan.
"""
        # Visa välkomstmeddelande som botmeddelande
        self.add_bot_message(welcome_message)
    
    def send_message(self):
        """Hantera sändning av meddelande från inmatningsfältet."""
        text = self.input_field.text().strip()
        if not text:
            return
        
        self.input_field.clear()
        
        # Om ett kommando är valt, lägg till det före meddelandet om det saknas
        command = self.command_combo.currentData()
        if command and not text.startswith(command):
            text = f"{command} {text}"
        
        # Visa användarens meddelande och bearbeta det
        self.add_user_message(text)
        
        # Uppdatera status och visa att botten arbetar
        self.status_bar.setText("Bearbetar...")
        
        # Använd en timer för att hantera bearbetningen asynkront
        # Detta förhindrar att användargränssnittet fryser för komplexa förfrågningar
        QTimer.singleShot(50, lambda: self.process_message(text))
    
    def process_message(self, text: str):
        """
        Skicka meddelandet till bot-motorn och visa svaret.
        
        Args:
            text: Meddelandetext från användaren
        """
        try:
            # Uppdatera konversationshistorik
            self.context["query_history"].append(text)
            
            # Hantera strukturerade kommandon
            command_match = re.match(r'^(-[tcfs])\s+(\S+)(.*)$', text)
            if command_match:
                command, product_id, rest = command_match.groups()
                rest = rest.strip()
                
                # Olika hantering beroende på botmotor
                if NLP_AVAILABLE:
                    # Använd process_input för avancerad motor
                    response = self.bot_engine.process_input(text, self.context)
                else:
                    # Fallback för standardmotor
                    response = self.bot_engine.execute_command(command, product_id, rest)
                    # Konvertera till standardiserat format för vidare hantering
                    if isinstance(response, dict):
                        formatted_text = response.get("formatted_text", "")
                        if not formatted_text:
                            # Skapa formaterad text om sådan saknas
                            if "result" in response and response["result"]:
                                result = response["result"]
                                formatted_text = result.get("formatted_text", "")
                    else:
                        formatted_text = str(response)
                        response = {
                            "status": "success",
                            "command": command,
                            "product_id": product_id,
                            "formatted_text": formatted_text
                        }
                
                # Extrahera produkt-id från svar om tillgängligt
                product_id = response.get("product_id", product_id)
                if product_id:
                    self.update_active_product(product_id)
                
                # Visa botens svar
                self.add_bot_message(response)
                
                # Emitta signal för kommandoexekvering
                self.command_executed.emit(command, product_id, response)
            else:
                # Hantera naturligt språk
                if NLP_AVAILABLE:
                    # Använd process_input för avancerad motor
                    response = self.bot_engine.process_input(text, self.context)
                    
                    # Uppdatera kontexten med eventuellt ny information
                    if "analysis" in response:
                        analysis = response["analysis"]
                        if "primary_intent" in analysis:
                            self.context["previous_intent"] = analysis["primary_intent"]
                    
                    # Extrahera produkt-id från svar om tillgängligt
                    if "result" in response and response["result"]:
                        result = response["result"]
                        if "product_id" in result:
                            self.update_active_product(result["product_id"])
                else:
                    # Fallback för standardmotor
                    response = self.bot_engine.process_query(text, self.context.get("active_product_id"))
                    # Konvertera till standardiserat format
                    if not isinstance(response, dict):
                        response = {"formatted_text": str(response)}
                
                # Visa botens svar
                self.add_bot_message(response)
        except Exception as e:
            logger.error(f"Fel vid meddelandebearbetning: {str(e)}")
            error_message = f"Ett fel uppstod vid bearbetning av meddelandet: {str(e)}"
            self.add_bot_message({"formatted_text": error_message, "status": "error"})
        finally:
            # Återställ statusen
            self.status_bar.setText("Redo")
    
    def add_user_message(self, text: str):
        """
        Lägg till ett användarmeddelande i chattvyn.
        
        Args:
            text: Meddelandetexten
        """
        # Skapa användarbubbla med texten
        bubble = ChatBubble(text, is_user=True)
        
        # Lägg till i högerjusterad container för bättre layout
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()  # Placerar bubblan till höger
        layout.addWidget(bubble)
        
        # Lägg till behållaren i chattlayouten
        self.chat_layout.addWidget(container)
        self.scroll_to_bottom()
    
    def add_bot_message(self, message: Union[str, Dict[str, Any]]):
        """
        Lägg till ett botmeddelande i chattvyn.
        
        Args:
            message: Botens svar som text eller svarsobjekt med 'formatted_text'
        """
        # Skapa botbubbla med meddelandet
        bubble = ChatBubble(message, is_user=False)
        
        # Lägg till i vänsterjusterad container för bättre layout
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(bubble)
        layout.addStretch()  # Placerar bubblan till vänster
        
        # Lägg till behållaren i chattlayouten
        self.chat_layout.addWidget(container)
        self.scroll_to_bottom()
    
    def display_system_message(self, html: str):
        """
        Visa ett systemmeddelande i chattvyn.
        
        Args:
            html: HTML-innehållet för systemmeddelandet
        """
        # Skapa behållare för systemmeddelande med centrerad layout
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 10, 0, 10)
        
        # Skapa ram med systemmeddelande
        system_frame = QFrame()
        system_frame.setStyleSheet("""
            QFrame {
                background-color: #2D2D30;
                border-radius: 10px;
                border: 1px solid #3E3E42;
                padding: 8px;
            }
        """)
        frame_layout = QVBoxLayout(system_frame)
        frame_layout.setContentsMargins(10, 8, 10, 8)
        
        # Skapa meddelandewidget
        message = QTextBrowser()
        message.setHtml(html)
        message.setStyleSheet("""
            QTextBrowser {
                background-color: transparent;
                border: none;
                color: #BBBBBB;
                font-style: italic;
            }
        """)
        message.setMaximumHeight(message.document().size().height() + 20)
        frame_layout.addWidget(message)
        
        # Lägg till i centrerad layout
        layout.addStretch()
        layout.addWidget(system_frame)
        layout.addStretch()
        
        # Lägg till i chattområdet
        self.chat_layout.addWidget(container)
        self.scroll_to_bottom()
    
    def scroll_to_bottom(self):
        """Scrolla chattvyn till det nedre slutet med fördröjning för bättre rendering."""
        # Använd timer för att säkerställa att alla widgets är korrekt renderade
        QTimer.singleShot(50, lambda: (
            self.chat_area.verticalScrollBar().setValue(
                self.chat_area.verticalScrollBar().maximum()
            )
        ))
    
    def update_active_product(self, product_id: str):
        """
        Uppdatera aktiv produkt och visa i gränssnittet.
        
        Args:
            product_id: Produktens ID
        """
        if not product_id or self.context.get("active_product_id") == product_id:
            return
        
        # Uppdatera kontext
        self.context["active_product_id"] = product_id
        
        # Visa informationsraden om den är dold
        if not self.info_bar.isVisible():
            self.info_bar.setVisible(True)
        
        # Uppdatera etiketten
        self.active_product_label.setText(f"Aktiv produkt: {product_id}")
        
        # Visa systemmeddelande
        self.display_system_message(f"<p>Aktiv produkt ändrad till: <b>{product_id}</b></p>")
        
        # Emitta signal
        self.active_product_changed.emit(product_id)
    
    def clear_chat(self):
        """Rensa chatt-historiken med bekräftelsedialog."""
        reply = QMessageBox.question(
            self, 'Bekräfta', 'Är du säker på att du vill rensa chathistoriken?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Rensa chattlayout
            while self.chat_layout.count():
                item = self.chat_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            
            # Rensa konversationshistorik
            self.context["query_history"] = []
            
            # Visa bekräftelsemeddelande
            self.display_system_message("<p>Chathistoriken har rensats.</p>")
            
            # Visa välkomstmeddelande igen
            self.show_welcome_message()
    
    def keyPressEvent(self, event: QKeyEvent):
        """
        Hantera tangentbordshändelser för hela widgeten.
        
        Args:
            event: Tangentbordshändelsen
        """
        # Ctrl+L för att rensa chatten
        if event.key() == Qt.Key_L and event.modifiers() & Qt.ControlModifier:
            self.clear_chat()
        # Esc för att rensa inmatningsfältet
        elif event.key() == Qt.Key_Escape:
            self.input_field.clear()
        else:
            # Vidarebefordra andra händelser
            super().keyPressEvent(event)