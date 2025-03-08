


# TODO LIST: IMPLEMENTERINGAR OCH FÖRBÄTTRINGAR


## 2. Förbättrad felsökning och indikering

Vi kan lägga till ett robust loggningssystem för felsökning:

```python
# nlp_bot_engine/utils/logging_manager.py

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

class LoggingManager:
    """
    Hanterar detaljerad loggning av interaktioner och systemhändelser.
    """
    
    def __init__(self, log_dir: str = "./logs", debug: bool = False):
        """
        Initialisera logghanteraren
        
        Args:
            log_dir: Katalog för loggfiler
            debug: Aktivera debugloggning
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True, parents=True)
        
        # Skapa loggare för olika typer av händelser
        self.interaction_log = self._setup_logger("interaction", self.log_dir / "interactions.log")
        self.error_log = self._setup_logger("error", self.log_dir / "errors.log")
        self.performance_log = self._setup_logger("performance", self.log_dir / "performance.log")
        
        # Exportera diagnostikdata periodiskt
        self.debug = debug
        
    def _setup_logger(self, name: str, log_file: Path) -> logging.Logger:
        """Konfigurera en specifik loggare"""
        logger = logging.getLogger(f"bot.{name}")
        
        # Filhanterare
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(file_handler)
        
        # Ställ in lägsta nivå
        logger.setLevel(logging.INFO)
        
        return logger
    
    def log_interaction(self, query: str, response: Dict[str, Any], 
                       context: Dict[str, Any], duration_ms: float) -> None:
        """Logga en användarinteraktion"""
        # Rensa känslig eller onödig data från kontexten
        clean_context = self._clean_context(context)
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "response_status": response.get("status"),
            "intent": response.get("analysis", {}).get("primary_intent", "unknown"),
            "confidence": response.get("analysis", {}).get("confidence", 0),
            "duration_ms": duration_ms,
            "context": clean_context
        }
        
        self.interaction_log.info(json.dumps(log_entry))
        
        # Mer detaljerad loggning i debugläge
        if self.debug:
            detailed_log = {
                **log_entry,
                "full_response": response,
                "entities": response.get("analysis", {}).get("entities", [])
            }
            debug_path = self.log_dir / "debug" / f"interaction_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
            debug_path.parent.mkdir(exist_ok=True)
            with open(debug_path, 'w', encoding='utf-8') as f:
                json.dump(detailed_log, f, indent=2)
    
    def log_error(self, error_type: str, message: str, details: Dict[str, Any] = None) -> None:
        """Logga ett fel eller en varning"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "message": message,
            "details": details or {}
        }
        self.error_log.error(json.dumps(log_entry))
    
    def log_performance(self, component: str, operation: str, duration_ms: float) -> None:
        """Logga prestandamätning"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "operation": operation,
            "duration_ms": duration_ms
        }
        self.performance_log.info(json.dumps(log_entry))
    
    def _clean_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Rensa kontext från stora objekt som inte behöver loggas"""
        if not context:
            return {}
            
        # Kopiera för att undvika att modifiera originalet
        clean = {}
        
        # Behåll bara relevant information
        keys_to_keep = [
            "active_product_id", 
            "previous_intent",
            "dialog_stage",
            "expertise_level"
        ]
        
        for key in keys_to_keep:
            if key in context:
                clean[key] = context[key]
        
        # För query_history, behåll bara antal och senaste frågan
        if "query_history" in context:
            history = context["query_history"]
            clean["query_history_count"] = len(history)
            if history:
                clean["last_query"] = history[-1]
        
        return clean
```

## 3. Förbättrad indexhantering

Vi kan lägga till funktionalitet för att uppdatera och underhålla index dynamiskt:

