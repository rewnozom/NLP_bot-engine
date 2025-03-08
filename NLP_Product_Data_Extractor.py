#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# NLP_Product_Data_Extractor.py

"""
Unified Product Data Extractor with NLP

This module uses NLP techniques to extract, integrate, and structure product data from markdown files.
It combines the functionality of multiple extractors (compatibility, technical specifications, product info)
and integrates all the data into a unified structure.

Features:
1. Extracts product information from all markdown files (not just _pro-documents)
2. Uses NLP for better text understanding and extraction
3. Maintains original directory structure
4. Provides comprehensive reporting
5. Handles compatibility relationships, technical specifications, and product identifiers
6. Generates structured data ready for database or API use

Dependencies:
- spaCy for NLP processing (with Swedish language model)
- pandas for data manipulation
- tqdm for progress visualization
- markdown for parsing markdown files
"""

import os
import re
import json
import shutil
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set, Union, Counter
from collections import defaultdict
import concurrent.futures
from dataclasses import dataclass, field, asdict
import importlib.util
import unicodedata
import hashlib


import json
from datetime import datetime

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Try to import the packages, provide installation instructions if not available
try:
    import spacy
    from spacy.tokens import Doc, Span, Token
    from spacy.matcher import Matcher, PhraseMatcher
    from spacy.language import Language
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    print("spaCy not installed. Please install it with: pip install spacy")
    print("After installing spaCy, download the Swedish model: python -m spacy download sv_core_news_lg")

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("tqdm not installed. Install it with: pip install tqdm")

try:
    import markdown
    import bs4
    from bs4 import BeautifulSoup
    HTML_PARSER_AVAILABLE = True
