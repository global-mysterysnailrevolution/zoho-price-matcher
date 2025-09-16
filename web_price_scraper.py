# -*- coding: utf-8 -*-
import os
import requests
import logging
from bs4 import BeautifulSoup
import re
import time
import random

logger = logging.getLogger(__name__)

class WebPriceScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def search_google_shopping(self, item_name):
        """Search Google Shopping for item prices"""
        try:
            # Search Google Shopping
            search_query = f"{item_name} price buy online"
            url = f"https://www.google.com/search?q={search_query}&tbm=shop"
            
            logger.info(f"🔍 Searching Google Shopping for: {item_name}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for price elements
            prices = []
            
            # Try different price selectors
            price_selectors = [
                '.a8Pemb',  # Google Shopping price
                '.g9WBQb',  # Alternative price selector
                '[data-ved]',  # Generic price elements
                '.price',  # Generic price class
            ]
            
            for selector in price_selectors:
                price_elements = soup.select(selector)
                for element in price_elements:
                    text = element.get_text().strip()
                    # Extract price numbers
                    price_match = re.search(r'\$?(\d+\.?\d*)', text)
                    if price_match:
                        try:
                            price = float(price_match.group(1))
                            if 0.01 <= price <= 10000:  # Reasonable price range
                                prices.append(price)
                        except ValueError:
                            continue
            
            if prices:
                avg_price = sum(prices) / len(prices)
                logger.info(f"💰 Found {len(prices)} prices for {item_name}, average: ${avg_price:.2f}")
                return avg_price
            else:
                logger.warning(f"⚠️ No prices found for {item_name}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error searching Google Shopping for {item_name}: {e}")
            return None
    
    def search_amazon(self, item_name):
        """Search Amazon for item prices with better anti-detection"""
        try:
            # Search Amazon
            search_query = item_name.replace(' ', '+')
            url = f"https://www.amazon.com/s?k={search_query}"
            
            # Better headers to avoid detection
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
                'DNT': '1'
            }
            
            logger.info(f"🛒 Searching Amazon for: {item_name}")
            
            # Add random delay to avoid rate limiting
            time.sleep(random.uniform(2, 4))
            
            response = self.session.get(url, headers=headers, timeout=15)
            
            # Check if we got blocked
            if response.status_code == 503:
                logger.warning(f"⚠️ Amazon blocked request for {item_name} (503) - skipping")
                return None
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for Amazon price elements
            prices = []
            price_selectors = [
                '.a-price-whole',  # Amazon price whole part
                '.a-offscreen',  # Amazon price offscreen
                '.a-price .a-offscreen',  # Nested price
                '.a-price-range .a-price-whole',  # Price range
                '.s-price-instructions-style .a-price-whole',  # Alternative selector
            ]
            
            for selector in price_selectors:
                price_elements = soup.select(selector)
                for element in price_elements:
                    text = element.get_text().strip()
                    # Extract price numbers
                    price_match = re.search(r'(\d+\.?\d*)', text)
                    if price_match:
                        try:
                            price = float(price_match.group(1))
                            if 0.01 <= price <= 10000:  # Reasonable price range
                                prices.append(price)
                                logger.info(f'🛒 Found Amazon price: ${price}')
                        except ValueError:
                            continue
            
            if prices:
                avg_price = sum(prices) / len(prices)
                logger.info(f"💰 Found {len(prices)} Amazon prices for {item_name}, average: ${avg_price:.2f}")
                return avg_price
            else:
                logger.warning(f"⚠️ No Amazon prices found for {item_name}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error searching Amazon for {item_name}: {e}")
            return None
    
    def search_thermo_fisher(self, item_name):
        """Search Thermo Fisher Scientific for lab equipment prices"""
        try:
            # Thermo Fisher search
            search_query = item_name.replace(' ', '%20')
            url = f"https://www.thermofisher.com/search/results?query={search_query}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            logger.info(f"🔬 Searching Thermo Fisher for: {item_name}")
            time.sleep(random.uniform(2, 3))
            
            response = self.session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            prices = []
            
            # Look for Thermo Fisher price elements
            price_selectors = [
                '.price',
                '.product-price',
                '.price-value',
                '[data-price]',
                '.price-current'
            ]
            
            for selector in price_selectors:
                price_elements = soup.select(selector)
                for element in price_elements:
                    text = element.get_text().strip()
                    price_match = re.search(r'\$(\d+\.?\d*)', text)
                    if price_match:
                        try:
                            price = float(price_match.group(1))
                            if 1 <= price <= 50000:  # Lab equipment can be expensive
                                prices.append(price)
                                logger.info(f'🔬 Found Thermo Fisher price: ${price}')
                        except ValueError:
                            continue
            
            if prices:
                avg_price = sum(prices) / len(prices)
                logger.info(f"💰 Found {len(prices)} Thermo Fisher prices for {item_name}, average: ${avg_price:.2f}")
                return avg_price
            else:
                logger.warning(f"⚠️ No Thermo Fisher prices found for {item_name}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error searching Thermo Fisher for {item_name}: {e}")
            return None

    def search_vwr(self, item_name):
        """Search VWR for lab equipment prices"""
        try:
            # VWR search
            search_query = item_name.replace(' ', '+')
            url = f"https://us.vwr.com/store/search?query={search_query}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            logger.info(f"🧪 Searching VWR for: {item_name}")
            time.sleep(random.uniform(2, 3))
            
            response = self.session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            prices = []
            
            # Look for VWR price elements
            price_selectors = [
                '.price',
                '.product-price',
                '.price-value',
                '[data-price]',
                '.price-current',
                '.price-now'
            ]
            
            for selector in price_selectors:
                price_elements = soup.select(selector)
                for element in price_elements:
                    text = element.get_text().strip()
                    price_match = re.search(r'\$(\d+\.?\d*)', text)
                    if price_match:
                        try:
                            price = float(price_match.group(1))
                            if 1 <= price <= 50000:  # Lab equipment can be expensive
                                prices.append(price)
                                logger.info(f'🧪 Found VWR price: ${price}')
                        except ValueError:
                            continue
            
            if prices:
                avg_price = sum(prices) / len(prices)
                logger.info(f"💰 Found {len(prices)} VWR prices for {item_name}, average: ${avg_price:.2f}")
                return avg_price
            else:
                logger.warning(f"⚠️ No VWR prices found for {item_name}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error searching VWR for {item_name}: {e}")
            return None

    def search_corning(self, item_name):
        """Search Corning for lab equipment prices"""
        try:
            # Corning search - they have specific product pages
            search_query = item_name.replace(' ', '+')
            url = f"https://www.corning.com/worldwide/en/products/life-sciences/products.html?search={search_query}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            logger.info(f"🔬 Searching Corning for: {item_name}")
            time.sleep(random.uniform(2, 3))
            
            response = self.session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            prices = []
            
            # Look for Corning price elements
            price_selectors = [
                '.price',
                '.product-price',
                '.price-value',
                '[data-price]',
                '.price-current'
            ]
            
            for selector in price_selectors:
                price_elements = soup.select(selector)
                for element in price_elements:
                    text = element.get_text().strip()
                    price_match = re.search(r'\$(\d+\.?\d*)', text)
                    if price_match:
                        try:
                            price = float(price_match.group(1))
                            if 1 <= price <= 50000:  # Lab equipment can be expensive
                                prices.append(price)
                                logger.info(f'🔬 Found Corning price: ${price}')
                        except ValueError:
                            continue
            
            if prices:
                avg_price = sum(prices) / len(prices)
                logger.info(f"💰 Found {len(prices)} Corning prices for {item_name}, average: ${avg_price:.2f}")
                return avg_price
            else:
                logger.warning(f"⚠️ No Corning prices found for {item_name}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error searching Corning for {item_name}: {e}")
            return None

    def detect_brand_and_search(self, item_name):
        """Detect brand from item name and search appropriate supplier"""
        try:
            item_lower = item_name.lower()
            
            # Brand detection and specific searches
            if 'corning' in item_lower:
                logger.info(f"🏷️ Detected Corning brand in: {item_name}")
                return self.search_corning(item_name)
            elif 'thermo' in item_lower or 'fisher' in item_lower:
                logger.info(f"🏷️ Detected Thermo Fisher brand in: {item_name}")
                return self.search_thermo_fisher(item_name)
            elif 'vwr' in item_lower:
                logger.info(f"🏷️ Detected VWR brand in: {item_name}")
                return self.search_vwr(item_name)
            elif 'falcon' in item_lower:
                logger.info(f"🏷️ Detected Falcon brand in: {item_name}")
                return self.search_thermo_fisher(item_name)  # Falcon is owned by Thermo Fisher
            elif 'nunc' in item_lower:
                logger.info(f"🏷️ Detected Nunc brand in: {item_name}")
                return self.search_thermo_fisher(item_name)  # Nunc is owned by Thermo Fisher
            elif 'bd' in item_lower:
                logger.info(f"🏷️ Detected BD brand in: {item_name}")
                return self.search_vwr(item_name)  # BD products often sold through VWR
            elif 'axygen' in item_lower:
                logger.info(f"🏷️ Detected Axygen brand in: {item_name}")
                return self.search_vwr(item_name)  # Axygen products often sold through VWR
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error in brand detection for {item_name}: {e}")
            return None

    def search_multiple_sources(self, item_name, sku=None):
        """Search multiple scientific suppliers and return average price"""
        try:
            prices = []
            
            # First try brand-specific search
            brand_price = self.detect_brand_and_search(item_name)
            if brand_price:
                prices.append(brand_price)
                logger.info(f"🎯 Found brand-specific price: ${brand_price}")
            
            # Search Google Shopping (good for general lab equipment)
            google_price = self.search_google_shopping(item_name)
            if google_price:
                prices.append(google_price)
            
            # Small delay between requests
            time.sleep(random.uniform(2, 4))
            
            # Search Thermo Fisher Scientific
            thermo_price = self.search_thermo_fisher(item_name)
            if thermo_price:
                prices.append(thermo_price)
            
            # Small delay between requests
            time.sleep(random.uniform(2, 4))
            
            # Search VWR
            vwr_price = self.search_vwr(item_name)
            if vwr_price:
                prices.append(vwr_price)
            
            # Small delay between requests
            time.sleep(random.uniform(2, 4))
            
            # Search Corning (especially for flasks and labware)
            corning_price = self.search_corning(item_name)
            if corning_price:
                prices.append(corning_price)
            
            # If we still don't have prices, try Amazon as fallback
            if not prices:
                logger.info(f"🔄 No scientific supplier prices found, trying Amazon as fallback...")
                time.sleep(random.uniform(2, 4))
                amazon_price = self.search_amazon(item_name)
                if amazon_price:
                    prices.append(amazon_price)
            
            if prices:
                avg_price = sum(prices) / len(prices)
                logger.info(f"🎯 Final average price for {item_name}: ${avg_price:.2f} (from {len(prices)} sources)")
                return avg_price
            else:
                logger.warning(f"⚠️ No prices found from any source for {item_name}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error searching multiple sources for {item_name}: {e}")
            return None

def main():
    """Test the web price scraper"""
    scraper = WebPriceScraper()
    
    test_items = [
        "Corning 175 cm² Flask Angled Neck Nonpyrogenic Polystyrene",
        "Tissue Culture Flask",
        "VWR Reagent Reservoir 50 mL",
        "BD 30mL Syringe Luer-Lok Tip",
        "Falcon IVF 4-well Dish"
    ]
    
    for item in test_items:
        price = scraper.search_multiple_sources(item)
        if price:
            print(f"✅ {item}: ${price:.2f}")
        else:
            print(f"❌ {item}: No price found")

if __name__ == '__main__':
    main()
