#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Image Transfer Module

This script transfers images from the converted_docs structure to the integrated_data structure,
maintaining the relationship between products and their associated images.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Set
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("image_transfer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ImageTransferConfig:
    # Source directory for converted docs
    CONVERTED_DOCS_DIR = Path("./converted_docs")
    
    # Target directory for integrated data
    INTEGRATED_DATA_DIR = Path("./integrated_data/products")
    
    # Image subdirectory name in product folders
    IMAGES_DIR_NAME = "images"
    
    # Supported image extensions
    SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    
    # Supported document type suffixes
    SUPPORTED_DOC_TYPES = [
        "_pro", "_produktblad", "_TEK", "_sak", "_man", "_ins", 
        "_CERT", "_BRO", "_INs", "_cert", "_prodblad", "_PRE", 
        "_bro", "_mdek", "_tek", "_MAN", "_PRO"
    ]

class ImageTransfer:
    """Handles the transfer of images from converted_docs to integrated_data structure"""
    
    def __init__(self):
        self.config = ImageTransferConfig()
        self.stats = {
            "total_products_processed": 0,
            "total_images_transferred": 0,
            "products_with_images": 0,
            "failed_transfers": 0
        }
        self.failed_transfers = []
    
    def process_all_products(self):
        """Process all products in the converted_docs directory"""
        logger.info("Starting image transfer process...")
        
        # Create the integrated data directory if it doesn't exist
        self.config.INTEGRATED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Find all product directories
        product_dirs = self._find_product_directories()
        
        for product_id, source_dirs in product_dirs.items():
            try:
                self._process_product(product_id, source_dirs)
                self.stats["total_products_processed"] += 1
            except Exception as e:
                logger.error(f"Error processing product {product_id}: {str(e)}")
                self.failed_transfers.append({
                    "product_id": product_id,
                    "error": str(e)
                })
        
        # Generate transfer report
        self._generate_report()
        
        logger.info("Image transfer process completed.")
        
    def _find_product_directories(self) -> Dict[str, List[Path]]:
        """
        Find all product directories in the converted_docs structure.
        Returns a dictionary mapping product IDs to their source directories.
        """
        product_dirs = {}
        
        # Walk through the converted_docs directory
        for root, dirs, files in os.walk(self.config.CONVERTED_DOCS_DIR):
            root_path = Path(root)
            
            # Check each directory for product files
            for dir_name in dirs:
                dir_path = root_path / dir_name
                
                # Check if this is a product directory by looking for supported doc types
                for doc_type in self.config.SUPPORTED_DOC_TYPES:
                    if dir_name.endswith(doc_type):
                        # Extract product ID (everything before the doc type)
                        product_id = dir_name[:-len(doc_type)]
                        
                        # Add to dictionary
                        if product_id not in product_dirs:
                            product_dirs[product_id] = []
                        product_dirs[product_id].append(dir_path)
        
        return product_dirs
    
    def _process_product(self, product_id: str, source_dirs: List[Path]):
        """Process images for a single product"""
        # Create target directory
        target_dir = self.config.INTEGRATED_DATA_DIR / product_id / self.config.IMAGES_DIR_NAME
        target_dir.mkdir(parents=True, exist_ok=True)
        
        images_found = False
        
        # Process each source directory
        for source_dir in source_dirs:
            # Find all image files in the source directory
            image_files = []
            for ext in self.config.SUPPORTED_IMAGE_EXTENSIONS:
                image_files.extend(source_dir.glob(f"*{ext}"))
            
            # Transfer each image
            for image_file in image_files:
                try:
                    # Create target path
                    target_path = target_dir / image_file.name
                    
                    # Copy the file
                    shutil.copy2(image_file, target_path)
                    self.stats["total_images_transferred"] += 1
                    images_found = True
                    
                    logger.debug(f"Transferred {image_file.name} to {target_path}")
                except Exception as e:
                    logger.error(f"Failed to transfer {image_file}: {str(e)}")
                    self.failed_transfers.append({
                        "product_id": product_id,
                        "file": str(image_file),
                        "error": str(e)
                    })
                    self.stats["failed_transfers"] += 1
        
        if images_found:
            self.stats["products_with_images"] += 1
    
    def _generate_report(self):
        """Generate a transfer report"""
        # Create report data
        report = {
            "statistics": self.stats,
            "failed_transfers": self.failed_transfers
        }
        
        # Save JSON report
        report_path = self.config.INTEGRATED_DATA_DIR.parent / "image_transfer_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # Create markdown report
        md_report_path = self.config.INTEGRATED_DATA_DIR.parent / "image_transfer_report.md"
        with open(md_report_path, 'w', encoding='utf-8') as f:
            f.write("# Image Transfer Report\n\n")
            
            f.write("## Statistics\n\n")
            f.write(f"- Total products processed: {self.stats['total_products_processed']}\n")
            f.write(f"- Total images transferred: {self.stats['total_images_transferred']}\n")
            f.write(f"- Products with images: {self.stats['products_with_images']}\n")
            f.write(f"- Failed transfers: {self.stats['failed_transfers']}\n\n")
            
            if self.failed_transfers:
                f.write("## Failed Transfers\n\n")
                for failure in self.failed_transfers:
                    f.write(f"### Product: {failure['product_id']}\n")
                    if 'file' in failure:
                        f.write(f"- File: {failure['file']}\n")
                    f.write(f"- Error: {failure['error']}\n\n")
        
        logger.info(f"Transfer report generated: {report_path}")

def main():
    """Main function"""
    transfer = ImageTransfer()
    transfer.process_all_products()

if __name__ == "__main__":
    main()