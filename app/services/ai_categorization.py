"""AI-powered product categorization service"""

import openai
from typing import List, Dict, Optional, Any
import logging
import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.category import Category

logger = logging.getLogger(__name__)

class AICategorization:
    """Service for AI-powered product categorization"""
def __init__(self, db: AsyncSession):
    self.db = db
    openai.api_key = settings.OPENAI_API_KEY
    
async def suggest_categories(
    self,
    title: str,
    description: str,
    num_suggestions: int = 3
) -> List[Dict[str, Any]]:
    """Suggest categories for a product using AI"""
    try:
        # Get all categories
        categories = await self.db.execute(select(Category))
        categories = categories.scalars().all()
        
        # Create category list for prompt
        category_list = [
            f"{cat.name} - {cat.description or 'No description'}"
            for cat in categories
        ]
        
        # Create prompt
        prompt = f"""
        Given the following product information, suggest the {num_suggestions} most appropriate categories:
        
        Product Title: {title}
        Product Description: {description}
        
        Available Categories:
        {chr(10).join(category_list)}
        
        Return a JSON array with {num_suggestions} category suggestions.
        Each suggestion should have:
        - category_name: exact name from the list
        - confidence: 0-100 score
        - reasoning: brief explanation
        
        Example format:
        [
            {{
                "category_name": "Electronics",
                "confidence": 95,
                "reasoning": "Product appears to be an electronic device"
            }}
        ]
        """
        
        # Call OpenAI
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a product categorization expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        # Parse response
        content = response.choices[0].message.content
        suggestions = json.loads(content)
        
        # Validate suggestions
        valid_suggestions = []
        category_names = {cat.name for cat in categories}
        
        for suggestion in suggestions:
            if suggestion["category_name"] in category_names:
                valid_suggestions.append(suggestion)
                
        return valid_suggestions[:num_suggestions]
        
    except Exception as e:
        logger.error(f"AI categorization error: {str(e)}")
        # Fallback to simple keyword matching
        return await self._fallback_categorization(title, description)
        
async def _fallback_categorization(
    self,
    title: str,
    description: str
) -> List[Dict[str, Any]]:
    """Fallback categorization using keywords"""
    text = f"{title} {description}".lower()
    
    # Keyword mappings
    keyword_categories = {
        "Gadgets": ["phone", "laptop", "computer", "tablet", "camera", "tv", "electronics"],
        "Fashion": ["shirt", "dress", "pants", "shoes", "clothing", "wear"],
        "Home": ["furniture", "decor", "garden", "kitchen", "bed", "home"],
        "Books & Toys": ["book", "novel", "reading", "author", "publication", "toy", "game", "play", "kids", "children"],
        "Sports & Fitness": ["sports", "fitness", "gym", "exercise", "game"],
        "Digital Products": ["software", "app", "digital", "online", "subscription"],
        "Beauty & Care": ["beauty", "cosmetic", "makeup", "skincare", "perfume", "care"],
        "Others": ["health", "medicine", "vitamin", "supplement", "medical", "food", "snack", "beverage", "drink", "eat"]
    }
    
    suggestions = []
    
    for category, keywords in keyword_categories.items():
        matches = sum(1 for keyword in keywords if keyword in text)
        if matches > 0:
            confidence = min(matches * 20, 100)
            suggestions.append({
                "category_name": category,
                "confidence": confidence,
                "reasoning": f"Contains {matches} related keywords"
            })
            
    # Sort by confidence
    suggestions.sort(key=lambda x: x["confidence"], reverse=True)
    
    return suggestions[:3]
    
async def auto_categorize_product(
    self,
    product_id: str,
    title: str,
    description: str
) -> Optional[str]:
    """Automatically categorize a product"""
    suggestions = await self.suggest_categories(title, description, 1)
    
    if suggestions and suggestions[0]["confidence"] >= 80:
        # High confidence, auto-assign
        category_name = suggestions[0]["category_name"]
        
        # Get category ID
        category = await self.db.execute(
            select(Category).where(Category.name == category_name)
        )
        category = category.scalar_one_or_none()
        
        if category:
            # Update product
            from app.models.product import Product
            await self.db.execute(
                update(Product)
                .where(Product.id == product_id)
                .values(
                    category_id=category.id,
                    ai_categorized=True
                )
            )
            await self.db.commit()
            
            logger.info(
                f"Auto-categorized product {product_id} to {category_name} "
                f"with {suggestions[0]['confidence']}% confidence"
            )
            
            return category.id
            
    return None


# """
# AI-powered product categorization service
# """

# from typing import Optional, List, Dict, Any
# import logging
# import re
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.naive_bayes import MultinomialNB
# import joblib
# import numpy as np

# from app.core.config import settings

# logger = logging.getLogger(__name__)

# class AICategorization:
#     """AI service for product categorization"""
    
#     def __init__(self):
#         self.model = None
#         self.vectorizer = None
#         self.categories = None
#         self._load_model()
    
