# -*- coding: utf-8 -*-
import requests
import pandas as pd
import cv2
import numpy as np
from pyzbar import pyzbar
import base64
from io import BytesIO
from PIL import Image
import logging
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BarcodeExtractor:
    def __init__(self):
        self.google_sheets_url = 'https://docs.google.com/spreadsheets/d/1igH2xZq48pb76bAG25rVBkxb8gODc0SqBHMLwu5hTSc/export?format=csv&gid=1761140701'
    
    def get_sheet_data(self):
        """Get data from Google Sheets"""
        try:
            logger.info("📊 Fetching Google Sheet data...")
            response = requests.get(self.google_sheets_url)
            response.raise_for_status()
            
            df = pd.read_csv(pd.StringIO(response.text))
            logger.info(f"✅ Successfully loaded {len(df)} rows")
            logger.info(f"📋 Columns: {list(df.columns)}")
            
            return df
        except Exception as e:
            logger.error(f"❌ Error fetching sheet data: {e}")
            return None
    
    def extract_barcode_from_image_url(self, image_url):
        """Extract barcode from image URL"""
        try:
            if pd.isna(image_url) or not image_url:
                return None
                
            logger.info(f"🔍 Extracting barcode from image: {image_url}")
            
            # Download image
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # Convert to OpenCV format
            image = Image.open(BytesIO(response.content))
            image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Extract barcodes
            barcodes = pyzbar.decode(image_cv)
            
            if barcodes:
                barcode_data = barcodes[0].data.decode('utf-8')
                barcode_type = barcodes[0].type
                logger.info(f"✅ Found barcode: {barcode_data} (Type: {barcode_type})")
                return barcode_data
            else:
                logger.warning("⚠️ No barcode found in image")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error extracting barcode: {e}")
            return None
    
    def extract_barcodes_from_sheet(self):
        """Extract barcodes from all images in the sheet"""
        df = self.get_sheet_data()
        if df is None:
            return None
        
        # Look for image column (could be named differently)
        image_columns = [col for col in df.columns if 'image' in col.lower() or 'picture' in col.lower() or 'photo' in col.lower()]
        
        if not image_columns:
            logger.warning("⚠️ No image columns found in sheet")
            return df
        
        image_col = image_columns[0]
        logger.info(f"🖼️ Using image column: {image_col}")
        
        # Extract barcodes
        df['barcode'] = df[image_col].apply(self.extract_barcode_from_image_url)
        
        # Count successful extractions
        successful_extractions = df['barcode'].notna().sum()
        logger.info(f"✅ Successfully extracted {successful_extractions} barcodes out of {len(df)} items")
        
        return df
    
    def get_items_with_barcodes(self):
        """Get items that have successfully extracted barcodes"""
        df = self.extract_barcodes_from_sheet()
        if df is None:
            return None
        
        # Filter items with barcodes
        items_with_barcodes = df[df['barcode'].notna()].copy()
        logger.info(f"📦 Found {len(items_with_barcodes)} items with barcodes")
        
        return items_with_barcodes

def main():
    """Test the barcode extractor"""
    extractor = BarcodeExtractor()
    
    # Extract barcodes from sheet
    items_with_barcodes = extractor.get_items_with_barcodes()
    
    if items_with_barcodes is not None and len(items_with_barcodes) > 0:
        print("\n🔍 Sample items with barcodes:")
        print(items_with_barcodes[['Item Name', 'barcode']].head(10))
    else:
        print("❌ No items with barcodes found")

if __name__ == "__main__":
    main()
