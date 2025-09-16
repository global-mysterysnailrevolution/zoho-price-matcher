# -*- coding: utf-8 -*-
import os
import requests
import pandas as pd
import logging
from bs4 import BeautifulSoup
import re
import time
import random
from urllib.parse import urljoin, urlparse
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

class EnhancedPriceMatcher:
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
        
        # Scientific equipment suppliers to prioritize
        self.scientific_suppliers = [
            'thermofisher.com', 'fishersci.com', 'vwr.com', 'corning.com',
            'sigmaaldrich.com', 'thomassci.com', 'coleparmer.com',
            'usascientific.com', 'eppendorf.com', 'greiner.com',
            'neb.com', 'qiagen.com', 'promega.com', 'tci.com',
            'bdbiosciences.com', 'cytiva.com'
        ]

    def get_google_sheets_data(self):
        """Fetch data from Google Sheets"""
        try:
            url = 'https://docs.google.com/spreadsheets/d/1igH2xZq48pb76bAG25rVBkxb8gODc0SqBHMLwu5hTSc/export?format=csv&gid=1761140701'
            
            logger.info('📊 Fetching data from Google Sheets...')
            response = requests.get(url)
            response.raise_for_status()
            
            df = pd.read_csv(pd.StringIO(response.text))
            logger.info(f'✅ Successfully fetched {len(df)} rows from Google Sheets')
            
            return df
            
        except Exception as e:
            logger.error(f'❌ Error fetching Google Sheets data: {e}')
            return None

    def google_search_item(self, item_name, manufacturer=None):
        """Search Google for the item and get first 7 sponsored links"""
        try:
            # Construct search query
            search_terms = [item_name]
            if manufacturer:
                search_terms.append(manufacturer)
            
            search_query = " ".join(search_terms)
            url = f"https://www.google.com/search?q={search_query}"
            
            logger.info(f"🔍 Google searching: {search_query}")
            
            # Add random delay
            time.sleep(random.uniform(1, 3))
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract sponsored links (first 7)
            sponsored_links = []
            
            # Look for various Google result link patterns
            link_selectors = [
                'div[data-ved] a[href*="http"]',  # Sponsored links
                '.g a[href*="http"]',  # Regular results
                '.yuRUbf a[href*="http"]',  # Alternative result links
                '.rc a[href*="http"]',  # Another result pattern
            ]
            
            for selector in link_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href and self.is_valid_supplier_link(href):
                        sponsored_links.append(href)
                        logger.info(f'🔗 Found supplier link: {href}')
                        
                        if len(sponsored_links) >= 7:  # Stop at 7 links
                            break
                
                if len(sponsored_links) >= 7:
                    break
            
            logger.info(f'✅ Found {len(sponsored_links)} sponsored links')
            return sponsored_links
            
        except Exception as e:
            logger.error(f'❌ Error in Google search: {e}')
            return []

    def is_valid_supplier_link(self, url):
        """Check if link is from a scientific supplier"""
        try:
            domain = urlparse(url).netloc.lower()
            return any(supplier in domain for supplier in self.scientific_suppliers)
        except:
            return False

    def scrape_page_info(self, url, original_item_name, manufacturer=None):
        """Scrape product information from a supplier page"""
        try:
            logger.info(f"🔍 Scraping page: {url}")
            
            # Add random delay
            time.sleep(random.uniform(2, 4))
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract product information
            page_info = {
                'url': url,
                'title': self.extract_title(soup),
                'price': self.extract_price(soup),
                'description': self.extract_description(soup),
                'specifications': self.extract_specifications(soup),
                'manufacturer': self.extract_manufacturer(soup),
                'part_number': self.extract_part_number(soup),
                'category': self.extract_category(soup)
            }
            
            logger.info(f"📋 Scraped info: {page_info['title'][:50]}... - ${page_info['price']}")
            return page_info
            
        except Exception as e:
            logger.error(f"❌ Error scraping {url}: {e}")
            return None

    def extract_title(self, soup):
        """Extract product title"""
        title_selectors = [
            'h1', '.product-title', '.item-title', '.product-name',
            '.product-header h1', '.product-info h1', 'title'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        return ""

    def extract_price(self, soup):
        """Extract product price"""
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
                if price and 0.01 <= price <= 50000:
                    return price
        
        # Also check data attributes
        for element in soup.find_all(attrs={'data-price': True}):
            try:
                price = float(element['data-price'])
                if 0.01 <= price <= 50000:
                    return price
            except (ValueError, KeyError):
                continue
        
        return None

    def extract_price_from_text(self, text):
        """Extract price from text"""
        if not text:
            return None
        
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
                    if 0.01 <= price <= 50000:
                        return price
                except ValueError:
                    continue
        return None

    def extract_description(self, soup):
        """Extract product description"""
        desc_selectors = [
            '.product-description', '.item-description', '.description',
            '.product-details', '.product-summary', '.overview'
        ]
        
        for selector in desc_selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)[:500]  # Limit length
        return ""

    def extract_specifications(self, soup):
        """Extract product specifications"""
        specs = {}
        
        # Look for specification tables
        spec_tables = soup.select('table, .specifications, .product-specs')
        for table in spec_tables:
            rows = table.select('tr')
            for row in rows:
                cells = row.select('td, th')
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)
                    specs[key] = value
        
        return specs

    def extract_manufacturer(self, soup):
        """Extract manufacturer from page"""
        manufacturer_selectors = [
            '.manufacturer', '.brand', '.vendor', '.supplier',
            '.product-brand', '.item-manufacturer'
        ]
        
        for selector in manufacturer_selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        
        # Try to extract from title or description
        title = self.extract_title(soup)
        description = self.extract_description(soup)
        
        # Look for known manufacturers
        text_to_search = f"{title} {description}".lower()
        for supplier in self.scientific_suppliers:
            if supplier.replace('.com', '') in text_to_search:
                return supplier.replace('.com', '').title()
        
        return ""

    def extract_part_number(self, soup):
        """Extract part number/catalog number"""
        # Look for common part number patterns
        part_number_patterns = [
            r'(?:cat(?:\.|:)?\s*#?\s*|ref\s*#?\s*|sku\s*#?\s*|pn\s*#?\s*|part\s*#?\s*|model\s*#?\s*)?([A-Za-z0-9][A-Za-z0-9\-_/\.]{2,})',
            r'(?:catalog\s*#?\s*|item\s*#?\s*|product\s*#?\s*)?([A-Za-z0-9][A-Za-z0-9\-_/\.]{2,})',
        ]
        
        text_to_search = f"{self.extract_title(soup)} {self.extract_description(soup)}"
        
        for pattern in part_number_patterns:
            matches = re.finditer(pattern, text_to_search, flags=re.I)
            for match in matches:
                candidate = match.group(1).strip(" .,:;()[]{}").upper()
                if len(candidate) >= 3 and not candidate.isdigit() and not candidate.isalpha():
                    return candidate
        
        return ""

    def extract_category(self, soup):
        """Extract product category"""
        category_selectors = [
            '.category', '.product-category', '.breadcrumb',
            '.nav-breadcrumb', '.product-nav'
        ]
        
        for selector in category_selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        return ""

    def score_match(self, original_item, page_info):
        """Score how well a page matches the original item"""
        score = 0.0
        
        original_name = original_item.get('item_name', '').lower()
        original_manufacturer = original_item.get('manufacturer', '').lower()
        
        page_title = page_info.get('title', '').lower()
        page_manufacturer = page_info.get('manufacturer', '').lower()
        page_description = page_info.get('description', '').lower()
        
        # Title similarity (40% weight)
        if page_title:
            title_similarity = fuzz.token_sort_ratio(original_name, page_title) / 100.0
            score += 0.4 * title_similarity
            logger.info(f"📝 Title similarity: {title_similarity:.2f}")
        
        # Manufacturer match (30% weight)
        if original_manufacturer and page_manufacturer:
            if original_manufacturer in page_manufacturer or page_manufacturer in original_manufacturer:
                score += 0.3
                logger.info(f"🏭 Manufacturer match: {page_manufacturer}")
        
        # Description contains original item name (20% weight)
        if page_description and original_name:
            if any(word in page_description for word in original_name.split() if len(word) > 3):
                score += 0.2
                logger.info(f"📋 Description contains item name")
        
        # Has price (10% weight)
        if page_info.get('price'):
            score += 0.1
            logger.info(f"💰 Has price: ${page_info['price']}")
        
        logger.info(f"🎯 Total match score: {score:.2f}")
        return score

    def find_best_match(self, original_item, page_infos):
        """Find the best matching page from scraped information"""
        if not page_infos:
            return None
        
        best_match = None
        best_score = 0
        
        for page_info in page_infos:
            if not page_info:
                continue
                
            score = self.score_match(original_item, page_info)
            
            if score > best_score:
                best_score = score
                best_match = page_info
        
        if best_match and best_score >= 0.3:  # Minimum threshold
            logger.info(f"✅ Best match found with score {best_score:.2f}: {best_match['title'][:50]}...")
            return best_match
        
        logger.warning(f"⚠️ No good match found (best score: {best_score:.2f})")
        return None

    def process_item(self, item_name, manufacturer=None, zoho_id=None, quantity=None):
        """Process a single item through the complete pipeline"""
        try:
            logger.info(f"🔄 Processing: {item_name}")
            if manufacturer:
                logger.info(f"🏭 Manufacturer: {manufacturer}")
            
            # Step 1: Google search for sponsored links
            sponsored_links = self.google_search_item(item_name, manufacturer)
            
            if not sponsored_links:
                logger.warning(f"⚠️ No sponsored links found for {item_name}")
                return None
            
            # Step 2: Scrape each sponsored link
            page_infos = []
            for link in sponsored_links:
                page_info = self.scrape_page_info(link, item_name, manufacturer)
                if page_info:
                    page_infos.append(page_info)
            
            if not page_infos:
                logger.warning(f"⚠️ No page info scraped for {item_name}")
                return None
            
            # Step 3: Score and find best match
            original_item = {
                'item_name': item_name,
                'manufacturer': manufacturer
            }
            
            best_match = self.find_best_match(original_item, page_infos)
            
            if not best_match:
                logger.warning(f"⚠️ No good match found for {item_name}")
                return None
            
            # Step 4: Return result
            result = {
                'original_item_name': item_name,
                'original_manufacturer': manufacturer,
                'zoho_id': zoho_id,
                'quantity': quantity,
                'matched_title': best_match['title'],
                'matched_price': best_match['price'],
                'matched_url': best_match['url'],
                'matched_manufacturer': best_match['manufacturer'],
                'matched_part_number': best_match['part_number'],
                'confidence_score': self.score_match(original_item, best_match)
            }
            
            logger.info(f"✅ Found match: {best_match['title'][:50]}... - ${best_match['price']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error processing {item_name}: {e}")
            return None

    def create_results_sheet(self, results):
        """Create a new sheet with results"""
        try:
            if not results:
                logger.warning("⚠️ No results to create sheet")
                return None
            
            # Create DataFrame
            df = pd.DataFrame(results)
            
            # Save to CSV
            output_file = 'price_matching_results.csv'
            df.to_csv(output_file, index=False)
            
            logger.info(f"✅ Created results sheet: {output_file}")
            logger.info(f"📊 {len(results)} items processed")
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Error creating results sheet: {e}")
            return None

    def run_full_process(self):
        """Run the complete process"""
        try:
            logger.info("🚀 Starting Enhanced Price Matching Process")
            logger.info("=" * 60)
            
            # Step 1: Get Google Sheets data
            df = self.get_google_sheets_data()
            if df is None:
                return
            
            # Step 2: Process items
            results = []
            processed_count = 0
            
            for index, row in df.iterrows():
                try:
                    item_name = str(row.get('Item Name', ''))
                    manufacturer = str(row.get('Manufacturer', '')) if pd.notna(row.get('Manufacturer')) else None
                    zoho_id = row.get('Zoho ID')
                    quantity = row.get('Quantity', 0)
                    
                    if not item_name or pd.isna(zoho_id):
                        continue
                    
                    # Process the item
                    result = self.process_item(item_name, manufacturer, zoho_id, quantity)
                    
                    if result:
                        results.append(result)
                    
                    processed_count += 1
                    
                    # Add delay to avoid rate limiting
                    time.sleep(random.uniform(3, 6))
                    
                except Exception as e:
                    logger.error(f"❌ Error processing row {index}: {e}")
                    continue
            
            # Step 3: Create results sheet
            self.create_results_sheet(results)
            
            logger.info("=" * 60)
            logger.info(f"✅ Process complete!")
            logger.info(f"📊 Items processed: {processed_count}")
            logger.info(f"💰 Successful matches: {len(results)}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error in full process: {e}")
            return None

def main():
    """Test the enhanced price matcher"""
    matcher = EnhancedPriceMatcher()
    
    # Test with a single item
    test_result = matcher.process_item(
        "Corning 175 cm² Flask Angled Neck Nonpyrogenic Polystyrene",
        manufacturer="Corning"
    )
    
    if test_result:
        print(f"✅ Test successful: {test_result['matched_title']} - ${test_result['matched_price']}")
    else:
        print("❌ Test failed")

if __name__ == "__main__":
    main()
