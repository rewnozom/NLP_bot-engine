# nlp_bot_engine/nlp/intent_analyzer.py

import logging
from typing import Dict, List, Any, Optional, Tuple

from ..core.config import BotConfig
from .processor import NLPProcessor

logger = logging.getLogger(__name__)

class IntentAnalyzer:
    """
    Analyserar användarfrågor för att identifiera intention.
    Kombinerar nyckelordsmatchning, kontextanalys och semantisk analys.
    """
    
    def __init__(self, config: BotConfig, nlp_processor: NLPProcessor):
        """
        Initialisera intentionsanalysator
        
        Args:
            config: Konfigurationsobjekt
            nlp_processor: NLP-processor för textanalys
        """
        self.config = config
        self.nlp_processor = nlp_processor
        
        # Fördefinierade intentionsprototyper för semantisk matchning
        self.intent_prototypes = {
            "technical": [
                "Vad är de tekniska specifikationerna för denna produkt?",
                "Vilka mått har produkten?",
                "Hur mycket väger produkten?",
                "Vilket material är produkten tillverkad av?",
                "Vad är spänningen för produkten?"
            ],
            "compatibility": [
                "Är denna produkt kompatibel med andra produkter?",
                "Passar produkten till min existerande installation?",
                "Vilka andra produkter fungerar med denna?",
                "Kan jag använda denna med produkt X?",
                "Vilka trycken passar denna produkt?"
            ],
            "summary": [
                "Berätta om denna produkt",
                "Vad är detta för produkt?",
                "Ge mig en översikt över produkten",
                "Vilken information finns om produkten?",
                "Vad används denna produkt till?"
            ],
            "search": [
                "Jag letar efter en produkt som...",
                "Hitta produkter som liknar...",
                "Sök efter produkter som...",
                "Finns det några produkter för...",
                "Jag behöver en produkt som kan..."
            ]
        }
        
        # Generera embeddings för intentionsprototyper om möjligt
        self.intent_embeddings = {}
        
        if self.nlp_processor.embedding_model:
            for intent, examples in self.intent_prototypes.items():
                # Använd genomsnitt av alla exempel
                embeddings = []
                for example in examples:
                    embedding = self.nlp_processor.get_embeddings(example)
                    if embedding:
                        embeddings.append(embedding)
                
                if embeddings:
                    import numpy as np
                    # Beräkna genomsnitt av alla embeddings
                    self.intent_embeddings[intent] = np.mean(embeddings, axis=0).tolist()
    
    def analyze_intent(self, text: str, entities: List[Dict[str, Any]], 
                      context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analysera användartexten för att identifiera huvudsaklig intention
        
        Args:
            text: Användartexten
            entities: Extraherade entiteter
            context: Kontextinformation
            
        Returns:
            Dict med intentionsanalys
        """
        # 1. Nyckelordsbaserad intentionsidentifiering
        keyword_intents = self.nlp_processor.detect_intent_keywords(text)
        
        # 2. Semantisk intentionsidentifiering (om embeddings finns)
        semantic_intents = self.detect_semantic_intent(text)
        
        # 3. Entitetsbaserad intentionsidentifiering
        entity_intents = self.detect_entity_based_intent(entities)
        
        # 4. Kontextbaserad intentionsidentifiering
        context_intents = self.detect_context_based_intent(context)
        
        # 5. Kombinera alla metoder med viktning
        combined_intents = self.combine_intent_scores(
            keyword_intents, semantic_intents, entity_intents, context_intents
        )
        
        # 6. Identifiera primär intention med konfidens
        primary_intent, confidence = self.determine_primary_intent(combined_intents)
        
        # 7. Sortera intentioner efter poäng
        sorted_intents = [
            {"intent": intent, "score": score}
            for intent, score in sorted(combined_intents.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return {
            "intents": sorted_intents,
            "primary_intent": primary_intent,
            "confidence": confidence,
            "keyword_based": keyword_intents,
            "semantic_based": semantic_intents,
            "entity_based": entity_intents,
            "context_based": context_intents
        }
    
    def detect_semantic_intent(self, text: str) -> Dict[str, float]:
        """
        Detektera intention baserat på semantisk likhet
        
        Args:
            text: Texten att analysera
            
        Returns:
            Dict med intentioner och deras poäng
        """
        # Om vi inte har embeddings, returnera tomma poäng
        if not self.intent_embeddings:
            return {intent: 0.0 for intent in self.intent_prototypes}
        
        # Skapa embedding för texten
        text_embedding = self.nlp_processor.get_embeddings(text)
        
        if not text_embedding:
            return {intent: 0.0 for intent in self.intent_prototypes}
        
        # Beräkna similarity med varje intentionsprototyp
        intent_scores = {}
        
        import numpy as np
        text_vec = np.array(text_embedding)
        
        for intent, prototype_vec in self.intent_embeddings.items():
            # Beräkna cosine similarity
            proto_vec = np.array(prototype_vec)
            
            dot_product = np.dot(text_vec, proto_vec)
            text_norm = np.linalg.norm(text_vec)
            proto_norm = np.linalg.norm(proto_vec)
            
            if text_norm == 0 or proto_norm == 0:
                similarity = 0.0
            else:
                similarity = dot_product / (text_norm * proto_norm)
            
            # Normalisera till [0,1]
            similarity = max(0.0, min(1.0, (similarity + 1) / 2))
            
            intent_scores[intent] = similarity
        
        return intent_scores
    
    def detect_entity_based_intent(self, entities: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Detektera intention baserat på extraherade entiteter
        
        Args:
            entities: Lista med extraherade entiteter
            
        Returns:
            Dict med intentioner och deras poäng
        """
        intent_scores = {
            "technical": 0.0,
            "compatibility": 0.0,
            "summary": 0.0,
            "search": 0.0
        }
        
        # Sammanställ entitetstyper
        entity_types = [entity["type"] for entity in entities]
        entity_types_count = {etype: entity_types.count(etype) for etype in set(entity_types)}
        
        # Öka poäng baserat på entitetstyper
        if "DIMENSION" in entity_types_count:
            intent_scores["technical"] += 0.6 * min(entity_types_count["DIMENSION"], 3) / 3
        
        if "COMPATIBILITY" in entity_types_count:
            intent_scores["compatibility"] += 0.8
        
        if "PRODUCT" in entity_types_count:
            # Om många produkter nämns, troligen en sökning
            if entity_types_count["PRODUCT"] > 1:
                intent_scores["search"] += 0.5
            else:
                # Annars troligen en produktsummering eller teknisk info
                intent_scores["summary"] += 0.4
                intent_scores["technical"] += 0.3
        
        # Om det finns flera produkter och kompatibilitetstermer, troligen kompatibilitetsfråga
        if entity_types_count.get("PRODUCT", 0) > 1 and "COMPATIBILITY" in entity_types_count:
            intent_scores["compatibility"] += 0.3
        
        # Om inga specifika entiteter hittades, anta summering
        if not entity_types:
            intent_scores["summary"] += 0.2
        
        return intent_scores
    
    def detect_context_based_intent(self, context: Dict[str, Any]) -> Dict[str, float]:
        """
        Detektera intention baserat på konversationskontext
        
        Args:
            context: Kontextinformation
            
        Returns:
            Dict med intentioner och deras poäng
        """
        intent_scores = {
            "technical": 0.0,
            "compatibility": 0.0,
            "summary": 0.0,
            "search": 0.0
        }
        
        # Analysera tidigare meddelanden/kontext
        query_history = context.get("query_history", [])
        
        if query_history:
            # Titta på tidigare intentioner i konversationen
            if context.get("previous_intent") == "summary":
                # Om förra var summary, troligt att nästa är mer specifik
                intent_scores["technical"] += 0.2
                intent_scores["compatibility"] += 0.2
            
            elif context.get("previous_intent") == "technical":
                # Om förra var teknisk, troligt att fortsätta med tekniska frågor
                intent_scores["technical"] += 0.3
            
            elif context.get("previous_intent") == "compatibility":
                # Om förra var kompabilitet, troligt att fortsätta med kompatibilitet
                intent_scores["compatibility"] += 0.3
            
            # Kolla om användaren just sökt och nu frågar om en produkt
            if context.get("previous_intent") == "search" and context.get("active_product_id"):
                intent_scores["summary"] += 0.4
        
        # Om ingen historik finns, anta summering
        else:
            intent_scores["summary"] += 0.1
        
        return intent_scores
    
    def combine_intent_scores(self, keyword_intents: Dict[str, float], 
                             semantic_intents: Dict[str, float],
                             entity_intents: Dict[str, float],
                             context_intents: Dict[str, float]) -> Dict[str, float]:
        """
        Kombinera intentionspoäng från olika metoder med vikter
        
        Args:
            keyword_intents: Intentionspoäng från nyckelord
            semantic_intents: Intentionspoäng från semantisk analys
            entity_intents: Intentionspoäng från entiteter
            context_intents: Intentionspoäng från kontext
            
        Returns:
            Dict med kombinerade intentionspoäng
        """
        # Vikter för olika metoder
        method_weights = {
            "keyword": 0.35,
            "semantic": 0.30,
            "entity": 0.25,
            "context": 0.10
        }
        
        combined_scores = {}
        
        # Kombinera poäng för varje intention
        for intent in keyword_intents.keys():
            combined_scores[intent] = (
                keyword_intents.get(intent, 0.0) * method_weights["keyword"] +
                semantic_intents.get(intent, 0.0) * method_weights["semantic"] +
                entity_intents.get(intent, 0.0) * method_weights["entity"] +
                context_intents.get(intent, 0.0) * method_weights["context"]
            )
        
        return combined_scores
    
    def determine_primary_intent(self, intent_scores: Dict[str, float]) -> Tuple[str, float]:
        """
        Identifiera primär intention och dess konfidens
        
        Args:
            intent_scores: Dict med intentionspoäng
            
        Returns:
            Tuppel med primär intention och konfidenspoäng
        """
        if not intent_scores:
            return "summary", 0.1
        
        # Hitta intentionen med högst poäng
        primary_intent = max(intent_scores.items(), key=lambda x: x[1])
        intent_name, highest_score = primary_intent
        
        # Sortera alla poäng i fallande ordning
        sorted_scores = sorted(intent_scores.values(), reverse=True)
        
        # Beräkna konfidens baserat på skillnad från runner-up
        confidence = highest_score
        
        # Om det finns minst två intentioner, se på differensen
        if len(sorted_scores) > 1:
            confidence_margin = highest_score - sorted_scores[1]
            
            # Justera konfidensen baserat på marginal till närmaste konkurrent
            if confidence_margin < 0.1:
                # Liten marginal - minska konfidensen
                confidence = highest_score * 0.8
            elif confidence_margin > 0.3:
                # Stor marginal - öka konfidensen något
                confidence = min(1.0, highest_score * 1.1)
        
        return intent_name, confidence