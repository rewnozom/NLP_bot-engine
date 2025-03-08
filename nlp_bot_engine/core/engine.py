# nlp_bot_engine/core/engine.py

import os
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from .config import BotConfig
from .data_manager import DataManager
from ..nlp.processor import NLPProcessor
from ..nlp.intent_analyzer import IntentAnalyzer
from ..nlp.entity_extractor import EntityExtractor
from ..nlp.context_manager import ContextManager
from ..dialog.response_generator import ResponseGenerator

logger = logging.getLogger(__name__)

class AdvancedBotEngine:
    """
    Avancerad botmotor med NLP-förmågor för att hantera komplexa och vaga frågor.
    Integrerar olika komponenter för språkförståelse, intentionsanalys och dynamisk svarshantering.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialisera botmotorn med konfiguration
        
        Args:
            config: Konfigurationsparametrar (använder standardvärden om None)
        """
        # Ladda konfiguration
        self.config = BotConfig(config or {})
        
        # Initiera datahanterare för index och produktdata
        self.data_manager = DataManager(self.config)
        
        # Initiera NLP-komponenter
        self.nlp_processor = NLPProcessor(self.config)
        self.intent_analyzer = IntentAnalyzer(self.config, self.nlp_processor)
        self.entity_extractor = EntityExtractor(self.config, self.nlp_processor)
        self.context_manager = ContextManager(self.config)
        
        # Initiera svarsgenereringen
        self.response_generator = ResponseGenerator(self.config)
        
        # Statistik och loggning
        self.stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "command_queries": 0,
            "natural_language_queries": 0,
            "ambiguous_queries": 0,
            "failures": 0,
            "start_time": datetime.now()
        }
        
        # Historik för konversationer
        self.query_history = []
        
        # Cacheminne för tidigare svar för att förbättra prestanda
        self.response_cache = {}
        
        logger.info("AdvancedBotEngine initialiserad")
        
    def process_input(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Huvudingång för all användarinmatning. Hanterar både direkta kommandon och naturligt språk.
        
        Args:
            user_input: Användarens fråga eller kommando
            context: Kontextinformation som aktiv produkt, användarhistorik, etc.
            
        Returns:
            Svarsobjekt med statusuppdatering och formaterad text
        """
        # Standardisera indata
        user_input = user_input.strip()
        context = context or {}
        
        # Uppdatera statistik
        self.stats["total_queries"] += 1
        
        # Spara till historik
        query_entry = {
            "timestamp": datetime.now().isoformat(),
            "input": user_input,
            "context": context.copy()  # Kopiera för att undvika referensproblem
        }
        self.query_history.append(query_entry)
        
        # Uppdatera kontext med historik
        if "query_history" not in context:
            context["query_history"] = []
        context["query_history"].append(user_input)
        
        # Kolla för strukturerade kommandon först
        command_match = re.match(r'^(-[tcfs])\s+(\S+)(.*)$', user_input)
        if command_match:
            self.stats["command_queries"] += 1
            command, product_id, params = command_match.groups()
            return self.execute_command(command, product_id, params.strip(), context)
        
        # Om inte kommando, vidare till NLP-processning för naturligt språk
        self.stats["natural_language_queries"] += 1
        return self.process_natural_language(user_input, context)
    
    def execute_command(self, command: str, product_id: str, params: str = "", 
                       context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Utför ett specifikt botkommando
        
        Args:
            command: Kommandotyp (-t, -c, -s, -f)
            product_id: Produktens ID
            params: Extra parametrar
            context: Kontextinformation
            
        Returns:
            Svarsobjekt med status och resultat
        """
        try:
            # Validera produkt-ID
            if not self.data_manager.validate_product_id(product_id):
                return {
                    "status": "error",
                    "message": f"Ogiltig produkt: {product_id}",
                    "command": command,
                    "product_id": product_id
                }
            
            # Sätt aktiv produkt i kontext
            if context is None:
                context = {}
            context["active_product_id"] = product_id
            
            # Kolla om vi har resultatet i cacheminnet
            cache_key = f"{command}:{product_id}:{params}"
            if cache_key in self.response_cache:
                logger.debug(f"Hittade cacheminne för {cache_key}")
                return self.response_cache[cache_key]
            
            # Utför kommandot
            if command == "-t":
                result = self.data_manager.get_technical_specs(product_id, params)
            elif command == "-c":
                result = self.data_manager.get_compatibility_info(product_id, params)
            elif command == "-s":
                result = self.data_manager.get_product_summary(product_id, params)
            elif command == "-f":
                result = self.data_manager.get_full_info(product_id, params)
            else:
                return {
                    "status": "error",
                    "message": f"Okänt kommando: {command}",
                    "command": command,
                    "product_id": product_id
                }
            
            # Generera ett rikt formaterat svar
            response = {
                "status": "success",
                "command": command,
                "product_id": product_id,
                "params": params,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            
            # Lägg till formaterad text från svarsgenereringen
            response_type = command[1]  # Extrahera t/c/s/f
            response["formatted_text"] = self.response_generator.format_command_response(
                response_type, product_id, result, context
            )
            
            # Cacha resultatet
            self.response_cache[cache_key] = response
            
            # Uppdatera statistik
            self.stats["successful_queries"] += 1
            
            return response
            
        except Exception as e:
            logger.error(f"Fel vid exekvering av kommando {command} för {product_id}: {str(e)}")
            self.stats["failures"] += 1
            return {
                "status": "error",
                "message": f"Ett fel uppstod: {str(e)}",
                "command": command,
                "product_id": product_id
            }
    
    def process_natural_language(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Processera naturligt språk med avancerad NLP och kontextförstående
        
        Args:
            query: Användarens fråga
            context: Kontextinformation
            
        Returns:
            Svarsobjekt med analysresultat och formaterad text
        """
        try:
            # Initiera kontext om den saknas
            context = context or {}
            
            # 1. Utför NLP-förbehandling
            processed_text = self.nlp_processor.preprocess(query)
            
            # 2. Analysera kontext och lös referenser
            context_analysis = self.context_manager.analyze_context(query, context)
            
            # 3. Extrahera entiteter (produkter, egenskaper, etc.)
            entities = self.entity_extractor.extract_entities(processed_text, context)
            
            # 4. Analysera intention (vad användaren vill göra)
            intent_analysis = self.intent_analyzer.analyze_intent(processed_text, entities, context)
            
            # 5. Kombinera all information i analysobjekt
            analysis = {
                "original_query": query,
                "processed_text": processed_text,
                "entities": entities,
                "intents": intent_analysis["intents"],
                "primary_intent": intent_analysis["primary_intent"],
                "confidence": intent_analysis["confidence"],
                "context_references": context_analysis.get("references", []),
                "resolved_entities": context_analysis.get("resolved_entities", {})
            }
            
            # 6. Hantera osäkerhet om konfidensen är låg
            if intent_analysis["confidence"] < self.config.min_confidence:
                return self.handle_low_confidence(analysis, context)
                
            # 7. Hämta produktinformation eller utför sökning baserat på analys
            result = self.execute_intent(analysis, context)
            
            # 8. Generera anpassat svar baserat på intention och resultat
            response = {
                "status": "success" if result.get("status") != "error" else "error",
                "query_type": "natural_language",
                "timestamp": datetime.now().isoformat(),
                "analysis": analysis,
                "result": result
            }
            
            # Generera formaterad text från svarsgenereringen
            response["formatted_text"] = self.response_generator.generate_nl_response(
                analysis, result, context
            )
            
            # Uppdatera statistik
            if response["status"] == "success":
                self.stats["successful_queries"] += 1
            else:
                self.stats["failures"] += 1
            
            return response
            
        except Exception as e:
            logger.error(f"Fel vid processning av naturligt språk: {str(e)}")
            self.stats["failures"] += 1
            return {
                "status": "error",
                "message": f"Ett fel uppstod vid analys av din fråga: {str(e)}",
                "query": query
            }
    
    def handle_low_confidence(self, analysis: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hantera osäkerhetsfall där botens konfidens är låg
        
        Args:
            analysis: Analysresultat från NLP-stegen
            context: Kontextinformation
            
        Returns:
            Svarsobjekt med klargörande frågor eller bästa gissning
        """
        self.stats["ambiguous_queries"] += 1
        
        # Extracta huvudintention och konfidens
        primary_intent = analysis["primary_intent"]
        confidence = analysis["confidence"]
        
        # Mycket låg konfidens - be om förtydligande
        if confidence < 0.4:
            # Generera klargörande frågor
            clarification_questions = self.generate_clarification_questions(analysis, context)
            
            return {
                "status": "needs_clarification",
                "query_type": "clarification_request",
                "analysis": analysis,
                "clarification_questions": clarification_questions,
                "formatted_text": self.response_generator.format_clarification_request(
                    analysis, clarification_questions, context
                )
            }
        
        # Medelhög konfidens - gör en kvalificerad gissning men informera användaren
        return {
            "status": "low_confidence",
            "query_type": "best_guess",
            "analysis": analysis,
            "result": self.execute_intent(analysis, context, ignore_confidence=True),
            "confidence": confidence,
            "alternative_intents": analysis["intents"][:3],  # Top 3 alternativa intentioner
            "formatted_text": self.response_generator.format_low_confidence_response(
                analysis, self.execute_intent(analysis, context, ignore_confidence=True), context
            )
        }
    
    def generate_clarification_questions(self, analysis: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generera lämpliga uppföljningsfrågor baserat på osäkerheten
        
        Args:
            analysis: Analysresultat från NLP-stegen
            context: Kontextinformation
            
        Returns:
            Lista med klargörande frågor och deras alternativ
        """
        questions = []
        
        # Kolla om vi har produktkandidater men är osäkra
        product_entities = [e for e in analysis["entities"] if e["type"] == "PRODUCT"]
        if product_entities and len(product_entities) > 1:
            # Flera produktkandidater - be användaren välja
            options = [{"id": e.get("product_id", ""), "name": e["text"]} for e in product_entities[:4]]
            questions.append({
                "type": "product_selection",
                "text": "Vilken av dessa produkter menar du?",
                "options": options
            })
        elif not product_entities and "PRODUCT" in analysis["entities"]:
            # Vag produktbeskrivning - föreslå sökningar
            suggested_searches = self.data_manager.suggest_products(analysis["original_query"])
            if suggested_searches:
                options = [{"id": p["product_id"], "name": p["name"]} for p in suggested_searches[:4]]
                questions.append({
                    "type": "product_suggestion",
                    "text": "Jag är inte säker på vilken produkt du menar. Är det någon av dessa?",
                    "options": options
                })
        
        # Kolla om intentionen är oklar
        if not analysis["primary_intent"] or analysis["confidence"] < 0.3:
            # Oklart vad användaren vill veta - ge alternativ
            questions.append({
                "type": "intent_selection",
                "text": "Vad vill du veta om produkten?",
                "options": [
                    {"id": "technical", "name": "Tekniska specifikationer"},
                    {"id": "compatibility", "name": "Kompatibilitetsinformation"},
                    {"id": "summary", "name": "Allmän produktinformation"},
                    {"id": "search", "name": "Sök efter produkter"}
                ]
            })
        
        # Om inga specifika frågor kunde genereras, ge en generell uppmaning
        if not questions:
            questions.append({
                "type": "general_clarification",
                "text": "Jag förstod inte riktigt din fråga. Kan du omformulera den eller vara mer specifik?",
                "options": []
            })
        
        return questions
    
    def execute_intent(self, analysis: Dict[str, Any], context: Dict[str, Any], 
                      ignore_confidence: bool = False) -> Dict[str, Any]:
        """
        Utför den identifierade intentionen baserat på analys
        
        Args:
            analysis: Analysresultat från NLP-stegen
            context: Kontextinformation
            ignore_confidence: Om True, utför även vid låg konfidens
            
        Returns:
            Resultat från den intentionsbaserade åtgärden
        """
        # Om konfidensen är för låg och vi inte ignorerar det, returnera ett tomt resultat
        if not ignore_confidence and analysis["confidence"] < self.config.min_confidence:
            return {"status": "low_confidence", "message": "Osäker tolkning av frågan"}
        
        # Identifiera huvudintention
        intent = analysis["primary_intent"]
        
        # Hämta produkt-ID om det finns i analysen
        product_id = None
        for entity in analysis["entities"]:
            if entity["type"] == "PRODUCT" and entity.get("product_id"):
                product_id = entity["product_id"]
                break
        
        # Alternativt, använd aktiv produkt från kontext
        if not product_id and context.get("active_product_id"):
            product_id = context["active_product_id"]
        
        # Utför intentionen om vi har en produkt
        if product_id:
            if intent == "technical":
                return self.data_manager.get_technical_specs(product_id)
            elif intent == "compatibility":
                return self.data_manager.get_compatibility_info(product_id)
            elif intent == "summary":
                return self.data_manager.get_product_summary(product_id)
            elif intent == "search":
                # Sök efter relaterade produkter
                search_terms = " ".join([e["text"] for e in analysis["entities"] if e["type"] != "PRODUCT"])
                return self.data_manager.search_products(search_terms)
            else:
                # Default till sammanfattning om intentionen är oklar
                return self.data_manager.get_product_summary(product_id)
        
        # Om vi inte har en produkt men intentionen är sökning
        if intent == "search" or not product_id:
            search_query = analysis["processed_text"]
            return self.data_manager.search_products(search_query)
        
        # Fallback om inget matchade
        return {
            "status": "error",
            "message": "Kunde inte utföra någon åtgärd baserat på din fråga. Var mer specifik eller ange en produkt."
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Hämta statistik om botens användning
        
        Returns:
            Statistikobjekt med användningsdata
        """
        stats = self.stats.copy()
        stats["uptime_seconds"] = (datetime.now() - stats["start_time"]).total_seconds()
        
        # Beräkna framgångsfrekvens
        if stats["total_queries"] > 0:
            stats["success_rate"] = stats["successful_queries"] / stats["total_queries"]
        else:
            stats["success_rate"] = 0
            
        return stats
    
    def learn_from_interaction(self, query: str, response: Dict[str, Any], 
                              user_feedback: Dict[str, Any] = None) -> None:
        """
        Lär från interaktioner för att förbättra framtida svar
        
        Args:
            query: Ursprunglig fråga
            response: Botens svar
            user_feedback: Användarens feedback (t.ex. var svaret hjälpsamt)
        """
        # Implementera lärande mekanismer här
        pass