```python
# Lägg till i DataManager-klassen

def update_index(self, index_name: str, key: str, value: Any) -> bool:
    """
    Uppdatera ett specifikt index dynamiskt
    
    Args:
        index_name: Namnet på indexet att uppdatera
        key: Nyckel att uppdatera
        value: Nytt värde
        
    Returns:
        True om uppdateringen lyckades
    """
    if index_name not in self.indices:
        logger.error(f"Indexet {index_name} finns inte")
        return False
    
    # Uppdatera indexet i minnet
    self.indices[index_name][key] = value
    
    # Uppdatera även indexfilen på disk
    index_path = self.integrated_data_dir / "indices" / f"{index_name}.json"
    try:
        # Läs nuvarande index
        with open(index_path, 'r', encoding='utf-8') as f:
            on_disk_index = json.load(f)
        
        # Uppdatera
        on_disk_index[key] = value
        
        # Spara
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(on_disk_index, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Uppdaterade index {index_name} med ny information för {key}")
        return True
        
    except Exception as e:
        logger.error(f"Fel vid uppdatering av index {index_name}: {str(e)}")
        return False

def rebuild_search_index(self) -> bool:
    """
    Bygg om sökindexet från produktdata
    
    Returns:
        True om ombyggnaden lyckades
    """
    try:
        # Initiera nytt sökindex
        text_search_index = {}
        
        # Gå igenom alla produkter
        for product_id in self.name_to_id_map.values():
            # Hämta produktsammanfattning
            summary = self.get_product_summary(product_id)
            
            if summary["status"] == "success":
                product_name = summary.get("summary", {}).get("product_name", "")
                description = summary.get("summary", {}).get("description", "")
                
                # Kombinera all relevanta text
                search_text = f"{product_name} {description}"
                
                # Lägg till tekniska specifikationer
                tech_data = self.get_technical_specs(product_id)
                if tech_data["status"] == "success":
                    for spec in tech_data.get("specs", []):
                        search_text += f" {spec.get('name', '')} {spec.get('raw_value', '')}"
                
                # Normalisera text för sökning och dela upp i ord
                search_text = search_text.lower()
                words = set(re.findall(r'\b\w+\b', search_text))
                
                # Uppdatera index
                for word in words:
                    if len(word) > 2:  # Ignorera mycket korta ord
                        if word not in text_search_index:
                            text_search_index[word] = []
                        if product_id not in text_search_index[word]:
                            text_search_index[word].append(product_id)
        
        # Uppdatera indexet i minnet
        self.indices["text_search_index"] = text_search_index
        
        # Spara till disk
        index_path = self.integrated_data_dir / "indices" / "text_search_index.json"
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(text_search_index, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Byggde om sökindexet med {len(text_search_index)} ord")
        return True
        
    except Exception as e:
        logger.error(f"Fel vid ombyggnad av sökindex: {str(e)}")
        return False
```

## 4. Användarprofiler för personalisering

Vi kan lägga till en användarprofil-klass för att spara och använda användarpreferenser:

