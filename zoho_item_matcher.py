# -*- coding: utf-8 -*-
import os
import requests
import pandas as pd
import logging
from io import StringIO
from rapidfuzz import fuzz
import time

logger = logging.getLogger(__name__)

class ZohoItemMatcher:
    def __init__(self):
        self.zoho_org_id = os.getenv('ZOHO_ORG_ID')
        
        # Initialize token manager
        from zoho_token_manager import ZohoTokenManager
        self.token_manager = ZohoTokenManager()
        
        # Zoho API endpoints
        self.zoho_base_url = 'https://www.zohoapis.com/inventory/v1'
        
        # Cache for Zoho items to avoid repeated API calls
        self.zoho_items_cache = None
        self.cache_timestamp = None

    def get_all_zoho_items(self):
        """Get all items from Zoho Inventory"""
        try:
            # Check if we have a recent cache (less than 5 minutes old)
            if (self.zoho_items_cache and self.cache_timestamp and 
                time.time() - self.cache_timestamp < 300):
                logger.info(f'📋 Using cached Zoho items ({len(self.zoho_items_cache)} items)')
                return self.zoho_items_cache
            
            headers = self.token_manager.get_headers()
            if not headers:
                logger.error('❌ No valid Zoho token available')
                return None

            url = f'{self.zoho_base_url}/items?organization_id={self.zoho_org_id}&per_page=200'
            all_items = []
            page = 1
            
            while True:
                logger.info(f'📋 Fetching Zoho items page {page}...')
                response = requests.get(f'{url}&page={page}', headers=headers)
                response.raise_for_status()
                
                data = response.json()
                items = data.get('items', [])
                
                if not items:
                    break
                    
                all_items.extend(items)
                page += 1
                
                # Add delay to avoid rate limiting
                time.sleep(0.5)
            
            # Cache the results
            self.zoho_items_cache = all_items
            self.cache_timestamp = time.time()
            
            logger.info(f'✅ Successfully fetched {len(all_items)} items from Zoho Inventory')
            return all_items
            
        except Exception as e:
            logger.error(f'❌ Error fetching Zoho items: {e}')
            return None

    def get_google_sheets_data(self):
        """Fetch data from Google Sheets"""
        try:
            url = 'https://docs.google.com/spreadsheets/d/1igH2xZq48pb76bAG25rVBkxb8gODc0SqBHMLwu5hTSc/export?format=csv&gid=1761140701'
            
            logger.info('📊 Fetching data from Google Sheets...')
            response = requests.get(url)
            response.raise_for_status()
            
            df = pd.read_csv(StringIO(response.text))
            logger.info(f'✅ Successfully fetched {len(df)} rows from Google Sheets')
            
            return df
            
        except Exception as e:
            logger.error(f'❌ Error fetching Google Sheets data: {e}')
            return None

    def find_best_zoho_match(self, sheet_item_name, zoho_items):
        """Find the best matching Zoho item for a sheet item name"""
        if not sheet_item_name or not zoho_items:
            return None
        
        best_match = None
        best_score = 0
        
        sheet_name_lower = sheet_item_name.lower().strip()
        
        for zoho_item in zoho_items:
            zoho_name = zoho_item.get('name', '').lower().strip()
            zoho_sku = zoho_item.get('sku', '').lower().strip()
            
            # Calculate similarity scores
            name_score = fuzz.token_sort_ratio(sheet_name_lower, zoho_name) / 100.0
            sku_score = fuzz.token_sort_ratio(sheet_name_lower, zoho_sku) / 100.0 if zoho_sku else 0
            
            # Use the higher score
            score = max(name_score, sku_score)
            
            # Boost score if it's an exact match or very close
            if sheet_name_lower == zoho_name:
                score = 1.0
            elif sheet_name_lower in zoho_name or zoho_name in sheet_name_lower:
                score = max(score, 0.8)
            
            if score > best_score:
                best_score = score
                best_match = zoho_item
        
        # Only return matches above 60% confidence
        if best_match and best_score >= 0.6:
            logger.info(f'🎯 Found match: "{sheet_item_name}" -> "{best_match["name"]}" (score: {best_score:.2f})')
            return best_match, best_score
        
        logger.warning(f'⚠️ No good match found for "{sheet_item_name}" (best score: {best_score:.2f})')
        return None, best_score

    def update_google_sheet_with_zoho_ids(self, df_with_zoho_ids):
        """Update Google Sheet with Zoho IDs"""
        try:
            from google_sheets_updater import GoogleSheetsUpdater
            
            updater = GoogleSheetsUpdater()
            
            # Find the column index for Zoho ID (or create new column)
            zoho_id_col = None
            for i, col in enumerate(df_with_zoho_ids.columns):
                if 'zoho' in col.lower() and 'id' in col.lower():
                    zoho_id_col = i
                    break
            
            if zoho_id_col is None:
                # Add new column for Zoho ID
                df_with_zoho_ids['Zoho ID'] = ''
                zoho_id_col = len(df_with_zoho_ids.columns) - 1
                logger.info(f'📝 Added new "Zoho ID" column at index {zoho_id_col}')
            
            # Update each row with Zoho ID
            updated_count = 0
            for index, row in df_with_zoho_ids.iterrows():
                zoho_id = row.get('zoho_id', '')
                if zoho_id:
                    success = updater.update_cell(index + 2, zoho_id_col + 1, zoho_id)
                    if success:
                        updated_count += 1
                        logger.info(f'✅ Updated row {index + 2} with Zoho ID: {zoho_id}')
                    else:
                        logger.warning(f'⚠️ Failed to update row {index + 2} with Zoho ID: {zoho_id}')
                
                # Add delay to avoid rate limiting
                time.sleep(0.1)
            
            logger.info(f'✅ Updated {updated_count} rows with Zoho IDs')
            return updated_count
            
        except Exception as e:
            logger.error(f'❌ Error updating Google Sheet: {e}')
            return 0

    def match_all_items(self):
        """Match all items from Google Sheet with Zoho Inventory items"""
        try:
            logger.info('🚀 Starting Zoho Item Matching Process')
            logger.info('=' * 60)
            
            # Check environment variables
            if not self.zoho_org_id:
                logger.error('❌ Missing ZOHO_ORG_ID environment variable')
                return None
            
            # Get Google Sheets data
            df = self.get_google_sheets_data()
            if df is None:
                return None
            
            # Get all Zoho items
            zoho_items = self.get_all_zoho_items()
            if not zoho_items:
                return None
            
            # Process each item
            matched_count = 0
            total_items = 0
            
            # Add new columns for matching results
            df['zoho_id'] = ''
            df['zoho_name'] = ''
            df['match_score'] = 0.0
            df['match_status'] = ''
            
            for index, row in df.iterrows():
                try:
                    item_name = str(row.get('Item Name', ''))
                    
                    if not item_name or item_name.lower() in ['nan', 'none', '']:
                        continue
                    
                    total_items += 1
                    logger.info(f'🔄 Matching: {item_name}')
                    
                    # Find best match
                    match_result = self.find_best_zoho_match(item_name, zoho_items)
                    
                    if match_result[0]:  # Found a match
                        zoho_item, score = match_result
                        df.at[index, 'zoho_id'] = zoho_item['item_id']
                        df.at[index, 'zoho_name'] = zoho_item['name']
                        df.at[index, 'match_score'] = score
                        df.at[index, 'match_status'] = 'MATCHED'
                        matched_count += 1
                        
                        logger.info(f'✅ Matched: {item_name} -> {zoho_item["name"]} (ID: {zoho_item["item_id"]})')
                    else:
                        df.at[index, 'match_status'] = 'NO_MATCH'
                        logger.warning(f'⚠️ No match found for: {item_name}')
                    
                    # Add delay to avoid rate limiting
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f'❌ Error processing row {index}: {e}')
                    df.at[index, 'match_status'] = 'ERROR'
                    continue
            
            # Update Google Sheet with Zoho IDs
            updated_count = self.update_google_sheet_with_zoho_ids(df)
            
            # Save results to CSV for review
            output_file = 'zoho_item_matching_results.csv'
            df.to_csv(output_file, index=False)
            
            logger.info('=' * 60)
            logger.info(f'✅ Item matching complete!')
            logger.info(f'📊 Total items processed: {total_items}')
            logger.info(f'🎯 Items matched: {matched_count}')
            logger.info(f'📝 Google Sheet rows updated: {updated_count}')
            logger.info(f'💾 Results saved to: {output_file}')
            
            return df
            
        except Exception as e:
            logger.error(f'❌ Error in item matching process: {e}')
            return None

def main():
    """Test the Zoho item matcher"""
    matcher = ZohoItemMatcher()
    
    # Test with a single item
    zoho_items = matcher.get_all_zoho_items()
    if zoho_items:
        test_result = matcher.find_best_zoho_match("Red Bull Sugarfree", zoho_items)
        if test_result[0]:
            print(f"✅ Test successful: Found match with score {test_result[1]:.2f}")
        else:
            print("❌ Test failed: No match found")
    else:
        print("❌ Test failed: Could not fetch Zoho items")

if __name__ == "__main__":
    main()
