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

class EmergencyStockRestorer:
    def __init__(self):
        self.zoho_org_id = os.getenv('ZOHO_ORG_ID')
        
        # Initialize token manager
        from zoho_token_manager import ZohoTokenManager
        self.token_manager = ZohoTokenManager()
        
        # Zoho API endpoints
        self.zoho_base_url = 'https://www.zohoapis.com/inventory/v1'
        
        # Default warehouse ID
        self.default_warehouse_id = '460000000038080'
        
    def get_item_current_stock(self, item_id, warehouse_id=None):
        """Get current stock level for an item"""
        try:
            headers = self.token_manager.get_headers()
            if not headers:
                logger.error('❌ No valid Zoho token available')
                return 0
                
            url = f'{self.zoho_base_url}/items/{item_id}?organization_id={self.zoho_org_id}'
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            item_data = data.get('item', {})
            
            # Get stock from warehouse data
            warehouses = item_data.get('warehouses', [])
            warehouse_id = warehouse_id or self.default_warehouse_id
            
            for warehouse in warehouses:
                if warehouse.get('warehouse_id') == warehouse_id:
                    current_stock = warehouse.get('available_quantity', 0)
                    return float(current_stock)
            
            return 0
            
        except Exception as e:
            logger.error(f'❌ Error getting current stock for item {item_id}: {e}')
            return 0
    
    def create_stock_adjustment(self, item_id, target_quantity, warehouse_id=None):
        """Create inventory adjustment to set stock levels"""
        try:
            # Get current stock first
            current_stock = self.get_item_current_stock(item_id, warehouse_id)
            
            # Calculate the adjustment needed
            adjustment_needed = target_quantity - current_stock
            
            if abs(adjustment_needed) < 0.01:  # No adjustment needed
                logger.info(f'✅ Stock already correct for item {item_id}: {current_stock}')
                return True
            
            url = f'{self.zoho_base_url}/inventoryadjustments?organization_id={self.zoho_org_id}'
            
            warehouse_id = warehouse_id or self.default_warehouse_id
            
            data = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'reason': f'EMERGENCY RESTORE: Setting to {target_quantity} (was {current_stock})',
                'adjustment_type': 'quantity',
                'location_id': warehouse_id,
                'line_items': [
                    {
                        'item_id': int(item_id),
                        'quantity_adjusted': float(adjustment_needed),
                        'unit': 'pcs'
                    }
                ]
            }
            
            logger.info(f'🔄 RESTORING item {item_id}: {current_stock} -> {target_quantity} (adjustment: {adjustment_needed})')
            
            headers = self.token_manager.get_headers()
            if not headers:
                logger.error('❌ No valid Zoho token available')
                return False
                
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            logger.info(f'✅ RESTORED stock for item {item_id}: {adjustment_needed} units')
            return True
            
        except Exception as e:
            logger.error(f'❌ Error restoring stock for item {item_id}: {e}')
            return False
    
    def restore_all_stock(self):
        """EMERGENCY: Restore all stock from Google Sheets"""
        logger.info('🚨 EMERGENCY STOCK RESTORATION STARTING')
        logger.info('=' * 60)
        logger.info('📊 Reading Google Sheets (THE TRUTH)')
        logger.info('📦 Restoring ALL stock levels')
        logger.info('🏪 Getting Commerce store back online')
        logger.info('=' * 60)
        
        # Check environment variables
        if not self.zoho_token or not self.zoho_org_id:
            logger.error('❌ Missing ZOHO_TOKEN or ZOHO_ORG_ID')
            return
        
        # Fetch Google Sheets data
        try:
            spreadsheet_id = '1igH2xZq48pb76bAG25rVBkxb8gODc0SqBHMLwu5hTSc'
            gid = '1761140701'
            csv_url = f'https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}'
            
            logger.info('📊 Fetching TRUTH from Google Sheets...')
            response = requests.get(csv_url, timeout=30)
            response.raise_for_status()
            
            csv_data = StringIO(response.text)
            df = pd.read_csv(csv_data)
            
            logger.info(f'✅ Successfully fetched {len(df)} rows from Google Sheets')
            
            # Process ALL items
            restored = 0
            skipped = 0
            
            for index, row in df.iterrows():
                item_name = row.get('Item Name', '')
                quantity = row.get('Quantity', 0)
                zoho_id = row.get('Zoho Item ID', '')
                
                if not item_name or not str(item_name).strip():
                    skipped += 1
                    continue
                
                # Convert quantity to float
                try:
                    qty_value = float(quantity) if quantity else 0
                except (ValueError, TypeError):
                    qty_value = 0
                
                # Only process items with Zoho IDs
                if zoho_id and str(zoho_id) != 'nan':
                    logger.info(f'🔄 RESTORING: {item_name} (ID: {zoho_id}) -> {qty_value} units')
                    
                    # Restore stock level
                    if self.create_stock_adjustment(zoho_id, qty_value):
                        restored += 1
                    
                    # Rate limiting
                    time.sleep(0.5)
                else:
                    skipped += 1
            
            logger.info('🎉 EMERGENCY RESTORATION COMPLETED!')
            logger.info(f'✅ Restored: {restored} items')
            logger.info(f'⏭️ Skipped: {skipped} items (no Zoho ID)')
            logger.info('🏪 Your Commerce store should be back online!')
            
        except Exception as e:
            logger.error(f'❌ EMERGENCY RESTORATION FAILED: {e}')

def main():
    restorer = EmergencyStockRestorer()
    restorer.restore_all_stock()

if __name__ == '__main__':
    main()