```python
# nlp_bot_engine/dialog/user_profile.py

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

class UserProfile:
    """
    Hanterar användarprofiler för anpassade svar och personalisering.
    """
    
    def __init__(self, user_id: str, profiles_dir: str = "./profiles"):
        """
        Initialisera användarprofil
        
        Args:
            user_id: Användarens ID
            profiles_dir: Katalog för profilfiler
        """
        self.user_id = user_id
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(exist_ok=True, parents=True)
        
        # Profildata
        self.profile_data = self.load_profile()
        
        # Om profilen är ny, initiera med standardvärden
        if not self.profile_data:
            self.profile_data = {
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "interaction_count": 0,
                "expertise_level": "beginner",
                "preferences": {
                    "detail_level": "medium",
                    "technical_focus": False,
                    "show_images": True
                },
                "viewed_products": [],
                "frequent_categories": {},
                "searches": [],
                "language": "sv"
            }
            self.save_profile()
    
    def load_profile(self) -> Dict[str, Any]:
        """
        Ladda användarprofil från disk
        
        Returns:
            Profildata eller tom dict om profilen inte finns
        """
        profile_path = self.profiles_dir / f"{self.user_id}.json"
        
        if profile_path.exists():
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        
        return {}
    
    def save_profile(self) -> bool:
        """
        Spara användarprofil till disk
        
        Returns:
            True om sparandet lyckades
        """
        profile_path = self.profiles_dir / f"{self.user_id}.json"
        
        try:
            # Uppdatera tidsstämpel
            self.profile_data["last_active"] = datetime.now().isoformat()
            
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(self.profile_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception:
            return False
    
    def update_from_interaction(self, query: str, response: Dict[str, Any]) -> None:
        """
        Uppdatera profilen baserat på en interaktion
        
        Args:
            query: Användarens fråga
            response: Botens svar
        """
        # Uppdatera interaktionsräknare
        self.profile_data["interaction_count"] += 1
        
        # Uppdatera senaste aktivitet
        self.profile_data["last_active"] = datetime.now().isoformat()
        
        # Lägg till i sökhistorik
        if "search" in response.get("query_type", ""):
            searches = self.profile_data.get("searches", [])
            searches.append({
                "query": query,
                "timestamp": datetime.now().isoformat()
            })
            # Behåll bara de 20 senaste sökningarna
            self.profile_data["searches"] = searches[-20:]
        
        # Lägg till visade produkter
        product_id = response.get("product_id")
        if product_id:
            viewed = self.profile_data.get("viewed_products", [])
            
            # Kontrollera om produkten redan finns i listan
            already_exists = False
            for item in viewed:
                if item.get("product_id") == product_id:
                    # Uppdatera befintlig post
                    item["view_count"] = item.get("view_count", 0) + 1
                    item["last_viewed"] = datetime.now().isoformat()
                    already_exists = True
                    break
            
            # Lägg till ny produkt om den inte redan finns
            if not already_exists:
                viewed.append({
                    "product_id": product_id,
                    "view_count": 1,
                    "first_viewed": datetime.now().isoformat(),
                    "last_viewed": datetime.now().isoformat()
                })
            
            # Sortera efter senast visad
            viewed = sorted(viewed, key=lambda x: x.get("last_viewed", ""), reverse=True)
            
            # Behåll bara de 50 senaste
            self.profile_data["viewed_products"] = viewed[:50]
        
        # Uppdatera expertisgrad baserat på interaktioner
        self.update_expertise_level(query, response)
        
        # Spara den uppdaterade profilen
        self.save_profile()
    
    def update_expertise_level(self, query: str, response: Dict[str, Any]) -> None:
        """
        Uppdatera expertisgrad baserat på interaktion
        
        Args:
            query: Användarens fråga
            response: Botens svar
        """
        current_level = self.profile_data.get("expertise_level", "beginner")
        
        # Räkna tekniska termer i frågan
        technical_terms = [
            "dimension", "specifikation", "effekt", "kompatibilitet", "material",
            "montering", "volt", "ampere", "newton", "pascal", "frekvens"
        ]
        
        query_lower = query.lower()
        tech_term_count = sum(1 for term in technical_terms if term in query_lower)
        
        # Identifiera komplexa frågor
        is_complex = len(query.split()) > 10 or "jämför" in query_lower
        
        # Uppdatera expertisgrad baserat på tecken
        if current_level == "beginner":
            if tech_term_count >= 2 or is_complex:
                self.profile_data["expertise_level"] = "intermediate"
        elif current_level == "intermediate":
            if tech_term_count >= 3 and is_complex:
                self.profile_data["expertise_level"] = "expert"
        elif current_level == "expert":
            # Behåll expertnivå, men uppdatera preferenser
            if tech_term_count > 0:
                self.profile_data["preferences"]["technical_focus"] = True
                
        # Ytterligare faktorer: interaktionsantalet
        if self.profile_data["interaction_count"] > 20 and current_level == "beginner":
            self.profile_data["expertise_level"] = "intermediate"
        elif self.profile_data["interaction_count"] > 50 and current_level == "intermediate":
            self.profile_data["expertise_level"] = "expert"
    
    def get_preference(self, key: str, default=None) -> Any:
        """Hämta en specifik preferens"""
        return self.profile_data.get("preferences", {}).get(key, default)
    
    def set_preference(self, key: str, value: Any) -> None:
        """Sätt en specifik preferens"""
        if "preferences" not in self.profile_data:
            self.profile_data["preferences"] = {}
        
        self.profile_data["preferences"][key] = value
        self.save_profile()
    
    def get_recently_viewed_products(self, limit: int = 5) -> List[str]:
        """Hämta nyligen visade produkter"""
        viewed = self.profile_data.get("viewed_products", [])
        return [item.get("product_id") for item in viewed[:limit]]
```

## 5. Stavningskontroll och korrigeringsmekanism

Vi kan lägga till stavningskontroll för att hantera felstavningar i frågor:

