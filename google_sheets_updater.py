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
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GoogleSheetsUpdater:
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        openai.api_key = self.openai_api_key
        
        # Google Sheets API scopes
        self.SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        self.SPREADSHEET_ID = '1igH2xZq48pb76bAG25rVBkxb8gODc0SqBHMLwu5hTSc'
        self.GID = '1761140701'
        
    def get_google_sheets_service(self):
        """Get authenticated Google Sheets service"""
        creds = None
        token_file = 'token_sheets.pickle'

        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("✅ Refreshed Google Sheets credentials")
                except Exception as e:
                    logger.error(f"❌ Failed to refresh credentials: {e}")
                    creds = None
            if not creds:
                if os.path.exists('credentials.json'):
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', self.SCOPES)
                    creds = flow.run_local_server(port=0)
                    logger.info("✅ Got new Google Sheets credentials")
                    with open(token_file, 'wb') as token:
                        pickle.dump(creds, token)
                else:
                    logger.error("❌ credentials.json not found. Cannot authenticate with Google Sheets.")
                    return None
        return build('sheets', 'v4', credentials=creds)
    
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
    
    def update_google_sheet_prices(self):
        """Update Google Sheet with online prices in column H"""
        logger.info('🚀 Google Sheets Price Updater')
        logger.info('=' * 60)
        logger.info('📊 Reading Google Sheets')
        logger.info('🔍 Searching web for current prices')
        logger.info('📝 Updating Column H with online prices')
        logger.info('=' * 60)
        
        # Get Google Sheets service
        sheets_service = self.get_google_sheets_service()
        if not sheets_service:
            logger.error("❌ Failed to initialize Google Sheets service")
            return
        
        # Read current data
        try:
            csv_url = f'https://docs.google.com/spreadsheets/d/{self.SPREADSHEET_ID}/export?format=csv&gid={self.GID}'
            logger.info('📊 Fetching data from Google Sheets...')
            response = requests.get(csv_url, timeout=30)
            response.raise_for_status()
            
            csv_data = StringIO(response.text)
            df = pd.read_csv(csv_data)
            
            logger.info(f'✅ Successfully fetched {len(df)} rows and {len(df.columns)} columns')
            logger.info(f'📋 Columns: {list(df.columns)}')
            
            # Process items and update prices
            updated_count = 0
            
            for index, row in df.iterrows():
                item_name = row.get('Item Name', '')
                sku = row.get('SKU', '')
                
                if not item_name or not str(item_name).strip():
                    continue
                
                logger.info(f'🔄 Processing: {item_name} (SKU: {sku})')
                
                # Search for current price
                current_price = self.search_item_price(item_name, sku)
                
                if current_price:
                    # Update column H (index 7) with the price
                    row_index = index + 2  # +2 because Google Sheets is 1-indexed and has header
                    
                    # Update the specific cell
                    range_name = f'Sheet1!H{row_index}'
                    body = {
                        'values': [[current_price]]
                    }
                    
                    result = sheets_service.spreadsheets().values().update(
                        spreadsheetId=self.SPREADSHEET_ID,
                        range=range_name,
                        valueInputOption='RAW',
                        body=body
                    ).execute()
                    
                    logger.info(f'✅ Updated Column H row {row_index} with price: ${current_price}')
                    updated_count += 1
                else:
                    logger.warning(f'⚠️ Could not find price for {item_name}')
                
                # Rate limiting
                time.sleep(2)
                
                # Demo limit
                if updated_count >= 10:
                    logger.info('🎯 Demo limit reached (10 items updated)')
                    break
            
            logger.info(f'🎉 Google Sheets update completed!')
            logger.info(f'✅ Updated: {updated_count} items with online prices')
            logger.info('📝 Check Column H in your Google Sheet!')
            
        except Exception as e:
            logger.error(f'❌ Error updating Google Sheets: {e}')

def main():
    updater = GoogleSheetsUpdater()
    updater.update_google_sheet_prices()

if __name__ == '__main__':
    main()
