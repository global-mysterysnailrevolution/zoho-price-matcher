# -*- coding: utf-8 -*-
import os
import json
import logging
import time
import requests
import pandas as pd
from io import StringIO
from datetime import datetime
import openai

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ZohoPriceStockMatcher:
    def __init__(self):
        self.zoho_org_id = os.getenv('ZOHO_ORG_ID')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # Set OpenAI API key
        openai.api_key = self.openai_api_key
        
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
                return []
                
            url = f'{self.zoho_base_url}/warehouses?organization_id={self.zoho_org_id}'
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f'✅ Found {len(data.get("warehouses", []))} warehouses')
            return data.get('warehouses', [])
        except Exception as e:
            logger.error(f'❌ Error fetching warehouses: {e}')
            return []
    
    def search_item_price(self, item_name, sku=None):
        """Use web scraping to search for current market price"""
        try:
            from web_price_scraper import WebPriceScraper
            
            scraper = WebPriceScraper()
            price = scraper.search_multiple_sources(item_name, sku)
            
            if price:
                logger.info(f'💰 Found real web price for {item_name}: ${price}')
                return price
            else:
                logger.warning(f'⚠️ No web price found for {item_name}')
                return None
                
        except Exception as e:
            logger.error(f'❌ Error searching web price for {item_name}: {e}')
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
    
    def create_stock_adjustment(self, item_id, quantity, warehouse_id=None):
        """Create inventory adjustment to update stock levels"""
        try:
            headers = self.token_manager.get_headers()
            if not headers:
                logger.error('❌ No valid Zoho token available')
                return False
            
            # Convert scientific notation to integer
            if 'e+' in str(item_id):
                item_id_int = int(float(item_id))
            else:
                item_id_int = int(item_id)
                
            url = f'{self.zoho_base_url}/inventoryadjustments?organization_id={self.zoho_org_id}'
            
            warehouse_id = warehouse_id or self.default_warehouse_id
            
            data = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'reason': 'Stock Reconciliation from Google Sheets',
                'adjustment_type': 'quantity',
                'location_id': warehouse_id,
                'line_items': [
                    {
                        'item_id': item_id_int,
                        'quantity_adjusted': float(quantity),
                        'unit': 'pcs'
                    }
                ]
            }
            
            logger.info(f'🔄 Creating stock adjustment for item {item_id_int}: {quantity} units')
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            logger.info(f'✅ Created stock adjustment for item {item_id_int}: {quantity} units')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error creating stock adjustment for item {item_id}: {e}')
            return False
    
    def process_item(self, row):
        """Process a single item from Google Sheets"""
        item_name = row.get('Item Name', '')
        sku = row.get('SKU', '')
        quantity = row.get('Quantity', 0)
        zoho_id = row.get('Zoho Item ID', '')
        
        if not item_name or not str(item_name).strip():
            return False
        
        logger.info(f'🔄 Processing: {item_name} (SKU: {sku})')
        
        # Convert quantity to float
        try:
            qty_value = float(quantity) if quantity else 0
        except (ValueError, TypeError):
            qty_value = 0
        
        # Search for current price
        current_price = self.search_item_price(item_name, sku)
        
        if zoho_id and str(zoho_id) != 'nan':
            # Item has Zoho ID - update both price and stock
            logger.info(f'📋 Updating existing item: {item_name} (ID: {zoho_id})')
            
            # Update price
            if current_price:
                self.update_item_price(zoho_id, current_price)
            
            # Update stock level
            if qty_value > 0:
                self.create_stock_adjustment(zoho_id, qty_value)
            
            logger.info(f'✅ Completed: {item_name} - Price: ${current_price}, Stock: {qty_value}')
            
        else:
            # Item doesn't have Zoho ID - need to find/create it
            logger.info(f'🔍 Item without Zoho ID: {item_name}')
            logger.info(f'💡 Would search Zoho for matching item and create if needed')
            logger.info(f'💰 Price: ${current_price}, Stock: {qty_value}')
        
        return True
    
    def run(self):
        """Main execution function"""
        logger.info('🚀 Zoho Inventory Price & Stock Matcher')
        logger.info('=' * 60)
        logger.info('📊 Reads Google Sheets')
        logger.info('🔍 Searches web for current prices')
        logger.info('💰 Updates Zoho Inventory prices')
        logger.info('📦 Updates Zoho Inventory stock levels')
        logger.info('=' * 60)
        
        # Check environment variables
        required_vars = ['OPENAI_API_KEY', 'ZOHO_ORG_ID', 'ZOHO_REFRESH_TOKEN', 'ZOHO_CLIENT_ID', 'ZOHO_CLIENT_SECRET']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.error(f'❌ Missing environment variables: {missing_vars}')
            return
        
        logger.info('✅ All environment variables are set!')
        
        # Get warehouses
        warehouses = self.get_warehouses()
        if warehouses:
            logger.info(f'🏢 Available warehouses: {[w.get("warehouse_name") for w in warehouses]}')
        
        # Fetch Google Sheets data
        try:
            spreadsheet_id = '1igH2xZq48pb76bAG25rVBkxb8gODc0SqBHMLwu5hTSc'
            gid = '1761140701'
            csv_url = f'https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}'
            
            logger.info('📊 Fetching data from Google Sheets...')
            response = requests.get(csv_url, timeout=30)
            response.raise_for_status()
            
            csv_data = StringIO(response.text)
            df = pd.read_csv(csv_data)
            
            logger.info(f'✅ Successfully fetched {len(df)} rows and {len(df.columns)} columns')
            
            # Process items
            processed = 0
            for index, row in df.iterrows():
                if self.process_item(row):
                    processed += 1
                
                # Rate limiting
                time.sleep(1)
                
                # Demo limit
                if processed >= 5:
                    logger.info('🎯 Demo limit reached (5 items processed)')
                    break
            
            logger.info(f'🎉 Processing completed: {processed} items processed')
            
        except Exception as e:
            logger.error(f'❌ Error: {e}')

def main():
    # Run emergency price restoration first
    logger.info('🚨 RUNNING EMERGENCY PRICE RESTORATION')
    from emergency_price_restore import EmergencyPriceRestorer
    price_restorer = EmergencyPriceRestorer()
    price_restorer.restore_all_prices()
    
    # Then run the main matcher
    logger.info('🚀 RUNNING MAIN PRICE & STOCK MATCHER')
    matcher = ZohoPriceStockMatcher()
    matcher.run()

if __name__ == '__main__':
    main()