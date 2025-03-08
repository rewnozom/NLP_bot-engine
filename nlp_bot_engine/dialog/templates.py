# nlp_bot_engine/dialog/templates.py

class ResponseTemplates:
    """
    Samling av svarsmallar för olika situationer och intentioner.
    """
    
    def __init__(self):
        """
        Initialisera mallsamlingen
        """
        self.templates = {
            # Generiska mallar
            "generic": "Jag sökte information om \"{query}\". Här är vad jag hittade.",
            
            "error": "Något gick fel: {error}",
            
            # Förtydligandemallar
            "generic_clarification": "Jag förstod inte riktigt din fråga \"{query}\". Kan du omformulera den eller vara mer specifik?",
            
            "product_clarification": "{question}\n\n{options}",
            
            "intent_clarification": "{question}\n\n{options}",
           
           # Mallar för låg konfidens
           "low_confidence_disclaimer": "Jag är inte helt säker, men jag tror att du frågar om {intent}.",
           
           "alternative_intents": "Du kanske också ville fråga om {alternatives}?",
           
           # Mallar för teknisk information
           "technical_beginner_intro": "Här är de viktigaste tekniska egenskaperna för {product_name} i ett förenklat format:",
           
           "no_technical_info": "Jag kunde tyvärr inte hitta någon teknisk information för {product_name}.",
           
           # Mallar för kompatibilitet
           "compatibility_intro": "Här är information om vilka produkter som {product_name} fungerar tillsammans med:",
           
           "no_compatibility_info": "Jag kunde tyvärr inte hitta någon kompatibilitetsinformation för {product_name}.",
           
           # Mallar för sammanfattningar
           "no_summary_info": "Jag kunde tyvärr inte hitta någon sammanfattande information för {product_name}.",
           
           # Mallar för sökning
           "no_search_results": "Jag kunde inte hitta några produkter som matchar din sökning '{query}'.",
           
           
           # Produktjämförelser
            "comparison_intro": "Här är en jämförelse mellan {product_name1} och {product_name2}:",
            "no_comparison_data": "Jag har inte tillräckligt med information för att jämföra dessa produkter.",

            # Felstavningar och korrigeringar
            "spelling_correction": "Jag antar att du menade \"{corrected_query}\" istället för \"{original_query}\".",

            # Dialoghantering
            "follow_up_question": "Angående {product_name}, {follow_up_response}",
            "multiple_products_question": "Du nämnde flera produkter. Vilken vill du veta mer om?",

            # Förslag
            "suggestion": "Du kanske också vill veta om {suggestion}?",
            "related_products_suggestion": "Liknande produkter du kanske är intresserad av:",

            # Hantering av produktserier
            "product_series_intro": "{series_name}-serien omfattar flera produkter med liknande egenskaper men olika {differentiator}.",
       }
   
    def get_template(self, template_key: str) -> str:
        """
        Hämta en mall baserat på nyckel
        
        Args:
            template_key: Mallens nyckel
            
        Returns:
            Malltext eller tom sträng om nyckeln inte finns
        """
        return self.templates.get(template_key, "")
    
    def add_template(self, template_key: str, template_text: str) -> None:
        """
        Lägg till eller uppdatera en mall
        
        Args:
            template_key: Mallens nyckel
            template_text: Mallens text
        """
        self.templates[template_key] = template_text