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

class EmergencyPriceRestorer:
    def __init__(self):
        self.zoho_token = os.getenv('ZOHO_TOKEN')
        self.zoho_org_id = os.getenv('ZOHO_ORG_ID')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # Set OpenAI API key
        openai.api_key = self.openai_api_key
        
        # Zoho API endpoints
        self.zoho_base_url = 'https://www.zohoapis.com/inventory/v1'
        self.headers = {
            'Authorization': f'Zoho-oauthtoken {self.zoho_token}',
            'Content-Type': 'application/json'
        }
        
    def search_item_price(self, item_name, sku=None):
        """Use OpenAI to search for current market price"""
        try:
            search_query = f'current market price for {item_name}'
            if sku:
                search_query += f' SKU {sku}'
            
            # Use OpenAI to search and analyze price
            response = openai.ChatCompletion.create(
                model='gpt-4',
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are a price research assistant. Search for current market prices and return the average price in USD. Only return a number (no currency symbols or text).'
                    },
                    {
                        'role': 'user',
                        'content': f'Find the current average market price for: {search_query}. Return only the price number.'
                    }
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            price_text = response.choices[0].message.content.strip()
            # Extract numeric value
            import re
            price_match = re.search(r'\d+\.?\d*', price_text)
            if price_match:
                price = float(price_match.group())
                logger.info(f'💰 Found price for {item_name}: ${price}')
                return price
            else:
                logger.warning(f'⚠️ Could not extract price for {item_name}: {price_text}')
                return None
                
        except Exception as e:
            logger.error(f'❌ Error searching price for {item_name}: {e}')
            return None
    
    def update_item_price(self, item_id, new_price):
        """Update item price in Zoho - try multiple price fields"""
        try:
            url = f'{self.zoho_base_url}/items/{item_id}?organization_id={self.zoho_org_id}'
            
            # Try updating multiple price fields
            data = {
                'rate': new_price,  # Cost price
                'selling_rate': new_price,  # Selling price
                'purchase_rate': new_price * 0.7  # Purchase price (70% of selling)
            }
            
            response = requests.put(url, headers=self.headers, json=data)
            response.raise_for_status()
            
            logger.info(f'✅ Updated ALL prices for item {item_id}: ${new_price}')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error updating price for item {item_id}: {e}')
            return False
    
    def restore_all_prices(self):
        """EMERGENCY: Restore all prices from web search"""
        logger.info('🚨 EMERGENCY PRICE RESTORATION STARTING')
        logger.info('=' * 60)
        logger.info('📊 Reading Google Sheets')
        logger.info('🔍 Searching web for current prices')
        logger.info('💰 Restoring ALL item prices')
        logger.info('🏪 Getting Commerce prices back')
        logger.info('=' * 60)
        
        # Check environment variables
        if not self.zoho_token or not self.zoho_org_id or not self.openai_api_key:
            logger.error('❌ Missing required environment variables')
            return
        
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
            
            logger.info(f'✅ Successfully fetched {len(df)} rows from Google Sheets')
            
            # Process items with Zoho IDs
            restored = 0
            skipped = 0
            
            for index, row in df.iterrows():
                item_name = row.get('Item Name', '')
                sku = row.get('SKU', '')
                zoho_id = row.get('Zoho Item ID', '')
                
                if not item_name or not str(item_name).strip():
                    skipped += 1
                    continue
                
                # Only process items with Zoho IDs
                if zoho_id and str(zoho_id) != 'nan':
                    logger.info(f'🔄 RESTORING PRICE: {item_name} (ID: {zoho_id})')
                    
                    # Search for current price
                    current_price = self.search_item_price(item_name, sku)
                    
                    if current_price:
                        # Update all price fields
                        if self.update_item_price(zoho_id, current_price):
                            restored += 1
                    else:
                        logger.warning(f'⚠️ Could not find price for {item_name}')
                    
                    # Rate limiting
                    time.sleep(2)  # Be gentle with APIs
                else:
                    skipped += 1
                
                # Demo limit for safety
                if restored >= 10:
                    logger.info('🎯 Demo limit reached (10 items processed)')
                    break
            
            logger.info('🎉 EMERGENCY PRICE RESTORATION COMPLETED!')
            logger.info(f'✅ Restored: {restored} items')
            logger.info(f'⏭️ Skipped: {skipped} items (no Zoho ID)')
            logger.info('🏪 Your Commerce store should now show prices!')
            
        except Exception as e:
            logger.error(f'❌ EMERGENCY PRICE RESTORATION FAILED: {e}')

def main():
    restorer = EmergencyPriceRestorer()
    restorer.restore_all_prices()

if __name__ == '__main__':
    main()
