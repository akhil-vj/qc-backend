"""ML-based product recommendation service"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timedelta
import logging
from collections import defaultdict
import asyncio

from app.models.product import Product
from app.models.order import Order, OrderItem
from app.models.user import User
from app.models.analytics import ProductView, UserActivity

logger = logging.getLogger(__name__)

class RecommendationService:
    """ML-based product recommendation service"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_personalized_recommendations(
        self,
        user_id: str,
        limit: int = 20,
        exclude_purchased: bool = True
    ) -> List[Dict[str, Any]]:
        """Get personalized product recommendations for user"""
        try:
            # Get user data
            user = await self.db.get(User, user_id)
            if not user:
                return await self.get_trending_products(limit)
                
            # Combine multiple recommendation strategies
            strategies = [
                self._get_collaborative_filtering_recommendations(user_id, limit * 2),
                self._get_content_based_recommendations(user_id, limit * 2),
                self._get_purchase_history_based_recommendations(user_id, limit),
                self._get_browsing_history_recommendations(user_id, limit)
            ]
            
            # Execute all strategies concurrently
            results = await asyncio.gather(*strategies, return_exceptions=True)
            
            # Merge and score results
            product_scores = defaultdict(float)
            weights = [0.3, 0.25, 0.25, 0.2]  # Strategy weights
            
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Recommendation strategy {idx} failed: {str(result)}")
                    continue
                    
                for product_id, score in result:
                    product_scores[product_id] += score * weights[idx]
                    
            # Get products to exclude
            excluded_ids = set()
            if exclude_purchased:
                excluded_ids = await self._get_purchased_product_ids(user_id)
                
            # Sort by score and get top products
            sorted_products = sorted(
                [(pid, score) for pid, score in product_scores.items() if pid not in excluded_ids],
                key=lambda x: x[1],
                reverse=True
            )[:limit]
            
            # Fetch product details
            product_ids = [pid for pid, _ in sorted_products]
            products = await self._fetch_product_details(product_ids)
            
            # Add recommendation metadata
            recommendations = []
            for product in products:
                product_dict = product.to_dict()
                product_dict['recommendation_score'] = product_scores[str(product.id)]
                product_dict['recommendation_reason'] = await self._get_recommendation_reason(
                    user_id, str(product.id)
                )
                recommendations.append(product_dict)
                
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting personalized recommendations: {str(e)}")
            return await self.get_trending_products(limit)
            
    async def _get_collaborative_filtering_recommendations(
        self,
        user_id: str,
        limit: int
    ) -> List[Tuple[str, float]]:
        """Get recommendations based on similar users' purchases"""
        # Find users with similar purchase patterns
        similar_users_query = """
        WITH user_products AS (
            SELECT DISTINCT oi.product_id
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            WHERE o.buyer_id = :user_id
            AND o.status IN ('delivered', 'confirmed')
        ),
        similar_users AS (
            SELECT 
                o.buyer_id,
                COUNT(DISTINCT oi.product_id) as common_products,
                COUNT(DISTINCT oi.product_id)::float / 
                    (SELECT COUNT(*) FROM user_products)::float as similarity_score
            FROM orders o
            JOIN order_items oi ON o.id = oi.order_id
            WHERE oi.product_id IN (SELECT product_id FROM user_products)
            AND o.buyer_id != :user_id
            AND o.status IN ('delivered', 'confirmed')
            GROUP BY o.buyer_id
            HAVING COUNT(DISTINCT oi.product_id) >= 3
            ORDER BY similarity_score DESC
            LIMIT 50
        )
        SELECT 
            oi.product_id,
            SUM(su.similarity_score) as score
        FROM similar_users su
        JOIN orders o ON su.buyer_id = o.buyer_id
        JOIN order_items oi ON o.id = oi.order_id
        WHERE oi.product_id NOT IN (SELECT product_id FROM user_products)
        AND o.status IN ('delivered', 'confirmed')
        GROUP BY oi.product_id
        ORDER BY score DESC
        LIMIT :limit
        """
        
        result = await self.db.execute(
            text(similar_users_query),
            {"user_id": user_id, "limit": limit}
        )
        
        return [(str(row.product_id), row.score) for row in result]
        
    async def _get_content_based_recommendations(
        self,
        user_id: str,
        limit: int
    ) -> List[Tuple[str, float]]:
        """Get recommendations based on product attributes"""
        # Get user's preferred categories and attributes
        preference_query = """
        WITH user_categories AS (
            SELECT 
                p.category_id,
                COUNT(*) as purchase_count,
                AVG(COALESCE(r.rating, 4)) as avg_rating
            FROM products p
            JOIN order_items oi ON p.id = oi.product_id
            JOIN orders o ON oi.order_id = o.id
            LEFT JOIN reviews r ON p.id = r.product_id AND r.user_id = :user_id
            WHERE o.buyer_id = :user_id
            AND o.status IN ('delivered', 'confirmed')
            GROUP BY p.category_id
        ),
        user_attributes AS (
            SELECT 
                jsonb_object_keys(p.attributes) as attribute_key,
                p.attributes->jsonb_object_keys(p.attributes) as attribute_value,
                COUNT(*) as frequency
            FROM products p
            JOIN order_items oi ON p.id = oi.product_id
            JOIN orders o ON oi.order_id = o.id
            WHERE o.buyer_id = :user_id
            AND o.status IN ('delivered', 'confirmed')
            AND p.attributes IS NOT NULL
            GROUP BY attribute_key, attribute_value
            HAVING COUNT(*) >= 2
        )
        SELECT 
            p.id as product_id,
            (
                COALESCE(uc.purchase_count, 0) * 0.3 +
                COALESCE(uc.avg_rating, 0) * 0.2 +
                (
                    SELECT COUNT(*)
                    FROM user_attributes ua
                    WHERE p.attributes @> jsonb_build_object(ua.attribute_key, ua.attribute_value)
                ) * 0.5
            ) as score
        FROM products p
        LEFT JOIN user_categories uc ON p.category_id = uc.category_id
        WHERE p.status = 'active'
        AND p.stock > 0
        ORDER BY score DESC
        LIMIT :limit
        """
        
        result = await self.db.execute(
            text(preference_query),
            {"user_id": user_id, "limit": limit}
        )
        
        return [(str(row.product_id), row.score) for row in result]
        
    async def _get_purchase_history_based_recommendations(
        self,
        user_id: str,
        limit: int
    ) -> List[Tuple[str, float]]:
        """Get recommendations based on purchase patterns"""
        # Find frequently bought together products
        query = """
        WITH user_orders AS (
            SELECT DISTINCT oi.product_id
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            WHERE o.buyer_id = :user_id
            AND o.status IN ('delivered', 'confirmed')
        ),
        frequently_bought_together AS (
            SELECT 
                oi2.product_id,
                COUNT(DISTINCT o.id) as co_occurrence_count,
                AVG(oi2.quantity) as avg_quantity
            FROM orders o
            JOIN order_items oi1 ON o.id = oi1.order_id
            JOIN order_items oi2 ON o.id = oi2.order_id
            WHERE oi1.product_id IN (SELECT product_id FROM user_orders)
            AND oi2.product_id NOT IN (SELECT product_id FROM user_orders)
            AND oi1.product_id != oi2.product_id
            AND o.status IN ('delivered', 'confirmed')
            GROUP BY oi2.product_id
            HAVING COUNT(DISTINCT o.id) >= 5
        )
        SELECT 
            fbt.product_id,
            (fbt.co_occurrence_count * 0.7 + fbt.avg_quantity * 0.3) as score
        FROM frequently_bought_together fbt
        JOIN products p ON fbt.product_id = p.id
        WHERE p.status = 'active'
        AND p.stock > 0
        ORDER BY score DESC
        LIMIT :limit
        """
        
        result = await self.db.execute(
            text(query),
            {"user_id": user_id, "limit": limit}
        )
        
        return [(str(row.product_id), row.score) for row in result]
        
    async def _get_browsing_history_recommendations(
        self,
        user_id: str,
        limit: int
    ) -> List[Tuple[str, float]]:
        """Get recommendations based on browsing history"""
        # Recent 30 days browsing history
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        query = """
        WITH view_scores AS (
            SELECT 
                pv.product_id,
                COUNT(*) as view_count,
                MAX(pv.created_at) as last_viewed,
                AVG(pv.duration_seconds) as avg_duration
            FROM product_views pv
            WHERE pv.user_id = :user_id
            AND pv.created_at >= :cutoff_date
            GROUP BY pv.product_id
        ),
        category_affinity AS (
            SELECT 
                p.category_id,
                SUM(vs.view_count) as category_views
            FROM view_scores vs
            JOIN products p ON vs.product_id = p.id
            GROUP BY p.category_id
        )
        SELECT 
            p.id as product_id,
            (
                COALESCE(vs.view_count, 0) * 0.2 +
                COALESCE(ca.category_views, 0) * 0.3 +
                p.trending_score * 0.2 +
                CASE 
                    WHEN vs.last_viewed > NOW() - INTERVAL '7 days' THEN 0.3
                    ELSE 0
                END
            ) as score
        FROM products p
        LEFT JOIN view_scores vs ON p.id = vs.product_id
        LEFT JOIN category_affinity ca ON p.category_id = ca.category_id
        WHERE p.status = 'active'
        AND p.stock > 0
        ORDER BY score DESC
        LIMIT :limit
        """
        
        result = await self.db.execute(
            text(query),
            {"user_id": user_id, "cutoff_date": cutoff_date, "limit": limit}
        )
        
        return [(str(row.product_id), row.score) for row in result]
        
    async def get_similar_products(
        self,
        product_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get products similar to a given product"""
        # Get the product
        product = await self.db.get(Product, product_id)
        if not product:
            return []
            
        # Find similar products based on multiple factors
        query = """
        WITH product_attributes AS (
            SELECT attributes, category_id, price, brand
            FROM products
            WHERE id = :product_id
        )
        SELECT 
            p.id,
            p.title,
            p.price,
            p.mrp,
            p.primary_image,
            p.rating,
            p.review_count,
            (
                -- Category similarity
                CASE WHEN p.category_id = pa.category_id THEN 0.4 ELSE 0 END +
                -- Price similarity (within 20%)
                CASE 
                    WHEN ABS(p.price - pa.price) / pa.price <= 0.2 THEN 0.2
                    ELSE 0
                END +
                -- Brand similarity
                CASE WHEN p.brand = pa.brand THEN 0.2 ELSE 0 END +
                -- Attribute similarity
                CASE 
                    WHEN p.attributes IS NOT NULL AND pa.attributes IS NOT NULL
                    THEN (
                        SELECT COUNT(*)::float / GREATEST(
                            jsonb_array_length(p.attributes),
                            jsonb_array_length(pa.attributes)
                        )
                        FROM jsonb_each(p.attributes) AS p_attr
                        JOIN jsonb_each(pa.attributes) AS pa_attr
                        ON p_attr.key = pa_attr.key AND p_attr.value = pa_attr.value
                    ) * 0.2
                    ELSE 0
                END
            ) as similarity_score
        FROM products p, product_attributes pa
        WHERE p.id != :product_id
        AND p.status = 'active'
        AND p.stock > 0
        ORDER BY similarity_score DESC
        LIMIT :limit
        """
        
        result = await self.db.execute(
            text(query),
            {"product_id": product_id, "limit": limit}
        )
        
        similar_products = []
        for row in result:
            similar_products.append({
                "id": str(row.id),
                "title": row.title,
                "price": float(row.price),
                "mrp": float(row.mrp) if row.mrp else None,
                "primary_image": row.primary_image,
                "rating": float(row.rating) if row.rating else None,
                "review_count": row.review_count,
                "similarity_score": row.similarity_score
            })
            
        return similar_products
        
    async def get_trending_products(
        self,
        limit: int = 20,
        category_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get trending products"""
        query = select(Product).where(
            Product.status == "active",
            Product.stock > 0
        )
        
        if category_id:
            query = query.where(Product.category_id == category_id)
            
        query = query.order_by(Product.trending_score.desc()).limit(limit)
        
        result = await self.db.execute(query)
        products = result.scalars().all()
        
        return [product.to_dict() for product in products]
        
    async def _get_purchased_product_ids(self, user_id: str) -> set:
        """Get IDs of products user has purchased"""
        query = """
        SELECT DISTINCT oi.product_id
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.buyer_id = :user_id
        AND o.status IN ('delivered', 'confirmed')
        """
        
        result = await self.db.execute(text(query), {"user_id": user_id})
        return {str(row.product_id) for row in result}
        
    async def _fetch_product_details(self, product_ids: List[str]) -> List[Product]:
        """Fetch product details for given IDs"""
        if not product_ids:
            return []
            
        query = select(Product).where(
            Product.id.in_(product_ids),
            Product.status == "active"
        )
        
        result = await self.db.execute(query)
        products = result.scalars().all()
        
        # Sort by the order of product_ids
        product_dict = {str(p.id): p for p in products}
        return [product_dict[pid] for pid in product_ids if pid in product_dict]
        
    async def _get_recommendation_reason(
        self,
        user_id: str,
        product_id: str
    ) -> str:
        """Get human-readable recommendation reason"""
        # Check various reasons
        reasons = []
        
        # Check if similar to purchased
        similar_purchased = await self.db.execute(
            text("""
            SELECT p.title
            FROM products p
            JOIN order_items oi ON p.id = oi.product_id
            JOIN orders o ON oi.order_id = o.id
            WHERE o.buyer_id = :user_id
            AND p.category_id = (SELECT category_id FROM products WHERE id = :product_id)
            LIMIT 1
            """),
            {"user_id": user_id, "product_id": product_id}
        )
        
        if similar_purchased.rowcount > 0:
            reasons.append("Similar to your previous purchases")
            
        # Check if trending
        product = await self.db.get(Product, product_id)
        if product and product.trending_score > 80:
            reasons.append("Trending now")
            
        # Check if frequently bought together
        fbt = await self.db.execute(
            text("""
            SELECT COUNT(*) as count
            FROM orders o
            JOIN order_items oi1 ON o.id = oi1.order_id
            JOIN order_items oi2 ON o.id = oi2.order_id
            WHERE oi1.product_id IN (
                SELECT product_id 
                FROM order_items oi 
                JOIN orders o ON oi.order_id = o.id 
                WHERE o.buyer_id = :user_id
            )
            AND oi2.product_id = :product_id
            """),
            {"user_id": user_id, "product_id": product_id}
        )
        
        if fbt.scalar() > 5:
            reasons.append("Frequently bought with your items")
            
        return " • ".join(reasons) if reasons else "Recommended for you"




# """Product recommendation engine"""

# from typing import List, Dict, Any, Optional
# import numpy as np
# from sklearn.metrics.pairwise import cosine_similarity
# from sklearn.feature_extraction.text import TfidfVectorizer
# import pandas as pd
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, and_, func

# from app.models import Product, Order, OrderItem, User, ProductView
# from app.core.cache import cache, cached

# class RecommendationEngine:
#     """ML-based product recommendation system"""
    
#     def __init__(self, db: AsyncSession):
#         self.db = db
        
#     @cached(key_prefix="recommendations:user", expire=3600)
#     async def get_user_recommendations(
#         self,
#         user_id: str,
#         limit: int = 20
#     ) -> List[Dict[str, Any]]:
#         """Get personalized recommendations for user"""
#         # Get user's purchase history
#         user_products = await self._get_user_interaction_products(user_id)
        
#         if not user_products:
#             # New user - return popular products
#             return await self.get_trending_products(limit)
            
#         # Collaborative filtering
#         collaborative_recs = await self._collaborative_filtering(
#             user_id,
#             user_products,
#             limit=limit * 2
#         )
        
#         # Content-based filtering
#         content_recs = await self._content_based_filtering(
#             user_products,
#             limit=limit * 2
#         )
        
#         # Merge and rank recommendations
#         recommendations = self._merge_recommendations(
#             collaborative_recs,
#             content_recs,
#             limit
#         )
        
#         return recommendations
        
#     async def get_similar_products(
#         self,
#         product_id: str,
#         limit: int = 10
#     ) -> List[Dict[str, Any]]:
#         """Get products similar to given product"""
#         product = await self.db.get(Product, product_id)
#         if not product:
#             return []
            
#         # Get all active products
#         all_products = await self.db.execute(
#             select(Product)
#             .where(
#                 and_(
#                     Product.status == "active",
#                     Product.id != product_id
#                 )
#             )
#         )
#         all_products = all_products.scalars().all()
        
#         # Calculate similarity scores
#         similarities = []
#         for other_product in all_products:
#             score = self._calculate_product_similarity(product, other_product)
#             similarities.append({
#                 "product": other_product,
#                 "score": score
#             })
            
#         # Sort by similarity
#         similarities.sort(key=lambda x: x["score"], reverse=True)
        
#         # Return top similar products
#         return [
#             {
#                 "id": str(item["product"].id),
#                 "title": item["product"].title,
#                 "price": item["product"].price,
#                 "thumbnail": item["product"].thumbnail,
#                 "similarity_score": item["score"]
#             }
#             for item in similarities[:limit]
#         ]
        
#     async def get_trending_products(
#         self,
#         limit: int = 20,
#         category_id: Optional[str] = None
#     ) -> List[Dict[str, Any]]:
#         """Get trending products based on recent activity"""
#         # Calculate trending score based on views, purchases, and recency
#         query = """
#         SELECT 
#             p.id,
#             p.title,
#             p.price,
#             p.thumbnail,
#             p.rating,
#             COUNT(DISTINCT pv.id) as view_count,
#             COUNT(DISTINCT oi.id) as purchase_count,
#             (
#                 COUNT(DISTINCT pv.id) * 0.3 +
#                 COUNT(DISTINCT oi.id) * 0.5 +
#                 COALESCE(p.rating, 0) * 0.2 +
#                 (1.0 / (EXTRACT(DAY FROM NOW() - p.created_at) + 1)) * 10
#             ) as trending_score
#         FROM products p
#         LEFT JOIN product_views pv ON p.id = pv.product_id 
#             AND pv.viewed_at > NOW() - INTERVAL '7 days'
#         LEFT JOIN order_items oi ON p.id = oi.product_id
#             AND oi.created_at > NOW() - INTERVAL '7 days'
#         WHERE p.status = 'active'
#         """
        
#         if category_id:
#             query += f" AND p.category_id = '{category_id}'"
            
#         query += """
#         GROUP BY p.id
#         ORDER BY trending_score DESC
#         LIMIT %s
#         """
        
#         result = await self.db.execute(query, (limit,))
        
#         return [
#             {
#                 "id": str(row.id),
#                 "title": row.title,
#                 "price": row.price,
#                 "thumbnail": row.thumbnail,
#                 "rating": row.rating,
#                 "trending_score": float(row.trending_score)
#             }
#             for row in result
#         ]
        
#     async def _get_user_interaction_products(self, user_id: str) -> List[str]:
#         """Get products user has interacted with"""
#         # Get purchased products
#         purchased = await self.db.execute(
#             select(OrderItem.product_id)
#             .join(Order)
#             .where(Order.buyer_id == user_id)
#             .distinct()
#         )
        
#         # Get viewed products
#         viewed = await self.db.execute(
#             select(ProductView.product_id)
#             .where(ProductView.user_id == user_id)
#             .order_by(ProductView.viewed_at.desc())
#             .limit(50)
#         )
        
#         product_ids = set()
#         product_ids.update(str(pid) for pid in purchased.scalars().all())
#         product_ids.update(str(pid) for pid in viewed.scalars().all())
        
#         return list(product_ids)
        
#     async def _collaborative_filtering(
#         self,
#         user_id: str,
#         user_products: List[str],
#         limit: int
#     ) -> List[Dict[str, Any]]:
#         """Collaborative filtering recommendations"""
#         # Find users with similar purchase patterns
#         similar_users_query = """
#         SELECT 
#             o.buyer_id,
#             COUNT(DISTINCT oi.product_id) as common_products
#         FROM orders o
#         JOIN order_items oi ON o.id = oi.order_id
#         WHERE o.buyer_id != %s
#             AND oi.product_id IN %s
#         GROUP BY o.buyer_id
#         ORDER BY common_products DESC
#         LIMIT 20
#         """
        
#         similar_users = await self.db.execute(
#             similar_users_query,
#             (user_id, tuple(user_products))
#         )
        
#         # Get products purchased by similar users
#         recommendations = {}
#         for similar_user in similar_users:
#             user_products_query = """
#             SELECT DISTINCT oi.product_id, p.title, p.price, p.thumbnail
#             FROM order_items oi
#             JOIN orders o ON oi.order_id = o.id
#             JOIN products p ON oi.product_id = p.id
#             WHERE o.buyer_id = %s
#                 AND oi.product_id NOT IN %s
#                 AND p.status = 'active'
#             """
            
#             products = await self.db.execute(
#                 user_products_query,
#                 (similar_user.buyer_id, tuple(user_products))
#             )
            
#             for product in products:
#                 if product.product_id not in recommendations:
#                     recommendations[product.product_id] = {
#                         "id": str(product.product_id),
#                         "title": product.title,
#                         "price": product.price,
#                         "thumbnail": product.thumbnail,
#                         "score": 0
#                     }
#                 recommendations[product.product_id]["score"] += similar_user.common_products
                
#         # Sort by score
#         sorted_recs = sorted(
#             recommendations.values(),
#             key=lambda x: x["score"],
#             reverse=True
#         )
        
#         return sorted_recs[:limit]
        
#     async def _content_based_filtering(
#         self,
#         user_products: List[str],
#         limit: int
#     ) -> List[Dict[str, Any]]:
#         """Content-based filtering recommendations"""
#         # Get user's products
#         user_product_features = await self.db.execute(
#             select(Product)
#             .where(Product.id.in_(user_products))
#         )
#         user_products_data = user_product_features.scalars().all()
        
#         # Get all products for comparison
#         all_products = await self.db.execute(
#             select(Product)
#             .where(
#                 and_(
#                     Product.status == "active",
#                     Product.id.notin_(user_products)
#                 )
#             )
#         )
#         all_products_data = all_products.scalars().all()
        
#         # Create feature vectors
#         recommendations = []
        
#         for product in all_products_data:
#             max_similarity = 0
            
#             for user_product in user_products_data:
#                 similarity = self._calculate_product_similarity(
#                     user_product,
#                     product
#                 )
#                 max_similarity = max(max_similarity, similarity)
                
#             if max_similarity > 0.3:  # Threshold
#                 recommendations.append({
#                     "id": str(product.id),
#                     "title": product.title,
#                     "price": product.price,
#                     "thumbnail": product.thumbnail,
#                     "score": max_similarity
#                 })
                
#         # Sort by similarity
#         recommendations.sort(key=lambda x: x["score"], reverse=True)
        
#         return recommendations[:limit]
        
#     def _calculate_product_similarity(
#         self,
#         product1: Product,
#         product2: Product
#     ) -> float:
#         """Calculate similarity between two products"""
#         score = 0.0
        
#         # Category similarity
#         if product1.category_id == product2.category_id:
#             score += 0.3
            
#         # Brand similarity
#         if product1.brand_id == product2.brand_id:
#             score += 0.2
            
#         # Price similarity (within 20% range)
#         price_ratio = min(product1.price, product2.price) / max(product1.price, product2.price)
#         if price_ratio > 0.8:
#             score += 0.2 * price_ratio
            
#         # Text similarity (title + description)
#         text_similarity = self._calculate_text_similarity(
#             f"{product1.title} {product1.description}",
#             f"{product2.title} {product2.description}"
#         )
#         score += 0.3 * text_similarity
        
#         return score
        
#     def _calculate_text_similarity(self, text1: str, text2: str) -> float:
#         """Calculate text similarity using TF-IDF"""
#         vectorizer = TfidfVectorizer()
#         tfidf_matrix = vectorizer.fit_transform([text1, text2])
#         similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
#         return similarity
        
#     def _merge_recommendations(
#         self,
#         collaborative: List[Dict],
#         content_based: List[Dict],
#         limit: int
#     ) -> List[Dict[str, Any]]:
#         """Merge and rank recommendations from different sources"""
#         all_recs = {}
        
#         # Add collaborative recommendations
#         for i, rec in enumerate(collaborative):
#             all_recs[rec["id"]] = {
#                 **rec,
#                 "final_score": rec["score"] * 0.6  # 60% weight
#             }
            
#         # Add content-based recommendations
#         for i, rec in enumerate(content_based):
#             if rec["id"] in all_recs:
#                 all_recs[rec["id"]]["final_score"] += rec["score"] * 0.4
#             else:
#                 all_recs[rec["id"]] = {
#                     **rec,
#                     "final_score": rec["score"] * 0.4  # 40% weight
#                 }
                
#         # Sort by final score
#         sorted_recs = sorted(
#             all_recs.values(),
#             key=lambda x: x["final_score"],
#             reverse=True
#         )
        
#         return sorted_recs[:limit]
