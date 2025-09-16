# -*- coding: utf-8 -*-
import os
import requests
import logging
from bs4 import BeautifulSoup
import re
import time
import random
import json
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

class WebPriceScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
            'DNT': '1'
        })
        
        # Scientific equipment manufacturers and their affiliates
        self.manufacturers = {
            'thermo_fisher': {
                'name': 'Thermo Fisher Scientific',
                'sites': [
                    'https://www.thermofisher.com',
                    'https://www.fishersci.com',
                    'https://www.invitrogen.com',
                    'https://www.appliedbiosystems.com'
                ],
                'search_paths': ['/search', '/catalog', '/products'],
                'brands': ['Thermo Fisher', 'Fisher Scientific', 'Invitrogen', 'Applied Biosystems', 'Life Technologies']
            },
            'corning': {
                'name': 'Corning',
                'sites': [
                    'https://www.corning.com',
                    'https://www.corning.com/lifesciences',
                    'https://www.falcon.com'
                ],
                'search_paths': ['/search', '/products', '/catalog'],
                'brands': ['Corning', 'Falcon', 'Costar']
            },
            'vwr': {
                'name': 'VWR International',
                'sites': [
                    'https://us.vwr.com',
                    'https://www.vwr.com'
                ],
                'search_paths': ['/search', '/catalog', '/products'],
                'brands': ['VWR', 'VWR International']
            },
            'bd': {
                'name': 'BD Biosciences',
                'sites': [
                    'https://www.bdbiosciences.com',
                    'https://www.bd.com'
                ],
                'search_paths': ['/search', '/products', '/catalog'],
                'brands': ['BD', 'Becton Dickinson', 'Falcon']
            },
            'millipore': {
                'name': 'MilliporeSigma',
                'sites': [
                    'https://www.sigmaaldrich.com',
                    'https://www.emdmillipore.com'
                ],
                'search_paths': ['/search', '/catalog', '/products'],
                'brands': ['Sigma-Aldrich', 'Millipore', 'EMD Millipore']
            }
        }

    def extract_price_from_text(self, text):
        """Extract price from text"""
        if not text:
            return None
        
        # Remove common currency symbols and extract numbers
        price_patterns = [
            r'\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $1,234.56
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*USD',  # 1,234.56 USD
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*\$',  # 1,234.56 $
            r'(\d+\.\d{2})',  # 123.45
            r'(\d+)'  # 123
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text.replace(',', ''))
            if match:
                try:
                    price = float(match.group(1))
                    if 0.01 <= price <= 50000:  # Scientific equipment price range
                        return price
                except ValueError:
                    continue
        return None

    def detect_brand_and_manufacturer(self, item_name):
        """Detect brand and manufacturer from item name"""
        item_lower = item_name.lower()
        
        for manufacturer_id, manufacturer_info in self.manufacturers.items():
            for brand in manufacturer_info['brands']:
                if brand.lower() in item_lower:
                    logger.info(f"🏷️ Detected brand: {brand} -> Manufacturer: {manufacturer_info['name']}")
                    return manufacturer_id, manufacturer_info, brand
        
        logger.info(f"❓ No specific brand detected for: {item_name}")
        return None, None, None

    def search_manufacturer_site(self, manufacturer_info, item_name, barcode=None):
        """Search manufacturer's website for item"""
        prices = []
        
        for site in manufacturer_info['sites']:
            try:
                logger.info(f"🔍 Searching {manufacturer_info['name']} site: {site}")
                
                # Try different search approaches
                search_queries = [item_name]
                if barcode:
                    search_queries.append(barcode)
                    search_queries.append(f"UPC {barcode}")
                
                for search_query in search_queries:
                    for search_path in manufacturer_info['search_paths']:
                        try:
                            # Construct search URL
                            search_url = urljoin(site, search_path)
                            params = {'q': search_query, 'search': search_query}
                            
                            # Add random delay
                            time.sleep(random.uniform(1, 3))
                            
                            response = self.session.get(search_url, params=params, timeout=15)
                            
                            if response.status_code == 200:
                                soup = BeautifulSoup(response.content, 'html.parser')
                                site_prices = self.extract_prices_from_page(soup, site)
                                prices.extend(site_prices)
                                
                                if site_prices:
                                    logger.info(f"💰 Found {len(site_prices)} prices on {site}")
                                    
                        except Exception as e:
                            logger.warning(f"⚠️ Error searching {site}{search_path}: {e}")
                            continue
                            
            except Exception as e:
                logger.error(f"❌ Error accessing {site}: {e}")
                continue
        
        return prices

    def extract_prices_from_page(self, soup, site_url):
        """Extract prices from a manufacturer's page"""
        prices = []
        
        # Common price selectors for manufacturer sites
        price_selectors = [
            '.price', '.cost', '.amount', '.value',
            '.product-price', '.item-price', '.list-price',
            '.sale-price', '.retail-price', '.wholesale-price',
            '[data-price]', '[data-cost]', '[data-amount]',
            '.price-current', '.price-now', '.price-display',
            '.pricing', '.cost-display', '.amount-display'
        ]
        
        for selector in price_selectors:
            elements = soup.select(selector)
            for element in elements:
                price_text = element.get_text(strip=True)
                price = self.extract_price_from_text(price_text)
                if price:
                    prices.append(price)
                    logger.info(f"💵 Found price: ${price} on {site_url}")
        
        # Also look for price in data attributes
        for element in soup.find_all(attrs={'data-price': True}):
            try:
                price = float(element['data-price'])
                if 0.01 <= price <= 50000:
                    prices.append(price)
                    logger.info(f"💵 Found data-price: ${price} on {site_url}")
            except (ValueError, KeyError):
                continue
        
        return prices

    def search_google_shopping(self, item_name, barcode=None):
        """Search Google Shopping for item prices"""
        try:
            # Construct search query
            search_terms = [item_name]
            if barcode:
                search_terms.append(f"UPC {barcode}")
                search_terms.append(f"barcode {barcode}")
            
            search_query = " ".join(search_terms)
            url = f"https://www.google.com/search?q={search_query}&tbm=shop"

            logger.info(f"🛒 Searching Google Shopping for: {search_query}")
            
            # Add random delay
            time.sleep(random.uniform(1, 2))
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for Google Shopping price elements
            price_selectors = [
                '.a8Pemb',  # Google Shopping price
                '.g9WBQb',  # Alternative price selector
                '[data-attrid="price"]',  # Price attribute
                '.price',  # Generic price class
                '.cost',  # Generic cost class
            ]

            prices = []
            for selector in price_selectors:
                price_elements = soup.select(selector)
                for element in price_elements:
                    price_text = element.get_text(strip=True)
                    price = self.extract_price_from_text(price_text)
                    if price:
                        prices.append(price)
                        logger.info(f'🛒 Found Google Shopping price: ${price}')

            if prices:
                avg_price = sum(prices) / len(prices)
                logger.info(f"💰 Found {len(prices)} Google Shopping prices, average: ${avg_price:.2f}")
                return avg_price
            else:
                logger.warning(f"⚠️ No Google Shopping prices found")
                return None

        except Exception as e:
            logger.error(f"❌ Error searching Google Shopping: {e}")
            return None

    def search_by_barcode(self, barcode):
        """Search for item prices using barcode/UPC"""
        try:
            if not barcode:
                return None
                
            logger.info(f"🔍 Searching by barcode: {barcode}")
            
            # Search Google Shopping with barcode
            search_query = f"UPC {barcode}"
            url = f"https://www.google.com/search?tbm=shop&q={search_query}"
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for Google Shopping price elements
            price_selectors = [
                '.a8Pemb',  # Google Shopping price
                '.g9WBQb',  # Google Shopping price alternative
                '.a8Pemb .a8Pemb',  # Nested price
                '.g9WBQb .g9WBQb',  # Nested price alternative
                '[data-attrid="price"]',  # Price attribute
                '.price',  # Generic price class
                '.cost',  # Generic cost class
            ]
            
            prices = []
            for selector in price_selectors:
                price_elements = soup.select(selector)
                for element in price_elements:
                    price_text = element.get_text(strip=True)
                    price = self.extract_price_from_text(price_text)
                    if price and 0.01 <= price <= 50000:  # Scientific equipment price range
                        prices.append(price)
                        logger.info(f'🔍 Found barcode-based price: ${price}')
            
            if prices:
                avg_price = sum(prices) / len(prices)
                logger.info(f"💰 Found {len(prices)} barcode-based prices, average: ${avg_price:.2f}")
                return round(avg_price, 2)
            else:
                logger.warning(f"⚠️ No barcode-based prices found")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error searching by barcode {barcode}: {e}")
            return None

    def search_similar_items(self, item_name):
        """Search for similar items to get price estimates"""
        try:
            logger.info(f"🔍 Searching for similar items to: {item_name}")
            
            # Extract key terms from item name
            key_terms = re.findall(r'\b\w+\b', item_name.lower())
            # Remove common words
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            key_terms = [term for term in key_terms if term not in stop_words and len(term) > 2]
            
            if len(key_terms) >= 2:
                # Search with reduced terms
                similar_query = " ".join(key_terms[:3])  # Use top 3 terms
                logger.info(f"🔍 Searching similar items with: {similar_query}")
                
                return self.search_google_shopping(similar_query)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error searching similar items: {e}")
            return None

    def search_multiple_sources(self, item_name, barcode=None):
        """Search multiple sources for item prices"""
        try:
            logger.info(f"🔍 Starting comprehensive price search for: {item_name}")
            if barcode:
                logger.info(f"🏷️ Using barcode: {barcode}")
            
            prices = []
            
            # 1. Detect brand and search manufacturer sites first
            manufacturer_id, manufacturer_info, brand = self.detect_brand_and_manufacturer(item_name)
            
            if manufacturer_info:
                logger.info(f"🏭 Searching manufacturer sites for {brand}")
                manufacturer_prices = self.search_manufacturer_site(manufacturer_info, item_name, barcode)
                prices.extend(manufacturer_prices)
            
            # 2. Search by barcode if available
            if barcode:
                logger.info(f"🔍 Searching by barcode: {barcode}")
                barcode_price = self.search_by_barcode(barcode)
                if barcode_price:
                    prices.append(barcode_price)
            
            # 3. Search Google Shopping
            logger.info(f"🛒 Searching Google Shopping")
            google_price = self.search_google_shopping(item_name, barcode)
            if google_price:
                prices.append(google_price)
            
            # 4. If still no prices, try similar items
            if not prices:
                logger.info(f"🔍 No direct prices found, searching similar items")
                similar_price = self.search_similar_items(item_name)
                if similar_price:
                    prices.append(similar_price)
            
            # Calculate final price
            if prices:
                # Remove outliers (prices that are too different from median)
                if len(prices) > 2:
                    prices.sort()
                    median = prices[len(prices)//2]
                    # Keep prices within 50% of median
                    filtered_prices = [p for p in prices if 0.5 * median <= p <= 1.5 * median]
                    if filtered_prices:
                        prices = filtered_prices
                
                avg_price = sum(prices) / len(prices)
                logger.info(f"💰 Final result: {len(prices)} prices found, average: ${avg_price:.2f}")
                return round(avg_price, 2)
            else:
                logger.warning(f"⚠️ No prices found for {item_name}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error searching multiple sources for {item_name}: {e}")
            return None

def main():
    """Test the web price scraper"""
    scraper = WebPriceScraper()
    
    test_items = [
        ("Corning 175 cm² Flask Angled Neck Nonpyrogenic Polystyrene", "123456789012"),
        ("Thermo Fisher Scientific Pipette Tips", "987654321098"),
        ("VWR Reagent Reservoir 50 mL", None),
        ("BD 30mL Syringe Luer-Lok Tip", "555666777888"),
        ("Falcon IVF 4-well Dish", None)
    ]
    
    for item_name, barcode in test_items:
        print(f"\n🔍 Testing: {item_name}")
        if barcode:
            print(f"🏷️ Barcode: {barcode}")
        
        price = scraper.search_multiple_sources(item_name, barcode)
        if price:
            print(f"✅ Price found: ${price:.2f}")
        else:
            print(f"❌ No price found")

if __name__ == '__main__':
    main()