```python
# nlp_bot_engine/utils/spell_checker.py

import re
from typing import Tuple, List, Dict, Set

class SpellChecker:
    """
    Enkel stavningskontroll specialiserad på produktterminologi.
    """
    
    def __init__(self, product_names: List[str] = None, custom_dictionary: List[str] = None):
        """
        Initialisera stavningskontroll
        
        Args:
            product_names: Lista med produktnamn för domänspecifik kontroll
            custom_dictionary: Lista med specialtermer att inkludera
        """
        # Grundläggande svenska ord
        self.dictionary = set([
            "produkt", "är", "och", "till", "från", "med", "utan", "för", 
            "hur", "vad", "vilken", "passar", "fungerar", "kan", "mått", 
            "dimensioner", "storlek", "färg", "material", "vikt", "pris",
            "teknisk", "specifikation", "kompatibel", "installation"
        ])
        
        # Specialiserad domänspecifik ordlista
        self.domain_terms = set([
            "artikelnummer", "monteringsanvisning", "handtag", "trycke", 
            "beslag", "dörr", "fönster", "montering", "låsregel", "stolpe"
        ])
        
        # Lägg till anpassade ord
        if custom_dictionary:
            self.domain_terms.update(custom_dictionary)
        
        # Lägg till produktnamn
        self.product_terms = set()
        if product_names:
            for name in product_names:
                # Dela upp sammansatta produktnamn i delar
                parts = re.findall(r'\b\w+\b', name.lower())
                self.product_terms.update(parts)
        
        # Kombinera alla ordlistor
        self.all_terms = self.dictionary | self.domain_terms | self.product_terms
    
    def check_and_suggest(self, text: str) -> Tuple[str, bool, List[Tuple[str, str]]]:
        """
        Kontrollera och föreslå korrigeringar för text
        
        Args:
            text: Texten att kontrollera
            
        Returns:
            Tuppel med (korrigerad text, om korrigerad, lista med korrigeringar)
        """
        words = re.findall(r'\b\w+\b', text.lower())
        corrections = []
        was_corrected = False
        
        for word in words:
            # Hoppa över korta ord och siffror
            if len(word) <= 2 or word.isdigit():
                continue
            
            # Kolla om ordet finns i våra ordlistor
            if word in self.all_terms:
                continue
            
            # Hitta närmaste matchning
            suggestion, distance = self.find_closest(word)
            
            # Om vi hittar en tillräckligt nära matchning
            if suggestion and distance <= 2:
                corrections.append((word, suggestion))
                was_corrected = True
        
        # Utför korrigeringar
        corrected_text = text
        if was_corrected:
            for original, correction in corrections:
                # Skapa ett mönster som matchar hela ordet
                pattern = r'\b' + re.escape(original) + r'\b'
                corrected_text = re.sub(pattern, correction, corrected_text, flags=re.IGNORECASE)
        
        return corrected_text, was_corrected, corrections
    
    def find_closest(self, word: str) -> Tuple[str, int]:
        """
        Hitta närmaste ordet i ordlistan
        
        Args:
            word: Ordet att hitta matchning för
            
        Returns:
            Tuppel med (närmaste matchning, avstånd)
        """
        # Prioritera domän- och produkttermer
        candidates = list(self.domain_terms) + list(self.product_terms) + list(self.dictionary)
        
        best_match = None
        best_distance = float('inf')
        
        # Kontrollera först om ordet börjar på samma sätt som någon term (prefix-matchning)
        prefix_candidates = [c for c in candidates if c.startswith(word[:2])]
        
        # Om vi har prefix-matchningar, begränsa sökningen till dem
        search_candidates = prefix_candidates if prefix_candidates else candidates
        
        for candidate in search_candidates:
            # Hoppa över för stor skillnad i längd
            if abs(len(candidate) - len(word)) > 3:
                continue
                
            distance = self.levenshtein_distance(word, candidate)
            
            if distance < best_distance:
                best_distance = distance
                best_match = candidate
        
        return best_match, best_distance
    
    def levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Beräkna Levenshtein-avstånd mellan två strängar
        
        Args:
            s1: Första strängen
            s2: Andra strängen
            
        Returns:
            Levenshtein-avstånd (antal ändringar)
        """
        # Optimerad implementation för prestanda
        if len(s1) < len(s2):
            return self.levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
```

## 6. Integrering med huvudmotorn

För att integrera de nya funktionerna i huvudmotorn, kan vi uppdatera konstruktorn i `AdvancedBotEngine`:

```python
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
    
    # Initiera logghanterare
    self.logging_manager = LoggingManager(
        log_dir=str(self.config.base_dir / "logs"), 
        debug=self.config.debug
    )
    
    # Initiera stavningskontroll med produktnamn
    product_names = list(self.data_manager.name_to_id_map.keys())
    self.spell_checker = SpellChecker(product_names)
    
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
```

Och uppdatera `process_natural_language` för att inkludera stavningskontroll:

```python
def process_natural_language(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Processera naturligt språk med avancerad NLP och kontextförstående
    
    Args:
        query: Användarens fråga
        context: Kontextinformation
        
    Returns:
        Svarsobjekt med analysresultat och formaterad text
    """
    start_time = datetime.now()
    
    try:
        # Initiera kontext om den saknas
        context = context or {}
        
        # 1. Kontrollera stavning och korrigera vid behov
        corrected_query, was_corrected, corrections = self.spell_checker.check_and_suggest(query)
        
        # Använd korrigerad fråga för vidare processning
        processing_query = corrected_query if was_corrected else query
        
        # 2. Utför NLP-förbehandling
        processed_text = self.nlp_processor.preprocess(processing_query)
        
        # 3. Analysera kontext och lös referenser
        context_analysis = self.context_manager.analyze_context(processing_query, context)
        
        # 4. Extrahera entiteter (produkter, egenskaper, etc.)
        entities = self.entity_extractor.extract_entities(processed_text, context)
        
        # 5. Analysera intention (vad användaren vill göra)
        intent_analysis = self.intent_analyzer.analyze_intent(processed_text, entities, context)
        
        # 6. Kombinera all information i analysobjekt
        analysis = {
            "original_query": query,
            "corrected_query": corrected_query if was_corrected else None,
            "was_corrected": was_corrected,
            "corrections": corrections,
            "processed_text": processed_text,
            "entities": entities,
            "intents": intent_analysis["intents"],
            "primary_intent": intent_analysis["primary_intent"],
            "confidence": intent_analysis["confidence"],
            "context_references": context_analysis.get("references", []),
            "resolved_entities": context_analysis.get("resolved_entities", {})
        }
        
        # 7. Hantera osäkerhet om konfidensen är låg
        if intent_analysis["confidence"] < self.config.min_confidence:
            result = self.handle_low_confidence(analysis, context)
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.logging_manager.log_interaction(query, result, context, duration_ms)
            return result
            
        # 8. Hämta produktinformation eller utför sökning baserat på analys
        result = self.execute_intent(analysis, context)
        
        # 9. Generera anpassat svar baserat på intention och resultat
        response = {
            "status": "success" if result.get("status") != "error" else "error",
            "query_type": "natural_language",
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis,
            "result": result
        }
        
        # 10. Inkludera information om stavningskorrigering
        if was_corrected:
            response["spelling_correction"] = {
                "original": query,
                "corrected": corrected_query,
                "corrections": corrections
            }
        
        # 11. Generera formaterad text från svarsgenereringen
        response["formatted_text"] = self.response_generator.generate_nl_response(
            analysis, result, context
        )
        
        # 12. Uppdatera statistik
        if response["status"] == "success":
            self.stats["successful_queries"] += 1
        else:
            self.stats["failures"] += 1
        
        # 13. Logga interaktion
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        self.logging_manager.log_interaction(query, response, context, duration_ms)

        return response
        
    except Exception as e:
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"Fel vid processning av naturligt språk: {str(e)}")
        self.stats["failures"] += 1
        
        error_response = {
            "status": "error",
            "message": f"Ett fel uppstod vid analys av din fråga: {str(e)}",
            "query": query
        }
        
        self.logging_manager.log_error("processing_error", str(e), {"query": query})
        self.logging_manager.log_interaction(query, error_response, context, duration_ms)
        
        return error_response
```

## 7. Produktjämförelsekomponent

En användbar funktion är att kunna jämföra produkter. Låt oss lägga till en komponent för det:

