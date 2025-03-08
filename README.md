# NLP Product Data Extractor & NLP Bot-Engine

This document provides an in-depth guide to the design, usage, and internal structure of two interconnected systems:
1. The **NLP Product Data Extractor**, which processes product documents and extracts structured data.
2. The **NLP Bot-Engine**, which uses advanced NLP techniques along with a graphical interface to answer product-related queries and interact with users.

---

## Part 1: NLP Product Data Extractor

### Overview
The **NLP Product Data Extractor** is a Python-based tool that leverages NLP techniques and regex to extract, integrate, and structure product data from markdown files. It is designed to handle various product documents and provides detailed reporting, error handling, and integration capabilities for further processing (e.g., database ingestion or API delivery).

### Key Features
- **Unified Extraction:** Combines NLP-based extraction with regex methods to identify product identifiers, technical specifications, and compatibility relationships.
- **NLP-Driven:** Uses spaCy (with the Swedish language model by default) for advanced entity recognition and text parsing.
- **Regex Fallback:** Complements NLP extraction with custom regex patterns for broader coverage.
- **Parallel Processing:** Processes large file sets concurrently via multi-threading.
- **Comprehensive Reporting:** Generates JSON, markdown, and quality reports detailing extraction statistics and potential issues.
- **Bot Response Generation:** Provides structured responses (technical, compatibility, summary) for integration with chatbot interfaces.
- **Maintainable Directory Structure:** Retains the original file structure while saving categorized outputs and integrated data.

### Dependencies and Installation

#### Required Packages
- **Python 3.x**
- **spaCy:**  
  - Install with: `pip install spacy`  
  - Download Swedish model (default): `python -m spacy download sv_core_news_lg`
- **tqdm:** For progress visualization (`pip install tqdm`)
- **markdown** and **BeautifulSoup4:** For parsing markdown/HTML (`pip install markdown beautifulsoup4`)
- **Standard Libraries:** os, re, json, shutil, logging, argparse, pathlib, datetime, collections, concurrent.futures, dataclasses, unicodedata, hashlib

### Quick Start

1. **Prepare Your Environment:**  
   Ensure all dependencies are installed and the module is cloned into your working directory.

2. **Organize Input Files:**  
   Place your markdown product documents in the default input directory (e.g., `./test_docs`) or another directory of your choice.

3. **Run the Extractor:**  
   Execute from the command line:
   ```bash
   ./NLP_Product_Data_Extractor.py --input <input_directory> --output <output_directory> --integrated <integrated_directory>
   ```
   Use additional options as needed (see Command-Line Arguments below).

### Command-Line Arguments
- `--input` or `-i`: Directory containing markdown files.
- `--output` or `-o`: Directory where extracted data will be saved.
- `--integrated`: Directory for integrated data output.
- `--workers` or `-w`: Number of worker threads (default: number of CPU cores).
- `--no-progress`: Disable the progress bar.
- `--verbose` or `-v`: Enable detailed output.
- `--model` or `-m`: Specify a spaCy model (default: `sv_core_news_lg`).
- `--no-bot`: Skip generating bot responses.

### Architecture and Code Structure

#### Main Components
- **Configuration (`ExtractorConfig`):**  
  Manages file type filters, directory paths, NLP model selection, extraction thresholds, and parallel processing options.
- **Data Structures:**  
  - `ProductIdentifier`: Stores product IDs (EANs, article numbers, etc.) with related metadata.
  - `TechnicalSpecification`: Captures technical details such as dimensions, voltage, or weight.
  - `CompatibilityRelation`: Represents compatibility relationships between products.
  - `ProductData`: Aggregates all extracted information for a product and provides helper methods (e.g., grouping by category).
- **Extraction Logic (`ProductDataExtractor`):**  
  - **NLP Extraction:** Uses spaCy to extract entities and technical patterns.
  - **Regex Extraction:** Uses regular expressions as a fallback or complementary method.
  - **Merging Functions:** Deduplicates and merges results from different methods.
  - **Reporting and Integration:** Saves output as JSON/JSONL files, generates integrated indices, and creates markdown/statistical reports.
  - **Bot Response Generation:** Prepares structured responses for chatbot integration.
- **Parallel Processing:**  
  Utilizes `ThreadPoolExecutor` (optionally with tqdm) to process files concurrently.
- **Logging:**  
  Writes detailed logs to both console and `unified_extractor.log`.

