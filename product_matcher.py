# -*- coding: utf-8 -*-
import re
import logging
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

class ProductMatcher:
    def __init__(self):
        # Manufacturer normalization mapping
        self.MANUF_NORMALIZE = {
            "thermo fisher": "Thermo Fisher Scientific",
            "thermo": "Thermo Fisher Scientific", 
            "fisher scientific": "Thermo Fisher Scientific",
            "fisher": "Thermo Fisher Scientific",
            "vwr": "Avantor",
            "avantor": "Avantor",
            "milliporesigma": "MilliporeSigma",
            "sigma-aldrich": "MilliporeSigma",
            "sigma": "MilliporeSigma",
            "corning": "Corning",
            "falcon": "Corning",
            "costar": "Corning",
            "eppendorf": "Eppendorf",
            "greiner": "Greiner Bio-One",
            "usa scientific": "USA Scientific",
            "nest": "NEST Scientific",
            "qiagen": "QIAGEN",
            "neb": "NEB",
            "new england biolabs": "NEB",
            "promega": "Promega",
            "tci": "TCI",
            "bd": "BD Biosciences",
            "becton dickinson": "BD Biosciences",
            "cytiva": "Cytiva",
            "ge healthcare": "Cytiva"
        }
        
        # MPN extraction patterns
        self.MPN_PATTERNS = [
            r"(?:cat(?:\.|:)?\s*#?\s*|ref\s*#?\s*|sku\s*#?\s*|pn\s*#?\s*|part\s*#?\s*|model\s*#?\s*)?([A-Za-z0-9][A-Za-z0-9\-_/\.]{2,})",
            r"(?:catalog\s*#?\s*|item\s*#?\s*|product\s*#?\s*)?([A-Za-z0-9][A-Za-z0-9\-_/\.]{2,})",
            r"([A-Z]{2,}\d{3,})",  # Pattern like BD123456
            r"(\d{4,}[A-Z]{1,})",  # Pattern like 1234A
        ]
        
        # Condition keywords
        self.CONDITION_KEYWORDS = {
            "new": ["new", "sealed", "unopened", "fresh"],
            "used": ["used", "opened", "second hand", "pre-owned"],
            "expired": ["expired", "outdated", "past date", "exp"],
            "damaged": ["damaged", "broken", "cracked", "defective"]
        }

    def normalize_manufacturer(self, manufacturer_text):
        """Normalize manufacturer names using fuzzy matching"""
        if not manufacturer_text:
            return None
            
        # Clean the input
        clean_text = re.sub(r"[^a-z\s]", "", manufacturer_text.lower())
        
        # Find best match using fuzzy matching
        best_match = process.extractOne(clean_text, self.MANUF_NORMALIZE.keys(), scorer=fuzz.partial_ratio)
        
        if best_match and best_match[1] >= 85:  # 85% similarity threshold
            normalized = self.MANUF_NORMALIZE[best_match[0]]
            logger.info(f"🏷️ Normalized '{manufacturer_text}' -> '{normalized}'")
            return normalized
        
        return manufacturer_text.strip()

    def extract_mpn(self, text):
        """Extract Manufacturer Part Number (MPN) from text"""
        if not text:
            return None
            
        # Clean the text
        clean_text = text.replace("\n", " ").strip()
        
        # Remove common noise words that might interfere
        clean_text = re.sub(r"\b(pack|case|cs|ea|each|pk|bx|rl|bag|sterile|non-sterile|box|tube|flask|dish)\b.*", "", clean_text, flags=re.I)
        
        # Try each pattern
        for pattern in self.MPN_PATTERNS:
            matches = re.finditer(pattern, clean_text, flags=re.I)
            for match in matches:
                candidate = match.group(1).strip(" .,:;()[]{}").upper()
                
                # Sanity filters
                if (len(candidate) >= 3 and 
                    not candidate.endswith((".", ",")) and
                    not candidate.isdigit() and  # Not just numbers
                    not candidate.isalpha()):    # Not just letters
                    logger.info(f"🔍 Extracted MPN: '{candidate}' from '{text[:50]}...'")
                    return candidate
        
        logger.warning(f"⚠️ No MPN found in: '{text[:50]}...'")
        return None

    def detect_condition(self, text):
        """Detect item condition from text"""
        if not text:
            return "unknown"
            
        text_lower = text.lower()
        
        for condition, keywords in self.CONDITION_KEYWORDS.items():
            if any(keyword in text_lower for keyword in keywords):
                logger.info(f"📦 Detected condition: {condition}")
                return condition
                
        return "unknown"

    def extract_pack_quantity(self, text):
        """Extract pack quantity from text"""
        if not text:
            return None
            
        # Look for patterns like "pack of 50", "case of 20", "box of 100"
        patterns = [
            r"(?:pack|case|box|bx|cs|pk)\s*of\s*(\d+)",
            r"(\d+)\s*(?:pack|case|box|bx|cs|pk)",
            r"(\d+)\s*(?:ea|each|pieces?|units?)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                qty = int(match.group(1))
                logger.info(f"📦 Extracted pack quantity: {qty}")
                return qty
                
        return None

    def extract_unit_type(self, text):
        """Extract unit type (tips, tubes, flasks, etc.)"""
        if not text:
            return None
            
        text_lower = text.lower()
        
        unit_types = {
            "tips": ["tip", "tips", "pipette tip"],
            "tubes": ["tube", "tubes", "test tube", "centrifuge tube"],
            "flasks": ["flask", "flasks", "culture flask", "erlenmeyer"],
            "dishes": ["dish", "dishes", "petri dish", "culture dish"],
            "plates": ["plate", "plates", "microplate", "well plate"],
            "syringes": ["syringe", "syringes"],
            "bottles": ["bottle", "bottles", "reagent bottle"],
            "beakers": ["beaker", "beakers"],
            "pipettes": ["pipette", "pipettes"]
        }
        
        for unit_type, keywords in unit_types.items():
            if any(keyword in text_lower for keyword in keywords):
                logger.info(f"🔬 Detected unit type: {unit_type}")
                return unit_type
                
        return None

    def create_product_key(self, item_name, manufacturer=None, mpn=None, pack_qty=None):
        """Create a standardized product key for matching"""
        key_parts = []
        
        # Add manufacturer
        if manufacturer:
            normalized_manuf = self.normalize_manufacturer(manufacturer)
            key_parts.append(normalized_manuf)
        
        # Add MPN (most important)
        if mpn:
            key_parts.append(mpn)
        
        # Add pack quantity if available
        if pack_qty:
            key_parts.append(f"pack_{pack_qty}")
        
        # Create key
        product_key = "_".join(key_parts) if key_parts else item_name.lower().replace(" ", "_")
        
        logger.info(f"🔑 Created product key: {product_key}")
        return product_key

    def score_price_match(self, item_data, price_data):
        """Score how well a price matches an item"""
        score = 0.0
        
        # MPN exact match (highest weight)
        if item_data.get("mpn") and price_data.get("mpn"):
            if item_data["mpn"].upper() == price_data["mpn"].upper():
                score += 0.5
                logger.info(f"✅ Exact MPN match: {item_data['mpn']}")
        
        # Manufacturer match
        if item_data.get("manufacturer") and price_data.get("manufacturer"):
            if (self.normalize_manufacturer(item_data["manufacturer"]) == 
                self.normalize_manufacturer(price_data["manufacturer"])):
                score += 0.2
                logger.info(f"✅ Manufacturer match: {item_data['manufacturer']}")
        
        # Title similarity
        if item_data.get("item_name") and price_data.get("title"):
            title_similarity = fuzz.token_sort_ratio(
                item_data["item_name"][:120], 
                price_data["title"][:120]
            ) / 100.0
            score += 0.2 * title_similarity
            logger.info(f"📝 Title similarity: {title_similarity:.2f}")
        
        # Pack quantity match
        if (item_data.get("pack_qty") and price_data.get("pack_qty") and
            str(item_data["pack_qty"]) == str(price_data["pack_qty"])):
            score += 0.1
            logger.info(f"📦 Pack quantity match: {item_data['pack_qty']}")
        
        logger.info(f"🎯 Total match score: {score:.2f}")
        return score

    def apply_condition_pricing(self, base_price, condition, is_reagent=False):
        """Apply condition-based pricing multipliers"""
        if not base_price:
            return None
            
        multipliers = {
            "new": 0.7,           # 70% of MSRP for resale
            "used": 0.4,          # 40% of MSRP for used
            "damaged": 0.2,       # 20% of MSRP for damaged
            "expired": 0.05 if is_reagent else 0.25,  # 5% for expired reagents, 25% for expired equipment
            "unknown": 0.5        # 50% for unknown condition
        }
        
        multiplier = multipliers.get(condition, 0.5)
        adjusted_price = base_price * multiplier
        
        logger.info(f"💰 Applied {condition} pricing: ${base_price:.2f} -> ${adjusted_price:.2f} (x{multiplier})")
        return round(adjusted_price, 2)

    def process_item(self, item_name, manufacturer=None, barcode=None, condition=None):
        """Process a single item and extract all relevant data"""
        logger.info(f"🔍 Processing item: {item_name}")
        
        # Extract MPN
        mpn = self.extract_mpn(item_name)
        
        # Normalize manufacturer
        normalized_manufacturer = self.normalize_manufacturer(manufacturer) if manufacturer else None
        
        # Detect condition if not provided
        detected_condition = condition or self.detect_condition(item_name)
        
        # Extract pack quantity
        pack_qty = self.extract_pack_quantity(item_name)
        
        # Extract unit type
        unit_type = self.extract_unit_type(item_name)
        
        # Create product key
        product_key = self.create_product_key(item_name, normalized_manufacturer, mpn, pack_qty)
        
        return {
            "item_name": item_name,
            "manufacturer": normalized_manufacturer,
            "mpn": mpn,
            "barcode": barcode,
            "condition": detected_condition,
            "pack_qty": pack_qty,
            "unit_type": unit_type,
            "product_key": product_key
        }

def main():
    """Test the product matcher"""
    matcher = ProductMatcher()
    
    test_items = [
        "Corning 175 cm² Flask Angled Neck Nonpyrogenic Polystyrene",
        "Thermo Fisher Scientific REF 123456 Pipette Tips Pack of 50",
        "VWR Catalog # ABC-789 Reagent Bottles Case of 20",
        "BD Falcon 30mL Syringe Luer-Lok Tip Sterile",
        "Used Eppendorf Tube Rack Expired 2023"
    ]
    
    for item in test_items:
        print(f"\n🔍 Testing: {item}")
        result = matcher.process_item(item)
        print(f"📋 Result: {result}")

if __name__ == "__main__":
    main()