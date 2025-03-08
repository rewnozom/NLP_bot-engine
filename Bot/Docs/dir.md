

### Filstruktur per produkt

Givet ursprungsstrukturen från en produktmapp:
```
docs\brandsläckare-filtar\50025313_pro\
├── 50025313_pro.md
├── 50025313_pro_meta.json
├── _page_0_Picture_1.jpeg
└── ...
```

Efter extraktion kommer varje produkt få sin egen strukturerade datakatalog som ser ut så här:

```
integrated_data/products/50025313/
├── article_info.jsonl         # Från EAN-extraktor
├── technical_specs.jsonl      # Från Teknisk-extraktor  
├── compatibility.jsonl        # Från Kompatibilitets-extraktor
├── summary.jsonl             # Genererad sammanfattning
├── full_info.md              # Original markdown-fil
└── command_responses/        # Bot-formaterade svar
    ├── technical_response.json
    ├── compatibility_response.json  
    └── summary_response.json
```

### JSONL-filernas innehåll

1. `article_info.jsonl`:
```jsonl
{"type": "EAN-13", "identifier": "1234567890123", "is_valid": true, "validation_message": "Giltig EAN-13"}
{"type": "Copiax-artikel", "identifier": "50025313", "is_valid": true, "validation_message": "Giltigt Copiax-format"}
```

2. `technical_specs.jsonl`:
```jsonl
{"category": "DIMENSIONS", "name": "Höjd", "raw_value": "150", "unit": "mm", "is_valid": true}
{"category": "WEIGHT", "name": "Vikt", "raw_value": "2.5", "unit": "kg", "is_valid": true}
```

3. `compatibility.jsonl`:
```jsonl
{"relation_type": "direct", "related_product": "ASSA Låshus 310-50", "numeric_ids": ["50093073"]}
{"relation_type": "requires", "related_product": "Monteringsstolpe S7", "numeric_ids": ["10009180"]}
```

4. `summary.jsonl`:
```jsonl
{"product_id": "50025313", "product_name": "ASSA Trycke 6696", "description": "...", "key_specifications": [...], "key_compatibility": [...]}
```

### Viktigaste insikterna:
1. Varje produkt får sin egen mapp under `integrated_data/products/`
2. JSONL-filerna är separerade per datatyp för enkel uppdatering
3. Bot-svaren sparas formaterade separat i `command_responses/`
4. All data är strukturerad för att enkelt kunna:
   - Bläddras manuellt
   - Redigeras via GUI
   - Uppdateras dynamiskt
   - Användas av boten för svar

