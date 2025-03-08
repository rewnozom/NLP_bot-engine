


# modules/data_processor.py

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
import re
import concurrent.futures
import threading
import queue
from collections import defaultdict

from .pattern_config import PatternConfig

logger = logging.getLogger(__name__)

class DataProcessor:
    """
    Handles processing and integration of product data from various sources.
    Coordinates with pattern matching and data validation.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pattern_config = PatternConfig()
        
        # Set up paths
        self.base_dir = Path(config.get("base_dir", "./converted_docs"))
        self.integrated_data_dir = Path(config.get("integrated_data_dir", "./nlp_bot_engine/data/integrated_data"))
        self.products_dir = self.integrated_data_dir / "products"
        
        # Ensure directories exist
        self.products_dir.mkdir(parents=True, exist_ok=True)
        (self.integrated_data_dir / "indices").mkdir(parents=True, exist_ok=True)
        
        # Processing state
        self.processing_queue = queue.Queue()
        self.processed_items = set()
        self.processing_errors = []
        self._processing_thread = None
        self._stop_processing = threading.Event()
        
        # Initialize indices
        self.indices = {
            "article": {},
            "ean": {},
            "compatibility": defaultdict(list),
            "technical": defaultdict(list),
            "text": defaultdict(list)
        }
        
        # Load existing indices
        self.load_indices()
    
    def load_indices(self):
        """Load existing indices from the integrated data directory"""
        index_dir = self.integrated_data_dir / "indices"
        
        # Load each index type
        index_files = {
            "article": "article_numbers.json",
            "ean": "ean_numbers.json",
            "compatibility": "compatibility_map.json",
            "technical": "technical_specs_index.json",
            "text": "text_search_index.json"
        }
        
        for index_type, filename in index_files.items():
            index_path = index_dir / filename
            if index_path.exists():
                try:
                    with open(index_path, 'r', encoding='utf-8') as f:
                        self.indices[index_type] = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading {index_type} index: {str(e)}")
                    # Initialize empty index if loading fails
                    self.indices[index_type] = {} if index_type in ["article", "ean"] else defaultdict(list)
    
    def save_indices(self):
        """Save current indices to disk"""
        index_dir = self.integrated_data_dir / "indices"
        
        for index_type, data in self.indices.items():
            index_path = index_dir / f"{index_type}_{'numbers' if index_type in ['article', 'ean'] else 'index'}.json"
            try:
                with open(index_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Error saving {index_type} index: {str(e)}")
    
    def start_processing(self):
        """Start the background processing thread"""
        if self._processing_thread is None or not self._processing_thread.is_alive():
            self._stop_processing.clear()
            self._processing_thread = threading.Thread(target=self._process_queue)
            self._processing_thread.daemon = True
            self._processing_thread.start()
    
    def stop_processing(self):
        """Stop the background processing thread"""
        if self._processing_thread and self._processing_thread.is_alive():
            self._stop_processing.set()
            self._processing_thread.join()
            self._processing_thread = None
    
    def _process_queue(self):
        """Process items from the queue in the background"""
        while not self._stop_processing.is_set():
            try:
                # Get item with timeout to allow checking stop flag
                item = self.processing_queue.get(timeout=1)
                
                try:
                    # Process the item based on its type
                    if isinstance(item, dict) and "type" in item:
                        if item["type"] == "product":
                            self.process_product(item["product_id"])
                        elif item["type"] == "file":
                            self.process_file(item["path"])
                    
                    # Mark as processed
                    self.processed_items.add(
                        item.get("product_id", item.get("path", "unknown"))
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing item {item}: {str(e)}")
                    self.processing_errors.append({
                        "item": item,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                
                finally:
                    self.processing_queue.task_done()
                    
            except queue.Empty:
                continue
    
    def queue_product(self, product_id: str):
        """Add a product to the processing queue"""
        if product_id not in self.processed_items:
            self.processing_queue.put({
                "type": "product",
                "product_id": product_id
            })
    
    def queue_file(self, file_path: Path):
        """Add a file to the processing queue"""
        if str(file_path) not in self.processed_items:
            self.processing_queue.put({
                "type": "file",
                "path": str(file_path)
            })


    def process_product(self, product_id: str):
        """Process all data for a specific product"""
        logger.info(f"Processing product: {product_id}")
        
        # Create product directory
        product_dir = self.products_dir / product_id
        product_dir.mkdir(exist_ok=True)
        
        try:
            # Process technical specifications
            self._process_technical_specs(product_id, product_dir)
            
            # Process compatibility information
            self._process_compatibility(product_id, product_dir)
            
            # Process article information
            self._process_article_info(product_id, product_dir)
            
            # Generate summary
            self._generate_product_summary(product_id, product_dir)
            
            # Update indices
            self._update_indices(product_id)
            
            logger.info(f"Successfully processed product: {product_id}")
            
        except Exception as e:
            logger.error(f"Error processing product {product_id}: {str(e)}")
            raise
    
    def _process_technical_specs(self, product_id: str, product_dir: Path):
        """Process technical specifications for a product"""
        tech_file = product_dir / "technical_specs.jsonl"
        
        # Find all technical spec files
        spec_files = []
        for file_type in self.config.get("supported_file_types", []):
            pattern = f"**/{product_id}{file_type}.md"
            spec_files.extend(self.base_dir.glob(pattern))
        
        if not spec_files:
            return
        
        # Process each file
        specs = []
        for file_path in spec_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Extract specs using patterns
                file_type = self._get_file_type(file_path.name)
                extracted_specs = self._extract_technical_specs(content, file_type)
                specs.extend(extracted_specs)
            
            except Exception as e:
                logger.error(f"Error processing technical specs from {file_path}: {str(e)}")
        
        # Save extracted specs
        if specs:
            with open(tech_file, 'w', encoding='utf-8') as f:
                for spec in specs:
                    json.dump(spec, f, ensure_ascii=False)
                    f.write('\n')
    
    def _process_compatibility(self, product_id: str, product_dir: Path):
        """Process compatibility information for a product"""
        compat_file = product_dir / "compatibility.jsonl"
        
        # Find relevant files
        compat_files = []
        for file_type in self.config.get("supported_file_types", []):
            pattern = f"**/{product_id}{file_type}.md"
            compat_files.extend(self.base_dir.glob(pattern))
        
        if not compat_files:
            return
        
        # Process each file
        relations = []
        for file_path in compat_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Extract compatibility info using patterns
                file_type = self._get_file_type(file_path.name)
                extracted_relations = self._extract_compatibility(content, file_type)
                relations.extend(extracted_relations)
            
            except Exception as e:
                logger.error(f"Error processing compatibility from {file_path}: {str(e)}")
        
        # Save extracted relations
        if relations:
            with open(compat_file, 'w', encoding='utf-8') as f:
                for relation in relations:
                    json.dump(relation, f, ensure_ascii=False)
                    f.write('\n')
    
    def _process_article_info(self, product_id: str, product_dir: Path):
        """Process article information for a product"""
        article_file = product_dir / "article_info.jsonl"
        
        # Find relevant files
        article_files = []
        for file_type in self.config.get("supported_file_types", []):
            pattern = f"**/{product_id}{file_type}.md"
            article_files.extend(self.base_dir.glob(pattern))
        
        if not article_files:
            return
        
        # Process each file
        identifiers = []
        for file_path in article_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Extract article info using patterns
                file_type = self._get_file_type(file_path.name)
                extracted_identifiers = self._extract_article_info(content, file_type)
                identifiers.extend(extracted_identifiers)
            
            except Exception as e:
                logger.error(f"Error processing article info from {file_path}: {str(e)}")
        
        # Save extracted identifiers
        if identifiers:
            with open(article_file, 'w', encoding='utf-8') as f:
                for identifier in identifiers:
                    json.dump(identifier, f, ensure_ascii=False)
                    f.write('\n')
    
    def _generate_product_summary(self, product_id: str, product_dir: Path):
        """Generate a summary of all product information"""
        summary_file = product_dir / "summary.jsonl"
        
        # Collect data from all sources
        summary = {
            "product_id": product_id,
            "generated_at": datetime.now().isoformat(),
            "product_name": None,
            "description": None,
            "key_specifications": [],
            "key_compatibility": [],
            "identifiers": {}
        }
        
        # Get product name and identifiers from article info
        article_file = product_dir / "article_info.jsonl"
        if article_file.exists():
            with open(article_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if not summary["product_name"] and "context" in data:
                            # Try to find product name in context
                            name_match = re.search(r'(?i)produktnamn\s*:\s*([^\n\r.]+)', data["context"])
                            if name_match:
                                summary["product_name"] = name_match.group(1).strip()
                        
                        # Collect identifiers
                        id_type = data.get("type")
                        id_value = data.get("identifier")
                        if id_type and id_value:
                            if id_type not in summary["identifiers"]:
                                summary["identifiers"][id_type] = []
                            summary["identifiers"][id_type].append(id_value)
                    except json.JSONDecodeError:
                        continue
        
        # Get key specifications
        tech_file = product_dir / "technical_specs.jsonl"
        if tech_file.exists():
            specs = []
            with open(tech_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        spec = json.loads(line)
                        specs.append(spec)
                    except json.JSONDecodeError:
                        continue
            
            # Select key specifications (max 10)
            specs.sort(key=lambda x: (
                x.get("importance", "normal") != "high",
                x.get("importance", "normal") != "medium"
            ))
            summary["key_specifications"] = specs[:10]
        
        # Get key compatibility
        compat_file = product_dir / "compatibility.jsonl"
        if compat_file.exists():
            relations = []
            with open(compat_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        relation = json.loads(line)
                        relations.append(relation)
                    except json.JSONDecodeError:
                        continue
            
            # Select key relations (max 10)
            relations.sort(key=lambda x: "numeric_ids" not in x)
            summary["key_compatibility"] = relations[:10]
        
        # Save summary
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False)
            f.write('\n')

    def _extract_technical_specs(self, content: str, file_type: str = None) -> List[Dict[str, Any]]:
        """Extract technical specifications from content using pattern matching"""
        specs = []
        
        # Get patterns for technical specs
        for subcategory in ["dimensions", "electrical", "performance", "material"]:
            patterns = self.pattern_config.get_patterns("technical", subcategory, file_type)
            
            for pattern in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    spec = {
                        "category": subcategory.upper(),
                        "name": match.group(1) if match.lastindex > 1 else "",
                        "raw_value": match.group(1 if match.lastindex == 1 else 2),
                        "unit": match.group(3) if match.lastindex > 2 else "",
                        "is_valid": True
                    }
                    specs.append(spec)
        
        return specs

    def _extract_compatibility(self, content: str, file_type: str = None) -> List[Dict[str, Any]]:
        """Extract compatibility information from content using pattern matching"""
        relations = []
        
        # Get patterns for compatibility
        for relation_type in ["direct", "requires", "fits"]:
            patterns = self.pattern_config.get_patterns("compatibility", relation_type, file_type)
            
            for pattern in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    relation = {
                        "relation_type": relation_type,
                        "related_product": match.group(1),
                        "context": match.group(0),
                        "is_valid": True
                    }
                    
                    # Try to extract article numbers
                    numbers = re.findall(r'\b\d{8}\b', match.group(1))
                    if numbers:
                        relation["numeric_ids"] = numbers
                    
                    relations.append(relation)
        
        return relations

    def _extract_article_info(self, content: str, file_type: str = None) -> List[Dict[str, Any]]:
        """Extract article information from content using pattern matching"""
        identifiers = []
        
        # Get patterns for article info
        for id_type in ["ean13", "article", "copiax_article"]:
            patterns = self.pattern_config.get_patterns("article", id_type, file_type)
            
            for pattern in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    identifier = {
                        "type": "EAN-13" if id_type == "ean13" else 
                            "Copiax-artikel" if id_type == "copiax_article" else
                            "Artikelnummer",
                        "identifier": match.group(1),
                        "context": match.group(0),
                        "is_valid": True
                    }
                    identifiers.append(identifier)
        
        return identifiers

    def _update_indices(self, product_id: str):
        """Update search indices for a product"""
        product_dir = self.products_dir / product_id
        
        # Update article number index
        article_file = product_dir / "article_info.jsonl"
        if article_file.exists():
            with open(article_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if data.get("type") in ["Artikelnummer", "Copiax-artikel"]:
                            identifier = data.get("identifier")
                            if identifier:
                                self.indices["article"][identifier] = product_id
                        elif data.get("type") in ["EAN-13", "EAN-8", "GTIN"]:
                            identifier = data.get("identifier")
                            if identifier:
                                self.indices["ean"][identifier] = product_id
                    except json.JSONDecodeError:
                        continue
        
        # Update compatibility index
        compat_file = product_dir / "compatibility.jsonl"
        if compat_file.exists():
            self.indices["compatibility"][product_id] = []
            with open(compat_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        relation = json.loads(line)
                        self.indices["compatibility"][product_id].append(relation)
                    except json.JSONDecodeError:
                        continue
        
        # Update technical specs index
        tech_file = product_dir / "technical_specs.jsonl"
        if tech_file.exists():
            with open(tech_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        spec = json.loads(line)
                        category = spec.get("category", "unknown")
                        self.indices["technical"][category].append({
                            "product_id": product_id,
                            "spec": spec
                        })
                    except json.JSONDecodeError:
                        continue
        
        # Update text search index
        summary_file = product_dir / "summary.jsonl"
        if summary_file.exists():
            with open(summary_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        summary = json.loads(line)
                        # Extract searchable text
                        searchable_text = [
                            summary.get("product_name", ""),
                            summary.get("description", "")
                        ]
                        # Add specs
                        for spec in summary.get("key_specifications", []):
                            searchable_text.extend([
                                spec.get("name", ""),
                                spec.get("value", ""),
                                spec.get("category", "")
                            ])
                        # Process text
                        words = set()
                        for text in searchable_text:
                            if text:
                                # Normalize and split into words
                                normalized = re.sub(r'[^\w\s]', ' ', text.lower())
                                words.update(w for w in normalized.split() if len(w) > 2)
                        # Update index
                        for word in words:
                            self.indices["text"][word].append(product_id)
                    except json.JSONDecodeError:
                        continue
        
        # Save updated indices
        self.save_indices()

    def _get_file_type(self, filename: str) -> Optional[str]:
        """Extract file type from filename"""
        for file_type in self.config.get("supported_file_types", []):
            if filename.endswith(file_type + ".md"):
                return file_type
        return None

    def process_file(self, file_path: str):
        """Process a single file for data extraction"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Extract product ID from filename
        file_type = self._get_file_type(file_path.name)
        if not file_type:
            raise ValueError(f"Unsupported file type: {file_path}")
        
        product_id = file_path.stem[:-len(file_type)]
        
        # Queue the product for processing
        self.queue_product(product_id)

    def get_processing_status(self) -> Dict[str, Any]:
        """Get current processing status"""
        return {
            "queue_size": self.processing_queue.qsize(),
            "processed_items": len(self.processed_items),
            "error_count": len(self.processing_errors),
            "is_processing": bool(self._processing_thread and self._processing_thread.is_alive())
        }

    def get_processing_errors(self) -> List[Dict[str, Any]]:
        """Get list of processing errors"""
        return self.processing_errors.copy()

    def clear_processing_errors(self):
        """Clear the processing errors list"""
        self.processing_errors.clear()




























