# nlp_bot_engine/nlp/entity_extractor.py

import re
import logging
from typing import Dict, List, Any, Optional, Tuple, Union

from ..core.config import BotConfig
from .processor import NLPProcessor

logger = logging.getLogger(__name__)

class EntityExtractor:
    """
    Extraherar entiteter från text, inklusive produkter, egenskaper och ID:n.
    Kombinerar mönsterigenkänning, NER och kontextförståelse.
    """
    
    def __init__(self, config: BotConfig, nlp_processor: NLPProcessor):
        """
        Initialisera entitetsextraktorn
        
        Args:
            config: Konfigurationsobjekt
            nlp_processor: NLP-processor för textanalys
        """
        self.config = config
        self.nlp_processor = nlp_processor
    
    def extract_entities(self, text: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Extrahera alla entiteter från texten
        
        Args:
            text: Texten att analysera
            context: Kontextinformation
            
        Returns:
            Lista med extraherade entiteter
        """
        # Initialisera kontextparameter
        context = context or {}
        
        # Samla entiteter från olika metoder
        entities = []
        
        # 1. Extrahera med spaCy NER om tillgänglig
        if self.nlp_processor.nlp:
            spacy_entities = self.extract_spacy_entities(text)
            entities.extend(spacy_entities)
        
        # 2. Extrahera med regelbundna uttryck (för att fånga produkt-ID, EAN, etc.)
        regex_entities = self.extract_regex_entities(text)
        entities.extend(regex_entities)
        
        # 3. Extrahera produktentiteter från produktnamn
        product_entities = self.extract_product_entities(text)
        entities.extend(product_entities)
        
        # 4. Extrahera relaterade entiteter från kontexten
        if context:
            context_entities = self.extract_context_entities(text, context)
            entities.extend(context_entities)
        
        # 5. Sammanfoga entiteter så att liknande entiteter slås ihop
        entities = self.merge_overlapping_entities(entities)
        
        # 6. Berika entiteter med produktreferenser och information
        entities = self.enrich_entities(entities, context)
        
        return entities
    
    def extract_spacy_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrahera entiteter med spaCy NER
        
        Args:
            text: Texten att analysera
            
        Returns:
            Lista med spaCy-entiteter
        """
        if not self.nlp_processor.nlp:
            return []
        
        doc = self.nlp_processor.nlp(text)
        entities = []
        
        for ent in doc.ents:
            entity = {
                "type": ent.label_,
                "text": ent.text,
                "start": ent.start_char,
                "end": ent.end_char,
                "confidence": 0.8,  # Standardkonfidens för spaCy NER
                "source": "spacy"
            }
            
            # Normalisera entitetstyper till våra standardtyper

            if ent.label_ in ["EAN"]:
                entity["type"] = "EAN"
            elif ent.label_ in ["PRODUCT", "WORK_OF_ART", "ORG"]:
                entity["type"] = "PRODUCT"
            elif ent.label_ in ["DIMENSION", "QUANTITY"]:
                entity["type"] = "DIMENSION"
            elif ent.label_ in ["COMPATIBILITY"]:
                entity["type"] = "COMPATIBILITY"
            
            entities.append(entity)
        
        return entities
    
    def extract_regex_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrahera entiteter med regelbundna uttryck
        
        Args:
            text: Texten att analysera
            
        Returns:
            Lista med regex-extraherade entiteter
        """
        entities = []
        
        # Artikelnummer-mönster
        article_patterns = [
            r'(?i)art(?:ikel)?\.?(?:nr|nummer)\.?\s*[:=]?\s*([A-Z0-9\-]{5,15})',
            r'(?<!\d)(\d{8})(?!\d)',  # Åttasiffrigt artikelnummer
        ]
        
        # EAN-mönster
        ean_patterns = [
            r'(?i)EAN(?:-13)?[:.\-]?\s*(\d{13})(?!\d)',
            r'(?<!\d)(\d{13})(?!\d)',  # Fristående 13-siffrigt nummer
            r'(?i)EAN(?:-8)?[:.\-]?\s*(\d{8})(?!\d)',
        ]
        
        # Dimensionsmönster
        dimension_patterns = [
            r'(\d+(?:[.,]\d+)?)\s*(?:mm|cm|m|tum)',
        ]
        
        # Leta efter artikelnummer
        for pattern in article_patterns:
            for match in re.finditer(pattern, text):
                article_number = match.group(1)
                entities.append({
                    "type": "ARTICLE_NUMBER",
                    "text": article_number,
                    "start": match.start(1),
                    "end": match.end(1),
                    "confidence": 0.9,
                    "source": "regex"
                })
        
        # Leta efter EAN-koder
        for pattern in ean_patterns:
            for match in re.finditer(pattern, text):
                ean = match.group(1)
                # Validera EAN om möjligt
                if self.is_valid_ean(ean):
                    entities.append({
                        "type": "EAN",
                        "text": ean,
                        "start": match.start(1),
                        "end": match.end(1),
                        "confidence": 0.95,
                        "source": "regex"
                    })
        
        # Leta efter dimensioner
        for pattern in dimension_patterns:
            for match in re.finditer(pattern, text):
                dimension = match.group(0)  # Hela matchningen inkl. enhet
                entities.append({
                    "type": "DIMENSION",
                    "text": dimension,
                    "start": match.start(0),
                    "end": match.end(0),
                    "confidence": 0.85,
                    "source": "regex"
                })
        
        return entities
    
    def extract_product_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrahera produkter genom matchning mot produktnamnsindex
        
        Args:
            text: Texten att analysera
            
        Returns:
            Lista med extraherade produkter
        """
        entities = []
        text_lower = text.lower()
        
        # Få produktnamnsmappning från nlp_processor
        name_to_id_map = getattr(self.nlp_processor, 'name_to_id_map', {})
        
        if not name_to_id_map and hasattr(self.nlp_processor, 'data_manager'):
            # Försök att få produktnamn från datahanteraren om de finns där
            name_to_id_map = getattr(self.nlp_processor.data_manager, 'name_to_id_map', {})
        
        # Sök efter produktnamn i texten
        for name, product_id in name_to_id_map.items():
            if name in text_lower:
                # Hitta startpositionen (kan finnas på flera ställen)
                start_pos = text_lower.find(name)
                
                # Medan vi hittar fler förekomster
                while start_pos != -1:
                    entities.append({
                        "type": "PRODUCT",
                        "text": text[start_pos:start_pos+len(name)],  # Använd originalkapitalisering
                        "start": start_pos,
                        "end": start_pos + len(name),
                        "confidence": 0.9,
                        "source": "product_index",
                        "product_id": product_id
                    })
                    
                    # Sök efter nästa förekomst
                    start_pos = text_lower.find(name, start_pos + 1)
        
        return entities
    
    def extract_context_entities(self, text: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extrahera entiteter baserat på kontext
        
        Args:
            text: Texten att analysera
            context: Kontextinformation
            
        Returns:
            Lista med kontextbaserade entiteter
        """
        entities = []
        
        # Om aktiv produkt finns i kontexten
        active_product_id = context.get("active_product_id")
        if active_product_id:
            # Kolla om texten innehåller kontext-refererande ord som "den", "denna", etc.
            context_refs = ["den", "denna", "det", "produkten", "artikeln"]
            text_lower = text.lower().split()
            
            for ref in context_refs:
                if ref in text_lower:
                    # Hämta produktnamn om möjligt
                    product_name = self.get_product_name(active_product_id)
                    
                    entities.append({
                        "type": "PRODUCT",
                        "text": product_name or f"Produkt {active_product_id}",
                        "start": -1,  # Implicit referens, ingen position i texten
                        "end": -1,
                        "confidence": 0.8,
                        "source": "context",
                        "product_id": active_product_id,
                        "is_contextual_reference": True
                    })
                    break  # En referens räcker
        
        return entities
    
    def merge_overlapping_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sammanfoga överlappande entiteter
        
        Args:
            entities: Lista med entiteter
            
        Returns:
            Lista med sammanfogade entiteter
        """
        if not entities:
            return []
        
        # Sortera efter startposition och sedan efter längd (längre först vid samma position)
        sorted_entities = sorted(entities, key=lambda e: (e.get("start", -1), -len(e.get("text", ""))))
        
        merged = []
        current = sorted_entities[0]
        
        for entity in sorted_entities[1:]:
            current_end = current.get("end", -1)
            next_start = entity.get("start", -1)
            
            # Om de överlappar
            if current_end >= next_start and next_start >= 0 and current_end >= 0:
                # Behåll den med högre konfidens eller den större om lika
                if entity.get("confidence", 0) > current.get("confidence", 0):
                    current = entity
            else:
                merged.append(current)
                current = entity
        
        # Lägg till den sista
        merged.append(current)
        
        return merged
    
    def enrich_entities(self, entities: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Berika entiteter med ytterligare information
        
        Args:
            entities: Lista med entiteter
            context: Kontextinformation
            
        Returns:
            Lista med berikade entiteter
        """
        enriched = []
        
        for entity in entities:
            # Kopiera entiteten för att undvika att modifiera originalet
            enriched_entity = entity.copy()
            
            # Berika olika entitetstyper
            if entity["type"] == "PRODUCT":
                # Se om vi redan har product_id
                if "product_id" not in entity:
                    # Försök att hitta produkt-ID baserat på namn
                    product_id = self.find_product_id_by_name(entity["text"])
                    if product_id:
                        enriched_entity["product_id"] = product_id
            
            elif entity["type"] == "ARTICLE_NUMBER":
                # Validera och hitta produkt-ID
                article_number = entity["text"]
                product_id = self.find_product_id_by_article_number(article_number)
                if product_id:
                    enriched_entity["product_id"] = product_id
                    enriched_entity["type"] = "PRODUCT"  # Konvertera till produktentitet
            
            elif entity["type"] == "EAN":
                # Validera och hitta produkt-ID
                ean = entity["text"]
                product_id = self.find_product_id_by_ean(ean)
                if product_id:
                    enriched_entity["product_id"] = product_id
                    enriched_entity["type"] = "PRODUCT"  # Konvertera till produktentitet
            
            # Lägg till berikad version
            enriched.append(enriched_entity)
        
        return enriched
    
    def is_valid_ean(self, ean: str) -> bool:
        """
        Validera en EAN-kod med checksumma
        
        Args:
            ean: EAN-koden att validera
            
        Returns:
            True om giltig, annars False
        """
        if not ean.isdigit():
            return False
        
        # EAN-8, EAN-13, UPC (12 digits), or GTIN-14
        if len(ean) not in [8, 12, 13, 14]:
            return False
        
        # Checksumma-beräkning
        total = 0
        for i, digit in enumerate(reversed(ean[:-1])):
            multiplier = 3 if i % 2 == 0 else 1
            total += int(digit) * multiplier
            
        check_digit = (10 - (total % 10)) % 10
        
        return check_digit == int(ean[-1])
    
    def get_product_name(self, product_id: str) -> Optional[str]:
        """
        Hämta produktnamn för ett givet produkt-ID
        
        Args:
            product_id: Produktens ID
            
        Returns:
            Produktnamn eller None om det inte hittas
        """
        # Försök att få tillgång till produkt-index eller datahanterare
        data_manager = getattr(self.nlp_processor, 'data_manager', None)
        
        if data_manager:
            return data_manager.get_product_name(product_id)
        
        return None
    
    def find_product_id_by_name(self, name: str) -> Optional[str]:
        """
        Hitta produkt-ID baserat på namn
        
        Args:
            name: Produktnamnet
            
        Returns:
            Produkt-ID eller None om det inte hittas
        """
        name_lower = name.lower()
        
        # Få produktnamnsmappning
        name_to_id_map = getattr(self.nlp_processor, 'name_to_id_map', {})
        
        if not name_to_id_map and hasattr(self.nlp_processor, 'data_manager'):
            name_to_id_map = getattr(self.nlp_processor.data_manager, 'name_to_id_map', {})
        
        # Exakt matchning
        if name_lower in name_to_id_map:
            return name_to_id_map[name_lower]
        
        # Alternativt, försök med fuzzy matching
        best_match = None
        best_score = 0
        
        for product_name, product_id in name_to_id_map.items():
            # Beräkna likhet
            similarity = self.calculate_name_similarity(name_lower, product_name)
            
            if similarity > best_score and similarity > 0.8:  # Minst 80% match
                best_score = similarity
                best_match = product_id
        
        return best_match
    
    def find_product_id_by_article_number(self, article_number: str) -> Optional[str]:
        """
        Hitta produkt-ID baserat på artikelnummer
        
        Args:
            article_number: Artikelnumret
            
        Returns:
            Produkt-ID eller None om det inte hittas
        """
        # Försök att få tillgång till artikelnummer-index
        data_manager = getattr(self.nlp_processor, 'data_manager', None)
        
        if data_manager and hasattr(data_manager, 'indices'):
            article_index = data_manager.indices.get("article_numbers", {})
            
            if article_number in article_index:
                # Artikelnummerindex kan ha flera produkter per nummer
                products = article_index[article_number]
                if products and isinstance(products, list) and isinstance(products[0], dict):
                    return products[0].get("product_id")
        
        return None
    
    def find_product_id_by_ean(self, ean: str) -> Optional[str]:
        """
        Hitta produkt-ID baserat på EAN
        
        Args:
            ean: EAN-kod
            
        Returns:
            Produkt-ID eller None om det inte hittas
        """
        # Försök att få tillgång till EAN-index
        data_manager = getattr(self.nlp_processor, 'data_manager', None)
        
        if data_manager and hasattr(data_manager, 'indices'):
            ean_index = data_manager.indices.get("ean_numbers", {})
            
            if ean in ean_index:
                # EAN-index kan ha flera produkter per EAN
                products = ean_index[ean]
                if products and isinstance(products, list) and isinstance(products[0], dict):
                    return products[0].get("product_id")
        
        return None
    
    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Beräkna likhet mellan två produktnamn
        
        Args:
            name1: Första namnet
            name2: Andra namnet
            
        Returns:
            Likhetspoäng mellan 0 och 1
        """
        # Enkel tokenisering
        tokens1 = set(name1.lower().split())
        tokens2 = set(name2.lower().split())
        
        # Jaccard-likhet
        if not tokens1 or not tokens2:
            return 0
        
        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))
        
        return intersection / union