```python
# nlp_bot_engine/utils/product_comparator.py

from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class ProductComparator:
    """
    Jämför två eller flera produkter och genererar en jämförelsetabell.
    """
    
    def __init__(self, data_manager):
        """
        Initialisera komparatorn
        
        Args:
            data_manager: Datahanterare för att hämta produktdata
        """
        self.data_manager = data_manager
    
    def compare_products(self, product_ids: List[str]) -> Dict[str, Any]:
        """
        Jämför flera produkter och hitta likheter och skillnader
        
        Args:
            product_ids: Lista med produkt-ID att jämföra
            
        Returns:
            Jämförelseresultat med likheter, skillnader och formaterad tabell
        """
        if len(product_ids) < 2:
            return {
                "status": "error",
                "message": "Minst två produkter behövs för jämförelse"
            }
        
        # Hämta produktdata för alla produkter
        products_data = []
        product_names = []
        
        for product_id in product_ids:
            tech_data = self.data_manager.get_technical_specs(product_id)
            summary = self.data_manager.get_product_summary(product_id)
            
            if tech_data["status"] != "success" or summary["status"] != "success":
                continue
            
            # Få produktnamn
            product_name = summary.get("summary", {}).get("product_name", f"Produkt {product_id}")
            product_names.append(product_name)
            
            # Samla specifikationer
            specs = {}
            for spec in tech_data.get("specs", []):
                name = spec.get("name", "").lower()
                if name:
                    specs[name] = {
                        "raw_value": spec.get("raw_value", ""),
                        "unit": spec.get("unit", ""),
                        "normalized_value": spec.get("normalized_value"),
                        "category": spec.get("category", "")
                    }
            
            products_data.append({
                "product_id": product_id,
                "name": product_name,
                "specs": specs
            })
        
        # Om vi inte kunde hämta data för minst två produkter
        if len(products_data) < 2:
            return {
                "status": "error",
                "message": "Kunde inte hämta tillräckligt med data för jämförelse"
            }
        
        # Hitta gemensamma specifikationer
        common_specs = self.find_common_specs(products_data)
        
        # Hitta unika specifikationer för varje produkt
        unique_specs = self.find_unique_specs(products_data)
        
        # Hitta viktiga skillnader
        key_differences = self.identify_key_differences(products_data, common_specs)
        
        # Formatera resultaten
        comparison_table = self.format_comparison_table(products_data, common_specs, key_differences)
        
        return {
            "status": "success",
            "product_ids": product_ids,
            "product_names": product_names,
            "common_specs": common_specs,
            "unique_specs": unique_specs,
            "key_differences": key_differences,
            "formatted_text": comparison_table
        }
    
    def find_common_specs(self, products_data: List[Dict[str, Any]]) -> Dict[str, List[Any]]:
        """
        Hitta specifikationer som är gemensamma för alla produkter
        
        Args:
            products_data: Lista med produktdata
            
        Returns:
            Dict med gemensamma specifikationer
        """
        # Hitta alla specifikationsnamn
        all_spec_names = set()
        for product in products_data:
            all_spec_names.update(product["specs"].keys())
        
        # Kontrollera vilka som finns för alla produkter
        common_specs = {}
        for spec_name in all_spec_names:
            values = []
            
            for product in products_data:
                if spec_name in product["specs"]:
                    spec = product["specs"][spec_name]
                    values.append({
                        "product_id": product["product_id"],
                        "value": spec["raw_value"],
                        "unit": spec["unit"],
                        "normalized": spec["normalized_value"]
                    })
                else:
                    break  # Inte gemensam om den saknas för någon produkt
            
            # Om vi har värden för alla produkter, lägg till som gemensam
            if len(values) == len(products_data):
                # Hämta kategori från första produkten (bör vara samma för alla)
                category = products_data[0]["specs"].get(spec_name, {}).get("category", "Övrigt")
                common_specs[spec_name] = {
                    "values": values,
                    "category": category,
                    "is_identical": self.are_values_identical(values)
                }
        
        return common_specs
    
    def find_unique_specs(self, products_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Hitta unika specifikationer för varje produkt
        
        Args:
            products_data: Lista med produktdata
            
        Returns:
            Dict med unika specifikationer per produkt
        """
        # Hitta alla specifikationsnamn totalt
        all_spec_names = set()
        for product in products_data:
            all_spec_names.update(product["specs"].keys())
        
        # För varje produkt, hitta vilka specifikationer som är unika
        unique_specs = {}
        
        for product in products_data:
            product_id = product["product_id"]
            unique_for_product = {}
            
            for spec_name, spec in product["specs"].items():
                # Kontrollera om denna specifikation finns i någon annan produkt
                is_unique = True
                for other_product in products_data:
                    if other_product["product_id"] != product_id and spec_name in other_product["specs"]:
                        is_unique = False
                        break
                
                if is_unique:
                    unique_for_product[spec_name] = {
                        "value": spec["raw_value"],
                        "unit": spec["unit"],
                        "category": spec["category"]
                    }
            
            if unique_for_product:
                unique_specs[product_id] = unique_for_product
        
        return unique_specs
    
    def identify_key_differences(self, products_data: List[Dict[str, Any]], 
                                common_specs: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Identifiera de viktigaste skillnaderna mellan produkterna
        
        Args:
            products_data: Lista med produktdata
            common_specs: Gemensamma specifikationer
            
        Returns:
            Dict med viktiga skillnader
        """
        # Fokusera på gemensamma specifikationer som har olika värden
        key_differences = {}
        
        for spec_name, spec_data in common_specs.items():
            if not spec_data["is_identical"]:
                # Kontrollera om detta är en viktig skillnad
                # Baserat på kategori: Dimensioner, Material, Vikt, etc. är ofta viktiga
                category = spec_data["category"]
                
                # Viktiga kategorier som vi alltid vill visa skillnader för
                important_categories = [
                    "Dimension", "Dimensioner", "Mått", "Storlek", 
                    "Material", "Vikt", "Prestanda", "Effekt"
                ]
                
                is_important = (
                    category in important_categories or
                    any(cat.lower() in category.lower() for cat in important_categories)
                )
                
                # Kontrollera även stora skillnader i numeriska värden
                values = spec_data["values"]
                numeric_values = [v["normalized"] for v in values if v["normalized"] is not None]
                
                has_large_diff = False
                if len(numeric_values) > 1 and all(isinstance(v, (int, float)) for v in numeric_values):
                    min_val = min(numeric_values)
                    max_val = max(numeric_values)
                    
                    # Om skillnaden är mer än 20% av minvärdet, betrakta som stor
                    if min_val > 0 and max_val / min_val > 1.2:
                        has_large_diff = True
                
                if is_important or has_large_diff:
                    key_differences[spec_name] = {
                        "values": values,
                        "category": category,
                        "importance": "high" if is_important else "medium"
                    }
        
        return key_differences
    
    def format_comparison_table(self, products_data: List[Dict[str, Any]], 
                               common_specs: Dict[str, Any],
                               key_differences: Dict[str, Dict[str, Any]]) -> str:
        """
        Formatera en jämförelsetabell
        
        Args:
            products_data: Lista med produktdata
            common_specs: Gemensamma specifikationer
            key_differences: Viktiga skillnader
            
        Returns:
            Formaterad jämförelsetabell som markdown
        """
        # Skapa tabellhuvud
        table_lines = ["# Produktjämförelse\n"]
        
        # Produktnamn i tabellhuvudet
        header = "| Egenskap |"
        divider = "|----------|"
        
        for product in products_data:
            product_name = product["name"]
            header += f" {product_name} |"
            divider += "------------|"
        
        table_lines.append(header)
        table_lines.append(divider)
        
        # Lägg till viktiga skillnader först
        if key_differences:
            table_lines.append("\n### Viktiga skillnader\n")
            
            for spec_name, diff_data in key_differences.items():
                row = f"| **{spec_name.title()}** |"
                
                for product in products_data:
                    product_id = product["product_id"]
                    
                    # Hitta värdet för denna produkt
                    value = ""
                    for val_data in diff_data["values"]:
                        if val_data["product_id"] == product_id:
                            value = val_data["value"]
                            if val_data["unit"] and val_data["unit"] not in value:
                                value += f" {val_data['unit']}"
                            break
                    
                    row += f" {value} |"
                
                table_lines.append(row)
        
        # Lägg till andra gemensamma specifikationer
        if common_specs:
            table_lines.append("\n### Gemensamma egenskaper\n")
            
            # Gruppera efter kategori för bättre struktur
            specs_by_category = {}
            for spec_name, spec_data in common_specs.items():
                if spec_name in key_differences:
                    continue  # Skippa de som redan visats
                    
                category = spec_data["category"]
                if category not in specs_by_category:
                    specs_by_category[category] = []
                
                specs_by_category[category].append((spec_name, spec_data))
            
            # Lägg till kategorivis
            for category, specs in specs_by_category.items():
                for spec_name, spec_data in specs:
                    row = f"| {spec_name.title()} |"
                    
                    for product in products_data:
                        product_id = product["product_id"]
                        
                        # Hitta värdet för denna produkt
                        value = ""
                        for val_data in spec_data["values"]:
                            if val_data["product_id"] == product_id:
                                value = val_data["value"]
                                if val_data["unit"] and val_data["unit"] not in value:
                                    value += f" {val_data['unit']}"
                                break
                        
                        row += f" {value} |"
                    
                    table_lines.append(row)
        
        # Lägg till unika specifikationer
        unique_specs = self.find_unique_specs(products_data)
        if any(unique_specs.values()):
            table_lines.append("\n### Unika egenskaper\n")
            
            for product in products_data:
                product_id = product["product_id"]
                product_name = product["name"]
                
                if product_id in unique_specs and unique_specs[product_id]:
                    table_lines.append(f"\n**Unika för {product_name}:**\n")
                    
                    for spec_name, spec_data in unique_specs[product_id].items():
                        value = spec_data["value"]
                        if spec_data["unit"] and spec_data["unit"] not in value:
                            value += f" {spec_data['unit']}"
                            
                        table_lines.append(f"- **{spec_name.title()}:** {value}")
        
        return "\n".join(table_lines)
    
    def are_values_identical(self, values: List[Dict[str, Any]]) -> bool:
        """
        Kontrollera om alla värden är identiska
        
        Args:
            values: Lista med värden
            
        Returns:
            True om alla värden är identiska
        """
        if not values:
            return True
            
        # Kontrollera råvärden
        raw_values = [v["value"] for v in values]
        if all(v == raw_values[0] for v in raw_values):
            return True
        
        # Om råvärden skiljer sig, kontrollera normaliserade värden
        norm_values = [v["normalized"] for v in values if v["normalized"] is not None]
        
        # Om vi har normaliserade värden för alla, jämför dem
        if norm_values and len(norm_values) == len(values):
            return all(v == norm_values[0] for v in norm_values)
        
        return False
```

