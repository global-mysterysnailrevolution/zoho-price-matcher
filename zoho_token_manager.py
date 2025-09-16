# -*- coding: utf-8 -*-
import os
import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ZohoTokenManager:
    def __init__(self):
        self.client_id = os.getenv('ZOHO_CLIENT_ID')
        self.client_secret = os.getenv('ZOHO_CLIENT_SECRET')
        self.refresh_token = os.getenv('ZOHO_REFRESH_TOKEN')
        self.access_token = os.getenv('ZOHO_TOKEN')
        self.token_expires_at = None
        
        # If we have a refresh token, try to get a fresh access token
        if self.refresh_token and not self.access_token:
            self.refresh_access_token()
    
    def refresh_access_token(self):
        """Refresh the access token using the refresh token"""
        try:
            url = 'https://accounts.zoho.com/oauth/v2/token'
            
            data = {
                'refresh_token': self.refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'refresh_token'
            }
            
            logger.info('🔄 Refreshing Zoho access token...')
            response = requests.post(url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get('access_token')
            
            # Calculate expiration time (usually 1 hour)
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            logger.info('✅ Successfully refreshed Zoho access token')
            logger.info(f'⏰ Token expires at: {self.token_expires_at}')
            
            return True
            
        except Exception as e:
            logger.error(f'❌ Failed to refresh access token: {e}')
            return False
    
    def get_valid_token(self):
        """Get a valid access token, refreshing if necessary"""
        # Check if token is expired or about to expire (5 minute buffer)
        if (self.token_expires_at and 
            datetime.now() + timedelta(minutes=5) >= self.token_expires_at):
            logger.info('🔄 Access token expired, refreshing...')
            if not self.refresh_access_token():
                return None
        
        return self.access_token
    
    def get_headers(self):
        """Get headers with valid access token"""
        token = self.get_valid_token()
        if not token:
            logger.error('❌ No valid access token available')
            return None
        
        return {
            'Authorization': f'Zoho-oauthtoken {token}',
            'Content-Type': 'application/json'
        }

def main():
    """Test the token manager"""
    manager = ZohoTokenManager()
    
    if manager.get_valid_token():
        print("✅ Token manager working!")
        headers = manager.get_headers()
        if headers:
            print("✅ Headers ready for API calls!")
        else:
            print("❌ Failed to get headers")
    else:
        print("❌ Token manager failed")

if __name__ == '__main__':
    main()