except ImportError:
    HTML_PARSER_AVAILABLE = False
    print("markdown or BeautifulSoup not installed. Install them with: pip install markdown beautifulsoup4")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("unified_extractor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============= Data Structures =============

@dataclass
class ProductIdentifier:
    """Product identifier information (article numbers, EAN, etc.)"""
    type: str
    value: str
    confidence: float = 1.0
    source_text: str = ""
    source_location: str = ""
    extracted_method: str = "regex"  # 'regex', 'nlp', 'pattern_match', etc.
    is_valid: bool = True
    validation_message: str = ""

@dataclass
class TechnicalSpecification:
    """Technical specification information"""
    category: str  # e.g., "dimensions", "electrical", "weight"
    name: str  # e.g., "height", "voltage", "weight"
    raw_value: str  # e.g., "10 cm", "220V", "5 kg"
    unit: str = ""  # e.g., "cm", "V", "kg"
    normalized_value: Optional[float] = None  # e.g., 10.0, 220.0, 5.0
    confidence: float = 1.0
    importance: str = "normal"  # "low", "normal", "high"
    source_text: str = ""
    source_location: str = ""
    extracted_method: str = "regex"

@dataclass
class CompatibilityRelation:
    """Compatibility relationship information"""
    relation_type: str  # e.g., "direct", "fits", "requires"
    related_product: str  # Name or description of related product
    numeric_ids: List[str] = field(default_factory=list)  # Article numbers or other identifiers
    context: str = ""  # Surrounding text for context
    confidence: float = 1.0
    source_text: str = ""
    source_location: str = ""
    extracted_method: str = "regex"

@dataclass
class ProductData:
    """Integrated product data"""
    product_id: str
    file_path: str
    filename: str
    product_name: str = ""
    product_description: str = ""
    identifiers: List[ProductIdentifier] = field(default_factory=list)
    specifications: List[TechnicalSpecification] = field(default_factory=list)
    compatibility: List[CompatibilityRelation] = field(default_factory=list)
    content_sample: str = ""  # First 1000 chars of the content
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def group_by_category(self):
        """Group data by categories for easier access"""
        # Group specifications by category
        specs_by_category = defaultdict(list)
        for spec in self.specifications:
            specs_by_category[spec.category].append(spec)
        
        # Group compatibility relations by type
        compat_by_type = defaultdict(list)
        for relation in self.compatibility:
            compat_by_type[relation.relation_type].append(relation)
        
        # Group identifiers by type
        ids_by_type = defaultdict(list)
        for identifier in self.identifiers:
            ids_by_type[identifier.type].append(identifier)
        
        return {
            "specs_by_category": dict(specs_by_category),
            "compat_by_type": dict(compat_by_type),
            "ids_by_type": dict(ids_by_type)
        }
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class ExtractorConfig:
    """Configuration settings for the extractor"""
    
    def __init__(self):
        # File types to process
        self.file_types = ["_pro", "_produktblad", "_TEK", "_sak", "_man", "_ins", 
                          "_CERT", "_BRO", "_INs", "_cert", "_prodblad", "_PRE", 
                          "_bro", "_mdek", "_tek", "_MAN", "_PRO"]
        
        # Base directories
        self.base_dir = Path("./test_docs")
        self.output_dir = Path("./nlp_bot_engine/data/extracted_data")
        self.integrated_dir = Path("./nlp_bot_engine/data/integrated_data")
        
        # Language model
        self.spacy_model = "sv_core_news_lg"  # Swedish large model
        
        # Entity labels for NLP processing
        self.custom_entity_labels = {
            "PRODUCT": "Produktnamn och -beteckningar",
            "ARTICLE_NUMBER": "Artikelnummer",
            "EAN": "EAN-koder och streckkodsnummer",
            "DIMENSION": "Måttbeteckningar",
            "ELECTRICAL": "Elektriska specifikationer",
            "WEIGHT": "Viktangivelser",
            "MATERIAL": "Materialtyper",
            "COMPATIBILITY": "Kompatibilitetsinformation"
        }
        
        # Confidence thresholds
        self.min_confidence = 0.7  # Minimum confidence for extraction
        
        # Parallel processing
        self.max_workers = os.cpu_count()
        
        # Output control
        self.verbose = True  # Detailed output
        self.progress_bar = True  # Show progress bars
        
        # Validation options
        self.validate = True  # Validate extracted data
        
        # File patterns to ignore
        self.ignore_patterns = ["*_meta.*"]


class ProductDataExtractor:
    """
    Main extractor class that handles all extraction, integration, and reporting
    using NLP techniques and pattern matching.
    """
    
    def __init__(self, config: ExtractorConfig = None):
        """
        Initialize the extractor with configuration
        
        Args:
            config: Configuration settings (or uses defaults if None)
        """
        self.config = config or ExtractorConfig()
        
        # Create output directories
        self.output_dir = self.config.output_dir
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Create integrated directories
        self.integrated_dir = self.config.integrated_dir
        self.integrated_dir.mkdir(exist_ok=True, parents=True)
        
        # Statistics tracking
        self.stats = {
            "total_files": 0,
            "processed_files": 0,
            "extracted_products": 0,
            "products_with_identifiers": 0,
            "products_with_specifications": 0,
            "products_with_compatibility": 0,
            "total_identifiers": 0,
            "total_specifications": 0,
            "total_compatibility": 0,
            "errors": 0,
            "warnings": 0,
            "start_time": datetime.now(),
            "end_time": None,
            "duration_seconds": 0
        }
        
        # Load NLP models if available
        self.nlp = None
        self.load_nlp_model()
        
        # Initialize matchers
        self.initialize_matchers()
        
        # Timestamp for this run
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Cache for processed data
        self.product_data_cache = {}
    
    def load_nlp_model(self):
        """Load the spaCy NLP model if available"""
        if not SPACY_AVAILABLE:
            logger.warning("spaCy not available. Operating with limited NLP capabilities.")
            return
        
        try:
            logger.info(f"Loading spaCy model: {self.config.spacy_model}")
            self.nlp = spacy.load(self.config.spacy_model)
            logger.info("NLP model loaded successfully")
            
            # Add custom components
            self.add_custom_components()
        except Exception as e:
            logger.error(f"Failed to load spaCy model: {str(e)}")
            self.nlp = None
    
    def add_custom_components(self):
        """Add custom components to the spaCy pipeline"""
        if not self.nlp:
            return
        
        # Kontrollera om entity ruler redan finns
        if not self.nlp.has_pipe("entity_ruler"):
            # Skapa entity ruler med factory-metoden
            ruler = self.nlp.add_pipe("entity_ruler", before="ner")
            
            # Lägg till mönster för produktentiteter
            patterns = [
                # EAN-mönster
                {"label": "EAN", "pattern": [{"SHAPE": "dddddddddddd"}]},  # 12-siffrig (UPC)
                {"label": "EAN", "pattern": [{"SHAPE": "ddddddddddddd"}]},  # 13-siffrig (EAN-13)
                {"label": "EAN", "pattern": [{"SHAPE": "dddddddddddddd"}]},  # 14-siffrig (GTIN)
                
                # Artikelnummermönster
                {"label": "ARTICLE_NUMBER", "pattern": [
                    {"LOWER": {"IN": ["artikelnr", "art.nr", "artnr", "artikel", "art", "artikelnummer"]}}, 
                    {"IS_PUNCT": True, "OP": "?"}, 
                    {"TEXT": {"REGEX": "[A-Z0-9\\-]{4,15}"}}
                ]},
                
                # Dimensionsmönster
                {"label": "DIMENSION", "pattern": [
                    {"TEXT": {"REGEX": "\\d+(?:[.,]\\d+)?"}}, 
                    {"LOWER": {"IN": ["mm", "cm", "m", "tum", "millimeter", "centimeter", "meter"]}}
                ]},
                
                # Ytterligare mönster kan läggas till här
            ]
            
            ruler.add_patterns(patterns)
            logger.info("Lade till anpassade entitetsigenkänningskomponenter")
    
    def initialize_matchers(self):
        """Initialize pattern matchers for extraction"""
        if not self.nlp:
            self.matcher = None
            self.phrase_matcher = None
            return
        
        # Create matcher for token patterns
        self.matcher = Matcher(self.nlp.vocab)
        
        # Add patterns for compatibility relations
        compatibility_patterns = [
            # Direct compatibility
            [{"LOWER": "kompatibel"}, {"LOWER": "med"}, {"POS": "NOUN", "OP": "+"}],
            [{"LOWER": "passar"}, {"LOWER": {"IN": ["till", "med", "för"]}}, {"POS": "NOUN", "OP": "+"}],
            [{"LOWER": "fungerar"}, {"LOWER": "med"}, {"POS": "NOUN", "OP": "+"}],
            
            # Required compatibility
            [{"LOWER": "kräver"}, {"POS": "NOUN", "OP": "+"}],
            [{"LOWER": "behöver"}, {"POS": "NOUN", "OP": "+"}],
            
            # Add more patterns as needed
        ]
        
        for i, pattern in enumerate(compatibility_patterns):
            self.matcher.add(f"COMPATIBILITY_{i}", [pattern])
        
        # Create phrase matcher for terminology
        self.phrase_matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        
        # Add phrases for technical categories
        tech_category_terms = {
            "DIMENSIONS": ["dimensioner", "mått", "storlek", "höjd", "bredd", "djup", "längd"],
            "ELECTRICAL": ["spänning", "volt", "ampere", "watt", "frekvens", "effekt", "elektricitet"],
            "WEIGHT": ["vikt", "kg", "gram", "g", "belastning"],
            "MATERIAL": ["material", "plast", "metall", "stål", "aluminium", "trä", "glas"]
        }
        
        for category, terms in tech_category_terms.items():
            patterns = [self.nlp.make_doc(term) for term in terms]
            self.phrase_matcher.add(category, patterns)
            
        logger.info("Initialized pattern matchers")
    
    def find_product_files(self) -> List[Path]:
        """
        Find all product files in the base directory
        
        Returns:
            List of Path objects for product files
        """
        product_files = []
        
        # Recursively search for files with matching extensions
        file_type_patterns = [f"*{ext}.md" for ext in self.config.file_types]
        
        for pattern in file_type_patterns:
            found_files = list(self.config.base_dir.glob(f"**/{pattern}"))
            product_files.extend(found_files)
        
        # Filter out meta files
        product_files = [f for f in product_files if "_meta" not in f.name]
        
        # Filter out files matching ignore patterns
        for ignore_pattern in self.config.ignore_patterns:
            product_files = [f for f in product_files if not f.match(ignore_pattern)]
        
        self.stats["total_files"] = len(product_files)
        logger.info(f"Found {len(product_files)} product files to process")
        
        return product_files
    
    def extract_product_id(self, filename: str) -> str:
        """
        Extract product ID from filename
        
        Args:
            filename: The filename to extract from
            
        Returns:
            The extracted product ID
        """
        # Try to match pattern with product ID at the beginning followed by file type
        for file_type in self.config.file_types:
            if file_type in filename:
                product_id = filename.split(file_type)[0]
                return product_id
        
        # Fallback: use the part before the first underscore
        return filename.split('_')[0]
    
    def preprocess_content(self, content: str) -> str:
        """
        Preprocess markdown content for better extraction
        
        Args:
            content: Raw markdown content
            
        Returns:
            Preprocessed content
        """
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Normalize whitespace (but preserve newlines)
        content = re.sub(r'[ \t]+', ' ', content)
        
        # Normalize bullet points
        content = re.sub(r'^\s*[•*-]\s*', '\n• ', content, flags=re.MULTILINE)
        
        # Add space after headings for better segmentation
        content = re.sub(r'(#+.*)\n', r'\1\n\n', content)
        
        return content
    

    def convert_datetimes_to_strings(self, obj):
        """
        Konverterar alla datetime-objekt i en dictionary till ISO-formaterade strängar
        
        Args:
            obj: Objektet som ska konverteras
            
        Returns:
            Objekt med konverterade datetime-värden
        """
        if isinstance(obj, dict):
            return {k: self.convert_datetimes_to_strings(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_datetimes_to_strings(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj

    def extract_html_sections(self, content: str) -> Dict[str, str]:
        """
        Convert markdown to HTML and extract sections
        
        Args:
            content: Preprocessed markdown content
            
        Returns:
            Dictionary of sections
        """
        if not HTML_PARSER_AVAILABLE:
            return {"full_content": content}
        
        # Convert markdown to HTML
        html = markdown.markdown(content)
        
        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract sections
        sections = {}
        sections["full_content"] = content
        
        # Find all headings
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        
        for heading in headings:
            section_title = heading.get_text().strip()
            section_content = []
            
            # Get all elements until the next heading
            for sibling in heading.next_siblings:
                if sibling.name and sibling.name.startswith('h'):
                    break
                section_content.append(str(sibling))
            
            sections[section_title] = ''.join(section_content)
        
        return sections
    
    def extract_with_nlp(self, content: str, product_id: str) -> Tuple[List[ProductIdentifier], List[TechnicalSpecification], List[CompatibilityRelation]]:
        """
        Extract information using NLP techniques
        
        Args:
            content: Preprocessed content
            product_id: The product ID
            
        Returns:
            Tuple of extracted identifiers, specifications, and compatibility relations
        """
        if not self.nlp:
            return [], [], []
        
        # Lists to store extracted information
        identifiers = []
        specifications = []
        compatibility_relations = []
        
        # Process the content with spaCy
        doc = self.nlp(content[:100000])  # Limit to avoid memory issues with very large documents
        
        # Extract named entities
        for ent in doc.ents:
            # Extract EAN codes
            if ent.label_ == "EAN" or ent.text.isdigit() and len(ent.text) in [8, 12, 13, 14]:
                if self.is_valid_ean(ent.text):
                    identifiers.append(ProductIdentifier(
                        type="EAN-" + str(len(ent.text)),
                        value=ent.text,
                        confidence=0.95,
                        source_text=ent.sent.text,
                        extracted_method="nlp_entity"
                    ))
            
            # Extract dimensions
            if ent.label_ == "DIMENSION":
                # Try to identify the dimension type (height, width, etc.)
                dimension_type = self.identify_dimension_type(ent)
                
                specifications.append(TechnicalSpecification(
                    category="DIMENSIONS",
                    name=dimension_type,
                    raw_value=ent.text,
                    unit=self.extract_unit(ent.text),
                    normalized_value=self.normalize_value(ent.text),
                    confidence=0.85,
                    source_text=ent.sent.text,
                    extracted_method="nlp_entity"
                ))
        
        # Use matcher for compatibility relations
        matches = self.matcher(doc)
        for match_id, start, end in matches:
            match_span = doc[start:end]
            relation_type = self.nlp.vocab.strings[match_id].split('_')[0].lower()
            
            # Extract the related product (usually after the matched pattern)
            related_product_span = doc[end:min(end+10, len(doc))]  # Take a few tokens after the match
            related_product = related_product_span.text.strip()
            
            # Clean up the related product text
            related_product = re.sub(r'[.,;:].*$', '', related_product)
            
            compatibility_relations.append(CompatibilityRelation(
                relation_type=relation_type,
                related_product=related_product,
                context=match_span.sent.text,
                confidence=0.8,
                source_text=match_span.sent.text,
                extracted_method="nlp_matcher"
            ))
        
        # Use phrase matcher for technical categories
        phrase_matches = self.phrase_matcher(doc)
        for match_id, start, end in phrase_matches:
            category = self.nlp.vocab.strings[match_id]
            match_span = doc[start:end]
            
            # Look for values after the category mention
            value_span = doc[end:min(end+15, len(doc))]  # Take some tokens after the match
            value_text = value_span.text.strip()
            
            # Try to extract numeric values with units
            value_match = re.search(r'(\d+(?:[.,]\d+)?)\s*([a-zA-ZåäöÅÄÖ]+)?', value_text)
            if value_match:
                value = value_match.group(1)
                unit = value_match.group(2) or ""
                
                specifications.append(TechnicalSpecification(
                    category=category,
                    name=match_span.text,
                    raw_value=value,
                    unit=unit,
                    normalized_value=self.normalize_value(value),
                    confidence=0.85,
                    source_text=match_span.sent.text,
                    extracted_method="nlp_phrase_matcher"
                ))
        
        return identifiers, specifications, compatibility_relations
    
    def extract_with_regex(self, content: str, product_id: str) -> Tuple[List[ProductIdentifier], List[TechnicalSpecification], List[CompatibilityRelation]]:
        """
        Extract information using regex patterns
        
        Args:
            content: Preprocessed content
            product_id: The product ID
            
        Returns:
            Tuple of extracted identifiers, specifications, and compatibility relations
        """
        # Lists to store extracted information
        identifiers = []
        specifications = []
        compatibility_relations = []
        
        # EAN patterns
        ean_patterns = [
            r'(?i)EAN(?:-13)?[:.\-]?\s*(\d{13})(?!\d)',
            r'(?i)(?:Global Trade Item Number|EAN-kod)[:.\-]?\s*(\d{13})(?!\d)',
            r'(?<!\d)(\d{13})(?!\d)',  # Standalone 13-digit number
            r'(?i)EAN(?:-8)?[:.\-]?\s*(\d{8})(?!\d)',
            r'(?<!\d)(\d{8})(?!\d)',   # Standalone 8-digit number
        ]
        
        # Article number patterns
        article_patterns = [
            r'(?i)Art(?:ikel)?\.?(?:nr|nummer)\.?\s*[:=]?\s*([A-Z0-9\-]{5,15})',
            r'(?i)(?:Artikel|Produkt)nummer\s*[:=]?\s*([A-Z0-9\-]{5,15})',
            r'(?i)E-n(?:r|ummer)\s*[:=]?\s*(\d{7})',
            r'(?<!\d)(50\d{6})(?!\d)',  # Copiax article numbers
        ]
        
        # Technical specification patterns
        tech_patterns = {
            "DIMENSIONS": [
                r'(?i)(?:Dimensioner|Storlek|Mått)[\s:]*\n?\s*(?:B|H|D|L)?\s*[xX]\s*(?:B|H|D|L)?\s*[xX]?\s*(?:B|H|D|L)?\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(?:mm|cm|m)\s*[xX]\s*(\d+(?:[.,]\d+)?)\s*(?:mm|cm|m)(?:\s*[xX]\s*(\d+(?:[.,]\d+)?)\s*(?:mm|cm|m))?',
                r'(?i)(?:Höjd|Bredd|Djup|Längd)\s*:\s*(\d+(?:[.,]\d+)?)\s*(?:mm|cm|m)',
            ],
            "ELECTRICAL": [
                r'(?i)(?:Spänning|Matningsspänning)\s*:\s*(\d+(?:[.,]\d+)?)\s*(?:V|kV|mV)',
                r'(?i)(?:Ström|Strömförbrukning)\s*:\s*(\d+(?:[.,]\d+)?)\s*(?:A|mA)',
                r'(?i)(?:Effekt|Power)\s*:\s*(\d+(?:[.,]\d+)?)\s*(?:W|kW)',
            ],
            "WEIGHT": [
                r'(?i)(?:Vikt|Weight)\s*:\s*(\d+(?:[.,]\d+)?)\s*(?:kg|g|gram)',
            ],
            "COLOR": [
                r'(?i)(?:Färg|Color|Kulör)\s*:\s*([^\n\r.]+)',
            ],
            "MATERIAL": [
                r'(?i)Material\s*:\s*([^\n\r.]+)',
            ],
        }
        
        # Compatibility patterns
        compat_patterns = {
            "direct": [
                r'(?i)kompatibel\s+med\s+([^\.;]+)(?:\.|\;|$)',
                r'(?i)compatible\s+with\s+([^\.;]+)(?:\.|\;|$)',
                r'(?i)fungerar\s+(?:med|tillsammans\s+med)\s+([^\.;]+)(?:\.|\;|$)',
            ],
            "fits": [
                r'(?i)passar\s+(?:till|med|för)\s+([^\.;]+)(?:\.|\;|$)',
                r'(?i)passar\s+(?:på|i)\s+([^\.;]+)(?:\.|\;|$)',
                r'(?i)fits\s+(?:on|in|with)\s+([^\.;]+)(?:\.|\;|$)',
            ],
            "requires": [
                r'(?i)kräver\s+([^\.;]+)(?:\.|\;|$)',
                r'(?i)requires\s+([^\.;]+)(?:\.|\;|$)',
                r'(?i)behöver\s+([^\.;]+)(?:\.|\;|$)',
            ],
        }
        
        # Extract EANs
        for pattern in ean_patterns:
            for match in re.finditer(pattern, content):
                ean = match.group(1)
                if self.is_valid_ean(ean):
                    identifiers.append(ProductIdentifier(
                        type=f"EAN-{len(ean)}",
                        value=ean,
                        confidence=0.9,
                        source_text=self.get_context(content, match.start(), match.end()),
                        extracted_method="regex"
                    ))
        
        # Extract article numbers
        for pattern in article_patterns:
            for match in re.finditer(pattern, content):
                article_number = match.group(1)
                identifiers.append(ProductIdentifier(
                    type="ARTICLE_NUMBER",
                    value=article_number,
                    confidence=0.85,
                    source_text=self.get_context(content, match.start(), match.end()),
                    extracted_method="regex"
                ))
        
        # Extract technical specifications
        for category, patterns in tech_patterns.items():
            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    # Different handling based on pattern
                    if category == "DIMENSIONS" and match.lastindex >= 2:
                        # This is a dimensions pattern with multiple measurements
                        width = match.group(1)
                        height = match.group(2)
                        depth = match.group(3) if match.lastindex >= 3 else None
                        
                        specifications.append(TechnicalSpecification(
                            category=category,
                            name="Width",
                            raw_value=width,
                            unit=self.extract_unit(width) or "mm",
                            normalized_value=self.normalize_value(width),
                            confidence=0.85,
                            source_text=self.get_context(content, match.start(), match.end()),
                            extracted_method="regex"
                        ))
                        
                        specifications.append(TechnicalSpecification(
                            category=category,
                            name="Height",
                            raw_value=height,
                            unit=self.extract_unit(height) or "mm",
                            normalized_value=self.normalize_value(height),
                            confidence=0.85,
                            source_text=self.get_context(content, match.start(), match.end()),
                            extracted_method="regex"
                        ))
                        
                        if depth:
                            specifications.append(TechnicalSpecification(
                                category=category,
                                name="Depth",
                                raw_value=depth,
                                unit=self.extract_unit(depth) or "mm",
                                normalized_value=self.normalize_value(depth),
                                confidence=0.85,
                                source_text=self.get_context(content, match.start(), match.end()),
                                extracted_method="regex"
                            ))
                    else:
                        # Standard pattern with single value
                        value = match.group(1)
                        name = self.extract_spec_name(match.group(0))
                        unit = self.extract_unit(value) or self.extract_unit(match.group(0))
                        
                        specifications.append(TechnicalSpecification(
                            category=category,
                            name=name,
                            raw_value=value,
                            unit=unit,
                            normalized_value=self.normalize_value(value),
                            confidence=0.85,
                            source_text=self.get_context(content, match.start(), match.end()),
                            extracted_method="regex"
                        ))
        
        # Extract compatibility relations
        for relation_type, patterns in compat_patterns.items():
            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    related_product = match.group(1).strip()
                    
                    # Clean the related product text
                    related_product = re.sub(r'[.,;:]$', '', related_product).strip()
                    
                    if not related_product:
                        continue
                    
                    # Try to extract article numbers from the related product
                    numeric_ids = self.extract_numeric_ids(related_product)
                    
                    compatibility_relations.append(CompatibilityRelation(
                        relation_type=relation_type,
                        related_product=related_product,
                        numeric_ids=numeric_ids,
                        context=self.get_context(content, match.start(), match.end()),
                        confidence=0.8,
                        source_text=self.get_context(content, match.start(), match.end()),
                        extracted_method="regex"
                    ))
        
        return identifiers, specifications, compatibility_relations
    
    def get_context(self, content: str, start: int, end: int, window_size: int = 150) -> str:
        """
        Get the surrounding context of a match
        
        Args:
            content: Full content
            start: Start position of match
            end: End position of match
            window_size: Size of context window
            
        Returns:
            Context string
        """
        context_start = max(0, start - window_size)
        context_end = min(len(content), end + window_size)
        
        # Get the context
        context = content[context_start:context_end]
        
        # Clean up whitespace
        context = re.sub(r'\s+', ' ', context).strip()
        
        return context
    
    def is_valid_ean(self, ean: str) -> bool:
        """
        Validate EAN code using checksum
        
        Args:
            ean: The EAN code to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not ean.isdigit():
            return False
        
        # EAN-8, EAN-13, UPC (12 digits), or GTIN-14
        if len(ean) not in [8, 12, 13, 14]:
            return False
        
        # Check digit calculation
        total = 0
        for i, digit in enumerate(reversed(ean[:-1])):
            multiplier = 3 if i % 2 == 0 else 1
            total += int(digit) * multiplier
            
        check_digit = (10 - (total % 10)) % 10
        
        return check_digit == int(ean[-1])
    
    def extract_unit(self, text: str) -> str:
        """
        Extract unit from text
        
        Args:
            text: Text to extract from
            
        Returns:
            Extracted unit or empty string
        """
        unit_match = re.search(r'[0-9.,]+\s*([a-zA-ZåäöÅÄÖ]+)$', text)
        if unit_match:
            return unit_match.group(1)
        
        # Common units
        units = ["mm", "cm", "m", "g", "kg", "V", "A", "W", "kW", "Hz", "°C"]
        for unit in units:
            if unit in text:
                return unit
                
        return ""
    
    def normalize_value(self, value_text: str) -> Optional[float]:
        """
        Normalize numeric value
        
        Args:
            value_text: Text containing value
            
        Returns:
            Normalized float value or None if not possible
        """
        # Extract the number part
        number_match = re.search(r'([0-9.,]+)', value_text)
        if not number_match:
            return None
            
        number_str = number_match.group(1)
        
        # Replace comma with dot for float parsing
        number_str = number_str.replace(',', '.')
        
        try:
            return float(number_str)
        except ValueError:
            return None
    
    def extract_spec_name(self, text: str) -> str:
        """
        Extract specification name from text
        
        Args:
            text: Text to extract from
            
        Returns:
            Extracted name
        """
        # Look for pattern "Name: Value"
        name_match = re.match(r'(?i)([^:]+):', text)
        if name_match:
            return name_match.group(1).strip()
        
        # Common specification names
        specs = {
            "dimension": ["höjd", "bredd", "djup", "längd", "diameter", "mått"],
            "electrical": ["spänning", "ström", "effekt", "frekvens"],
            "weight": ["vikt", "belastning"],
            "material": ["material"],
            "color": ["färg", "kulör"]
        }
        
        for category, terms in specs.items():
            for term in terms:
                if term.lower() in text.lower():
                    return term.capitalize()
        
        return "Specifikation"  # Default if no name found
    
    def extract_numeric_ids(self, text: str) -> List[str]:
        """
        Extract numeric IDs (article numbers, etc.) from text
        
        Args:
            text: Text to extract from
            
        Returns:
            List of extracted IDs
        """
        numeric_ids = []
        
        # Patterns for different types of IDs
        id_patterns = [
            r'(?<!\d)(\d{5,8})(?!\d)',  # 5-8 digits (typical article numbers)
            r'E-(?:nr\.?|nummer)?\s*:?\s*(\d{7})',  # E-number format
            r'(?<!\d)(\d{13})(?!\d)',  # 13 digits (EAN)
            r'(?<!\d)(\d{12})(?!\d)',  # 12 digits (UPC)
            r'(?<!\d)(\d{8})(?!\d)',   # 8 digits (EAN-8)
        ]
        
        for pattern in id_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                id_value = match.group(1).strip()
                if id_value:
                    numeric_ids.append(id_value)
        
        return numeric_ids
    
    def identify_dimension_type(self, entity: Span) -> str:
        """
        Identify dimension type from named entity
        
        Args:
            entity: Named entity span
            
        Returns:
            Dimension type name
        """
        # Look for dimension type in context
        context = entity.sent.text.lower()
        
        dimension_types = {
            "höjd": "Height",
            "bredd": "Width",
            "djup": "Depth",
            "längd": "Length",
            "diameter": "Diameter",
            "radie": "Radius"
        }
        
        for swedish, english in dimension_types.items():
            if swedish in context:
                return english
        
        return "Dimension"  # Default if no specific type identified
    
    def extract_product_data(self, file_path: Path) -> Optional[ProductData]:
        """
        Extract all product data from a file
        
        Args:
            file_path: Path to the file
            
        Returns:
            ProductData object or None if extraction failed
        """
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Extract product ID
            product_id = self.extract_product_id(file_path.stem)
            
            # Preprocess content
            preprocessed_content = self.preprocess_content(content)
            
            # Initialize product data
            product_data = ProductData(
                product_id=product_id,
                file_path=str(file_path),
                filename=file_path.name,
                content_sample=preprocessed_content[:1000] if len(preprocessed_content) > 1000 else preprocessed_content
            )
            
            # Extract HTML sections
            sections = self.extract_html_sections(preprocessed_content)
            
            # Extract product name from content
            product_name = self.extract_product_name(preprocessed_content, product_id)
            product_data.product_name = product_name
            
            # Extract product description
            product_description = self.extract_product_description(preprocessed_content, sections)
            product_data.product_description = product_description
            
            # Extract data using NLP
            nlp_identifiers, nlp_specs, nlp_compat = self.extract_with_nlp(preprocessed_content, product_id)
            
            # Extract data using regex
            regex_identifiers, regex_specs, regex_compat = self.extract_with_regex(preprocessed_content, product_id)
            
            # Merge and deduplicate results
            product_data.identifiers = self.merge_identifiers(nlp_identifiers, regex_identifiers)
            product_data.specifications = self.merge_specifications(nlp_specs, regex_specs)
            product_data.compatibility = self.merge_compatibility(nlp_compat, regex_compat)
            
            # Update statistics
            self.stats["processed_files"] += 1
            self.stats["extracted_products"] += 1
            self.stats["total_identifiers"] += len(product_data.identifiers)
            self.stats["total_specifications"] += len(product_data.specifications)
            self.stats["total_compatibility"] += len(product_data.compatibility)
            
            if product_data.identifiers:
                self.stats["products_with_identifiers"] += 1
            if product_data.specifications:
                self.stats["products_with_specifications"] += 1
            if product_data.compatibility:
                self.stats["products_with_compatibility"] += 1
            
            # Add metadata
            product_data.metadata = {
                "extraction_timestamp": self.timestamp,
                "sections": list(sections.keys()),
                "extraction_methods": {
                    "nlp_available": self.nlp is not None,
                    "identifier_methods": self.get_extraction_methods(product_data.identifiers),
                    "specification_methods": self.get_extraction_methods(product_data.specifications),
                    "compatibility_methods": self.get_extraction_methods(product_data.compatibility),
                }
            }
            
            # Cache the product data
            self.product_data_cache[product_id] = product_data
            
            return product_data
            
        except Exception as e:
            logger.error(f"Error extracting data from {file_path}: {str(e)}")
            self.stats["errors"] += 1
            return None
    
    def extract_product_name(self, content: str, product_id: str) -> str:
        """
        Extract product name from content
        
        Args:
            content: Preprocessed content
            product_id: Product ID
            
        Returns:
            Extracted product name
        """
        # Try to find name in the first heading
        heading_match = re.search(r'^#\s+([^\n]+)', content, re.MULTILINE)
        if heading_match:
            return heading_match.group(1).strip()
        
        # Try to find "Produktnamn:" pattern
        name_match = re.search(r'(?i)produktnamn\s*:\s*([^\n\r.]+)', content)
        if name_match:
            return name_match.group(1).strip()
        
        # Try to find "Produkt:" pattern
        product_match = re.search(r'(?i)produkt\s*:\s*([^\n\r.]+)', content)
        if product_match:
            return product_match.group(1).strip()
        
        # Fallback: use product ID
        return f"Produkt {product_id}"
    
    def extract_product_description(self, content: str, sections: Dict[str, str]) -> str:
        """
        Extract product description from content
        
        Args:
            content: Preprocessed content
            sections: Content sections
            
        Returns:
            Extracted description
        """
        # Check if we have a description section
        description_sections = [
            "Beskrivning", "Om produkten", "Produktbeskrivning", 
            "Description", "About the product", "Product Description"
        ]
        
        for section_name in description_sections:
            if section_name in sections:
                # Clean HTML tags if present
                description = BeautifulSoup(sections[section_name], 'html.parser').get_text()
                description = description.strip()
                if description:
                    # Limit length
                    if len(description) > 500:
                        description = description[:497] + "..."
                    return description
        
        # Try to find a paragraph that might be a description
        paragraphs = re.findall(r'\n\n([^#].+?)\n\n', content, re.DOTALL)
        for paragraph in paragraphs:
            # Skip short paragraphs or those containing specifications
            if len(paragraph) > 50 and not re.search(r'[0-9]+\s*[a-zA-Z]+\s*[xX]\s*[0-9]+', paragraph):
                # Limit length
                paragraph = paragraph.strip()
                if len(paragraph) > 500:
                    paragraph = paragraph[:497] + "..."
                return paragraph
        
        return ""
    
    def merge_identifiers(self, nlp_identifiers: List[ProductIdentifier], regex_identifiers: List[ProductIdentifier]) -> List[ProductIdentifier]:
        """
        Merge and deduplicate identifiers
        
        Args:
            nlp_identifiers: Identifiers from NLP extraction
            regex_identifiers: Identifiers from regex extraction
            
        Returns:
            Merged list of identifiers
        """
        all_identifiers = nlp_identifiers + regex_identifiers
        
        # Use a dictionary to deduplicate by type and value
        deduplicated = {}
        
        for identifier in all_identifiers:
            key = (identifier.type, identifier.value)
            
            # If we haven't seen this identifier or the current one has higher confidence, use it
            if key not in deduplicated or identifier.confidence > deduplicated[key].confidence:
                deduplicated[key] = identifier
        
        return list(deduplicated.values())
    
    def merge_specifications(self, nlp_specs: List[TechnicalSpecification], regex_specs: List[TechnicalSpecification]) -> List[TechnicalSpecification]:
        """
        Merge and deduplicate specifications
        
        Args:
            nlp_specs: Specifications from NLP extraction
            regex_specs: Specifications from regex extraction
            
        Returns:
            Merged list of specifications
        """
        all_specs = nlp_specs + regex_specs
        
        # Use a dictionary to deduplicate by category, name, and value
        deduplicated = {}
        
        for spec in all_specs:
            # Create a key for deduplication
            key = (spec.category, spec.name, spec.raw_value)
            
            # If we haven't seen this spec or the current one has higher confidence, use it
            if key not in deduplicated or spec.confidence > deduplicated[key].confidence:
                deduplicated[key] = spec
        
        return list(deduplicated.values())
    
    def merge_compatibility(self, nlp_compat: List[CompatibilityRelation], regex_compat: List[CompatibilityRelation]) -> List[CompatibilityRelation]:
        """
        Merge and deduplicate compatibility relations
        
        Args:
            nlp_compat: Compatibility relations from NLP extraction
            regex_compat: Compatibility relations from regex extraction
            
        Returns:
            Merged list of compatibility relations
        """
        all_compat = nlp_compat + regex_compat
        
        # Use a dictionary to deduplicate by type and related product
        deduplicated = {}
        
        for relation in all_compat:
            # Create a key for deduplication
            key = (relation.relation_type, relation.related_product)
            
            # If we haven't seen this relation or the current one has higher confidence, use it
            if key not in deduplicated or relation.confidence > deduplicated[key].confidence:
                deduplicated[key] = relation
        
        return list(deduplicated.values())
    
    def get_extraction_methods(self, items: List) -> Dict[str, int]:
        """
        Count extraction methods used
        
        Args:
            items: List of extracted items
            
        Returns:
            Dictionary with counts per method
        """
        methods = Counter([item.extracted_method for item in items])
        return dict(methods)
    
    def save_product_data(self, product_data: ProductData, output_dir: Path = None) -> Path:
        """
        Save product data to JSON file
        
        Args:
            product_data: The product data to save
            output_dir: Optional output directory (uses default if None)
            
        Returns:
            Path to the saved file
        """
        if output_dir is None:
            output_dir = self.output_dir / "products" / product_data.product_id
        
        # Create directory structure
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Save to JSON file
        output_file = output_dir / f"{product_data.product_id}_data.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # Convert to dictionary
            data_dict = product_data.to_dict()
            json.dump(self.convert_datetimes_to_strings(data_dict), f, ensure_ascii=False, indent=2)
        
        # Also save to categorized files
        self.save_categorized_data(product_data, output_dir)
        
        return output_file
    
    def save_categorized_data(self, product_data: ProductData, output_dir: Path):
        """
        Save categorized data to separate files
        
        Args:
            product_data: The product data to save
            output_dir: Output directory
        """
        # Save identifiers
        if product_data.identifiers:
            ids_file = output_dir / f"{product_data.product_id}_identifiers.jsonl"
            with open(ids_file, 'w', encoding='utf-8') as f:
                for identifier in product_data.identifiers:
                    f.write(json.dumps(asdict(identifier), ensure_ascii=False) + '\n')
        
        # Save specifications
        if product_data.specifications:
            specs_file = output_dir / f"{product_data.product_id}_specifications.jsonl"
            with open(specs_file, 'w', encoding='utf-8') as f:
                for spec in product_data.specifications:
                    f.write(json.dumps(asdict(spec), ensure_ascii=False) + '\n')
        
        # Save compatibility
        if product_data.compatibility:
            compat_file = output_dir / f"{product_data.product_id}_compatibility.jsonl"
            with open(compat_file, 'w', encoding='utf-8') as f:
                for compat in product_data.compatibility:
                    f.write(json.dumps(asdict(compat), ensure_ascii=False) + '\n')
        
        # Save summary
        summary = {
            "product_id": product_data.product_id,
            "product_name": product_data.product_name,
            "description": product_data.product_description,
            "file_path": product_data.file_path,
            "identifier_count": len(product_data.identifiers),
            "specification_count": len(product_data.specifications),
            "compatibility_count": len(product_data.compatibility),
            "extraction_timestamp": self.timestamp
        }
        
        summary_file = output_dir / f"{product_data.product_id}_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    
    def integrate_products(self, output_dir: Path = None):
        """
        Integrate all extracted product data into a unified structure
        
        Args:
            output_dir: Optional output directory (uses default if None)
        """
        if output_dir is None:
            output_dir = self.integrated_dir
        
        # Create directory structure
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Create subdirectories
        indices_dir = output_dir / "indices"
        indices_dir.mkdir(exist_ok=True, parents=True)
        
        products_dir = output_dir / "products"
        products_dir.mkdir(exist_ok=True, parents=True)
        
        # Build indices
        article_index = defaultdict(list)
        ean_index = defaultdict(list)
        compatibility_map = defaultdict(list)
        technical_index = defaultdict(list)
        text_search_index = defaultdict(list)
        
        # Process each product in the cache
        for product_id, product_data in self.product_data_cache.items():
            # Create product directory
            product_dir = products_dir / product_id
            product_dir.mkdir(exist_ok=True, parents=True)
            
            # Save integrated data files
            
            # 1. Save identifiers
            if product_data.identifiers:
                ids_file = product_dir / "article_info.jsonl"
                with open(ids_file, 'w', encoding='utf-8') as f:
                    for identifier in product_data.identifiers:
                        # Add product_id if not present
                        id_data = asdict(identifier)
                        if "product_id" not in id_data:
                            id_data["product_id"] = product_id
                        
                        f.write(json.dumps(id_data, ensure_ascii=False) + '\n')
                        
                        # Update indices
                        if identifier.type.startswith("EAN"):
                            ean_index[identifier.value].append({
                                "product_id": product_id,
                                "id_type": identifier.type
                            })
                        elif "ARTICLE" in identifier.type:
                            article_index[identifier.value].append({
                                "product_id": product_id,
                                "id_type": identifier.type
                            })
            
            # 2. Save technical specifications
            if product_data.specifications:
                specs_file = product_dir / "technical_specs.jsonl"
                with open(specs_file, 'w', encoding='utf-8') as f:
                    for spec in product_data.specifications:
                        # Add product_id if not present
                        spec_data = asdict(spec)
                        if "product_id" not in spec_data:
                            spec_data["product_id"] = product_id
                        
                        f.write(json.dumps(spec_data, ensure_ascii=False) + '\n')
                        
                        # Update technical index
                        technical_index[spec.category].append({
                            "product_id": product_id,
                            "spec": spec_data
                        })
            
            # 3. Save compatibility relations
            if product_data.compatibility:
                compat_file = product_dir / "compatibility.jsonl"
                with open(compat_file, 'w', encoding='utf-8') as f:
                    for relation in product_data.compatibility:
                        # Add product_id if not present
                        relation_data = asdict(relation)
                        if "product_id" not in relation_data:
                            relation_data["product_id"] = product_id
                        
                        f.write(json.dumps(relation_data, ensure_ascii=False) + '\n')
                        
                        # Update compatibility map
                        compatibility_map[product_id].append({
                            "related_product": relation.related_product,
                            "relation_type": relation.relation_type,
                            "numeric_ids": relation.numeric_ids
                        })
                        
                        # Add reverse relation for direct compatibility
                        if relation.relation_type in ["direct", "fits", "compatible_with"]:
                            compatibility_map[relation.related_product].append({
                                "related_product": product_id,
                                "relation_type": "compatible_with",
                                "numeric_ids": []
                            })
            
            # 4. Save summary with key information
            self.generate_product_summary(product_data, product_dir)
            
            # 5. Copy original markdown file if available
            self.copy_original_markdown(product_data, product_dir)
            
            # 6. Update text search index
            self.update_text_search_index(product_data, text_search_index)
        
        # Save indices
        with open(indices_dir / "article_numbers.json", 'w', encoding='utf-8') as f:
            json.dump(dict(article_index), f, ensure_ascii=False, indent=2)
        
        with open(indices_dir / "ean_numbers.json", 'w', encoding='utf-8') as f:
            json.dump(dict(ean_index), f, ensure_ascii=False, indent=2)
        
        with open(indices_dir / "compatibility_map.json", 'w', encoding='utf-8') as f:
            json.dump(dict(compatibility_map), f, ensure_ascii=False, indent=2)
        
        with open(indices_dir / "technical_specs_index.json", 'w', encoding='utf-8') as f:
            json.dump(dict(technical_index), f, ensure_ascii=False, indent=2)
        
        with open(indices_dir / "text_search_index.json", 'w', encoding='utf-8') as f:
            json.dump(dict(text_search_index), f, ensure_ascii=False, indent=2)
        
        logger.info(f"Integrated data saved to {output_dir}")
    
    def generate_product_summary(self, product_data: ProductData, product_dir: Path):
        """
        Generate and save a product summary
        
        Args:
            product_data: The product data
            product_dir: Output directory for the product
        """
        # Create summary structure
        summary = {
            "product_id": product_data.product_id,
            "generated_at": self.timestamp,
            "product_name": product_data.product_name,
            "description": product_data.product_description,
            "key_specifications": [],
            "key_compatibility": [],
            "identifiers": {}
        }
        
        # Group identifiers by type
        for identifier in product_data.identifiers:
            if identifier.type not in summary["identifiers"]:
                summary["identifiers"][identifier.type] = []
            summary["identifiers"][identifier.type].append(identifier.value)
        
        # Select key specifications (up to 10)
        specs_by_category = defaultdict(list)
        for spec in product_data.specifications:
            specs_by_category[spec.category].append(spec)
        
        # Take up to 2 specs per category, prioritizing by importance
        for category, specs in specs_by_category.items():
            # Sort by importance
            sorted_specs = sorted(specs, key=lambda x: (
                x.importance != "high",
                x.importance != "medium",
                not x.raw_value
            ))
            
            # Take up to 2 per category
            for spec in sorted_specs[:2]:
                if len(summary["key_specifications"]) < 10:
                    summary["key_specifications"].append({
                        "category": spec.category,
                        "name": spec.name,
                        "value": spec.raw_value,
                        "unit": spec.unit
                    })
        
        # Select key compatibility relations (up to 10)
        compat_by_type = defaultdict(list)
        for relation in product_data.compatibility:
            compat_by_type[relation.relation_type].append(relation)
        
        # Take up to 3 relations per type, prioritizing those with numeric IDs
        for relation_type, relations in compat_by_type.items():
            # Sort by whether they have numeric IDs
            sorted_relations = sorted(relations, key=lambda x: (
                not x.numeric_ids,
                not x.related_product
            ))
            
            # Take up to 3 per type
            for relation in sorted_relations[:3]:
                if len(summary["key_compatibility"]) < 10:
                    summary["key_compatibility"].append({
                        "type": relation.relation_type,
                        "related_product": relation.related_product,
                        "has_product_id": bool(relation.numeric_ids),
                        "numeric_ids": relation.numeric_ids
                    })
        
        # Save summary
        summary_file = product_dir / "summary.jsonl"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(summary, ensure_ascii=False) + '\n')
    
    def copy_original_markdown(self, product_data: ProductData, product_dir: Path):
        """
        Copy original markdown file to the product directory
        
        Args:
            product_data: The product data
            product_dir: Output directory for the product
        """
        # Check if the original file exists
        original_file = Path(product_data.file_path)
        if original_file.exists():
            # Copy to the product directory
            target_file = product_dir / "full_info.md"
            try:
                shutil.copy2(original_file, target_file)
            except Exception as e:
                logger.error(f"Error copying original file: {str(e)}")
    
    def update_text_search_index(self, product_data: ProductData, text_search_index: Dict[str, List[str]]):
        """
        Update the text search index with product data
        
        Args:
            product_data: The product data
            text_search_index: The index to update
        """
        # Extract text for search
        search_text = f"{product_data.product_name} {product_data.product_description} {product_data.content_sample}"
        
        # Normalize text for search
        search_text = unicodedata.normalize('NFKD', search_text)
        search_text = re.sub(r'[^\w\s]', ' ', search_text.lower())
        
        # Split into words
        words = set(word for word in search_text.split() if len(word) > 2)
        
        # Add to index
        for word in words:
            if word not in text_search_index:
                text_search_index[word] = []
            if product_data.product_id not in text_search_index[word]:
                text_search_index[word].append(product_data.product_id)
    
    def process_files_parallel(self):
        """Process all files in parallel and save the extracted data"""
        # Find all product files
        product_files = self.find_product_files()
        
        if not product_files:
            logger.warning("No product files found!")
            return
        
        # Create output directory structure
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.output_dir.joinpath("products").mkdir(exist_ok=True, parents=True)
        
        # Process files in parallel
        max_workers = self.config.max_workers or os.cpu_count()
        logger.info(f"Processing {len(product_files)} files with {max_workers} workers")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Use tqdm for progress bar if available
            if TQDM_AVAILABLE and self.config.progress_bar:
                files_iterator = tqdm(product_files, desc="Extracting data", unit="file")
            else:
                files_iterator = product_files
            
            # Submit all files for processing
            future_to_file = {executor.submit(self.extract_product_data, file_path): file_path for file_path in files_iterator}
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    product_data = future.result()
                    if product_data:
                        self.save_product_data(product_data)
                except Exception as e:
                    logger.error(f"Error processing {file_path.name}: {str(e)}")
                    self.stats["errors"] += 1
        
        # Update end time and duration
        self.stats["end_time"] = datetime.now()
        self.stats["duration_seconds"] = (self.stats["end_time"] - self.stats["start_time"]).total_seconds()
        
        # Integrate the data
        self.integrate_products()
        
        # Generate reports
        self.generate_reports()
        
        logger.info(f"Processed {self.stats['processed_files']} files in {self.stats['duration_seconds']:.1f} seconds")
        logger.info(f"Extracted {self.stats['extracted_products']} products")
        logger.info(f"Products with identifiers: {self.stats['products_with_identifiers']}")
        logger.info(f"Products with specifications: {self.stats['products_with_specifications']}")
        logger.info(f"Products with compatibility: {self.stats['products_with_compatibility']}")
    
    def generate_reports(self):
        """Generate reports about the extracted data"""
        reports_dir = self.output_dir / "reports"
        reports_dir.mkdir(exist_ok=True, parents=True)
        
        # 1. Generate statistical summary
        stats_file = reports_dir / f"extraction_stats_{self.timestamp}.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.convert_datetimes_to_strings(self.stats), f, ensure_ascii=False, indent=2)
        
        # 2. Generate markdown report
        self.generate_markdown_report(reports_dir)
        
        # 3. Generate extraction quality report
        self.generate_quality_report(reports_dir)
        
        logger.info(f"Reports generated in {reports_dir}")
    
    def generate_markdown_report(self, reports_dir: Path):
        """
        Generate a comprehensive markdown report
        
        Args:
            reports_dir: Directory to save the report
        """
        report_file = reports_dir / f"extraction_report_{self.timestamp}.md"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            # Header and summary
            f.write("# Product Data Extraction Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Overall statistics
            f.write("## Summary\n\n")
            f.write(f"- **Total files processed:** {self.stats['processed_files']} of {self.stats['total_files']}\n")
            f.write(f"- **Products extracted:** {self.stats['extracted_products']}\n")
            f.write(f"- **Extraction duration:** {self.stats['duration_seconds']:.1f} seconds\n\n")
            
            # Data type statistics
            f.write("## Data Coverage\n\n")
            f.write("| Data Type | Products | Total Extracted | Percentage |\n")
            f.write("|-----------|----------|-----------------|------------|\n")
            
            if self.stats['extracted_products'] > 0:
                id_pct = (self.stats['products_with_identifiers'] / self.stats['extracted_products']) * 100
                spec_pct = (self.stats['products_with_specifications'] / self.stats['extracted_products']) * 100
                compat_pct = (self.stats['products_with_compatibility'] / self.stats['extracted_products']) * 100
                
                f.write(f"| Identifiers | {self.stats['products_with_identifiers']} | {self.stats['total_identifiers']} | {id_pct:.1f}% |\n")
                f.write(f"| Specifications | {self.stats['products_with_specifications']} | {self.stats['total_specifications']} | {spec_pct:.1f}% |\n")
                f.write(f"| Compatibility | {self.stats['products_with_compatibility']} | {self.stats['total_compatibility']} | {compat_pct:.1f}% |\n")
            
            # Sample products
            f.write("\n## Sample Products\n\n")
            
            # Get a few sample products
            sample_count = min(5, len(self.product_data_cache))
            samples = list(self.product_data_cache.values())[:sample_count]
            
            for sample in samples:
                f.write(f"### {sample.product_name} ({sample.product_id})\n\n")
                
                # Product description
                if sample.product_description:
                    f.write(f"{sample.product_description}\n\n")
                
                # Identifiers
                if sample.identifiers:
                    f.write("**Identifiers:**\n\n")
                    for identifier in sample.identifiers[:5]:  # Show up to 5
                        f.write(f"- {identifier.type}: {identifier.value}\n")
                    if len(sample.identifiers) > 5:
                        f.write(f"- ...and {len(sample.identifiers) - 5} more\n")
                    f.write("\n")
                
                # Specifications
                if sample.specifications:
                    f.write("**Technical Specifications:**\n\n")
                    for spec in sample.specifications[:5]:  # Show up to 5
                        unit_str = f" {spec.unit}" if spec.unit else ""
                        f.write(f"- {spec.name}: {spec.raw_value}{unit_str}\n")
                    if len(sample.specifications) > 5:
                        f.write(f"- ...and {len(sample.specifications) - 5} more\n")
                    f.write("\n")
                
                # Compatibility
                if sample.compatibility:
                    f.write("**Compatibility:**\n\n")
                    for relation in sample.compatibility[:5]:  # Show up to 5
                        f.write(f"- {relation.relation_type.capitalize()}: {relation.related_product}\n")
                    if len(sample.compatibility) > 5:
                        f.write(f"- ...and {len(sample.compatibility) - 5} more\n")
                    f.write("\n")
            
            # Errors and issues
            f.write("\n## Errors and Issues\n\n")
            f.write(f"- **Errors:** {self.stats['errors']}\n")
            f.write(f"- **Warnings:** {self.stats['warnings']}\n\n")
            
            # Next steps
            f.write("\n## Next Steps\n\n")
            f.write("1. **Review extracted data** for quality and completeness\n")
            f.write("2. **Analyze compatibility relations** to find patterns\n")
            f.write("3. **Enhance the extraction model** based on quality reports\n")
            f.write("4. **Integrate the data** with other systems\n\n")
            
            f.write(f"*Report generated by Unified Product Data Extractor {self.timestamp}*\n")
    
    def generate_quality_report(self, reports_dir: Path):
        """
        Generate a report on extraction quality
        
        Args:
            reports_dir: Directory to save the report
        """
        quality_file = reports_dir / f"extraction_quality_{self.timestamp}.json"
        
        # Analyze extraction quality
        quality_stats = {
            "timestamp": self.timestamp,
            "overall_coverage": {
                "products_with_identifiers_pct": (self.stats['products_with_identifiers'] / self.stats['extracted_products'] * 100) 
                    if self.stats['extracted_products'] > 0 else 0,
                "products_with_specs_pct": (self.stats['products_with_specifications'] / self.stats['extracted_products'] * 100)
                    if self.stats['extracted_products'] > 0 else 0,
                "products_with_compat_pct": (self.stats['products_with_compatibility'] / self.stats['extracted_products'] * 100)
                    if self.stats['extracted_products'] > 0 else 0,
            },
            "extraction_methods": {
                "identifiers": defaultdict(int),
                "specifications": defaultdict(int),
                "compatibility": defaultdict(int)
            },
            "confidence_stats": {
                "identifiers": {
                    "high": 0,
                    "medium": 0,
                    "low": 0
                },
                "specifications": {
                    "high": 0,
                    "medium": 0,
                    "low": 0
                },
                "compatibility": {
                    "high": 0,
                    "medium": 0,
                    "low": 0
                }
            },
            "missing_data": [],
            "low_quality_products": []
        }
        
        # Analyze each product
        for product_id, product_data in self.product_data_cache.items():
            # Count extraction methods
            for identifier in product_data.identifiers:
                quality_stats["extraction_methods"]["identifiers"][identifier.extracted_method] += 1
                
                # Categorize confidence
                if identifier.confidence >= 0.9:
                    quality_stats["confidence_stats"]["identifiers"]["high"] += 1
                elif identifier.confidence >= 0.7:
                    quality_stats["confidence_stats"]["identifiers"]["medium"] += 1
                else:
                    quality_stats["confidence_stats"]["identifiers"]["low"] += 1
            
            for spec in product_data.specifications:
                quality_stats["extraction_methods"]["specifications"][spec.extracted_method] += 1
                
                # Categorize confidence
                if spec.confidence >= 0.9:
                    quality_stats["confidence_stats"]["specifications"]["high"] += 1
                elif spec.confidence >= 0.7:
                    quality_stats["confidence_stats"]["specifications"]["medium"] += 1
                else:
                    quality_stats["confidence_stats"]["specifications"]["low"] += 1
            
            for relation in product_data.compatibility:
                quality_stats["extraction_methods"]["compatibility"][relation.extracted_method] += 1
                
                # Categorize confidence
                if relation.confidence >= 0.9:
                    quality_stats["confidence_stats"]["compatibility"]["high"] += 1
                elif relation.confidence >= 0.7:
                    quality_stats["confidence_stats"]["compatibility"]["medium"] += 1
                else:
                    quality_stats["confidence_stats"]["compatibility"]["low"] += 1
            
            # Check for missing data
            missing = []
            if not product_data.identifiers:
                missing.append("identifiers")
            if not product_data.specifications:
                missing.append("specifications")
            if not product_data.compatibility:
                missing.append("compatibility")
            
            if missing:
                quality_stats["missing_data"].append({
                    "product_id": product_id,
                    "product_name": product_data.product_name,
                    "missing": missing
                })
            
            # Check for low quality (too little data or low confidence)
            low_quality = False
            if len(product_data.identifiers) + len(product_data.specifications) + len(product_data.compatibility) < 3:
                low_quality = True
            
            avg_confidence = 0
            total_items = 0
            
            for identifier in product_data.identifiers:
                avg_confidence += identifier.confidence
                total_items += 1
            
            for spec in product_data.specifications:
                avg_confidence += spec.confidence
                total_items += 1
            
            for relation in product_data.compatibility:
                avg_confidence += relation.confidence
                total_items += 1
            
            if total_items > 0:
                avg_confidence /= total_items
                if avg_confidence < 0.75:
                    low_quality = True
            
            if low_quality:
                quality_stats["low_quality_products"].append({
                    "product_id": product_id,
                    "product_name": product_data.product_name,
                    "item_count": len(product_data.identifiers) + len(product_data.specifications) + len(product_data.compatibility),
                    "avg_confidence": avg_confidence if total_items > 0 else 0
                })
        
        # Convert defaultdicts to regular dicts for JSON serialization
        quality_stats["extraction_methods"]["identifiers"] = dict(quality_stats["extraction_methods"]["identifiers"])
        quality_stats["extraction_methods"]["specifications"] = dict(quality_stats["extraction_methods"]["specifications"])
        quality_stats["extraction_methods"]["compatibility"] = dict(quality_stats["extraction_methods"]["compatibility"])
        
        # Save quality report
        with open(quality_file, 'w', encoding='utf-8') as f:
            json.dump(self.convert_datetimes_to_strings(quality_stats), f, ensure_ascii=False, indent=2)
    
    def generate_bot_responses(self):
        """Generate structured responses for bot commands"""
        # Create bot response directory
        bot_dir = self.integrated_dir / "bot_responses"
        bot_dir.mkdir(exist_ok=True, parents=True)
        
        # Process each product
        for product_id, product_data in self.product_data_cache.items():
            # Create product response directory
            product_response_dir = bot_dir / product_id
            product_response_dir.mkdir(exist_ok=True, parents=True)
            
            # Generate technical response (-t command)
            self.generate_technical_response(product_data, product_response_dir)
            
            # Generate compatibility response (-c command)
            self.generate_compatibility_response(product_data, product_response_dir)
            
            # Generate summary response (-s command)
            self.generate_summary_response(product_data, product_response_dir)
        
        logger.info(f"Bot responses generated in {bot_dir}")
    
    def generate_technical_response(self, product_data: ProductData, output_dir: Path):
        """
        Generate technical response for -t command
        
        Args:
            product_data: The product data
            output_dir: Output directory
        """
        # Create response structure
        response = {
            "product_id": product_data.product_id,
            "command": "-t",
            "timestamp": datetime.now().isoformat(),
            "product_name": product_data.product_name,
            "has_technical_info": len(product_data.specifications) > 0,
            "technical_categories": {},
            "all_specifications": [asdict(spec) for spec in product_data.specifications],
            "markdown_response": ""
        }
        
        # Group specifications by category
        grouped = product_data.group_by_category()
        specs_by_category = grouped["specs_by_category"]
        
        # Convert to serializable format
        for category, specs in specs_by_category.items():
            response["technical_categories"][category] = [asdict(spec) for spec in specs]
        
        # Generate markdown response
        markdown = [f"# Tekniska specifikationer för {product_data.product_name}", ""]
        
        # Add product ID
        markdown.append(f"**Artikelnummer:** {product_data.product_id}")
        
        # Add EAN codes if available
        eans = [id.value for id in product_data.identifiers if id.type.startswith("EAN")]
        if eans:
            markdown.append(f"**EAN:** {', '.join(eans)}")
        
        markdown.append("")  # Empty line
        
        # If no specs available
        if not product_data.specifications:
            markdown.append("Ingen teknisk information tillgänglig för denna produkt.")
        else:
            # Add each category
            for category, specs in specs_by_category.items():
                markdown.append(f"## {category}")
                markdown.append("")
                
                for spec in specs:
                    # Format specification line
                    unit_str = f" {spec.unit}" if spec.unit else ""
                    markdown.append(f"- **{spec.name}:** {spec.raw_value}{unit_str}")
                
                markdown.append("")  # Empty line between categories
        
        # Join all lines
        response["markdown_response"] = "\n".join(markdown)
        
        # Save response
        with open(output_dir / "technical_response.json", 'w', encoding='utf-8') as f:
            json.dump(self.convert_datetimes_to_strings(response), f, ensure_ascii=False, indent=4)
    
    def generate_compatibility_response(self, product_data: ProductData, output_dir: Path):
        """
        Generate compatibility response for -c command
        
        Args:
            product_data: The product data
            output_dir: Output directory
        """
        # Create response structure
        response = {
            "product_id": product_data.product_id,
            "command": "-c",
            "timestamp": datetime.now().isoformat(),
            "product_name": product_data.product_name,
            "has_compatibility_info": len(product_data.compatibility) > 0,
            "compatibility_groups": {},
            "related_products": [],
            "markdown_response": ""
        }
        
        # Group compatibility relations
        grouped = product_data.group_by_category()
        compat_by_type = grouped["compat_by_type"]
        
        # Define display names for relation types
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
        
        # Convert relation types to display names
        display_groups = {}
        for rel_type, relations in compat_by_type.items():
            display_name = relation_display.get(rel_type, rel_type.replace("_", " ").title())
            display_groups[display_name] = [asdict(rel) for rel in relations]
        
        response["compatibility_groups"] = display_groups
        
        # Create related products list
        for relation in product_data.compatibility:
            related_product = {
                "related_product_id": None,
                "relation_type": relation.relation_type,
                "name": relation.related_product,
                "numeric_ids": relation.numeric_ids,
                "notes": relation.context
            }
            
            # If we have numeric IDs, use the first one as related_product_id
            if relation.numeric_ids:
                related_product["related_product_id"] = relation.numeric_ids[0]
            
            response["related_products"].append(related_product)
        
        # Generate markdown response
        markdown = [f"# Kompatibilitetsinformation för {product_data.product_name}", ""]
        
        # Add product ID
        markdown.append(f"**Artikelnummer:** {product_data.product_id}")
        
        # Add EAN codes if available
        eans = [id.value for id in product_data.identifiers if id.type.startswith("EAN")]
        if eans:
            markdown.append(f"**EAN:** {', '.join(eans)}")
        
        markdown.append("")  # Empty line
        
        # If no compatibility info available
        if not product_data.compatibility:
            markdown.append("Ingen kompatibilitetsinformation tillgänglig för denna produkt.")
        else:
            # Add each relation type
            for display_name, relations in display_groups.items():
                markdown.append(f"## {display_name}")
                markdown.append("")
                
                for relation_dict in relations:
                    related_product = relation_dict["related_product"]
                    
                    # Format with article number if available
                    if relation_dict["numeric_ids"]:
                        markdown.append(f"- {related_product} (Art.nr: {relation_dict['numeric_ids'][0]})")
                    else:
                        markdown.append(f"- {related_product}")
                
                markdown.append("")  # Empty line between categories
        
        # Join all lines
        response["markdown_response"] = "\n".join(markdown)
        
        # Save response
        with open(output_dir / "compatibility_response.json", 'w', encoding='utf-8') as f:
            json.dump(self.convert_datetimes_to_strings(response), f, ensure_ascii=False, indent=4)
    
    def generate_summary_response(self, product_data: ProductData, output_dir: Path):
        """
        Generate summary response for -s command
        
        Args:
            product_data: The product data
            output_dir: Output directory
        """
        # Get grouped data
        grouped = product_data.group_by_category()
        specs_by_category = grouped["specs_by_category"]
        compat_by_type = grouped["compat_by_type"]
        ids_by_type = grouped["ids_by_type"]
        
        # Create summary data structure
        summary_data = {
            "product_id": product_data.product_id,
            "generated_at": self.timestamp,
            "product_name": product_data.product_name,
            "description": product_data.product_description,
            "key_specifications": [],
            "key_compatibility": [],
            "identifiers": {}
        }
        
        # Add identifiers by type
        for id_type, identifiers in ids_by_type.items():
            summary_data["identifiers"][id_type] = [id.value for id in identifiers]
        
        # Select key specifications (up to 10)
        for category, specs in specs_by_category.items():
            # Sort by importance
            sorted_specs = sorted(specs, key=lambda x: (
                x.importance != "high",
                x.importance != "medium",
                not x.raw_value
            ))
            
            # Take up to 2 per category
            for spec in sorted_specs[:2]:
                if len(summary_data["key_specifications"]) < 10:
                    summary_data["key_specifications"].append({
                        "category": spec.category,
                        "name": spec.name,
                        "value": spec.raw_value,
                        "unit": spec.unit
                    })
        
        # Select key compatibility relations (up to 10)
        for relation_type, relations in compat_by_type.items():
            # Sort by whether they have numeric IDs
            sorted_relations = sorted(relations, key=lambda x: (
                not x.numeric_ids,
                not x.related_product
            ))
            
            # Take up to 3 per type
            for relation in sorted_relations[:3]:
                if len(summary_data["key_compatibility"]) < 10:
                    summary_data["key_compatibility"].append({
                        "type": relation.relation_type,
                        "related_product": relation.related_product,
                        "has_product_id": bool(relation.numeric_ids),
                        "numeric_ids": relation.numeric_ids
                    })
        
        # Create response structure
        response = {
            "product_id": product_data.product_id,
            "command": "-s",
            "timestamp": datetime.now().isoformat(),
            "product_name": product_data.product_name,
            "summary_data": summary_data,
            "markdown_response": ""
        }
        
        # Generate markdown response
        markdown = [f"# {product_data.product_name}", ""]
        
        # Add product ID
        markdown.append(f"**Artikelnummer:** {product_data.product_id}")
        
        # Add identifiers
        for id_type, values in summary_data["identifiers"].items():
            if values:
                markdown.append(f"**{id_type}:** {', '.join(values)}")
        
        markdown.append("")  # Empty line
        
        # Add description
        if product_data.product_description:
            markdown.append(product_data.product_description)
            markdown.append("")
        
        # Add technical specifications
        if summary_data["key_specifications"]:
            markdown.append("## Tekniska specifikationer")
            markdown.append("")
            
            for spec in summary_data["key_specifications"]:
                unit_str = f" {spec['unit']}" if spec['unit'] else ""
                markdown.append(f"- **{spec['name']}:** {spec['value']}{unit_str}")
            
            markdown.append("")
        
        # Add compatibility
        if summary_data["key_compatibility"]:
            markdown.append("## Kompatibilitet")
            markdown.append("")
            
            # Define display names for relation types
            relation_display = {
                "direct": "Kompatibel med",
                "fits": "Passar till",
                "requires": "Kräver",
                "recommended": "Rekommenderas med",
                "designed_for": "Designad för",
                "accessory": "Tillbehör till"
            }
            
            # Group by relation type
            compat_by_display = defaultdict(list)
            for relation in summary_data["key_compatibility"]:
                rel_type = relation["type"]
                display_name = relation_display.get(rel_type, rel_type.replace("_", " ").title())
                compat_by_display[display_name].append(relation)
            
            # Add each group
            for display_name, relations in compat_by_display.items():
                markdown.append(f"### {display_name}")
                markdown.append("")
                
                for relation in relations:
                    related_product = relation["related_product"]
                    
                    # Format with article number if available
                    if relation["numeric_ids"]:
                        markdown.append(f"- {related_product} (Art.nr: {relation['numeric_ids'][0]})")
                    else:
                        markdown.append(f"- {related_product}")
                
                markdown.append("")
        
        # Join all lines
        response["markdown_response"] = "\n".join(markdown)
        
        # Save response
        with open(output_dir / "summary_response.json", 'w', encoding='utf-8') as f:
            json.dump(self.convert_datetimes_to_strings(response), f, ensure_ascii=False, indent=4)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Unified Product Data Extractor with NLP")
    
    # Add arguments
    parser.add_argument('--input', '-i', type=str, 
                        help='Input directory containing markdown files')
    parser.add_argument('--output', '-o', type=str, 
                        help='Output directory for extracted data')
    parser.add_argument('--integrated', type=str, 
                        help='Output directory for integrated data')
    parser.add_argument('--workers', '-w', type=int, 
                        help='Number of worker threads (default: CPU count)')
    parser.add_argument('--no-progress', action='store_true', 
                        help='Disable progress bar')
    parser.add_argument('--verbose', '-v', action='store_true', 
                        help='Enable verbose output')
    parser.add_argument('--model', '-m', type=str, 
                        help='spaCy model to use (default: sv_core_news_lg)')
    parser.add_argument('--no-bot', action='store_true',
                        help='Skip generating bot responses')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Create configuration
    config = ExtractorConfig()
    
    # Apply command-line arguments
    if args.input:
        config.base_dir = Path(args.input)
    if args.output:
        config.output_dir = Path(args.output)
    if args.integrated:
        config.integrated_dir = Path(args.integrated)
    if args.workers:
        config.max_workers = args.workers
    if args.no_progress:
        config.progress_bar = False
    if args.verbose:
        config.verbose = True
    if args.model:
        config.spacy_model = args.model
    
    # Create extractor
    extractor = ProductDataExtractor(config)
    
    # Process all files
    extractor.process_files_parallel()
    
    # Generate bot responses
    if not args.no_bot:
        extractor.generate_bot_responses()
    
    print(f"Processing complete. Reports available in {config.output_dir}/reports")


if __name__ == "__main__":
    main()