# nlp_bot_engine/dialog/response_generator.py

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from ..core.config import BotConfig
from .templates import ResponseTemplates

logger = logging.getLogger(__name__)

class ResponseGenerator:
    """
    Genererar dynamiska svar baserat på intention, analys och resultat.
    Anpassar detaljnivå och formulering baserat på användarkontext.
    """
    
    def __init__(self, config: BotConfig):
        """
        Initialisera svarsgeneratorn
        
        Args:
            config: Konfigurationsobjekt
        """
        self.config = config
        self.templates = ResponseTemplates()
    
    def format_command_response(self, command_type: str, product_id: str, 
                               result: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Formatterar svar för en kommandoförfrågan
        
        Args:
            command_type: Typen av kommando (t, c, s, f)
            product_id: Produktens ID
            result: Resultatet från kommandot
            context: Kontextinformation
            
        Returns:
            Formaterat svar som text
        """
        # Om resultatet har en status som inte är success, returnera felmeddelandet
        if result.get("status") != "success":
            return self.format_error_response(result.get("message", "Ett fel uppstod"))
        
        # Om resultatet har förformaterad text, använd den
        if "formatted_text" in result:
            return result["formatted_text"]
        
        # Annars, använd mallar baserat på kommandotyp
        if command_type == "t":
            template = self.config.response_templates.get("technical")
            return self.fill_template(template, {
                "product_name": self.get_product_name(product_id),
                "product_id": product_id,
                "specifications": result.get("formatted_text", "Ingen teknisk information tillgänglig")
            })
            
        elif command_type == "c":
            template = self.config.response_templates.get("compatibility")
            return self.fill_template(template, {
                "product_name": self.get_product_name(product_id),
                "product_id": product_id,
                "compatibility": result.get("formatted_text", "Ingen kompatibilitetsinformation tillgänglig")
            })
            
        elif command_type == "s":
            template = self.config.response_templates.get("summary")
            return self.fill_template(template, {
                "product_name": self.get_product_name(product_id),
                "product_id": product_id,
                "description": result.get("summary", {}).get("description", ""),
                "specifications": self.format_key_specifications(result.get("summary", {}).get("key_specifications", [])),
                "compatibility": self.format_key_compatibility(result.get("summary", {}).get("key_compatibility", []))
            })
            
        elif command_type == "f":
            # Full info är redan formaterad
            return result.get("content", "Ingen fullständig information tillgänglig")
        
        # Fallback
        return result.get("formatted_text", "Inget resultat att visa")
    
    def generate_nl_response(self, analysis: Dict[str, Any], result: Dict[str, Any], 
                            context: Dict[str, Any]) -> str:
        """
        Generera svar för naturligt språkförfrågningar
        
        Args:
            analysis: Analysresultat från NLP-stegen
            result: Resultat från intentionsutförande
            context: Kontextinformation
            
        Returns:
            Genererat svar
        """
        # Om resultatet har en status som inte är success, returnera felmeddelandet
        if result.get("status") == "error":
            return self.format_error_response(result.get("message", "Ett fel uppstod"))
        
        # Identifiera huvudintention och anpassa svarsstil
        primary_intent = analysis.get("primary_intent")
        
        # Kontrollera expertisgrad för att anpassa detaljnivå
        expertise_level = self.infer_expertise_level(context)
        
        # Hämta entiteter för att personalisera svaret
        entities = analysis.get("entities", [])
        
        # Identifiera eventuell produkt i entiteter
        product_id = None
        for entity in entities:
            if entity.get("type") == "PRODUCT" and entity.get("product_id"):
                product_id = entity.get("product_id")
                break
        
        # Om ingen produkt hittades i entiteter, kontrollera resultat och kontext
        if not product_id:
            product_id = result.get("product_id") or context.get("active_product_id")
        
        # Generera svar baserat på intention
        if primary_intent == "technical":
            return self.generate_technical_response(result, product_id, expertise_level)
            
        elif primary_intent == "compatibility":
            return self.generate_compatibility_response(result, product_id, expertise_level)
            
        elif primary_intent == "summary":
            return self.generate_summary_response(result, product_id, expertise_level)
            
        elif primary_intent == "search":
            return self.generate_search_response(result, analysis.get("original_query", ""), expertise_level)
        
        # Om resultatet har förformaterad text men vi inte kunde identifiera intention
        if "formatted_text" in result:
            return result["formatted_text"]
        
        # Fallback till generiskt svar
        return self.templates.get_template("generic").format(
            query=analysis.get("original_query", ""),
               timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
           )
   
    def format_clarification_request(self, analysis: Dict[str, Any], 
                                    questions: List[Dict[str, Any]], 
                                    context: Dict[str, Any]) -> str:
        """
        Formatera en förfrågan om förtydligande när botten är osäker
        
        Args:
            analysis: Analysresultat från NLP-stegen
            questions: Lista med klargörande frågor
            context: Kontextinformation
            
        Returns:
            Formaterad förfrågan om förtydligande
        """
        # Om inga frågor, använd ett generiskt förtydligande
        if not questions:
            return self.templates.get_template("generic_clarification").format(
                query=analysis.get("original_query", "")
            )
        
        # Formatera den första frågan
        question = questions[0]
        question_type = question.get("type", "")
        
        if question_type == "product_selection":
            options_text = "\n".join([f"- {opt['name']} (Art.nr: {opt['id']})" 
                                        for opt in question.get("options", [])])
            
            return self.templates.get_template("product_clarification").format(
                question=question.get("text", "Vilken produkt menar du?"),
                options=options_text
            )
            
        elif question_type == "intent_selection":
            options_text = "\n".join([f"- {opt['name']}" 
                                        for opt in question.get("options", [])])
            
            return self.templates.get_template("intent_clarification").format(
                question=question.get("text", "Vad vill du veta?"),
                options=options_text
            )
            
        elif question_type == "general_clarification":
            return self.templates.get_template("generic_clarification").format(
                query=analysis.get("original_query", "")
            )
        
        # Fallback
        return self.templates.get_template("generic_clarification").format(
            query=analysis.get("original_query", "")
        )
    
    def format_low_confidence_response(self, analysis: Dict[str, Any], result: Dict[str, Any], 
                                        context: Dict[str, Any]) -> str:
        """
        Formatera svar när botten har låg konfidens men ändå gör en kvalificerad gissning
        
        Args:
            analysis: Analysresultat från NLP-stegen
            result: Resultatet från intentionsutförandet
            context: Kontextinformation
            
        Returns:
            Formaterat svar med reservationer
        """
        # Få originalsvar som skulle genererats med full konfidens
        original_response = self.generate_nl_response(analysis, result, context)
        
        # Lägg till en inledande text som indikerar osäkerhet
        confidence_disclaimer = self.templates.get_template("low_confidence_disclaimer").format(
            intent=self.get_intent_display_name(analysis.get("primary_intent", ""))
        )
        
        # Lägg till alternativa intentioner om sådana finns
        alternatives = ""
        if len(analysis.get("intents", [])) > 1:
            alt_intents = analysis.get("intents")[1:3]  # Ta upp till två alternativ
            alt_names = [self.get_intent_display_name(i["intent"]) for i in alt_intents]
            
            alternatives = self.templates.get_template("alternative_intents").format(
                alternatives=", ".join(alt_names)
            )
        
        return f"{confidence_disclaimer}\n\n{original_response}\n\n{alternatives}"
    
    def generate_technical_response(self, result: Dict[str, Any], product_id: str, 
                                    expertise_level: str) -> str:
        """
        Generera svar för tekniska frågor med anpassad detaljnivå
        
        Args:
            result: Resultatdata
            product_id: Produktens ID
            expertise_level: Användarens expertisgrad
            
        Returns:
            Formaterad teknisk information
        """
        # Om resultatet har förformaterad text, anpassa den efter expertisgrad
        if "formatted_text" in result:
            formatted_text = result["formatted_text"]
            
            # För experter, behåll all detaljerad information
            if expertise_level == "expert":
                return formatted_text
            
            # För mellanliggande nivå, behåll det mesta men förenkla vissa delar
            elif expertise_level == "intermediate":
                # Till exempel, ta bort mycket tekniska specifikationer
                return formatted_text
            
            # För nybörjare, förenkla och förtydliga
            else:
                # Lägg till förklarande text och förenkla terminologi
                intro = self.templates.get_template("technical_beginner_intro").format(
                    product_name=self.get_product_name(product_id)
                )
                return f"{intro}\n\n{formatted_text}"
        
        # Om ingen förformaterad text, generera från specs
        specs = result.get("specs", [])
        specs_by_category = result.get("specs_by_category", {})
        
        if not specs and not specs_by_category:
            return self.templates.get_template("no_technical_info").format(
                product_name=self.get_product_name(product_id)
            )
        
        # Om vi har kategorier, använd dem
        if specs_by_category:
            formatted_sections = [f"# Tekniska specifikationer för {self.get_product_name(product_id)}", ""]
            
            formatted_sections.append(f"**Artikelnummer:** {product_id}")
            formatted_sections.append("")
            
            # Sortera kategorier för att få viktiga först
            priority_categories = ["Dimensioner", "Mått", "Grundläggande", "Material", "Vikt"]
            categories = list(specs_by_category.keys())
            
            # Sortera så att prioriterade kategorier kommer först
            sorted_categories = sorted(categories, 
                                        key=lambda x: (
                                            0 if x in priority_categories else 
                                            priority_categories.index(x) if x in priority_categories else 
                                            999
                                        ))
            
            # Lägg till varje kategori
            for category in sorted_categories:
                category_specs = specs_by_category[category]
                
                # För nybörjare, visa bara viktiga kategorier och begränsad mängd specs
                if expertise_level == "beginner" and category not in priority_categories and len(category_specs) > 2:
                    category_specs = category_specs[:2]  # Bara visa de första två
                
                formatted_sections.append(f"## {category}")
                
                for spec in category_specs:
                    name = spec.get("name", "")
                    value = spec.get("raw_value", "")
                    unit = spec.get("unit", "")
                    
                    if name and value:
                        spec_line = f"- **{name}:** {value}"
                        if unit and unit not in value:
                            spec_line += f" {unit}"
                        formatted_sections.append(spec_line)
                
                formatted_sections.append("")  # Tomrad mellan kategorier
            
            # För nybörjare, lägg till förklarande text
            if expertise_level == "beginner":
                formatted_sections.insert(2, self.templates.get_template("technical_beginner_intro").format(
                    product_name=self.get_product_name(product_id)
                ))
                formatted_sections.insert(3, "")  # Tomrad
            
            return "\n".join(formatted_sections)
        
        # Fallback till enkel listning av specs
        formatted_sections = [f"# Tekniska specifikationer för {self.get_product_name(product_id)}", ""]
        formatted_sections.append(f"**Artikelnummer:** {product_id}")
        formatted_sections.append("")
        
        for spec in specs:
            name = spec.get("name", "")
            value = spec.get("raw_value", "")
            unit = spec.get("unit", "")
            
            if name and value:
                spec_line = f"- **{name}:** {value}"
                if unit and unit not in value:
                    spec_line += f" {unit}"
                formatted_sections.append(spec_line)
        
        return "\n".join(formatted_sections)
    
    def generate_compatibility_response(self, result: Dict[str, Any], product_id: str, 
                                        expertise_level: str) -> str:
        """
        Generera svar för kompatibilitetsfrågor med anpassad detaljnivå
        
        Args:
            result: Resultatdata
            product_id: Produktens ID
            expertise_level: Användarens expertisgrad
            
        Returns:
            Formaterad kompatibilitetsinformation
        """
        # Om resultatet har förformaterad text, använd den som bas
        if "formatted_text" in result:
            formatted_text = result["formatted_text"]
            
            # Experter får allt som det är
            if expertise_level == "expert":
                return formatted_text
            
            # För nybörjare och mellanliggande, lägg till förklarande text
            intro = self.templates.get_template("compatibility_intro").format(
                product_name=self.get_product_name(product_id)
            )
            
            # För nybörjare, förenkla texten något
            if expertise_level == "beginner":
                # Ersätt tekniska termer med enklare förklaringar
                formatted_text = self.simplify_technical_terms(formatted_text)
            
            return f"{intro}\n\n{formatted_text}"
        
        # Om ingen förformaterad text, generera från relationer
        relations = result.get("relations", [])
        relations_by_type = result.get("relations_by_type", {})
        
        if not relations and not relations_by_type:
            return self.templates.get_template("no_compatibility_info").format(
                product_name=self.get_product_name(product_id)
            )
        
        # Om vi har relationstyper, använd dem
        if relations_by_type:
            formatted_sections = [f"# Kompatibilitetsinformation för {self.get_product_name(product_id)}", ""]
            
            formatted_sections.append(f"**Artikelnummer:** {product_id}")
            formatted_sections.append("")
            
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
            
            # Lägg till varje relationstyp
            for rel_type, relations in relations_by_type.items():
                display_name = relation_display.get(rel_type, rel_type.replace("_", " ").title())
                formatted_sections.append(f"## {display_name}")
                
                for relation in relations:
                    related_product = relation.get("related_product", "")
                    numeric_ids = relation.get("numeric_ids", [])
                    
                    if related_product:
                        relation_text = f"- {related_product}"
                        if numeric_ids:
                            relation_text += f" (Art.nr: {numeric_ids[0]})"
                        formatted_sections.append(relation_text)
                
                formatted_sections.append("")  # Tomrad mellan kategorier
            
            # För nybörjare, lägg till förklarande text
            if expertise_level in ["beginner", "intermediate"]:
                formatted_sections.insert(2, self.templates.get_template("compatibility_intro").format(
                    product_name=self.get_product_name(product_id)
                ))
                formatted_sections.insert(3, "")  # Tomrad
            
            return "\n".join(formatted_sections)
        
        # Fallback till enkel listning av relationer
        formatted_sections = [f"# Kompatibilitetsinformation för {self.get_product_name(product_id)}", ""]
        formatted_sections.append(f"**Artikelnummer:** {product_id}")
        formatted_sections.append("")
        
        # Gruppera efter relationstyp
        grouped_relations = {}
        for relation in relations:
            rel_type = relation.get("relation_type", "other")
            if rel_type not in grouped_relations:
                grouped_relations[rel_type] = []
            grouped_relations[rel_type].append(relation)
        
        # Definiera visningsnamn för relationstyper
        relation_display = {
            "direct": "Kompatibel med",
            "fits": "Passar till",
            "requires": "Kräver",
            "recommended": "Rekommenderas med"
        }
        
        # Lägg till varje relationstyp
        for rel_type, rels in grouped_relations.items():
            display_name = relation_display.get(rel_type, rel_type.replace("_", " ").title())
            formatted_sections.append(f"## {display_name}")
            
            for relation in rels:
                related_product = relation.get("related_product", "")
                if related_product:
                    formatted_sections.append(f"- {related_product}")
            
            formatted_sections.append("")  # Tomrad mellan kategorier
        
        return "\n".join(formatted_sections)
    
    def generate_summary_response(self, result: Dict[str, Any], product_id: str, 
                                    expertise_level: str) -> str:
        """
        Generera sammanfattningssvar med anpassad detaljnivå
        
        Args:
            result: Resultatdata
            product_id: Produktens ID
            expertise_level: Användarens expertisgrad
            
        Returns:
            Formaterad produktsammanfattning
        """
        # Om resultatet har förformaterad text, använd den
        if "formatted_text" in result:
            return result["formatted_text"]
        
        # Om vi har ett summary-objekt, formatera det
        summary = result.get("summary", {})
        
        if not summary:
            return self.templates.get_template("no_summary_info").format(
                product_name=self.get_product_name(product_id)
            )
        
        formatted_sections = []
        
        # Lägg till produktnamn och ID
        product_name = summary.get("product_name", self.get_product_name(product_id))
        formatted_sections.append(f"# {product_name}")
        formatted_sections.append("")
        formatted_sections.append(f"**Artikelnummer:** {product_id}")
        
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
            
            # Gruppera efter kategori för bättre struktur
            specs_by_category = {}
            for spec in summary["key_specifications"]:
                category = spec.get("category", "Övrigt")
                if category not in specs_by_category:
                    specs_by_category[category] = []
                specs_by_category[category].append(spec)
            
            # För experter och mellanliggande, visa kategoriserade specifikationer
            if expertise_level in ["expert", "intermediate"] and len(specs_by_category) > 1:
                for category, specs in specs_by_category.items():
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
                    
                    formatted_sections.append("")  # Tomrad mellan kategorier
            else:
                # För nybörjare, visa platt lista utan kategorier
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
            compat_by_type = {}
            for relation in summary["key_compatibility"]:
                rel_type = relation.get("type", "other")
                if rel_type not in compat_by_type:
                    compat_by_type[rel_type] = []
                compat_by_type[rel_type].append(relation)
            
            # Definiera visningsnamn för relationstyper
            relation_display = {
                "direct": "Kompatibel med",
                "fits": "Passar till",
                "requires": "Kräver",
                "recommended": "Rekommenderas med",
                "designed_for": "Designad för",
                "accessory": "Tillbehör till"
            }
            
            # Experter får mer strukturerad information
            if expertise_level in ["expert", "intermediate"] and len(compat_by_type) > 1:
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
                    
                    formatted_sections.append("")  # Tomrad mellan kategorier
            else:
                # För nybörjare, visa platt lista med beskrivande text
                for relation in summary["key_compatibility"]:
                    rel_type = relation.get("type", "other")
                    display_name = relation_display.get(rel_type, "")
                    related_product = relation.get("related_product", "")
                    
                    if related_product:
                        if display_name:
                            compat_text = f"- {display_name}: {related_product}"
                        else:
                            compat_text = f"- {related_product}"
                            
                        if relation.get("numeric_ids"):
                            compat_text += f" (Art.nr: {relation['numeric_ids'][0]})"
                            
                        formatted_sections.append(compat_text)
                
                formatted_sections.append("")  # Tomrad
        
        return "\n".join(formatted_sections)
    
    def generate_search_response(self, result: Dict[str, Any], query: str, 
                                expertise_level: str) -> str:
        """
        Generera svar för sökfrågor
        
        Args:
            result: Sökresultat
            query: Ursprunglig sökfråga
            expertise_level: Användarens expertisgrad
            
        Returns:
            Formaterad sökresultatlista
        """
        # Om resultatet har förformaterad text, använd den
        if "formatted_text" in result:
            return result["formatted_text"]
        
        # Hämta matchningar
        matches = result.get("matches", [])
        
        if not matches:
            return self.templates.get_template("no_search_results").format(
                query=query
            )
        
        # Formatera sökresultaten
        formatted_sections = [f"# Sökresultat för '{query}'", ""]
        
        # För experter, visa även matchningspoäng
        if expertise_level == "expert":
            formatted_sections.append("| Produkt | Artikelnummer | Matchningspoäng |")
            formatted_sections.append("|---------|---------------|-----------------|")
            
            for match in matches:
                name = match.get("name", "")
                product_id = match.get("product_id", "")
                score = match.get("score", 0)
                
                formatted_sections.append(f"| {name} | {product_id} | {score:.2f} |")
        else:
            # För vanliga användare, enklare lista
            for i, match in enumerate(matches, 1):
                name = match.get("name", "")
                product_id = match.get("product_id", "")
                
                formatted_sections.append(f"{i}. **{name}** (Art.nr: {product_id})")
        
        # Lägg till instruktioner om hur man får mer info
        formatted_sections.append("")
        formatted_sections.append("Använd kommandot `-s <artikelnr>` för att se mer information om en produkt.")
        
        return "\n".join(formatted_sections)
    
    def format_error_response(self, error_message: str) -> str:
        """
        Formatera ett felmeddelande
        
        Args:
            error_message: Felmeddelandet
            
        Returns:
            Formaterat felmeddelande
        """
        return self.templates.get_template("error").format(
            error=error_message
        )
    
    def fill_template(self, template: str, values: Dict[str, str]) -> str:
        """
        Fyll i en mall med värden
        
        Args:
            template: Mallen att använda
            values: Värden att fylla i
            
        Returns:
            Ifylld mall
        """
        try:
            return template.format(**values)
        except KeyError as e:
            logger.warning(f"Saknat värde i mall: {str(e)}")
            # Fallback - ersätt saknade värden med tomma strängar
            for key in str(e).strip("'"):
                if key not in values:
                    values[key] = ""
            return template.format(**values)
        except Exception as e:
            logger.error(f"Fel vid ifyllning av mall: {str(e)}")
            return template  # Returnera oförändrad mall vid fel
    
    def format_key_specifications(self, specs: List[Dict[str, Any]]) -> str:
        """
        Formatera nyckelspecifikationer
        
        Args:
            specs: Lista med specifikationer
            
        Returns:
            Formaterad text
        """
        if not specs:
            return ""
        
        formatted_lines = ["## Viktiga specifikationer", ""]
        
        for spec in specs:
            name = spec.get("name", "")
            value = spec.get("value", "")
            unit = spec.get("unit", "")
            
            if name and value:
                spec_text = f"- **{name}:** {value}"
                if unit and unit not in value:
                    spec_text += f" {unit}"
                formatted_lines.append(spec_text)
        
        return "\n".join(formatted_lines)
    
    def format_key_compatibility(self, compatibility: List[Dict[str, Any]]) -> str:
        """
        Formatera nyckelkompatibilitetsinformation
        
        Args:
            compatibility: Lista med kompatibilitetsrelationer
            
        Returns:
            Formaterad text
        """
        if not compatibility:
            return ""
        
        formatted_lines = ["## Kompatibilitet", ""]
        
        # Gruppera efter relationstyp
        grouped = {}
        for relation in compatibility:
            rel_type = relation.get("type", "other")
            if rel_type not in grouped:
                grouped[rel_type] = []
            grouped[rel_type].append(relation)
        
        # Definiera visningsnamn för relationstyper
        relation_display = {
            "direct": "Kompatibel med",
            "fits": "Passar till",
            "requires": "Kräver",
            "recommended": "Rekommenderas med",
            "designed_for": "Designad för",
            "accessory": "Tillbehör till"
        }
        
        # Formatera för varje relationstyp
        for rel_type, relations in grouped.items():
            display_name = relation_display.get(rel_type, rel_type.replace("_", " ").title())
            
            if len(grouped) > 1:  # Om fler än en typ, använd underrubriker
                formatted_lines.append(f"### {display_name}")
            
            for relation in relations:
                related_product = relation.get("related_product", "")
                numeric_ids = relation.get("numeric_ids", [])
                
                if related_product:
                    relation_text = f"- {related_product}"
                    if numeric_ids:
                        relation_text += f" (Art.nr: {numeric_ids[0]})"
                    formatted_lines.append(relation_text)
            
            formatted_lines.append("")  # Tomrad mellan kategorier
        
        return "\n".join(formatted_lines)
    
    def get_product_name(self, product_id: str) -> str:
        """
        Hämta produktnamn för ett produkt-ID
        
        Args:
            product_id: Produktens ID
            
        Returns:
            Produktnamn eller generisk text
        """
        # Detta skulle normalt använda någon form av produktdatabas
        # men här returnerar vi ett generiskt namn
        return f"Produkt {product_id}"
    
    def get_intent_display_name(self, intent: str) -> str:
        """
        Hämta visningsnamn för en intention
        
        Args:
            intent: Intentionskod
            
        Returns:
            Visningsnamn
        """
        intent_display = {
            "technical": "tekniska specifikationer",
            "compatibility": "kompatibilitetsinformation",
            "summary": "produktsammanfattning",
            "search": "produktsökning"
        }
        
        return intent_display.get(intent, intent)
    
    def infer_expertise_level(self, context: Dict[str, Any]) -> str:
        """
        Härleda användarens expertisgrad från kontext
        
        Args:
            context: Kontextinformation
            
        Returns:
            Expertisgrad (beginner/intermediate/expert)
        """
        # Om expertisgrad redan finns i kontexten, använd den
        if "expertise_level" in context:
            return context["expertise_level"]
        
        # Härleda från frågehistorik
        query_history = context.get("query_history", [])
        
        if not query_history:
            return "intermediate"  # Standardnivå för ny användare
        
        # Analysera tidigare frågor för att bedöma expertis
        technical_terms = [
            "specifikation", "dimensioner", "tolerans", "teknisk", "material",
            "effekt", "spänning", "kompatibilitet", "monteringsanvisning"
        ]
        
        # Räkna tekniska termer i historiken
        technical_count = 0
        for query in query_history:
            query_lower = query.lower()
            for term in technical_terms:
                if term in query_lower:
                    technical_count += 1
        
        # Bedöm nivå baserat på tekniska termer och historiklängd
        if technical_count >= 3 or len(query_history) >= 10:
            return "expert"
        elif technical_count >= 1 or len(query_history) >= 3:
            return "intermediate"
        else:
            return "beginner"
    
    def simplify_technical_terms(self, text: str) -> str:
        """
        Förenkla tekniska termer i text för nybörjaranvändare
        
        Args:
            text: Texten att förenkla
            
        Returns:
            Förenklad text
        """
        # Ersättningsordbok för tekniska termer
        replacements = {
            r'\b([Dd]imensioner)\b': r'mått',
            r'\b([Kk]ompatibilitet)\b': r'passar tillsammans med',
            r'\b([Ss]pecifikationer)\b': r'egenskaper',
            r'\b([Mm]ontering)\b': r'installation',
            r'\b([Tt]olerans)\b': r'tillåten avvikelse',
            r'\b([Ee]ffekt)\b': r'strömförbrukning'
        }
        
        # Utför ersättningar
        simplified_text = text
        for pattern, replacement in replacements.items():
            simplified_text = re.sub(pattern, replacement, simplified_text)
        
        return simplified_text