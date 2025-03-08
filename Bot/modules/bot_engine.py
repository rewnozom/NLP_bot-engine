# modules/bot_engine.py

import json
import re
import os
from pathlib import Path
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict

from .pattern_config import PatternConfig
from .data_processor import DataProcessor

logger = logging.getLogger(__name__)

class BotEngine:
    """
    Avancerad botmotor som hanterar både strukturerade kommandon och naturligt språk.
    Integrerar med DataProcessor för datahantering och PatternConfig för mönsterigenkänning.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pattern_config = PatternConfig()
        self.data_processor = DataProcessor(config)
        
        # Grundläggande sökvägar
        self.integrated_data_dir = Path(config.get("integrated_data_dir", "./integrated_data"))
        self.products_dir = self.integrated_data_dir / "products"
        
        # Ladda index och cache
        self.load_indices()
        self.response_cache = {}
        self.query_history = []
        
        # Konfigurera svarsmallar
        self.response_templates = {
            "technical": config.get("bot_settings", {}).get("response_template_tech", 
                "# Tekniska specifikationer för {product_name}\n\n" +
                "**Artikelnummer:** {product_id}\n\n{specifications}"),
            "compatibility": config.get("bot_settings", {}).get("response_template_compat",
                "# Kompatibilitetsinformation för {product_name}\n\n" +
                "**Artikelnummer:** {product_id}\n\n{compatibility}"),
            "summary": config.get("bot_settings", {}).get("response_template_summary",
                "# {product_name}\n\n**Artikelnummer:** {product_id}\n\n" +
                "{description}\n\n{specifications}\n\n{compatibility}")
        }
    
    def load_indices(self):
        """Laddar alla nödvändiga index för snabb sökning"""
        self.indices = {
            "article": self._load_index("article_numbers.json"),
            "ean": self._load_index("ean_numbers.json"),
            "compatibility": self._load_index("compatibility_map.json"),
            "technical": self._load_index("technical_specs_index.json"),
            "text": self._load_index("text_search_index.json"),
            "product_names": self._load_index("product_names.json")
        }
        
        # Bygg omvänt index för produktnamn till ID
        self.name_to_id_map = {}
        for product_id, data in self.indices.get("product_names", {}).items():
            name = data.get("name", "").lower()
            if name:
                self.name_to_id_map[name] = product_id
    
    def _load_index(self, index_name: str) -> Dict[str, Any]:
        """Laddar ett specifikt index från fil"""
        index_path = self.integrated_data_dir / "indices" / index_name
        try:
            if index_path.exists():
                with open(index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Kunde inte ladda index {index_name}: {str(e)}")
        return {}
    
    def process_input(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Huvudingång för all inmatning. Hanterar både kommandon och naturligt språk.
        
        Args:
            user_input: Användarens inmatning (kommando eller fråga)
            context: Eventuell kontextinformation (aktiv produkt, tidigare dialog, etc.)
            
        Returns:
            Dict med processad respons och metadata
        """
        # Standardisera inmatning
        user_input = user_input.strip()
        context = context or {}
        
        # Spara i historiken
        self.query_history.append({
            "timestamp": datetime.now().isoformat(),
            "input": user_input,
            "context": context
        })
        
        # Kontrollera om det är ett strukturerat kommando
        if command_match := re.match(r'^(-[tcfs])\s+(\S+)(.*)$', user_input):
            command, product_id, params = command_match.groups()
            return self.execute_command(command, product_id, params.strip(), context)
        
        # Om inte kommando, processa som naturligt språk
        return self.process_natural_language(user_input, context)
    
    def execute_command(self, command: str, product_id: str, 
                       params: str = "", context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Exekverar ett specifikt botkommando.
        
        Args:
            command: Kommandot (-t, -c, -s, -f)
            product_id: Produkt-ID att utföra kommandot på
            params: Eventuella extra parametrar
            context: Kontextinformation
            
        Returns:
            Dict med kommandots resultat och metadata
        """
        try:
            # Validera produkt-ID
            if not self.validate_product_id(product_id):
                return {
                    "status": "error",
                    "message": f"Ogiltig produkt: {product_id}",
                    "command": command,
                    "product_id": product_id
                }
            
            # Utför kommandot
            if command == "-t":
                result = self.get_technical_specs(product_id, params)
            elif command == "-c":
                result = self.get_compatibility_info(product_id, params)
            elif command == "-s":
                result = self.get_product_summary(product_id, params)
            elif command == "-f":
                result = self.get_full_info(product_id, params)
            else:
                return {
                    "status": "error",
                    "message": f"Okänt kommando: {command}",
                    "command": command,
                    "product_id": product_id
                }
            
            # Bygg respons
            response = {
                "status": "success",
                "command": command,
                "product_id": product_id,
                "params": params,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            
            # Cacha resultatet
            cache_key = f"{command}:{product_id}:{params}"
            self.response_cache[cache_key] = response
            
            return response
            
        except Exception as e:
            logger.error(f"Fel vid exekvering av kommando {command} för {product_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Ett fel uppstod: {str(e)}",
                "command": command,
                "product_id": product_id
            }




    def process_natural_language(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Processar naturliga språkfrågor genom att identifiera intention och extrahera relevant information.
        
        Args:
            query: Användarens fråga i naturligt språk
            context: Kontextinformation (aktiv produkt, etc.)
            
        Returns:
            Dict med processad respons och metadata
        """
        # Normalisera frågan
        query_lower = query.lower()
        
        # Identifiera intentioner i frågan
        intent_matches = {
            "compatibility": any(word in query_lower for word in [
                "passar", "kompatibel", "fungerar med", "kan användas med", 
                "passar till", "monteringsstolpe", "trycke", "tillsammans med"
            ]),
            "technical": any(word in query_lower for word in [
                "teknisk", "specifikation", "mått", "dimension", "vikt",
                "effekt", "spänning", "ström", "material"
            ]),
            "summary": any(word in query_lower for word in [
                "berätta om", "vad är", "information om", "beskriv",
                "sammanfatta", "översikt"
            ])
        }
        
        # Extrahera produktinformation
        product_info = self.extract_product_info(query)
        
        # Om ingen produkt hittades, använd aktiv produkt från kontext
        if not product_info and context and context.get("active_product_id"):
            product_info = {
                "product_id": context["active_product_id"],
                "match_type": "context"
            }
        
        # Om vi har en produkt, generera lämpligt svar
        if product_info:
            primary_intent = self.determine_primary_intent(intent_matches)
            
            response = {
                "status": "success",
                "query_type": "natural_language",
                "original_query": query,
                "product_info": product_info,
                "detected_intents": intent_matches,
                "primary_intent": primary_intent,
                "timestamp": datetime.now().isoformat()
            }
            
            # Generera svar baserat på primär intention
            if primary_intent == "compatibility":
                response["result"] = self.get_compatibility_info(product_info["product_id"])
            elif primary_intent == "technical":
                response["result"] = self.get_technical_specs(product_info["product_id"])
            else:  # default to summary
                response["result"] = self.get_product_summary(product_info["product_id"])
            
            return response
        
        # Om ingen produkt hittades, gör en generell sökning
        return self.handle_general_query(query, intent_matches)
    
    def extract_product_info(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extraherar produktinformation från text genom flera metoder:
        1. Direkta artikelnummer
        2. Produktnamn
        3. EAN-koder
        4. Fuzzy matching av produktnamn
        """
        # Sök efter artikelnummer
        article_match = re.search(r'(?<!\d)(\d{8})(?!\d)', text)
        if article_match:
            product_id = article_match.group(1)
            if self.validate_product_id(product_id):
                return {"product_id": product_id, "match_type": "article_number"}
        
        # Sök efter produktnamn i text
        text_lower = text.lower()
        for name, product_id in self.name_to_id_map.items():
            if name in text_lower:
                return {"product_id": product_id, "match_type": "product_name"}
        
        # Sök efter EAN-koder
        ean_match = re.search(r'(?<!\d)(\d{13})(?!\d)', text)
        if ean_match:
            ean = ean_match.group(1)
            if ean in self.indices["ean"]:
                product_id = self.indices["ean"][ean][0]["product_id"]
                return {"product_id": product_id, "match_type": "ean"}
        
        # Fuzzy matching av produktnamn som sista utväg
        best_match = self.find_best_product_match(text)
        if best_match:
            return {"product_id": best_match, "match_type": "fuzzy_match"}
        
        return None
    
    def get_technical_specs(self, product_id: str, params: str = "") -> Dict[str, Any]:
        """Hämtar och formaterar tekniska specifikationer för en produkt"""
        product_dir = self.products_dir / product_id
        tech_path = product_dir / "technical_specs.jsonl"
        
        if not tech_path.exists():
            return {
                "status": "error",
                "message": "Inga tekniska specifikationer tillgängliga"
            }
        
        try:
            # Läs tekniska specifikationer
            specs = []
            with open(tech_path, 'r', encoding='utf-8') as f:
                for line in f:
                    specs.append(json.loads(line))
            
            # Gruppera specifikationer efter kategori
            grouped_specs = defaultdict(list)
            for spec in specs:
                category = spec.get("category", "Övrigt")
                grouped_specs[category].append(spec)
            
            # Formatera specifikationer för presentation
            formatted_specs = []
            for category, category_specs in grouped_specs.items():
                formatted_specs.append(f"## {category}")
                for spec in category_specs:
                    name = spec.get("name", "")
                    value = spec.get("raw_value", "")
                    unit = spec.get("unit", "")
                    
                    if name and value:
                        formatted_spec = f"- **{name}:** {value}"
                        if unit and unit not in value:
                            formatted_spec += f" {unit}"
                        formatted_specs.append(formatted_spec)
            
            return {
                "status": "success",
                "specs": specs,
                "formatted_text": "\n\n".join(formatted_specs)
            }
            
        except Exception as e:
            logger.error(f"Fel vid läsning av tekniska specifikationer för {product_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Kunde inte läsa tekniska specifikationer: {str(e)}"
            }
    
    def get_compatibility_info(self, product_id: str, params: str = "") -> Dict[str, Any]:
        """Hämtar och formaterar kompatibilitetsinformation för en produkt"""
        product_dir = self.products_dir / product_id
        compat_path = product_dir / "compatibility.jsonl"
        
        if not compat_path.exists():
            return {
                "status": "error",
                "message": "Ingen kompatibilitetsinformation tillgänglig"
            }
        
        try:
            # Läs kompatibilitetsinformation
            relations = []
            with open(compat_path, 'r', encoding='utf-8') as f:
                for line in f:
                    relations.append(json.loads(line))
            
            # Gruppera relationer efter typ
            grouped_relations = defaultdict(list)
            for relation in relations:
                rel_type = relation.get("relation_type", "Övrigt")
                grouped_relations[rel_type].append(relation)
            
            # Formatera relationer för presentation
            formatted_relations = []
            for rel_type, type_relations in grouped_relations.items():
                formatted_relations.append(f"## {rel_type.title()}")
                for relation in type_relations:
                    related_product = relation.get("related_product", "")
                    numeric_ids = relation.get("numeric_ids", [])
                    
                    if related_product:
                        relation_text = f"- {related_product}"
                        if numeric_ids:
                            relation_text += f" (Art.nr: {numeric_ids[0]})"
                        formatted_relations.append(relation_text)
            
            return {
                "status": "success",
                "relations": relations,
                "formatted_text": "\n\n".join(formatted_relations)
            }
            
        except Exception as e:
            logger.error(f"Fel vid läsning av kompatibilitetsinformation för {product_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Kunde inte läsa kompatibilitetsinformation: {str(e)}"
            }
    
    def find_best_product_match(self, text: str) -> Optional[str]:
        """Hittar bästa produktmatchningen för en text genom fuzzy matching"""
        text_words = set(text.lower().split())
        best_score = 0
        best_match = None
        
        for name, product_id in self.name_to_id_map.items():
            name_words = set(name.split())
            # Beräkna överlappning mellan ord
            overlap = len(text_words & name_words)
            score = overlap / max(len(text_words), len(name_words))
            
            if score > best_score and score > 0.5:  # Minst 50% matchning
                best_score = score
                best_match = product_id
        
        return best_match
    
    def validate_product_id(self, product_id: str) -> bool:
        """Validerar att ett produkt-ID existerar och är giltigt"""
        product_dir = self.products_dir / product_id
        return product_dir.exists() and product_dir.is_dir()
    
    def determine_primary_intent(self, intent_matches: Dict[str, bool]) -> str:
        """Bestämmer primär intention baserat på matchningar"""
        # Om flera intentioner detekteras, prioritera i denna ordning
        priority_order = ["compatibility", "technical", "summary"]
        for intent in priority_order:
            if intent_matches.get(intent):
                return intent
        return "summary"  # Default till sammanfattning
    
    def handle_general_query(self, query: str, intent_matches: Dict[str, bool]) -> Dict[str, Any]:
        """Hanterar generella frågor där ingen specifik produkt identifierats"""
        # Gör en fritextsökning efter relevanta produkter
        matching_products = self.search_products(query)
        
        if matching_products:
            response = {
                "status": "success",
                "query_type": "general_search",
                "original_query": query,
                "detected_intents": intent_matches,
                "matching_products": matching_products[:5],  # Begränsa till top 5
                "suggestion": "Hittade följande produkter som kan vara relevanta:"
            }
            
            # Formatera produktlista
            formatted_products = ["## Relevanta produkter\n"]
            for product in matching_products[:5]:
                product_id = product["product_id"]
                name = product.get("name", f"Produkt {product_id}")
                score = product.get("score", 0)
                formatted_products.append(f"- **{name}** (Art.nr: {product_id})")
            
            response["formatted_text"] = "\n".join(formatted_products)
            return response
        
        return {
            "status": "no_results",
            "message": "Kunde inte hitta någon relevant information för din fråga."
        }
    
    def search_products(self, query: str) -> List[Dict[str, Any]]:
        """Söker efter produkter baserat på fritextfråga"""
        query_words = set(query.lower().split())
        results = []
        
        # Sök i text-index
        for word in query_words:
            if word in self.indices["text"]:
                for product_id in self.indices["text"][word]:
                    product_name = self.indices.get("product_names", {}).get(product_id, {}).get("name", "")
                    results.append({
                        "product_id": product_id,
                        "name": product_name,
                        "score": 1  # Kan förbättras med mer sofistikerad scoring
                    })
        
        # Ta bort dubletter och sortera efter relevans
        unique_results = {}
        for result in results:
            product_id = result["product_id"]
            if product_id not in unique_results or result["score"] > unique_results[product_id]["score"]:
                unique_results[product_id] = result
        
        return sorted(unique_results.values(), key=lambda x: x["score"], reverse=True)



    def get_product_summary(self, product_id: str, params: str = "") -> Dict[str, Any]:
        """Hämtar och formaterar en omfattande produktsammanfattning"""
        product_dir = self.products_dir / product_id
        summary_path = product_dir / "summary.jsonl"
        
        if not summary_path.exists():
            # Generate summary on-the-fly if no cached summary exists
            return self.generate_dynamic_summary(product_id)
        
        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary = json.loads(f.readline())
            
            # Format the summary
            formatted_sections = []
            
            # Add product name and basic info
            if summary.get("product_name"):
                formatted_sections.append(f"# {summary['product_name']}")
            else:
                formatted_sections.append(f"# Produkt {product_id}")
            
            # Add identifiers
            id_section = ["## Identifierare"]
            for id_type, values in summary.get("identifiers", {}).items():
                if values:
                    id_section.append(f"- **{id_type}:** {', '.join(values)}")
            if len(id_section) > 1:
                formatted_sections.extend(id_section)
            
            # Add description
            if summary.get("description"):
                formatted_sections.append("## Beskrivning")
                formatted_sections.append(summary["description"])
            
            # Add key specifications
            if summary.get("key_specifications"):
                formatted_sections.append("## Viktiga specifikationer")
                for spec in summary["key_specifications"]:
                    name = spec.get("name", "")
                    value = spec.get("value", "")
                    unit = spec.get("unit", "")
                    if name and value:
                        spec_text = f"- **{name}:** {value}"
                        if unit and unit not in value:
                            spec_text += f" {unit}"
                        formatted_sections.append(spec_text)
            
            # Add compatibility information
            if summary.get("key_compatibility"):
                formatted_sections.append("## Kompatibilitet")
                for relation in summary["key_compatibility"]:
                    rel_type = relation.get("type", "").replace("_", " ").title()
                    related_product = relation.get("related_product", "")
                    if rel_type and related_product:
                        compat_text = f"- **{rel_type}:** {related_product}"
                        if relation.get("numeric_ids"):
                            compat_text += f" (Art.nr: {relation['numeric_ids'][0]})"
                        formatted_sections.append(compat_text)
            
            return {
                "status": "success",
                "summary": summary,
                "formatted_text": "\n\n".join(formatted_sections)
            }
            
        except Exception as e:
            logger.error(f"Fel vid läsning av produktsammanfattning för {product_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Kunde inte läsa produktsammanfattning: {str(e)}"
            }

    def generate_dynamic_summary(self, product_id: str) -> Dict[str, Any]:
        """Genererar en dynamisk sammanfattning när ingen cache finns"""
        try:
            summary = {
                "product_id": product_id,
                "generated_at": datetime.now().isoformat(),
                "product_name": None,
                "description": None,
                "key_specifications": [],
                "key_compatibility": [],
                "identifiers": {}
            }
            
            # Get technical specs
            tech_result = self.get_technical_specs(product_id)
            if tech_result["status"] == "success":
                summary["key_specifications"] = tech_result.get("specs", [])[:5]  # Top 5 specs
            
            # Get compatibility info
            compat_result = self.get_compatibility_info(product_id)
            if compat_result["status"] == "success":
                summary["key_compatibility"] = compat_result.get("relations", [])[:5]  # Top 5 relations
            
            # Format and return
            return self.get_product_summary(product_id)  # Reuse formatting logic
        
        except Exception as e:
            logger.error(f"Fel vid generering av dynamisk sammanfattning för {product_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Kunde inte generera sammanfattning: {str(e)}"
            }

    def get_full_info(self, product_id: str, params: str = "") -> Dict[str, Any]:
        """Hämtar och formaterar fullständig produktinformation"""
        product_dir = self.products_dir / product_id
        full_info_path = product_dir / "full_info.md"
        
        if not full_info_path.exists():
            return {
                "status": "error",
                "message": "Ingen fullständig information tillgänglig"
            }
        
        try:
            with open(full_info_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                "status": "success",
                "content": content,
                "formatted_text": content  # Already in markdown format
            }
            
        except Exception as e:
            logger.error(f"Fel vid läsning av fullständig information för {product_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Kunde inte läsa fullständig information: {str(e)}"
            }

    def analyze_query_context(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyserar frågan och dess kontext för bättre förståelse"""
        analysis = {
            "query_type": "unknown",
            "identified_entities": [],
            "context_references": [],
            "suggested_responses": []
        }
        
        # Check for contextual references
        context_refs = {
            "den": "product_reference",
            "denna": "product_reference",
            "det": "property_reference",
            "dessa": "multiple_reference"
        }
        
        words = query.lower().split()
        for word in words:
            if word in context_refs:
                analysis["context_references"].append({
                    "word": word,
                    "type": context_refs[word]
                })
        
        # Try to identify specific aspects being asked about
        aspect_patterns = {
            "mått": "dimensions",
            "storlek": "dimensions",
            "effekt": "power",
            "spänning": "voltage",
            "passar": "compatibility",
            "fungerar": "compatibility",
            "material": "material",
            "färg": "color"
        }
        
        for word in words:
            if word in aspect_patterns:
                analysis["identified_entities"].append({
                    "type": "aspect",
                    "value": aspect_patterns[word]
                })
        
        # Determine query type
        if analysis["context_references"]:
            analysis["query_type"] = "contextual"
        elif any(e["type"] == "aspect" for e in analysis["identified_entities"]):
            analysis["query_type"] = "aspect_specific"
        else:
            analysis["query_type"] = "general"
        
        return analysis

    def build_response(self, response_type: str, data: Dict[str, Any], context: Dict[str, Any] = None) -> str:
        """Bygger ett formaterat svar baserat på typ och data"""
        if response_type in self.response_templates:
            template = self.response_templates[response_type]
            
            # Get product name
            product_id = data.get("product_id")
            product_name = self.indices.get("product_names", {}).get(product_id, {}).get("name", f"Produkt {product_id}")
            
            # Replace template variables
            response = template.format(
                product_name=product_name,
                product_id=product_id,
                specifications=data.get("formatted_text", ""),
                compatibility=data.get("formatted_text", ""),
                description=data.get("description", "")
            )
            
            return response
        
        return data.get("formatted_text", "")

    def handle_contextual_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Hanterar frågor som refererar till tidigare kontext"""
        # Analyze the query and its context
        analysis = self.analyze_query_context(query, context)
        
        # If we have an active product in context
        if context.get("active_product_id"):
            product_id = context["active_product_id"]
            
            # If asking about a specific aspect
            if analysis["query_type"] == "aspect_specific":
                aspect = analysis["identified_entities"][0]["value"]
                if aspect in ["dimensions", "power", "voltage", "material", "color"]:
                    return self.get_technical_specs(product_id)
                elif aspect == "compatibility":
                    return self.get_compatibility_info(product_id)
            
            # Default to summary for general questions about the active product
            return self.get_product_summary(product_id)
        
        return {
            "status": "error",
            "message": "Kunde inte förstå frågan i nuvarande kontext"
        }

