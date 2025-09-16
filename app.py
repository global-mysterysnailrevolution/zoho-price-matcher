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

class ZohoPriceStockMatcher:
    def __init__(self):
        self.zoho_org_id = os.getenv('ZOHO_ORG_ID')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')

        # Initialize token manager
        from zoho_token_manager import ZohoTokenManager
        self.token_manager = ZohoTokenManager()

        # Zoho API endpoints
        self.zoho_base_url = 'https://www.zohoapis.com/inventory/v1'

        # Default warehouse ID (you may need to get this from your Zoho account)
        self.default_warehouse_id = '460000000038080'  # Update this with your actual warehouse ID

    def get_warehouses(self):
        """Get list of warehouses/locations"""
        try:
            headers = self.token_manager.get_headers()
            if not headers:
                logger.error('❌ No valid Zoho token available')
                return None

            url = f'{self.zoho_base_url}/settings/warehouses?organization_id={self.zoho_org_id}'
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            warehouses = response.json().get('warehouses', [])
            logger.info(f'✅ Found {len(warehouses)} warehouses')
            return warehouses
            
        except Exception as e:
            logger.error(f'❌ Error getting warehouses: {e}')
            return None

    def search_item_price(self, item_name, sku=None, barcode=None, manufacturer=None):
        """Search for item price using enhanced product matching and web scraping"""
        try:
            from web_price_scraper import WebPriceScraper
            from product_matcher import ProductMatcher
            
            # Initialize matcher and scraper
            matcher = ProductMatcher()
            scraper = WebPriceScraper()
            
            # Process the item to extract MPN, condition, etc.
            item_data = matcher.process_item(item_name, manufacturer, barcode)
            
            logger.info(f'🔍 Processed item data: {item_data}')
            
            # Search for prices using multiple approaches
            prices = []
            
            # 1. Search by MPN if available (most accurate)
            if item_data.get('mpn'):
                logger.info(f'🔍 Searching by MPN: {item_data["mpn"]}')
                mpn_price = scraper.search_multiple_sources(item_data['mpn'], item_data.get('barcode'))
                if mpn_price:
                    prices.append({
                        'price': mpn_price,
                        'source': 'mpn_search',
                        'confidence': 0.9,
                        'mpn': item_data['mpn']
                    })
            
            # 2. Search by barcode if available
            if barcode:
                logger.info(f'🔍 Searching by barcode: {barcode}')
                barcode_price = scraper.search_by_barcode(barcode)
                if barcode_price:
                    prices.append({
                        'price': barcode_price,
                        'source': 'barcode_search',
                        'confidence': 0.8,
                        'barcode': barcode
                    })
            
            # 3. Search by item name (fallback)
            logger.info(f'🔍 Searching by item name: {item_name}')
            name_price = scraper.search_multiple_sources(item_name, barcode)
            if name_price:
                prices.append({
                    'price': name_price,
                    'source': 'name_search',
                    'confidence': 0.6,
                    'title': item_name
                })
            
            # Choose best price based on confidence
            if prices:
                # Sort by confidence and pick the best
                best_price_data = max(prices, key=lambda x: x['confidence'])
                base_price = best_price_data['price']
                
                # Apply condition-based pricing
                final_price = matcher.apply_condition_pricing(
                    base_price, 
                    item_data['condition'],
                    is_reagent=item_data.get('unit_type') in ['reagents', 'chemicals']
                )
                
                logger.info(f'💰 Final price for {item_name}: ${final_price} (from {best_price_data["source"]})')
                return final_price
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

    def create_stock_adjustment(self, item_id, new_quantity, warehouse_id=None):
        """Create inventory adjustment to set stock level"""
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
            
            # Use default warehouse if not specified
            if not warehouse_id:
                warehouse_id = self.default_warehouse_id
            
            url = f'{self.zoho_base_url}/inventoryadjustments?organization_id={self.zoho_org_id}'
            
            data = {
                'adjustment_date': datetime.now().strftime('%Y-%m-%d'),
                'reason': 'Stock update from Google Sheets',
                'line_items': [{
                    'item_id': item_id_str,
                    'warehouse_id': warehouse_id,
                    'quantity_adjusted': new_quantity
                }]
            }
            
            logger.info(f'📦 Creating stock adjustment for item {item_id_str}: {new_quantity} units')
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            logger.info(f'✅ Created stock adjustment for item {item_id_str}')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error creating stock adjustment for item {item_id}: {e}')
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
        """Main function to match items and update prices/stock"""
        try:
            logger.info('🚀 Starting Zoho Inventory Price & Stock Matcher')
            logger.info('=' * 60)
            
            # Check environment variables
            if not self.zoho_org_id:
                logger.error('❌ Missing ZOHO_ORG_ID environment variable')
                return
            
            # Get Google Sheets data
            df = self.get_google_sheets_data()
            if df is None:
                return
            
            # Process each item
            updated_count = 0
            price_updated_count = 0
            stock_updated_count = 0
            
            for index, row in df.iterrows():
                try:
                    item_name = str(row.get('Item Name', ''))
                    zoho_id = row.get('Zoho ID')
                    quantity = row.get('Quantity', 0)
                    manufacturer = row.get('Manufacturer', '')
                    barcode = row.get('Barcode', '')
                    
                    if not item_name or pd.isna(zoho_id):
                        continue
                    
                    logger.info(f'🔄 Processing: {item_name} (ID: {zoho_id})')
                    
                    # Search for price
                    current_price = self.search_item_price(item_name, manufacturer=manufacturer, barcode=barcode)
                    
                    if current_price:
                        # Update Zoho Inventory price
                        if self.update_item_price(zoho_id, current_price):
                            price_updated_count += 1
                        
                        # Update Google Sheet with found price
                        self.update_google_sheet_price(index, current_price)
                    
                    # Update stock level
                    if not pd.isna(quantity) and quantity > 0:
                        if self.create_stock_adjustment(zoho_id, int(quantity)):
                            stock_updated_count += 1
                    
                    updated_count += 1
                    
                    # Add delay to avoid rate limiting
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f'❌ Error processing row {index}: {e}')
                    continue
            
            logger.info('=' * 60)
            logger.info(f'✅ Processing complete!')
            logger.info(f'📊 Items processed: {updated_count}')
            logger.info(f'💰 Prices updated: {price_updated_count}')
            logger.info(f'📦 Stock levels updated: {stock_updated_count}')
            
        except Exception as e:
            logger.error(f'❌ Error in main processing: {e}')

def main():
    """Main entry point"""
    logger.info('🚀 Zoho Inventory Price & Stock Matcher')
    logger.info('=' * 60)
    logger.info('📊 Reads Google Sheets')
    logger.info('🔍 Searches web for current prices')
    logger.info('💰 Updates Zoho Inventory prices')
    logger.info('📦 Updates Zoho Inventory stock levels')
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
    matcher = ZohoPriceStockMatcher()
    matcher.match_and_update_items()

if __name__ == '__main__':
    main()