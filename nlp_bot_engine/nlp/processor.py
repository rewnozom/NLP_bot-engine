# nlp_bot_engine/nlp/processor.py

import re
import logging
import unicodedata
from typing import Dict, List, Any, Optional, Tuple, Union
import importlib.util

from ..core.config import BotConfig

logger = logging.getLogger(__name__)

class NLPProcessor:
    """
    Huvudprocessor för NLP-funktionalitet.
    Ansvarar för tokenisering, lemmatisering, och grundläggande textbearbetning.
    Fungerar som gränssnitt mot underliggande NLP-bibliotek.
    """
    
    def __init__(self, config: BotConfig):
        """
        Initialisera NLP-processorn
        
        Args:
            config: Konfigurationsobjekt
        """
        self.config = config
        self.nlp = None
        self.embedding_model = None
        
        # Ladda spaCy-modell om tillgänglig
        if config.use_nlp:
            self.load_spacy()
            self.load_embedding_model()
    
    def load_spacy(self) -> bool:
        """
        Ladda spaCy-modellen
        
        Returns:
            True om laddningen lyckades, annars False
        """
        try:
            # Kolla om spaCy är installerat
            if importlib.util.find_spec("spacy") is None:
                logger.warning("spaCy är inte installerat. Vissa NLP-funktioner kommer att vara begränsade.")
                return False
            
            import spacy
            self.nlp = spacy.load(self.config.spacy_model)
            logger.info(f"Laddade spaCy-modell: {self.config.spacy_model}")
            self.add_custom_components()
            return True
            
        except Exception as e:
            logger.error(f"Kunde inte ladda spaCy-modell: {str(e)}")
            return False
    
    def load_embedding_model(self) -> bool:
        """
        Ladda modell för embeddings (vektorrepresentationer)
        
        Returns:
            True om laddningen lyckades, annars False
        """
        try:
            # Kolla om transformers är installerat
            if importlib.util.find_spec("transformers") is None:
                logger.warning("transformers är inte installerat. Semantisk sökning kommer att vara begränsad.")
                return False
            
            from transformers import AutoTokenizer, AutoModel
            import torch
            
            # Ladda tokenizer och modell
            tokenizer = AutoTokenizer.from_pretrained(self.config.embeddings_model)
            model = AutoModel.from_pretrained(self.config.embeddings_model)
            
            # Spara som attribut
            self.embedding_tokenizer = tokenizer
            self.embedding_model = model
            
            logger.info(f"Laddade embedding-modell: {self.config.embeddings_model}")
            return True
            
        except Exception as e:
            logger.error(f"Kunde inte ladda embedding-modell: {str(e)}")
            self.embedding_tokenizer = None
            self.embedding_model = None
            return False
    
    def add_custom_components(self) -> None:
        """
        Lägg till anpassade komponenter till spaCy-pipelinen
        """
        if not self.nlp:
            return
        
        try:
            # Kontrollera om entity ruler redan finns
            if not self.nlp.has_pipe("entity_ruler"):
                # Skapa entity ruler med factory-metoden
                ruler = self.nlp.add_pipe("entity_ruler", before="ner")
                
                # Lägg till mönster för produktentiteter
                patterns = [
                    # EAN-mönster
                    {"label": "EAN", "pattern": [{"SHAPE": "dddddddddddd"}]},  # 12-siffrig (UPC)
                    {"label": "EAN", "pattern": [{"SHAPE": "ddddddddddddd"}]},  # 13-siffrig (EAN-13)
                    
                    # Artikelnummermönster
                    {"label": "PRODUCT", "pattern": [
                        {"LOWER": {"IN": ["artikelnr", "art.nr", "artnr", "artikel", "art", "artikelnummer"]}}, 
                        {"IS_PUNCT": True, "OP": "?"}, 
                        {"TEXT": {"REGEX": "[A-Z0-9\\-]{4,15}"}}
                    ]},
                    
                    # Produktmodellmönster
                    {"label": "PRODUCT", "pattern": [
                        {"LOWER": {"IN": ["modell", "model"]}},
                        {"IS_PUNCT": True, "OP": "?"},
                        {"TEXT": {"REGEX": "[A-Z0-9\\-]{2,10}"}}
                    ]},
                    
                    # Dimensionsmönster
                    {"label": "DIMENSION", "pattern": [
                        {"TEXT": {"REGEX": "\\d+(?:[.,]\\d+)?"}}, 
                        {"LOWER": {"IN": ["mm", "cm", "m", "tum", "millimeter", "centimeter", "meter"]}}
                    ]},
                    
                    # Kompatibilitetsmönster
                    {"label": "COMPATIBILITY", "pattern": [
                        {"LOWER": {"IN": ["kompatibel", "passar", "fungerar"]}},
                        {"LOWER": {"IN": ["med", "till", "för", "tillsammans"]}},
                        {"POS": "NOUN"}
                    ]}
                ]
                
                ruler.add_patterns(patterns)
                logger.info("Lade till anpassade entitetsigenkänningskomponenter")
        
        except Exception as e:
            logger.error(f"Fel vid tillägg av anpassade komponenter: {str(e)}")
    
    def preprocess(self, text: str) -> str:
        """
        Förbehandla text innan NLP-analys
        
        Args:
            text: Texten att förbehandla
            
        Returns:
            Förbehandlad text
        """
        # Standardisera whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Normalisera unicode-tecken
        text = unicodedata.normalize('NFKD', text)
        
        # Standardisera punktuation (t.ex. ersätt dubbla streck med enkla)
        text = re.sub(r'--', '-', text)
        text = re.sub(r'\.\.+', '...', text)
        
        # Standardisera citat
        text = re.sub(r'[""„]', '"', text)
        text = re.sub(r'[''`]', "'", text)
        
        return text
    
    def tokenize(self, text: str) -> List[Dict[str, Any]]:
        """
        Tokenisera text i ord och meningar
        
        Args:
            text: Texten att tokenisera
            
        Returns:
            Lista med tokens och deras attribut
        """
        if not self.nlp:
            # Enkel tokenisering om spaCy inte är tillgänglig
            return [{"text": token} for token in text.split()]
        
        doc = self.nlp(text)
        
        # Extrahera token-information
        tokens = []
        for token in doc:
            tokens.append({
                "text": token.text,
                "lemma": token.lemma_,
                "pos": token.pos_,
                "is_stop": token.is_stop,
                "i": token.i,  # Index inom dokumentet
                "start_char": token.idx,  # Startposition i texten
                "end_char": token.idx + len(token.text)  # Slutposition i texten
            })
        
        return tokens
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Utför fullständig språkanalys på texten
        
        Args:
            text: Texten att analysera
            
        Returns:
            Dict med analysresultat
        """
        if not self.nlp:
            logger.warning("spaCy inte tillgänglig, kan inte utföra fullständig analys")
            return {
                "tokens": self.tokenize(text),
                "entities": [],
                "sentences": [text]
            }
        
        # Preprocessa och analysera
        preprocessed_text = self.preprocess(text)
        doc = self.nlp(preprocessed_text)
        
        # Extrahera entiteter
        entities = []
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "label": ent.label_,
                "start_char": ent.start_char,
                "end_char": ent.end_char,
                "start_token": ent.start,
                "end_token": ent.end
            })
        
        # Extrahera meningar
        sentences = []
        for sent in doc.sents:
            sentences.append(sent.text)
        
        # Extrahera substantiv och andra viktiga termer
        key_terms = []
        for token in doc:
            if token.pos_ in ["NOUN", "PROPN", "ADJ"] and not token.is_stop:
                key_terms.append({
                    "text": token.text,
                    "lemma": token.lemma_,
                    "pos": token.pos_
                })
        
        return {
            "tokens": self.tokenize(preprocessed_text),
            "entities": entities,
            "sentences": sentences,
            "key_terms": key_terms
        }
    
    def extract_key_terms(self, text: str) -> List[str]:
        """
        Extrahera nyckeltermer från texten (substantiv, egennamn, etc.)
        
        Args:
            text: Texten att analysera
            
        Returns:
            Lista med nyckeltermer
        """
        if not self.nlp:
            # Enkel extrahering baserat på ordlängd och frekvens
            words = text.lower().split()
            # Filtrera bort korta ord och vanliga stoppord
            stopwords = {"och", "eller", "men", "om", "så", "att", "en", "ett", "den", "det", "de", "i", "på", "med", "för", "till"}
            key_terms = [word for word in words if len(word) > 3 and word not in stopwords]
            return list(set(key_terms))  # Ta bort dubletter
        
        doc = self.nlp(text)
        key_terms = []
        
        for token in doc:
            # Inkludera substantiv, egennamn, adjektiv och siffror
            if (token.pos_ in ["NOUN", "PROPN", "ADJ", "NUM"] and not token.is_stop) or token.ent_type_:
                key_terms.append(token.lemma_)
        
        return list(set(key_terms))  # Ta bort dubletter
    
    def get_embeddings(self, text: str) -> Optional[List[float]]:
        """
        Skapa vektorrepresentation (embedding) för en text
        
        Args:
            text: Texten att skapa embedding för
            
        Returns:
            Vektor som representerar texten eller None om det inte går
        """
        if not self.embedding_model or not self.embedding_tokenizer:
            logger.warning("Embedding-modell inte tillgänglig, kan inte generera vektorrepresentation")
            return None
        
        try:
            import torch
            
            # Tokenisera texten
            inputs = self.embedding_tokenizer(
                text, 
                return_tensors="pt", 
                padding=True, 
                truncation=True, 
                max_length=512
            )
            
            # Generera embeddings
            with torch.no_grad():
                outputs = self.embedding_model(**inputs)
            
            # Använd genomsnitt av sista lagrets hidden states
            embeddings = outputs.last_hidden_state.mean(dim=1)
            
            # Konvertera till lista för enklare serialisering
            return embeddings[0].tolist()
            
        except Exception as e:
            logger.error(f"Fel vid generering av embeddings: {str(e)}")
            return None
    
    def semantic_similarity(self, text1: str, text2: str) -> Optional[float]:
        """
        Beräkna semantisk likhet mellan två texter
        
        Args:
            text1: Första texten
            text2: Andra texten
            
        Returns:
            Likhetsvärde mellan 0 och 1, eller None vid fel
        """
        emb1 = self.get_embeddings(text1)
        emb2 = self.get_embeddings(text2)
        
        if emb1 is None or emb2 is None:
            return None
        
        try:
            import numpy as np
            
            # Konvertera till numpy-arrays
            vec1 = np.array(emb1)
            vec2 = np.array(emb2)
            
            # Beräkna cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
                
            return dot_product / (norm1 * norm2)
            
        except Exception as e:
            logger.error(f"Fel vid beräkning av semantisk likhet: {str(e)}")
            return None
    
    def detect_intent_keywords(self, text: str) -> Dict[str, float]:
        """
        Detektera intention baserat på nyckelord
        
        Args:
            text: Texten att analysera
            
        Returns:
            Dict med intentionstyper och deras sannolikhet
        """
        text_lower = text.lower()
        
        # Intentionsmönster med nyckelord
        intent_patterns = {
            "technical": [
                "teknisk", "specifikation", "mått", "dimension", "vikt", "material",
                "effekt", "spänning", "ström", "hur ser", "hur stor", "hur tung"
            ],
            "compatibility": [
                "passar", "kompatibel", "fungerar med", "kan användas med", "passar till",
                "monteringsstolpe", "trycke", "tillsammans med", "går att använda"
            ],
            "summary": [
                "berätta om", "vad är", "information om", "beskriv", "sammanfatta", 
                "översikt", "produktfakta", "vad betyder", "vad innebär"
            ],
            "search": [
                "hitta", "sök", "leta", "finns det", "har ni", "jag letar efter",
                "jag behöver en", "alternativ till", "liknande"
            ]
        }
        
        # Beräkna matchningspoäng för varje intention
        intent_scores = {}
        
        for intent, keywords in intent_patterns.items():
            score = sum(1.0 for keyword in keywords if keyword in text_lower)
            # Normalisera baserat på antal nyckelord
            normalized_score = score / len(keywords) if score > 0 else 0.0
            intent_scores[intent] = normalized_score
        
        # Om inga träffar, sätt summary som default med låg poäng
        if all(score == 0.0 for score in intent_scores.values()):
            intent_scores["summary"] = 0.1
        
        return intent_scores