## 8. Implementering i `bot_engine`-klassen

För att använda dessa nya komponenter, uppdatera `AdvancedBotEngine`-klassen med en ny metod för att hantera produktjämförelser:

```python
def compare_products(self, product_ids: List[str], context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Jämför två eller flera produkter och generera en jämförelsetabell
    
    Args:
        product_ids: Lista med produkt-ID att jämföra
        context: Kontextinformation
        
    Returns:
        Jämförelseresultat med formaterad tabell
    """
    if not hasattr(self, 'product_comparator'):
        from ..utils.product_comparator import ProductComparator
        self.product_comparator = ProductComparator(self.data_manager)
    
    # Utför jämförelsen
    comparison = self.product_comparator.compare_products(product_ids)
    
    # Om jämförelsen misslyckades
    if comparison.get("status") != "success":
        return {
            "status": "error",
            "message": comparison.get("message", "Kunde inte jämföra produkterna"),
            "product_ids": product_ids
        }
    
    # Generera ett formaterat svar
    response = {
        "status": "success",
        "query_type": "product_comparison",
        "product_ids": product_ids,
        "comparison": comparison,
        "formatted_text": comparison.get("formatted_text", "")
    }
    
    return response
```

`execute_intent` för att lägga till "comparison" som en intentionstyp:

