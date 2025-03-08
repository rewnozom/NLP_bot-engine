# nlp_bot_engine/core/data_manager.py

import json
import os
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict

from .config import BotConfig

logger = logging.getLogger(__name__)

class DataManager:
    """
    Hanterar data och index för produkter och deras egenskaper.
    Ansvarar för att läsa, söka och extrahera produktinformation.
    """
    
    def __init__(self, config: BotConfig):
        """
        Initialisera datahanteraren med konfiguration
        
        Args:
            config: Konfigurationsobjekt
        """
        self.config = config
        
        # Grundläggande sökvägar
        self.integrated_data_dir = config.integrated_data_dir
        self.products_dir = config.products_dir
        
        # Ladda index
        self.indices = self.load_indices()
        
        # Bygg omvänt index för produktnamn till ID
        self.name_to_id_map = {}
        for product_id, data in self.indices.get("product_names", {}).items():
            name = data.get("name", "").lower()
            if name:
                self.name_to_id_map[name] = product_id
        
        # Cache för produktdata
        self.product_cache = {}
        
        logger.info(f"DataManager initialiserad med {len(self.name_to_id_map)} produkter")
    
    def load_indices(self) -> Dict[str, Dict[str, Any]]:
        """
        Ladda alla indexfiler för sökning och åtkomst
        
        Returns:
            Dict med alla index
        """
        index_types = [
            "article_numbers.json",
            "ean_numbers.json",
            "compatibility_map.json", 
            "technical_specs_index.json",
            "text_search_index.json",
            "product_names.json"
        ]
        
        # Initiera indices-dictionary
        indices = {}
        
        # Ladda varje indextyp
        for index_name in index_types:
            index_data = self._load_index(index_name)
            
            # Extrahera basnamnet utan filändelse för nyckeln
            key = index_name.split('.')[0]
            indices[key] = index_data
        
        return indices
    
    def _load_index(self, index_name: str) -> Dict[str, Any]:
        """
        Ladda ett specifikt index från fil
        
        Args:
            index_name: Filnamnet för indexet
            
        Returns:
            Index som dict eller tom dict vid fel
        """
        index_path = self.integrated_data_dir / "indices" / index_name
        try:
            if index_path.exists():
                with open(index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Kunde inte ladda index {index_name}: {str(e)}")
        return {}
    
    def get_technical_specs(self, product_id: str, params: str = "") -> Dict[str, Any]:
        """
        Hämta tekniska specifikationer för en produkt
        
        Args:
            product_id: Produktens ID
            params: Extra parametrar (t.ex. filterinställningar)
            
        Returns:
            Dict med specifikationer och status
        """
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
            
            # Filtrera baserat på parametrar om det finns
            if params:
                # Tolka parametrar som filter
                filter_terms = [term.lower() for term in params.split()]
                
                # Filtrera både kategorier och specifikationer
                filtered_specs = defaultdict(list)
                for category, category_specs in grouped_specs.items():
                    if any(term in category.lower() for term in filter_terms):
                        filtered_specs[category] = category_specs
                    else:
                        # Filtrera individuella specifikationer
                        matching_specs = []

                        for spec in category_specs:
                            name = spec.get("name", "").lower()
                            value = str(spec.get("raw_value", "")).lower()
                            if any(term in name or term in value for term in filter_terms):
                                matching_specs.append(spec)
                        
                        if matching_specs:
                            filtered_specs[category] = matching_specs
                
                # Använd filtrerade specifikationer om några matchningar hittades
                if filtered_specs:
                    grouped_specs = filtered_specs
            
            # Formatera specifikationer för presentation
            formatted_specs = []
            for category, category_specs in grouped_specs.items():
                formatted_specs.append(f"## {category}")
                for spec in sorted(category_specs, key=lambda x: x.get("importance", "normal"), reverse=True):
                    name = spec.get("name", "")
                    value = spec.get("raw_value", "")
                    unit = spec.get("unit", "")
                    
                    if name and value:
                        formatted_spec = f"- **{name}:** {value}"
                        if unit and unit not in value:
                            formatted_spec += f" {unit}"
                        formatted_specs.append(formatted_spec)
                
                formatted_specs.append("")  # Tomrad mellan kategorier
            
            return {
                "status": "success",
                "specs": specs,
                "specs_by_category": dict(grouped_specs),
                "formatted_text": "\n".join(formatted_specs)
            }
            
        except Exception as e:
            logger.error(f"Fel vid läsning av tekniska specifikationer för {product_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Kunde inte läsa tekniska specifikationer: {str(e)}"
            }
    
    def get_compatibility_info(self, product_id: str, params: str = "") -> Dict[str, Any]:
        """
        Hämta kompatibilitetsinformation för en produkt
        
        Args:
            product_id: Produktens ID
            params: Extra parametrar (t.ex. filterinställningar)
            
        Returns:
            Dict med kompatibilitetsinformation och status
        """
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
            
            # Filtrera baserat på parametrar om det finns
            if params:
                # Tolka parametrar som filter
                filter_terms = [term.lower() for term in params.split()]
                
                # Filtrera både relationstyper och relaterade produkter
                filtered_relations = defaultdict(list)
                for rel_type, type_relations in grouped_relations.items():
                    if any(term in rel_type.lower() for term in filter_terms):
                        filtered_relations[rel_type] = type_relations
                    else:
                        # Filtrera individuella relationer
                        matching_relations = []
                        for relation in type_relations:
                            related_product = relation.get("related_product", "").lower()
                            if any(term in related_product for term in filter_terms):
                                matching_relations.append(relation)
                        
                        if matching_relations:
                            filtered_relations[rel_type] = matching_relations
                
                # Använd filtrerade relationer om några matchningar hittades
                if filtered_relations:
                    grouped_relations = filtered_relations
            
            # Formatera relationer för presentation
            formatted_relations = []
            
            # Definiera visningsnamn för relationstyper
            relation_display = {
                "direct": "Kompatibel med",
                "fits": "Passar till",
                "requires": "Kräver",
                "recommended": "Rekommenderas med",
                "designed_for": "Designad för",
                "accessory": "Tillbehör till",
                "replacement": "Ersätter",
                "replaced_by": "Ersätts av",
                "not_compatible": "Ej kompatibel med"
            }
            
            for rel_type, type_relations in grouped_relations.items():
                # Använd visningsnamn om tillgängligt, annars formatera relationstypen
                display_name = relation_display.get(rel_type, rel_type.replace("_", " ").title())
                formatted_relations.append(f"## {display_name}")
                
                for relation in sorted(type_relations, key=lambda x: x.get("confidence", 0), reverse=True):
                    related_product = relation.get("related_product", "")
                    numeric_ids = relation.get("numeric_ids", [])
                    
                    if related_product:
                        relation_text = f"- {related_product}"
                        if numeric_ids:
                            relation_text += f" (Art.nr: {numeric_ids[0]})"
                        formatted_relations.append(relation_text)
                
                formatted_relations.append("")  # Tomrad mellan kategorier
            
            return {
                "status": "success",
                "relations": relations,
                "relations_by_type": dict(grouped_relations),
                "formatted_text": "\n".join(formatted_relations)
            }
            
        except Exception as e:
            logger.error(f"Fel vid läsning av kompatibilitetsinformation för {product_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Kunde inte läsa kompatibilitetsinformation: {str(e)}"
            }
    
    def get_product_summary(self, product_id: str, params: str = "") -> Dict[str, Any]:
        """
        Hämta sammanställning av produktinformation
        
        Args:
            product_id: Produktens ID
            params: Extra parametrar (ej använt för närvarande)
            
        Returns:
            Dict med sammanställd produktinformation och status
        """
        product_dir = self.products_dir / product_id
        summary_path = product_dir / "summary.jsonl"
        
        if not summary_path.exists():
            # Om ingen cachad sammanfattning finns, generera dynamiskt
            return self.generate_dynamic_summary(product_id)
        
        try:
            with open(summary_path, 'r', encoding='utf-8') as f:
                summary = json.loads(f.readline())
            
            # Formatera sammanfattningen
            formatted_sections = []
            
            # Lägg till produktnamn och grundläggande info
            if summary.get("product_name"):
                formatted_sections.append(f"# {summary['product_name']}")
            else:
                formatted_sections.append(f"# Produkt {product_id}")
            
            # Lägg till identifierare
            id_section = ["## Identifierare"]
            for id_type, values in summary.get("identifiers", {}).items():
                if values:
                    id_section.append(f"- **{id_type}:** {', '.join(values)}")
            if len(id_section) > 1:
                formatted_sections.extend(id_section)
                formatted_sections.append("")  # Tomrad
            
            # Lägg till beskrivning
            if summary.get("description"):
                formatted_sections.append("## Beskrivning")
                formatted_sections.append(summary["description"])
                formatted_sections.append("")  # Tomrad
            
            # Lägg till viktiga specifikationer
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
                formatted_sections.append("")  # Tomrad
            
            # Lägg till kompatibilitetsinformation
            if summary.get("key_compatibility"):
                formatted_sections.append("## Kompatibilitet")
                
                # Gruppera efter relationstyp
                compat_by_type = defaultdict(list)
                for relation in summary["key_compatibility"]:
                    compat_by_type[relation.get("type", "other")].append(relation)
                
                # Definiera visningsnamn för relationstyper
                relation_display = {
                    "direct": "Kompatibel med",
                    "fits": "Passar till",
                    "requires": "Kräver",
                    "recommended": "Rekommenderas med"
                }
                
                for rel_type, relations in compat_by_type.items():
                    display_name = relation_display.get(rel_type, rel_type.replace("_", " ").title())
                    formatted_sections.append(f"### {display_name}")
                    
                    for relation in relations:
                        related_product = relation.get("related_product", "")
                        if related_product:
                            compat_text = f"- {related_product}"
                            if relation.get("numeric_ids"):
                                compat_text += f" (Art.nr: {relation['numeric_ids'][0]})"
                            formatted_sections.append(compat_text)
                    
                    formatted_sections.append("")  # Tomrad
            
            return {
                "status": "success",
                "summary": summary,
                "formatted_text": "\n".join(formatted_sections)
            }
            
        except Exception as e:
            logger.error(f"Fel vid läsning av produktsammanfattning för {product_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Kunde inte läsa produktsammanfattning: {str(e)}"
            }
    
    def generate_dynamic_summary(self, product_id: str) -> Dict[str, Any]:
        """
        Generera en dynamisk sammanfattning när ingen cache finns
        
        Args:
            product_id: Produktens ID
            
        Returns:
            Dict med dynamiskt genererad sammanfattning
        """
        try:
            # Skapa basis för dynamisk sammanfattning
            summary = {
                "product_id": product_id,
                "generated_at": datetime.now().isoformat(),
                "product_name": self.get_product_name(product_id),
                "description": None,
                "key_specifications": [],
                "key_compatibility": [],
                "identifiers": {}
            }
            
            # Hämta tekniska specifikationer
            tech_result = self.get_technical_specs(product_id)
            if tech_result["status"] == "success":
                # Extrahera beskrivning om sådan finns
                for spec in tech_result.get("specs", []):
                    if spec.get("category", "").lower() in ["general", "allmänt", "beskrivning", "description"]:
                        if spec.get("name", "").lower() in ["beskrivning", "description"]:
                            summary["description"] = spec.get("raw_value", "")
                
                # Välj ut de viktigaste specifikationerna (upp till 5)
                key_specs = []
                
                # Sortera efter viktighet och sedan kategori
                sorted_specs = sorted(
                    tech_result.get("specs", []),
                    key=lambda x: (
                        0 if x.get("importance") == "high" else 
                        1 if x.get("importance") == "medium" else 2,
                        x.get("category", "")
                    )
                )
                
                # Ta max 5 viktiga specifikationer
                for spec in sorted_specs[:5]:
                    key_specs.append({
                        "name": spec.get("name", ""),
                        "value": spec.get("raw_value", ""),
                        "unit": spec.get("unit", ""),
                        "category": spec.get("category", "")
                    })
                
                summary["key_specifications"] = key_specs
            
            # Hämta kompatibilitetsinformation
            compat_result = self.get_compatibility_info(product_id)
            if compat_result["status"] == "success":
                # Välj ut de viktigaste kompatibilitetsrelationerna (upp till 5)
                key_compat = []
                
                # Sortera efter viktighet (de som har produkt-ID först)
                sorted_compat = sorted(
                    compat_result.get("relations", []),
                    key=lambda x: (
                        0 if x.get("numeric_ids") else 1,
                        x.get("confidence", 0)
                    ),
                    reverse=True
                )
                
                # Ta max 5 viktiga relationer
                for relation in sorted_compat[:5]:
                    key_compat.append({
                        "type": relation.get("relation_type", ""),
                        "related_product": relation.get("related_product", ""),
                        "has_product_id": bool(relation.get("numeric_ids")),
                        "numeric_ids": relation.get("numeric_ids", [])
                    })
                
                summary["key_compatibility"] = key_compat
            
            # Hämta identifierare från artikel_info.jsonl om den finns
            ids_path = self.products_dir / product_id / "article_info.jsonl"
            if ids_path.exists():
                try:
                    ids_by_type = defaultdict(list)
                    with open(ids_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            identifier = json.loads(line)
                            id_type = identifier.get("type", "")
                            value = identifier.get("value", "")
                            if id_type and value:
                                ids_by_type[id_type].append(value)
                    
                    summary["identifiers"] = dict(ids_by_type)
                except Exception as e:
                    logger.warning(f"Kunde inte läsa identifierare för {product_id}: {str(e)}")
            
            # Återanvänd formateringslogik från get_product_summary
            result = {
                "status": "success",
                "summary": summary,
                "dynamically_generated": True
            }
            
            # Skapa formatterad text
            formatted_text = self.format_summary(summary)
            result["formatted_text"] = formatted_text
            
            return result
            
        except Exception as e:
            logger.error(f"Fel vid generering av dynamisk sammanfattning för {product_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Kunde inte generera sammanfattning: {str(e)}"
            }
    
    def format_summary(self, summary: Dict[str, Any]) -> str:
        """
        Formatera en sammanfattning som markdown-text
        
        Args:
            summary: Sammanfattningsobjektet
            
        Returns:
            Formaterad markdown-text
        """
        formatted_sections = []
        
        # Lägg till produktnamn och grundläggande info
        if summary.get("product_name"):
            formatted_sections.append(f"# {summary['product_name']}")
        else:
            formatted_sections.append(f"# Produkt {summary.get('product_id', '')}")
        
        formatted_sections.append("")  # Tomrad
        
        # Lägg till produkt-ID om det finns
        if "product_id" in summary:
            formatted_sections.append(f"**Artikelnummer:** {summary['product_id']}")
            formatted_sections.append("")  # Tomrad
        
        # Lägg till identifierare
        id_lines = []
        for id_type, values in summary.get("identifiers", {}).items():
            if values:
                id_lines.append(f"**{id_type}:** {', '.join(values)}")
        
        if id_lines:
            formatted_sections.extend(id_lines)
            formatted_sections.append("")  # Tomrad
        
        # Lägg till beskrivning
        if summary.get("description"):
            formatted_sections.append("## Beskrivning")
            formatted_sections.append(summary["description"])
            formatted_sections.append("")  # Tomrad
        
        # Lägg till viktiga specifikationer
        if summary.get("key_specifications"):
            formatted_sections.append("## Viktiga specifikationer")
            
            # Gruppera efter kategori
            specs_by_category = defaultdict(list)
            for spec in summary["key_specifications"]:
                category = spec.get("category", "Övrigt")
                specs_by_category[category].append(spec)
            
            # Lägg till per kategori
            for category, specs in specs_by_category.items():
                if len(specs_by_category) > 1:  # Om mer än en kategori, visa kategorinamn
                    formatted_sections.append(f"### {category}")
                
                for spec in specs:
                    name = spec.get("name", "")
                    value = spec.get("value", "")
                    unit = spec.get("unit", "")
                    if name and value:
                        spec_text = f"- **{name}:** {value}"
                        if unit and unit not in value:
                            spec_text += f" {unit}"
                        formatted_sections.append(spec_text)
            
            formatted_sections.append("")  # Tomrad
        
        # Lägg till kompatibilitetsinformation
        if summary.get("key_compatibility"):
            formatted_sections.append("## Kompatibilitet")
            
            # Gruppera efter relationstyp
            compat_by_type = defaultdict(list)
            for relation in summary["key_compatibility"]:
                compat_by_type[relation.get("type", "other")].append(relation)
            
            # Definiera visningsnamn för relationstyper
            relation_display = {
                "direct": "Kompatibel med",
                "fits": "Passar till",
                "requires": "Kräver",
                "recommended": "Rekommenderas med",
                "designed_for": "Designad för",
                "accessory": "Tillbehör till",
                "replacement": "Ersätter",
                "replaced_by": "Ersätts av"
            }
            
            for rel_type, relations in compat_by_type.items():
                display_name = relation_display.get(rel_type, rel_type.replace("_", " ").title())
                if len(compat_by_type) > 1:  # Om mer än en relationstyp, visa typ
                    formatted_sections.append(f"### {display_name}")
                
                for relation in relations:
                    related_product = relation.get("related_product", "")
                    if related_product:
                        compat_text = f"- {related_product}"
                        if relation.get("numeric_ids"):
                            compat_text += f" (Art.nr: {relation['numeric_ids'][0]})"
                        formatted_sections.append(compat_text)
            
            formatted_sections.append("")  # Tomrad
        
        return "\n".join(formatted_sections)
    
    def get_full_info(self, product_id: str, params: str = "") -> Dict[str, Any]:
        """
        Hämta fullständig information för en produkt
        
        Args:
            product_id: Produktens ID
            params: Extra parametrar
            
        Returns:
            Dict med fullständig information och status
        """
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
                "formatted_text": content  # Redan i markdown-format
            }
            
        except Exception as e:
            logger.error(f"Fel vid läsning av fullständig information för {product_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Kunde inte läsa fullständig information: {str(e)}"
            }
    
    def get_product_name(self, product_id: str) -> str:
        """
        Hämta produktnamn baserat på ID
        
        Args:
            product_id: Produktens ID
            
        Returns:
            Produktnamn eller generiskt namn om inget hittas
        """
        product_names = self.indices.get("product_names", {})
        if product_id in product_names:
            return product_names[product_id].get("name", f"Produkt {product_id}")
        
        return f"Produkt {product_id}"
    
    def validate_product_id(self, product_id: str) -> bool:
        """
        Validera att ett produkt-ID existerar
        
        Args:
            product_id: Produktens ID
            
        Returns:
            True om produkten existerar, annars False
        """
        product_dir = self.products_dir / product_id
        return product_dir.exists() and product_dir.is_dir()
    
    def search_products(self, query: str, max_results: int = None) -> Dict[str, Any]:
        """
        Sök efter produkter baserat på fritextfråga
        
        Args:
            query: Söktermen
            max_results: Maximalt antal resultat att returnera
            
        Returns:
            Dict med sökresultat och status
        """
        if max_results is None:
            max_results = self.config.max_search_results
        
        # Förbehandla sökfrågan
        query = query.lower()
        query_words = set(query.split())
        
        # Resultatsamling
        results = []
        
        # Sök i text-index för exakta träffar
        exact_matches = set()
        for word in query_words:
            if word in self.indices.get("text_search_index", {}):
                for product_id in self.indices["text_search_index"][word]:
                    exact_matches.add(product_id)
        
        # Lägg till exakta träffar först
        for product_id in exact_matches:
            product_name = self.get_product_name(product_id)
            results.append({
                "product_id": product_id,
                "name": product_name,
                "score": 1.0,  # Högsta poäng för exakta träffar
                "match_type": "exact"
            })
        
        # Om vi inte har tillräckligt med exakta träffar, gör fuzzy matching
        if len(results) < max_results:
            fuzzy_matches = self.find_fuzzy_matches(query, max_results=max_results-len(results))
            
            # Filtrera bort dubbletter
            existing_ids = {result["product_id"] for result in results}
            for match in fuzzy_matches:
                if match["product_id"] not in existing_ids:
                    results.append(match)
        
        # Sortera efter poäng och begränsa resultaten
        results = sorted(results, key=lambda x: x["score"], reverse=True)[:max_results]
        
        # Formatera sökresultaten för presentation
        formatted_results = ["## Sökresultat", ""]
        
        if not results:
            formatted_results.append("Inga produkter hittades som matchar din sökning.")
        else:
            for i, result in enumerate(results, 1):
                formatted_results.append(f"{i}. **{result['name']}** (Art.nr: {result['product_id']})")
            
            formatted_results.append("")
            formatted_results.append("Använd kommandot `-s <artikelnr>` för att se mer information om en produkt.")
        
        return {
            "status": "success",
            "query": query,
            "matches": results,
            "total_matches": len(results),
            "formatted_text": "\n".join(formatted_results)
        }
    
    def find_fuzzy_matches(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Hitta produkter genom fuzzy matching (ungefärlig matchning)
        
        Args:
            query: Söktermen
            max_results: Maximalt antal resultat
            
        Returns:
            Lista med matchande produkter
        """
        # Förbehandla sökfrågan
        query_words = set(query.lower().split())
        
        # Resultatsamling med poäng
        scored_matches = []
        
        # Gå igenom alla produktnamn och beräkna matchningspoäng
        for name, product_id in self.name_to_id_map.items():
            name_words = set(name.split())
            
            # Beräkna överlappning mellan ord
            overlap = len(query_words & name_words)
            
            # Beräkna poäng baserat på antal matchande ord och total längd
            if overlap > 0:
                score = overlap / (len(query_words) + len(name_words) - overlap)  # Jaccard-likhet
                
                # Lägg till extra poäng för längre matchningar
                if overlap > 1:
                    score += 0.1 * overlap
                
                # Straffa kortare namn (ofta generiska)
                if len(name_words) <= 2:
                    score *= 0.8
                
                # Lägg till om poängen är över ett tröskelvärde
                if score > 0.2:
                    scored_matches.append({
                        "product_id": product_id,
                        "name": name.title(),  # Gör första bokstaven stor
                        "score": score,
                        "match_type": "fuzzy"
                    })
        
        # Sortera efter poäng och begränsa antalet resultat
        return sorted(scored_matches, key=lambda x: x["score"], reverse=True)[:max_results]
    
    def suggest_products(self, query: str, max_suggestions: int = 3) -> List[Dict[str, Any]]:
        """
        Föreslå produkter baserat på en fråga
        
        Args:
            query: Frågan eller söktermen
            max_suggestions: Maximalt antal förslag
            
        Returns:
            Lista med produktförslag
        """
        # Använd sökmotorn för att hitta relevanta produkter
        search_results = self.search_products(query, max_results=max_suggestions)
        
        # Extrahera produktförslagen
        suggestions = search_results.get("matches", [])
        
        return suggestions
    
    def find_related_products(self, product_id: str, relation_types: List[str] = None) -> List[Dict[str, Any]]:
        """
        Hitta produkter relaterade till en given produkt
        
        Args:
            product_id: Produktens ID
            relation_types: Lista med relationstyper att filtrera på
            
        Returns:
            Lista med relaterade produkter
        """
        # Hämta kompatibilitetskartan
        compat_map = self.indices.get("compatibility_map", {})
        
        if product_id not in compat_map:
            return []
        
        # Hämta alla relationer för produkten
        relations = compat_map[product_id]
        
        # Filtrera på relationstyper om angivet
        if relation_types:
            relations = [r for r in relations if r.get("relation_type") in relation_types]
        
        # Konvertera till resultatformat
        related_products = []
        for relation in relations:
            related_product = relation.get("related_product", "")
            relation_type = relation.get("relation_type", "")
            numeric_ids = relation.get("numeric_ids", [])
            
            # Försök att identifiera produkt-ID om möjligt
            target_product_id = None
            if numeric_ids:
                target_product_id = numeric_ids[0]
            elif related_product.lower() in self.name_to_id_map:
                target_product_id = self.name_to_id_map[related_product.lower()]
            
            if related_product:
                related_products.append({
                    "product_id": target_product_id,
                    "name": related_product,
                    "relation_type": relation_type,
                    "numeric_ids": numeric_ids
                })
        
        return related_products

