# modules/pattern_config.py

import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

class PatternConfig:
    """
    Configuration class for managing regex patterns used in data extraction.
    Handles loading, validation, and application of patterns for different document types.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        # Default configuration path
        self.config_path = config_path or Path("config/patterns.json")
        
        # Initialize pattern categories
        self._init_default_patterns()
        
        # Load custom patterns if they exist
        self.load_patterns()
        
        # Compiled pattern cache
        self._pattern_cache = {}
    
    def _init_default_patterns(self):
        """Initialize default pattern sets for different categories"""
        self.patterns = {
            "article": {
                "ean13": {
                    "patterns": [
                        r'(?i)EAN(?:-13)?[:.\-]?\s*(\d{13})(?!\d)',
                        r'(?i)(?:Global Trade Item Number|EAN-kod)[:.\-]?\s*(\d{13})(?!\d)',
                        r'(?<!\d)(\d{13})(?!\d)'
                    ],
                    "validation": r'^\d{13}$',
                    "priority": "high"
                },
                "article_number": {
                    "patterns": [
                        r'(?i)Art(?:ikel)?\.?(?:nr|nummer)\.?\s*:\s*([A-Z0-9\-]{5,15})',
                        r'(?i)Produkt(?:nr|nummer)\.?\s*:\s*([A-Z0-9\-]{5,15})'
                    ],
                    "validation": r'^[A-Z0-9\-]{5,15}$',
                    "priority": "high"
                },
                "copiax_article": {
                    "patterns": [
                        r'(?i)(?<!\d)(50\d{6})(?!\d)',
                        r'(?i)Copiax-artikel\s*:\s*(50\d{6})'
                    ],
                    "validation": r'^50\d{6}$',
                    "priority": "medium"
                }
            },
            "technical": {
                "dimensions": {
                    "patterns": [
                        r'(?i)(?:Mått|Dimensioner)\s*:\s*(\d+(?:[,.]\d+)?)\s*(?:x|\*)\s*(\d+(?:[,.]\d+)?)\s*(?:x|\*)\s*(\d+(?:[,.]\d+)?)\s*(?:mm|cm|m)',
                        r'(?i)(?:Höjd|Bredd|Djup)\s*:\s*(\d+(?:[,.]\d+)?)\s*(?:mm|cm|m)'
                    ],
                    "validation": r'^\d+(?:[,.]\d+)?$',
                    "priority": "high"
                },
                "electrical": {
                    "patterns": [
                        r'(?i)(?:Spänning|Voltage)\s*:\s*(\d+(?:[,.]\d+)?)\s*(?:V|kV|mV)',
                        r'(?i)(?:Ström|Current)\s*:\s*(\d+(?:[,.]\d+)?)\s*(?:A|mA)'
                    ],
                    "validation": r'^\d+(?:[,.]\d+)?$',
                    "priority": "high"
                },
                "material": {
                    "patterns": [
                        r'(?i)Material\s*:\s*([^\.;]+)',
                        r'(?i)Tillverkad av\s*:\s*([^\.;]+)'
                    ],
                    "validation": r'^[A-Za-zåäöÅÄÖ\s\-,]+$',
                    "priority": "medium"
                },
                "color": {
                    "patterns": [
                        r'(?i)Färg\s*:\s*([^\.;]+)',
                        r'(?i)Kulör\s*:\s*([^\.;]+)'
                    ],
                    "validation": r'^[A-Za-zåäöÅÄÖ\s\-,]+$',
                    "priority": "low"
                }
            },
            "compatibility": {
                "direct": {
                    "patterns": [
                        r'(?i)kompatibel\s+med\s+([^\.;]+)(?:\.|\;|$)',
                        r'(?i)fungerar\s+med\s+([^\.;]+)(?:\.|\;|$)',
                        r'(?i)passar\s+till\s+([^\.;]+)(?:\.|\;|$)'
                    ],
                    "validation": None,
                    "priority": "high"
                },
                "requires": {
                    "patterns": [
                        r'(?i)kräver\s+([^\.;]+)(?:\.|\;|$)',
                        r'(?i)måste\s+ha\s+([^\.;]+)(?:\.|\;|$)'
                    ],
                    "validation": None,
                    "priority": "high"
                },
                "fits": {
                    "patterns": [
                        r'(?i)passar\s+i\s+([^\.;]+)(?:\.|\;|$)',
                        r'(?i)monteras\s+på\s+([^\.;]+)(?:\.|\;|$)'
                    ],
                    "validation": None,
                    "priority": "medium"
                }
            }
        }
        
        # File type specific overrides
        self.file_type_patterns = {
            "_pro": {
                "article": {
                    "ean13": {
                        "patterns": [
                            r'(?i)EAN(?:-13)?(?:[-:]|\s+)\s*(\d{13})(?!\d)',
                            r'(?i)GTIN(?:-13)?(?:[-:]|\s+)\s*(\d{13})(?!\d)'
                        ]
                    }
                }
            },
            "_produktblad": {
                "technical": {
                    "dimensions": {
                        "patterns": [
                            r'(?i)(?:Dimensioner|Storlek|Mått)[\s:]*\n\s*(?:B|H|D|L)?\s*[xX]\s*(?:B|H|D|L)?\s*[xX]?\s*(?:B|H|D|L)?\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(?:mm|cm|m)\s*[xX]\s*(\d+(?:[.,]\d+)?)\s*(?:mm|cm|m)(?:\s*[xX]\s*(\d+(?:[.,]\d+)?)\s*(?:mm|cm|m))?'
                        ]
                    }
                }
            }
        }
    
    def load_patterns(self):
        """Load patterns from configuration file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Update patterns with loaded configuration
                if "patterns" in config:
                    self._merge_patterns(self.patterns, config["patterns"])
                
                if "file_type_patterns" in config:
                    self._merge_patterns(self.file_type_patterns, config["file_type_patterns"])
                
                # Clear pattern cache after loading new patterns
                self._pattern_cache.clear()
                
                logger.info(f"Successfully loaded patterns from {self.config_path}")
                
            except Exception as e:
                logger.error(f"Error loading patterns from {self.config_path}: {str(e)}")
    
    def save_patterns(self):
        """Save current patterns to configuration file"""
        try:
            config = {
                "patterns": self.patterns,
                "file_type_patterns": self.file_type_patterns,
                "last_updated": datetime.now().isoformat()
            }
            
            # Create config directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            logger.info(f"Successfully saved patterns to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Error saving patterns to {self.config_path}: {str(e)}")
            raise
    
    def _merge_patterns(self, base: Dict, update: Dict):
        """Recursively merge pattern dictionaries"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_patterns(base[key], value)
            else:
                base[key] = value
    
    def get_patterns(self, category: str, subcategory: str, 
                    file_type: Optional[str] = None) -> List[str]:
        """
        Get patterns for a specific category and subcategory.
        Optionally considers file type specific patterns.
        """
        patterns = []
        
        # Get base patterns
        if (category in self.patterns and 
            subcategory in self.patterns[category] and 
            "patterns" in self.patterns[category][subcategory]):
            patterns.extend(self.patterns[category][subcategory]["patterns"])
        
        # Apply file type specific patterns if available
        if file_type and file_type in self.file_type_patterns:
            if (category in self.file_type_patterns[file_type] and
                subcategory in self.file_type_patterns[file_type][category] and
                "patterns" in self.file_type_patterns[file_type][category][subcategory]):
                # Replace base patterns with file type specific ones
                patterns = self.file_type_patterns[file_type][category][subcategory]["patterns"]
        
        return patterns
    
    def get_validation_pattern(self, category: str, subcategory: str) -> Optional[str]:
        """Get validation pattern for a category and subcategory"""
        if (category in self.patterns and 
            subcategory in self.patterns[category] and 
            "validation" in self.patterns[category][subcategory]):
            return self.patterns[category][subcategory]["validation"]
        return None
    
    def get_priority(self, category: str, subcategory: str) -> str:
        """Get priority level for a category and subcategory"""
        if (category in self.patterns and 
            subcategory in self.patterns[category] and 
            "priority" in self.patterns[category][subcategory]):
            return self.patterns[category][subcategory]["priority"]
        return "low"
    
    def compile_pattern(self, pattern: str) -> re.Pattern:
        """Compile a pattern and cache it"""
        if pattern not in self._pattern_cache:
            try:
                self._pattern_cache[pattern] = re.compile(pattern, re.MULTILINE | re.DOTALL)
            except re.error as e:
                logger.error(f"Error compiling pattern '{pattern}': {str(e)}")
                raise
        return self._pattern_cache[pattern]
    
    def add_pattern(self, category: str, subcategory: str, pattern: str,
                   file_type: Optional[str] = None):
        """Add a new pattern"""
        try:
            # Validate pattern by trying to compile it
            re.compile(pattern)
            
            if file_type:
                # Add file type specific pattern
                if file_type not in self.file_type_patterns:
                    self.file_type_patterns[file_type] = {}
                if category not in self.file_type_patterns[file_type]:
                    self.file_type_patterns[file_type][category] = {}
                if subcategory not in self.file_type_patterns[file_type][category]:
                    self.file_type_patterns[file_type][category][subcategory] = {
                        "patterns": []
                    }
                
                self.file_type_patterns[file_type][category][subcategory]["patterns"].append(pattern)
            else:
                # Add base pattern
                if category not in self.patterns:
                    self.patterns[category] = {}
                if subcategory not in self.patterns[category]:
                    self.patterns[category][subcategory] = {
                        "patterns": [],
                        "validation": None,
                        "priority": "low"
                    }
                
                self.patterns[category][subcategory]["patterns"].append(pattern)
            
            # Clear cache for this pattern
            self._pattern_cache.clear()
            
            # Save updated patterns
            self.save_patterns()
            
        except re.error as e:
            logger.error(f"Invalid pattern '{pattern}': {str(e)}")
            raise ValueError(f"Invalid regular expression: {str(e)}")
    
    def remove_pattern(self, category: str, subcategory: str, pattern: str,
                      file_type: Optional[str] = None):
        """Remove a pattern"""
        if file_type:
            if (file_type in self.file_type_patterns and
                category in self.file_type_patterns[file_type] and
                subcategory in self.file_type_patterns[file_type][category] and
                "patterns" in self.file_type_patterns[file_type][category][subcategory]):
                patterns = self.file_type_patterns[file_type][category][subcategory]["patterns"]
                if pattern in patterns:
                    patterns.remove(pattern)
                    self._pattern_cache.clear()
                    self.save_patterns()
        else:
            if (category in self.patterns and
                subcategory in self.patterns[category] and
                "patterns" in self.patterns[category][subcategory]):
                patterns = self.patterns[category][subcategory]["patterns"]
                if pattern in patterns:
                    patterns.remove(pattern)
                    self._pattern_cache.clear()
                    self.save_patterns()
    
    def validate_value(self, category: str, subcategory: str, value: str) -> bool:
        """Validate a value using the appropriate validation pattern"""
        validation_pattern = self.get_validation_pattern(category, subcategory)
        if validation_pattern:
            try:
                return bool(re.match(validation_pattern, value))
            except re.error:
                return False
        return True
    
    def get_all_categories(self) -> List[str]:
        """Get list of all available categories"""
        return list(self.patterns.keys())
    
    def get_subcategories(self, category: str) -> List[str]:
        """Get list of all subcategories for a category"""
        if category in self.patterns:
            return list(self.patterns[category].keys())
        return []
    










    def get_file_types(self) -> List[str]:
        """Get list of all file types with specific patterns"""
        return list(self.file_type_patterns.keys())

    def get_pattern_info(self, category: str, subcategory: str, 
                        file_type: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed information about patterns for a category/subcategory"""
        info = {
            "category": category,
            "subcategory": subcategory,
            "patterns": [],
            "validation": None,
            "priority": "low",
            "file_type_specific": False
        }
        
        # Get base patterns
        if category in self.patterns and subcategory in self.patterns[category]:
            cat_info = self.patterns[category][subcategory]
            info["patterns"] = cat_info.get("patterns", [])
            info["validation"] = cat_info.get("validation")
            info["priority"] = cat_info.get("priority", "low")
        
        # Add file type specific patterns if requested
        if file_type and file_type in self.file_type_patterns:
            if (category in self.file_type_patterns[file_type] and
                subcategory in self.file_type_patterns[file_type][category]):
                info["patterns"] = self.file_type_patterns[file_type][category][subcategory].get("patterns", [])
                info["file_type_specific"] = True
        
        return info

    def analyze_patterns(self, text: str, category: str, subcategory: str,
                        file_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Analyze text using patterns and return detailed match information.
        Useful for pattern testing and debugging.
        """
        results = []
        patterns = self.get_patterns(category, subcategory, file_type)
        
        for pattern in patterns:
            try:
                compiled = self.compile_pattern(pattern)
                matches = list(compiled.finditer(text))
                
                result = {
                    "pattern": pattern,
                    "match_count": len(matches),
                    "matches": []
                }
                
                for match in matches:
                    match_info = {
                        "full_match": match.group(0),
                        "groups": [match.group(i) for i in range(1, match.lastindex + 1)] if match.lastindex else [],
                        "start": match.start(),
                        "end": match.end()
                    }
                    result["matches"].append(match_info)
                
                results.append(result)
                
            except re.error as e:
                results.append({
                    "pattern": pattern,
                    "error": str(e),
                    "match_count": 0,
                    "matches": []
                })
        
        return results

    def suggest_patterns(self, text: str, category: str, subcategory: str) -> List[str]:
        """
        Analyze text and suggest new patterns based on common formats found.
        Uses heuristics to identify potential patterns.
        """
        suggestions = []
        
        if category == "article":
            # Look for number patterns
            numbers = re.findall(r'\b\d+\b', text)
            lengths = Counter(len(num) for num in numbers)
            
            # If we find many numbers of the same length, suggest a pattern
            for length, count in lengths.items():
                if count >= 3:  # At least 3 occurrences
                    suggestions.append(f"(?<!\d)(\d{{{length}}})(?!\d)")
        
        elif category == "technical":
            # Look for measurement patterns
            measurements = re.findall(r'\d+(?:[,.]\d+)?\s*(?:mm|cm|m|V|A|kg)', text)
            if measurements:
                # Create pattern based on most common unit
                units = Counter(re.findall(r'[A-Za-z]+', m)[0] for m in measurements)
                most_common_unit = units.most_common(1)[0][0]
                suggestions.append(
                    f'(?i)([^:]+):\s*(\d+(?:[,.]\d+)?)\s*{most_common_unit}'
                )
        
        elif category == "compatibility":
            # Look for common compatibility phrases
            phrases = [
                r'passar med',
                r'fungerar tillsammans med',
                r'kan användas med',
                r'är kompatibel med'
            ]
            
            # Find contexts around these phrases
            for phrase in phrases:
                contexts = re.findall(f'.{{0,30}}{phrase}.{{0,30}}', text)
                if contexts:
                    # Create pattern based on context
                    suggestions.append(
                        f'(?i){phrase}\s+([^\.;]+)(?:\.|\;|$)'
                    )
        
        return list(set(suggestions))  # Remove duplicates

    def export_patterns(self, export_path: Optional[Path] = None) -> Path:
        """
        Export all patterns to a formatted JSON file.
        Includes metadata and documentation.
        """
        if export_path is None:
            export_path = self.config_path.parent / f"pattern_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        export_data = {
            "metadata": {
                "exported_at": datetime.now().isoformat(),
                "version": "1.0",
                "categories": self.get_all_categories(),
                "file_types": self.get_file_types()
            },
            "patterns": self.patterns,
            "file_type_patterns": self.file_type_patterns,
            "documentation": {
                "categories": {
                    cat: {
                        "subcategories": {
                            subcat: self.get_pattern_info(cat, subcat)
                            for subcat in self.get_subcategories(cat)
                        }
                    }
                    for cat in self.get_all_categories()
                }
            }
        }
        
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=4)
            logger.info(f"Successfully exported patterns to {export_path}")
            return export_path
        
        except Exception as e:
            logger.error(f"Error exporting patterns: {str(e)}")
            raise

    def import_patterns(self, import_path: Path):
        """
        Import patterns from a JSON file.
        Validates the import data before applying.
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            # Validate import data structure
            if not isinstance(import_data, dict):
                raise ValueError("Invalid import data format")
            
            if "patterns" not in import_data or "file_type_patterns" not in import_data:
                raise ValueError("Missing required pattern sections")
            
            # Validate all patterns by trying to compile them
            for category in import_data["patterns"].values():
                for subcat in category.values():
                    if "patterns" in subcat:
                        for pattern in subcat["patterns"]:
                            try:
                                re.compile(pattern)
                            except re.error as e:
                                raise ValueError(f"Invalid pattern '{pattern}': {str(e)}")
            
            # If validation passes, update patterns
            self.patterns = import_data["patterns"]
            self.file_type_patterns = import_data["file_type_patterns"]
            
            # Clear pattern cache
            self._pattern_cache.clear()
            
            # Save the imported patterns
            self.save_patterns()
            
            logger.info(f"Successfully imported patterns from {import_path}")
            
        except Exception as e:
            logger.error(f"Error importing patterns: {str(e)}")
            raise