# -*- coding: utf-8 -*-
import os
import json
import logging
import time
import requests
import pandas as pd
from io import StringIO
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ZohoPriceMatcher:
    def __init__(self):
        self.zoho_org_id = os.getenv('ZOHO_ORG_ID')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')

        # Initialize token manager
        from zoho_token_manager import ZohoTokenManager
        self.token_manager = ZohoTokenManager()

        # Zoho API endpoints
        self.zoho_base_url = 'https://www.zohoapis.com/inventory/v1'


    def search_item_price(self, item_name, sku=None, barcode=None, manufacturer=None):
        """Search for item price using enhanced Google search and sponsored link scraping"""
        try:
            from enhanced_price_matcher import EnhancedPriceMatcher
            
            # Initialize enhanced matcher
            matcher = EnhancedPriceMatcher()
            
            # Process the item through the complete pipeline
            result = matcher.process_item(item_name, manufacturer, barcode=barcode)
            
            if result and result.get('matched_price'):
                logger.info(f'💰 Found price for {item_name}: ${result["matched_price"]} (confidence: {result["confidence_score"]:.2f})')
                return result['matched_price']
            else:
                logger.warning(f'⚠️ No price found for {item_name}')
                return None
                
        except Exception as e:
            logger.error(f'❌ Error searching price for {item_name}: {e}')
            return None

    def update_item_price(self, item_id, new_price):
        """Update item price in Zoho"""
        try:
            headers = self.token_manager.get_headers()
            if not headers:
                logger.error('❌ No valid Zoho token available')
                return False
            
            # Convert scientific notation to integer string
            if 'e+' in str(item_id):
                item_id_str = f"{int(float(item_id))}"
            else:
                item_id_str = str(item_id)
                
            url = f'{self.zoho_base_url}/items/{item_id_str}?organization_id={self.zoho_org_id}'
            
            data = {
                'rate': new_price,
                'selling_rate': new_price,  # Also update selling rate for Commerce
                'purchase_rate': new_price * 0.7  # Purchase rate (70% of selling)
            }
            
            logger.info(f'🔄 Updating item {item_id_str} with price ${new_price}')
            logger.info(f'🔗 URL: {url}')
            logger.info(f'📦 Data: {data}')
            
            response = requests.put(url, headers=headers, json=data)
            
            # Log response details for debugging
            logger.info(f'📊 Response Status: {response.status_code}')
            logger.info(f'📋 Response Headers: {dict(response.headers)}')
            
            if response.status_code != 200:
                logger.error(f'❌ API Error Response: {response.text}')
            
            response.raise_for_status()
            
            logger.info(f'✅ Updated price for item {item_id_str} to ${new_price}')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error updating price for item {item_id}: {e}')
            return False


    def get_google_sheets_data(self):
        """Fetch data from Google Sheets"""
        try:
            # Google Sheets CSV export URL
            url = 'https://docs.google.com/spreadsheets/d/1igH2xZq48pb76bAG25rVBkxb8gODc0SqBHMLwu5hTSc/export?format=csv&gid=1761140701'
            
            logger.info('📊 Fetching data from Google Sheets...')
            response = requests.get(url)
            response.raise_for_status()
            
            # Read CSV data
            df = pd.read_csv(StringIO(response.text))
            logger.info(f'✅ Successfully fetched {len(df)} rows from Google Sheets')
            
            return df
            
        except Exception as e:
            logger.error(f'❌ Error fetching Google Sheets data: {e}')
            return None

    def update_google_sheet_price(self, row_index, price):
        """Update price in Google Sheet"""
        try:
            from google_sheets_updater import GoogleSheetsUpdater
            
            updater = GoogleSheetsUpdater()
            success = updater.update_cell(row_index + 2, 8, price)  # Column H (index 8)
            
            if success:
                logger.info(f'✅ Updated Google Sheet row {row_index + 2} with price ${price}')
            else:
                logger.warning(f'⚠️ Failed to update Google Sheet row {row_index + 2}')
                
            return success
            
        except Exception as e:
            logger.error(f'❌ Error updating Google Sheet: {e}')
            return False

    def match_and_update_items(self):
        """Main function to match items and update prices only"""
        try:
            logger.info('🚀 Starting Zoho Inventory Price Matcher')
            logger.info('=' * 60)
            
            # Check environment variables
            if not self.zoho_org_id:
                logger.error('❌ Missing ZOHO_ORG_ID environment variable')
                return
            
            # Step 1: Match items with Zoho Inventory first
            logger.info('🔍 Step 1: Matching items with Zoho Inventory...')
            from zoho_item_matcher import ZohoItemMatcher
            
            item_matcher = ZohoItemMatcher()
            matched_df = item_matcher.match_all_items()
            
            if matched_df is None:
                logger.error('❌ Failed to match items with Zoho Inventory')
                return
            
            # Step 2: Process items that have Zoho IDs
            logger.info('💰 Step 2: Processing items with prices...')
            
            # Filter to only items that were matched
            matched_items = matched_df[matched_df['match_status'] == 'MATCHED']
            
            if len(matched_items) == 0:
                logger.warning('⚠️ No items were matched with Zoho Inventory')
                return
            
            logger.info(f'📊 Processing {len(matched_items)} matched items...')
            
            # Process each matched item
            updated_count = 0
            price_updated_count = 0
            
            for index, row in matched_items.iterrows():
                try:
                    item_name = str(row.get('Item Name', ''))
                    zoho_id = row.get('zoho_id')
                    quantity = row.get('Quantity', 0)
                    manufacturer = str(row.get('Manufacturer', '')) if pd.notna(row.get('Manufacturer')) else None
                    barcode = str(row.get('Barcode', '')) if pd.notna(row.get('Barcode')) else None
                    
                    if not item_name or not zoho_id:
                        logger.warning(f'⚠️ Skipping row {index}: Missing item name or Zoho ID')
                        continue
                    
                    logger.info(f'🔄 Processing: {item_name} (Zoho ID: {zoho_id})')
                    
                    # Search for price using enhanced matcher
                    current_price = self.search_item_price(item_name, manufacturer=manufacturer, barcode=barcode)
                    
                    if current_price:
                        # Update Zoho Inventory price
                        if self.update_item_price(zoho_id, current_price):
                            price_updated_count += 1
                        
                        # Update Google Sheet with found price
                        self.update_google_sheet_price(index, current_price)
                    
                    # Stock levels are NOT updated - prices only
                    
                    updated_count += 1
                    
                    # Add delay to avoid rate limiting
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f'❌ Error processing row {index}: {e}')
                    continue
            
            logger.info('=' * 60)
            logger.info(f'✅ Processing complete!')
            logger.info(f'📊 Items processed: {updated_count}')
            logger.info(f'💰 Prices updated: {price_updated_count}')
            
        except Exception as e:
            logger.error(f'❌ Error in main processing: {e}')

def main():
    """Main entry point"""
    logger.info('🚀 Zoho Inventory Price Matcher')
    logger.info('=' * 60)
    logger.info('📊 Reads Google Sheets')
    logger.info('🔍 Searches web for current prices')
    logger.info('💰 Updates Zoho Inventory prices')
    logger.info('=' * 60)
    
    # Check environment variables
    required_vars = ['ZOHO_ORG_ID', 'ZOHO_REFRESH_TOKEN', 'ZOHO_CLIENT_ID', 'ZOHO_CLIENT_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f'❌ Missing environment variables: {missing_vars}')
        logger.info('Please set these environment variables:')
        for var in missing_vars:
            logger.info(f' {var}=your_value_here')
        return
    
    # Run the main matcher
    matcher = ZohoPriceMatcher()
    matcher.match_and_update_items()

if __name__ == '__main__':
    main()