```python
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
    
    # Hämta entiteter
    entities = analysis["entities"]
    
    # Hämta produkt-ID:n om de finns i analysen
    product_ids = []
    for entity in entities:
        if entity["type"] == "PRODUCT" and entity.get("product_id"):
            product_ids.append(entity["product_id"])
    
    # Om inga produkt-ID, se om det finns ett i context
    if not product_ids and context.get("active_product_id"):
        product_ids.append(context["active_product_id"])
    
    # Specialfall: Om intentionen är jämförelse och vi har minst två produkter
    if intent == "comparison" and len(product_ids) >= 2:
        return self.compare_products(product_ids, context)
    
    # Standardfall: Om vi har minst en produkt
    if product_ids:
        product_id = product_ids[0]  # Använd första produkten
        
        if intent == "technical":
            return self.data_manager.get_technical_specs(product_id)
        elif intent == "compatibility":
            return self.data_manager.get_compatibility_info(product_id)
        elif intent == "summary":
            return self.data_manager.get_product_summary(product_id)
        elif intent == "search":
            # Sök efter relaterade produkter
            search_terms = " ".join([e["text"] for e in entities if e["type"] != "PRODUCT"])
            return self.data_manager.search_products(search_terms)
        else:
            # Default till sammanfattning om intentionen är oklar
            return self.data_manager.get_product_summary(product_id)
    
    # Om vi inte har en produkt men intentionen är sökning
    if intent == "search" or not product_ids:
        search_query = analysis["processed_text"]
        return self.data_manager.search_products(search_query)
    
    # Fallback om inget matchade
    return {
        "status": "error",
        "message": "Kunde inte utföra någon åtgärd baserat på din fråga. Var mer specifik eller ange en produkt."
    }
```