#     def _load_model(self):
#         """Load pre-trained model"""
#         try:
#             # In production, load from saved model files
#             # For now, we'll use a simple rule-based approach
#             self.categories = {
#                 "electronics": ["phone", "laptop", "computer", "tablet", "camera", "tv", "television", "headphone", "speaker", "smartwatch"],
#                 "fashion": ["shirt", "tshirt", "dress", "jeans", "pants", "shoes", "jacket", "coat", "sweater", "kurta", "saree"],
#                 "home": ["furniture", "sofa", "bed", "table", "chair", "kitchen", "utensil", "decor", "mattress", "curtain"],
#                 "beauty": ["makeup", "cosmetic", "perfume", "skincare", "shampoo", "soap", "cream", "lotion", "lipstick", "foundation"],
#                 "books": ["book", "novel", "textbook", "magazine", "kindle", "ebook", "paperback", "hardcover", "comics", "manga"],
#                 "sports": ["cricket", "football", "basketball", "tennis", "gym", "fitness", "yoga", "running", "cycling", "sports"],
#                 "grocery": ["rice", "dal", "oil", "sugar", "salt", "spices", "vegetables", "fruits", "milk", "bread"],
#                 "toys": ["toy", "game", "puzzle", "doll", "lego", "board game", "action figure", "educational", "kids", "children"]
#             }
#         except Exception as e:
#             logger.error(f"Failed to load AI model: {str(e)}")
    
#     async def suggest_category(
#         self,
#         title: str,
#         description: Optional[str] = None
#     ) -> Optional[str]:
#         """
#         Suggest category for product
        
#         Args:
#             title: Product title
#             description: Product description
            
#         Returns:
#             Suggested category name
#         """
#         try:
#             # Combine title and description
#             text = f"{title} {description or ''}".lower()
            
#             # Clean text
#             text = re.sub(r'[^a-z0-9\s]', ' ', text)
#             words = text.split()
            
#             # Score each category
#             category_scores = {}
            
#             for category, keywords in self.categories.items():
#                 score = sum(1 for word in words if word in keywords)
#                 if score > 0:
#                     category_scores[category] = score
            
#             # Return category with highest score
#             if category_scores:
#                 return max(category_scores, key=category_scores.get)
            
#             return None
            
#         except Exception as e:
#             logger.error(f"Category suggestion failed: {str(e)}")
#             return None
    
#     async def extract_attributes(
#         self,
#         title: str,
#         description: str
#     ) -> Dict[str, Any]:
#         """
#         Extract product attributes from text
        
#         Args:
#             title: Product title
#             description: Product description
            
#         Returns:
#             Extracted attributes
#         """
#         attributes = {}
#         text = f"{title} {description}".lower()
        
#         # Extract colors
#         colors = ["red", "blue", "green", "yellow", "black", "white", "grey", "gray", "pink", "purple", "orange", "brown"]
#         found_colors = [color for color in colors if color in text]
#         if found_colors:
#             attributes["colors"] = found_colors
        
#         # Extract sizes
#         size_patterns = [
#             r'\b(xs|s|m|l|xl|xxl|xxxl)\b',
#             r'\b(\d+)\s*(gb|mb|tb)\b',
#             r'\b(\d+)\s*(inch|inches|")\b',
#             r'\b(\d+)\s*(cm|mm|m)\b'
#         ]
        
#         sizes = []
#         for pattern in size_patterns:
#             matches = re.findall(pattern, text, re.IGNORECASE)
#             sizes.extend(matches)
        
#         if sizes:
#             attributes["sizes"] = sizes
        
#         # Extract brand (simple approach)
#         known_brands = ["samsung", "apple", "nike", "adidas", "sony", "lg", "dell", "hp", "lenovo", "asus"]
#         found_brands = [brand for brand in known_brands if brand in text]
#         if found_brands:
#             attributes["brand"] = found_brands[0]
        
#         return attributes
    
#     async def generate_tags(
#         self,
#         title: str,
#         description: str,
#         category: Optional[str] = None
#     ) -> List[str]:
#         """
#         Generate tags for product
        
#         Args:
#             title: Product title
#             description: Product description
#             category: Product category
            
#         Returns:
#             List of relevant tags
#         """
#         tags = []
#         text = f"{title} {description}".lower()
        
#         # Clean and tokenize
#         text = re.sub(r'[^a-z0-9\s]', ' ', text)
#         words = text.split()
        
#         # Remove common words
#         stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
#         words = [w for w in words if w not in stop_words and len(w) > 2]
        
#         # Get unique words
#         unique_words = list(set(words))
        
#         # Add category as tag
#         if category:
#             tags.append(category)
        
#         # Add top frequent words as tags (max 10)
#         word_freq = {}
#         for word in words:
#             word_freq[word] = word_freq.get(word, 0) + 1
        
#         sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
#         tags.extend([word for word, _ in sorted_words[:10]])
        
#         # Remove duplicates and return
#         return list(set(tags))[:15]  # Max 15 tags
