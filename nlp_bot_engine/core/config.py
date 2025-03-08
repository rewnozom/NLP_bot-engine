# nlp_bot_engine/core/config.py

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

class BotConfig:
    """
    Konfigurationshanterare för botmotorn.
    Hanterar konfigurationsparametrar och standardvärden.
    """
    
    def __init__(self, config_dict: Dict[str, Any] = None):
        """
        Initialisera konfiguration med givna parametrar eller standardvärden
        
        Args:
            config_dict: Konfigurationsparametrar som dict
        """
        config_dict = config_dict or {}
        
        # Hitta rotkatalogen för projektet
        # Om vi kör från Github/main.py, då är root_dir = Github
        # Om vi kör från nlp_bot_engine/någon_fil.py, då är root_dir = parent av nlp_bot_engine
        current_file = Path(__file__).resolve()
        if "nlp_bot_engine" in str(current_file):
            # Vi är i nlp_bot_engine-modulen
            root_dir = current_file.parent.parent.parent  # Gå upp från core/config.py till förälder av nlp_bot_engine
        else:
            # Antar att vi kör från annan plats, använd current working directory
            root_dir = Path(os.getcwd())
        
        # Bassökvägar relativt rotkatalogen
        self.root_dir = root_dir
        self.base_dir = root_dir / config_dict.get("base_dir", "data")
        self.integrated_data_dir = root_dir / config_dict.get("integrated_data_dir", "integrated_data")
        self.cache_dir = root_dir / config_dict.get("cache_dir", "cache")
        
        # Skapa om de inte existerar
        self.integrated_data_dir.mkdir(exist_ok=True, parents=True)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        
        # Produktdatakatalog
        self.products_dir = self.integrated_data_dir / "products"
        
        # Debug-logga faktiska sökvägar
        print(f"Script running from: {os.getcwd()}")
        print(f"Root directory: {self.root_dir.absolute()}")
        print(f"Base directory: {self.base_dir.absolute()}")
        print(f"Integrated data directory: {self.integrated_data_dir.absolute()}")
        print(f"Products directory: {self.products_dir.absolute()}")
        print(f"Products directory exists: {self.products_dir.exists()}")
        
        # Sök också efter alternativa platser om produktkatalogen inte finns
        if not self.products_dir.exists():
            alt_product_dirs = [
                root_dir / "data" / "integrated_data" / "products",
                root_dir / "nlp_bot_engine" / "data" / "integrated_data" / "products",
                root_dir.parent / "integrated_data" / "products"
            ]
            
            for alt_dir in alt_product_dirs:
                if alt_dir.exists():
                    print(f"Found alternative products directory: {alt_dir}")
                    self.products_dir = alt_dir
                    self.integrated_data_dir = alt_dir.parent
                    break
        
        # NLP-inställningar
        self.use_nlp = config_dict.get("use_nlp", True)
        self.spacy_model = config_dict.get("spacy_model", "sv_core_news_lg")  # Svenska (stor modell)
        self.embeddings_model = config_dict.get("embeddings_model", "KBLab/sentence-bert-swedish-cased")
        self.min_confidence = config_dict.get("min_confidence", 0.6)
        
        # Svarsalternativ
        self.response_settings = config_dict.get("response_settings", {})
        self.max_search_results = config_dict.get("max_search_results", 5)
        
        # Svarsgenerering
        self.response_templates = config_dict.get("response_templates", {
            "technical": "# Tekniska specifikationer för {product_name}\n\n" +
                         "**Artikelnummer:** {product_id}\n\n{specifications}",
            "compatibility": "# Kompatibilitetsinformation för {product_name}\n\n" +
                             "**Artikelnummer:** {product_id}\n\n{compatibility}",
            "summary": "# {product_name}\n\n" +
                       "**Artikelnummer:** {product_id}\n\n" +
                       "{description}\n\n{specifications}\n\n{compatibility}"
        })
        
        # Prestandainställningar
        self.cache_enabled = config_dict.get("cache_enabled", True)
        self.cache_ttl = config_dict.get("cache_ttl", 3600)  # 1 timme
        self.max_workers = config_dict.get("max_workers", os.cpu_count())
        
        # Debug och loggning
        self.debug = config_dict.get("debug", False)
        self.verbose = config_dict.get("verbose", False)
        
        # Återkoppling och lärande
        self.enable_learning = config_dict.get("enable_learning", False)
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Konvertera konfigurationen till en dictionary
        
        Returns:
            Dict representation av konfigurationen
        """
        return {
            "base_dir": str(self.base_dir),
            "integrated_data_dir": str(self.integrated_data_dir),
            "cache_dir": str(self.cache_dir),
            "products_dir": str(self.products_dir),
            "use_nlp": self.use_nlp,
            "spacy_model": self.spacy_model,
            "embeddings_model": self.embeddings_model,
            "min_confidence": self.min_confidence,
            "response_settings": self.response_settings,
            "max_search_results": self.max_search_results,
            "response_templates": self.response_templates,
            "cache_enabled": self.cache_enabled,
            "cache_ttl": self.cache_ttl,
            "max_workers": self.max_workers,
            "debug": self.debug,
            "verbose": self.verbose,
            "enable_learning": self.enable_learning
        }
    
    def update(self, new_config: Dict[str, Any]) -> None:
        """
        Uppdatera konfigurationen med nya parametrar
        
        Args:
            new_config: Nya konfigurationsparametrar
        """
        # Återinitiera med kombinerade konfigurationer
        current_config = self.to_dict()
        current_config.update(new_config)
        self.__init__(current_config)