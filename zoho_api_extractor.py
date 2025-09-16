#!/usr/bin/env python3
"""
Zoho Inventory API Documentation Extractor
This script navigates through the Zoho Inventory API documentation and extracts
all relevant information for our price matching application.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from urllib.parse import urljoin, urlparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ZohoAPIExtractor:
    def __init__(self):
        self.base_url = "https://www.zoho.com/inventory/api/v1/introduction/"
        self.visited_urls = set()
        self.api_data = {
            'endpoints': {},
            'authentication': {},
            'rate_limits': {},
            'data_structures': {},
            'items_api': {},
            'organizations_api': {}
        }
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def extract_page_content(self, url):
        """Extract content from a single page"""
        try:
            logger.info(f"Extracting content from: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract main content
            content = {
                'url': url,
                'title': soup.find('title').text if soup.find('title') else '',
                'content': soup.get_text(),
                'links': []
            }
            
            # Extract all internal links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.startswith('/') or 'zoho.com/inventory/api' in href:
                    full_url = urljoin(url, href)
                    if full_url not in self.visited_urls:
                        content['links'].append(full_url)
            
            return content
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            return None

    def extract_api_endpoints(self, content):
        """Extract API endpoints and their details from content"""
        if not content:
            return
            
        text = content['content']
        url = content['url']
        
        # Look for API endpoint patterns
        endpoint_patterns = [
            r'`([A-Z]+)\s+([^`]+)`',  # HTTP methods and endpoints
            r'https://[^/\s]+/inventory/v\d+/([^\s`]+)',  # Full URLs
            r'/([a-z-]+/[a-z-]+)',  # Endpoint paths
        ]
        
        for pattern in endpoint_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    method, endpoint = match
                    self.api_data['endpoints'][endpoint] = {
                        'method': method,
                        'url': url,
                        'description': self.extract_description_around_match(text, match)
                    }
                else:
                    self.api_data['endpoints'][match] = {
                        'url': url,
                        'description': self.extract_description_around_match(text, match)
                    }

    def extract_description_around_match(self, text, match):
        """Extract description text around a matched pattern"""
        try:
            if isinstance(match, tuple):
                search_text = match[1]
            else:
                search_text = match
                
            index = text.find(search_text)
            if index != -1:
                start = max(0, index - 200)
                end = min(len(text), index + 200)
                return text[start:end].strip()
        except:
            pass
        return ""

    def extract_items_api_info(self, content):
        """Extract specific information about Items API"""
        if not content or 'items' not in content['url'].lower():
            return
            
        text = content['content']
        
        # Look for item-related information
        item_patterns = [
            r'item_id',
            r'item_name',
            r'rate',
            r'price',
            r'sku',
            r'description',
            r'unit',
            r'quantity'
        ]
        
        for pattern in item_patterns:
            if pattern in text.lower():
                self.api_data['items_api'][pattern] = self.extract_description_around_match(text, pattern)

    def crawl_documentation(self):
        """Main method to crawl through all documentation"""
        logger.info("Starting Zoho API documentation crawl...")
        
        # Start with the main page
        queue = [self.base_url]
        
        while queue:
            current_url = queue.pop(0)
            
            if current_url in self.visited_urls:
                continue
                
            self.visited_urls.add(current_url)
            
            # Extract content
            content = self.extract_page_content(current_url)
            if content:
                # Extract API information
                self.extract_api_endpoints(content)
                self.extract_items_api_info(content)
                
                # Add new links to queue
                for link in content['links']:
                    if link not in self.visited_urls and 'zoho.com/inventory/api' in link:
                        queue.append(link)
            
            # Be respectful with requests
            time.sleep(1)
            
            # Limit the crawl to prevent infinite loops
            if len(self.visited_urls) > 50:
                logger.info("Reached crawl limit, stopping...")
                break

    def save_extracted_data(self, filename='zoho_api_data.json'):
        """Save extracted data to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.api_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved extracted data to {filename}")
        except Exception as e:
            logger.error(f"Error saving data: {str(e)}")

    def generate_api_reference(self):
        """Generate a comprehensive API reference"""
        reference = {
            'base_url': 'https://www.zohoapis.com/inventory/v1',
            'authentication': 'OAuth 2.0',
            'rate_limits': {
                'requests_per_minute': 100,
                'concurrent_requests': 10,
                'daily_limits': {
                    'free': 1000,
                    'standard': 2000,
                    'professional': 5000,
                    'premium': 10000,
                    'enterprise': 10000
                }
            },
            'key_endpoints': {
                'organizations': '/organizations',
                'items': '/items',
                'contacts': '/contacts',
                'sales_orders': '/salesorders',
                'invoices': '/invoices'
            }
        }
        
        return reference

def main():
    """Main execution function"""
    extractor = ZohoAPIExtractor()
    
    # Crawl the documentation
    extractor.crawl_documentation()
    
    # Save extracted data
    extractor.save_extracted_data()
    
    # Generate API reference
    reference = extractor.generate_api_reference()
    
    print("=== ZOHO INVENTORY API REFERENCE ===")
    print(json.dumps(reference, indent=2))
    
    print(f"\nTotal pages crawled: {len(extractor.visited_urls)}")
    print(f"Total endpoints found: {len(extractor.api_data['endpoints'])}")

if __name__ == "__main__":
    main()