### Detailed Processing Flow
1. **Initialization:**  
   Parse command-line arguments and instantiate `ExtractorConfig` and `ProductDataExtractor`.
2. **File Discovery:**  
   `find_product_files()` recursively searches the input directory for matching markdown files.
3. **Data Extraction:**  
   For each file, `extract_product_data()` reads content, extracts a product ID, name, description, and runs NLP and regex extraction methods.
4. **Saving and Reporting:**  
   Saves extracted data in structured directories, generates indices and various reports (statistical, markdown, quality).
5. **Bot Responses:**  
   Optionally generates structured bot responses for technical, compatibility, or summary queries.

### Developer Tips & Future Enhancements
- **Customizing Extraction:** Adjust custom entity patterns in `add_custom_components()` or refine regex in `extract_with_regex`.
- **Improving Performance:** Tweak `max_workers` in `ExtractorConfig` if needed.
- **Error Handling:** Consult `unified_extractor.log` for issues.
- **Integration:** Extend output for databases, APIs, or dashboards.
- **Testing:** Create unit tests for individual modules (e.g., Data Manager, Entity Extractor).

### Conclusion
The NLP Product Data Extractor is a robust tool for processing product documents and extracting structured data using a mix of NLP and regex techniques. This documentation serves as a guide for developers to understand, modify, and extend the tool.

---

## Part 2: NLP Bot-Engine

### Overview
The **NLP Bot-Engine** is a Python-based application that combines a PySide6-based graphical interface with advanced NLP capabilities. It is designed to answer complex product-related queries by using techniques such as intent analysis, entity extraction, context management, and semantic matching. The bot integrates product data (from indices and extraction outputs) to provide detailed, formatted responses in a chat interface.

### Architecture

#### GUI & Application Core (`main.py`)
- Sets up the main window and UI panels: **Chat Interface**, **Product Explorer**, **JSON Editor**, **Settings Panel**, and **Report Viewer**.
- Applies themes and font settings via helper modules and handles user interactions.

#### Core Modules (under `nlp_bot_engine/core`)
- **Engine (`engine.py`):**  
  - **AdvancedBotEngine** acts as the central orchestrator. It differentiates between direct command queries (using prefixes like `-t`, `-c`, etc.) and natural language queries.
  - Updates statistics, caches responses, and delegates to the Data Manager and Response Generator.
- **Data Manager (`data_manager.py`):**  
  - Manages access to integrated product data and indices (technical specs, compatibility, summaries, product names).
  - Provides search functionality and builds/updates product name mappings.
- **Configuration (`config.py`):**  
  - Centralizes configuration settings (directory paths, NLP settings, response templates, caching, performance parameters).
  - Automatically sets up required directories and adjusts paths based on the runtime environment.

#### Dialog Modules (under `nlp_bot_engine/dialog`)
- **Response Generator (`response_generator.py`):**  
  - Formats dynamic responses based on query analysis using a collection of templates.
  - Adjusts response detail according to inferred user expertise.
- **Templates (`templates.py`):**  
  - Contains a collection of predefined response templates for various scenarios (technical, compatibility, summary, clarification, errors).

#### NLP Modules (under `nlp_bot_engine/nlp`)
- **Processor (`processor.py`):**  
  - Serves as the main NLP interface. Handles text preprocessing, tokenization, and generates embeddings using transformer models.
- **Entity Extractor (`entity_extractor.py`):**  
  - Extracts entities (product identifiers, dimensions, etc.) using spaCy’s NER, regex-based methods, and product index matching.
  - Merges overlapping entities and enriches them with additional product data.
- **Intent Analyzer (`intent_analyzer.py`):**  
  - Combines keyword-based, semantic, entity-based, and context-based approaches to identify user intent.
  - Outputs a ranked list of intents along with confidence scores.
- **Context Manager (`context_manager.py`):**  
  - Maintains conversation context by tracking query history, resolving pronoun references, and updating the active product based on previous interactions.

### Dependencies & Setup

#### Required Packages
- **Python 3.x**
- **PySide6:** For GUI components  
  `pip install PySide6`
- **spaCy:** For NLP processing  
  `pip install spacy` and download the model: `python -m spacy download sv_core_news_lg`
- **Transformers:** For embeddings and semantic analysis  
  `pip install transformers`
- **Numpy:** For numerical operations  
  `pip install numpy`
