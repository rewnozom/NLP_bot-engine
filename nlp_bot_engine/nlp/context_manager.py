# nlp_bot_engine/nlp/context_manager.py

import logging
from typing import Dict, List, Any, Optional, Tuple

from ..core.config import BotConfig

logger = logging.getLogger(__name__)

class ContextManager:
    """
    Hanterar konversationskontext och referensupplösning.
    Spårar tidigare frågor, aktiva produkter och dialogstatus.
    """
    
    def __init__(self, config: BotConfig):
        """
        Initialisera kontexthanteraren
        
        Args:
            config: Konfigurationsobjekt
        """
        self.config = config
        
    def analyze_context(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analysera frågan i dess kontext för bättre förståelse
        
        Args:
            query: Användarens fråga
            context: Kontextinformation
            
        Returns:
            Utökad kontextanalys
        """
        # Standardisera kontextparameter
        if context is None:
            context = {}
        
        # Analysresultat
        analysis = {
            "query_type": "unknown",
            "references": [],
            "resolved_entities": {},
            "suggested_products": [],
            "context_products": []
        }
        
        # Kolla om det finns en aktiv produkt i kontexten
        active_product_id = context.get("active_product_id")
        if active_product_id:
            analysis["context_products"].append({
                "product_id": active_product_id,
                "relation": "active"
            })
        
        # Identifiera kontextberoendetyp
        context_type = self.identify_context_type(query, context)
        analysis["query_type"] = context_type
        
        # Lös referenser om det är en kontextberoende fråga
        if context_type in ["follow_up", "reference", "comparison"]:
            references = self.identify_references(query)
            analysis["references"] = references
            
            # Lös upp referenserna mot kontexten
            resolved = self.resolve_references(references, context)
            analysis["resolved_entities"] = resolved
        
        # Lägg till dialoghistorik
        if "query_history" in context:
            analysis["dialog_history"] = context["query_history"]
        
        # Lägg till tidigare intention om sådan finns
        if "previous_intent" in context:
            analysis["previous_intent"] = context["previous_intent"]
        
        return analysis
    
    def identify_context_type(self, query: str, context: Dict[str, Any]) -> str:
        """
        Identifiera typ av kontextberoende i frågan
        
        Args:
            query: Användarens fråga
            context: Kontextinformation
            
        Returns:
            Kontextberoendetyp
        """
        query_lower = query.lower()
        
        # Kontrollera för specifika referensord
        reference_terms = {
            "follow_up": ["mer", "fortsätt", "berätta mer", "och", "också"],
            "reference": ["den", "denna", "det", "dessa", "dom", "dom här", "den där", "detta"],
            "comparison": ["jämfört med", "kontra", "vs", "versus", "jämför", "skillnad", "skillnaden mellan"]
        }
        
        # Kolla om frågan innehåller referenstermer
        for context_type, terms in reference_terms.items():
            if any(term in query_lower for term in terms):
                return context_type
        
        # Kolla om det är en kort fråga utan specifik produkt (troligen uppföljning)
        if len(query_lower.split()) <= 3 and context.get("active_product_id"):
            return "follow_up"
        
        # Standardtyp om inget annat matchar
        return "independent"
    
    def identify_references(self, query: str) -> List[Dict[str, Any]]:
        """
        Identifiera referenser i texten (t.ex. "den", "denna", osv.)
        
        Args:
            query: Användarens fråga
            
        Returns:
            Lista med identifierade referenser
        """
        query_lower = query.lower()
        references = []
        
        # Definiera referenstyper och deras nyckelord
        reference_types = {
            "product": ["den", "denna", "den här", "produkten", "artikeln"],
            "property": ["det", "detta", "den egenskapen", "den funktionen"],
            "multiple": ["dessa", "de", "dom", "de här", "dom här", "produkterna"]
        }
        
        # Sök efter referenser i texten
        for ref_type, keywords in reference_types.items():
            for keyword in keywords:
                if keyword in query_lower:
                    # Hitta position i texten
                    start_pos = query_lower.find(keyword)
                    
                    references.append({
                        "type": ref_type,
                        "text": keyword,
                        "start": start_pos,
                        "end": start_pos + len(keyword)
                    })
        
        return references
    
    def resolve_references(self, references: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Lös upp identifierade referenser mot kontexten
        
        Args:
            references: Lista med identifierade referenser
            context: Kontextinformation
            
        Returns:
            Dict med upplösta referenser
        """
        resolved = {}
        
        for ref in references:
            ref_type = ref["type"]
            
            if ref_type == "product" and context.get("active_product_id"):
                # Lös "den"/"denna" till aktiv produkt
                resolved[ref["text"]] = {
                    "type": "product",
                    "product_id": context["active_product_id"]
                }
                
            elif ref_type == "property" and context.get("last_mentioned_property"):
                # Lös "det"/"detta" till senast nämnda egenskap
                resolved[ref["text"]] = {
                    "type": "property",
                    "property": context["last_mentioned_property"]
                }
                
            elif ref_type == "multiple" and context.get("mentioned_products"):
                # Lös "dessa"/"de" till tidigare nämnda produkter
                resolved[ref["text"]] = {
                    "type": "products",
                    "product_ids": context["mentioned_products"]
                }
        
        return resolved
    
    def update_context(self, current_context: Dict[str, Any], new_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uppdatera kontexten med ny information
        
        Args:
            current_context: Nuvarande kontextinformation
            new_info: Ny information att lägga till
            
        Returns:
            Uppdaterad kontextinformation
        """
        # Kopiera nuvarande kontext för att undvika att modifiera original
        updated_context = current_context.copy()
        
        # Uppdatera aktiv produkt om ny information finns
        if "product_id" in new_info:
            updated_context["active_product_id"] = new_info["product_id"]
            
            # Uppdatera listan över nämnda produkter
            mentioned_products = updated_context.get("mentioned_products", [])
            if new_info["product_id"] not in mentioned_products:
                mentioned_products.append(new_info["product_id"])
            updated_context["mentioned_products"] = mentioned_products
        
        # Uppdatera senast nämnda egenskap
        if "property" in new_info:
            updated_context["last_mentioned_property"] = new_info["property"]
        
        # Uppdatera senaste intention
        if "primary_intent" in new_info:
            updated_context["previous_intent"] = new_info["primary_intent"]
        
        # Uppdatera användarhistorik
        if "query" in new_info:
            query_history = updated_context.get("query_history", [])
            query_history.append(new_info["query"])
            
            # Begränsa historiken till senaste 10 frågor
            if len(query_history) > 10:
                query_history = query_history[-10:]
                
            updated_context["query_history"] = query_history
        
        return updated_context
    
    def extract_conversation_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrahera aktuell konversationsstatus
        
        Args:
            context: Kontextinformation
            
        Returns:
            Dict med konversationsstatus
        """
        state = {
            "active_product": context.get("active_product_id"),
            "dialog_stage": "unknown",
            "mentioned_products": context.get("mentioned_products", []),
            "previous_intent": context.get("previous_intent"),
            "session_duration": context.get("session_duration", 0)
        }
        
        # Bestäm dialogstadium baserat på historik och förekomst av aktiv produkt
        if not context.get("query_history"):
            state["dialog_stage"] = "initial"
        elif context.get("active_product_id"):
            if state["previous_intent"] in ["technical", "compatibility"]:
                state["dialog_stage"] = "detailed_inquiry"
            else:
                state["dialog_stage"] = "product_exploration"
        else:
            state["dialog_stage"] = "search"
        
        return state