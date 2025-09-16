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
        """Search Amazon for item prices"""
        try:
            # Search Amazon
            search_query = item_name.replace(' ', '+')
            url = f"https://www.amazon.com/s?k={search_query}"
            
            logger.info(f"🛒 Searching Amazon for: {item_name}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for Amazon price elements
            prices = []
            price_selectors = [
                '.a-price-whole',  # Amazon price whole part
                '.a-offscreen',  # Amazon price offscreen
                '.a-price .a-offscreen',  # Nested price
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
    
    def search_multiple_sources(self, item_name, sku=None):
        """Search multiple sources and return average price"""
        try:
            prices = []
            
            # Search Google Shopping
            google_price = self.search_google_shopping(item_name)
            if google_price:
                prices.append(google_price)
            
            # Small delay between requests
            time.sleep(random.uniform(1, 3))
            
            # Search Amazon
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
        "Red Bull Sugarfree",
        "Energy Drink",
        "Tissue Culture Flask"
    ]
    
    for item in test_items:
        price = scraper.search_multiple_sources(item)
        if price:
            print(f"✅ {item}: ${price:.2f}")
        else:
            print(f"❌ {item}: No price found")

if __name__ == '__main__':
    main()