- **Standard Libraries:** logging, re, json, datetime, etc.

#### Setup Instructions
1. **Clone the Repository:**  
   Ensure all modules (GUI, core, dialog, NLP) are arranged according to the repository structure.
2. **Install Dependencies:**  
   ```bash
   pip install PySide6 spacy transformers numpy
   ```
   Download the required spaCy model:
   ```bash
   python -m spacy download sv_core_news_lg
   ```
3. **Configuration:**  
   Modify default paths, NLP settings, and response templates in `nlp_bot_engine/core/config.py` or supply a custom configuration dictionary.

### Usage

- **Launching the Application:**  
  Run the main entry point:
  ```bash
  python main.py
  ```
  This opens the Developer Bot-Chat window with three panels:
  - Left Panel: **Product Explorer** and **Settings Panel**
  - Right Panel: **Chat Interface** and **JSON Editor**
  - Additional Panel: **Report Viewer**

- **Interacting with the Bot:**  
  - **Direct Commands:** Use command prefixes (`-t`, `-c`, `-s`, `-f`) with a product ID (and optional parameters) to retrieve technical, compatibility, summary, or full product information.
  - **Natural Language Queries:** Type your question directly. The engine preprocesses the text, extracts entities, determines intent, and updates conversation context before generating a formatted response.

### Module Responsibilities

#### Application Core (`main.py`)
- Initializes the GUI, connects signals between panels, loads/saves configuration, and routes user selections to the appropriate modules.

#### Engine (`engine.py`)
- **AdvancedBotEngine:**  
  Orchestrates query processing by distinguishing command versus natural language inputs, updating statistics, caching responses, and delegating data retrieval and response formatting.

#### Data Management (`data_manager.py`)
- Loads product indices (article numbers, EAN codes, compatibility maps, etc.) and manages product data retrieval (technical specs, summaries, compatibility).
- Builds and updates product name mappings.

#### Configuration (`config.py`)
- Sets default directories (integrated data, cache, products), defines NLP settings (spaCy model, embeddings model, confidence thresholds), and response templates.

#### Response Generation (`response_generator.py` & `templates.py`)
- Formats responses for both command-based and natural language queries.
- Adjusts the level of detail based on inferred user expertise.

#### NLP Components
- **Processor (`processor.py`):**  
  Handles text preprocessing, tokenization, and loads spaCy and transformer models for embeddings.
- **Entity Extractor (`entity_extractor.py`):**  
  Extracts entities via spaCy NER, regex, and product index matching. Merges overlapping entities and enriches them.
- **Intent Analyzer (`intent_analyzer.py`):**  
  Combines multiple approaches (keywords, semantics, entities, context) to identify the user’s intent.
- **Context Manager (`context_manager.py`):**  
  Tracks conversation history, active products, and resolves ambiguous references in user queries.

### Workflow

1. **User Input Handling:**  
   The AdvancedBotEngine receives input from the chat interface.
2. **Command vs. Natural Language:**  
   Direct commands (prefixed with `-`) are processed immediately, while natural language queries are passed through NLP processing (preprocessing, entity extraction, intent analysis, context update).
3. **Response Generation:**  
   The Response Generator formats the answer using appropriate templates and returns a structured response.
4. **Display:**  
   The formatted response is displayed in the chat window, and related data may be updated in the JSON Editor or Report Viewer.

### Developer Tips & Future Enhancements

- **Extending Functionality:**  
  - To add new response templates, update `templates.py` and adjust logic in the Response Generator.
  - Enhance entity extraction by refining regex patterns or spaCy custom components.
  - Improve intent detection by adjusting weightings or expanding the list of intent prototypes.
- **Configuration Adjustments:**  
  - Update default paths, caching settings, and performance parameters in `config.py` as needed.
  - Use the Settings Panel to modify configuration at runtime.
- **Testing & Logging:**  
  - Leverage logging (to file and console) for troubleshooting.
  - Develop unit tests for core modules (Data Manager, Entity Extractor, Intent Analyzer).
- **Performance & Learning:**  
  - Monitor cache usage and adjust `max_workers` and cache TTL.
  - Consider integrating learning mechanisms using user feedback to refine intent detection and response quality.

### Conclusion
The NLP Bot-Engine is a robust, modular system that leverages advanced NLP techniques to understand and respond to product-related queries. This documentation provides a detailed overview to help developers understand, maintain, and extend the system.
