"""Complete search service with Elasticsearch"""

from typing import List, Dict, Any, Optional, Tuple
from elasticsearch import AsyncElasticsearch, helpers
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
import logging
import json
from datetime import datetime

from app.core.config import settings
from app.models.product import Product
from app.models.category import Category

logger = logging.getLogger(__name__)

class SearchService:
    """Complete search service with Elasticsearch"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.es = AsyncElasticsearch([settings.ELASTICSEARCH_URL])
        self.index_prefix = "quickcart_"
        
    async def initialize_indices(self):
        """Initialize Elasticsearch indices with proper mappings"""
        # Products index mapping
        products_mapping = {
            "settings": {
                "analysis": {
                    "analyzer": {
                        "autocomplete": {
                            "tokenizer": "autocomplete",
                            "filter": ["lowercase"]
                        },
                        "autocomplete_search": {
                            "tokenizer": "lowercase"
                        }
                    },
                    "tokenizer": {
                        "autocomplete": {
                            "type": "edge_ngram",
                            "min_gram": 2,
                            "max_gram": 10,
                            "token_chars": ["letter", "digit"]
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "title": {
                        "type": "text",
                        "analyzer": "standard",
                        "fields": {
                            "autocomplete": {
                                "type": "text",
                                "analyzer": "autocomplete",
                                "search_analyzer": "autocomplete_search"
                            },
                            "keyword": {"type": "keyword"}
                        }
                    },
                    "description": {"type": "text"},
                    "category": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}}
                    },
                    "category_id": {"type": "keyword"},
                    "brand": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}}
                    },
                    "price": {"type": "float"},
                    "mrp": {"type": "float"},
                    "discount_percentage": {"type": "float"},
                    "rating": {"type": "float"},
                    "review_count": {"type": "integer"},
                    "tags": {"type": "keyword"},
                    "attributes": {"type": "object", "enabled": False},
                    "seller_id": {"type": "keyword"},
                    "seller_name": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}}
                    },
                    "stock": {"type": "integer"},
                    "is_active": {"type": "boolean"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                    "view_count": {"type": "integer"},
                    "purchase_count": {"type": "integer"},
                    "trending_score": {"type": "float"},
                    "location": {"type": "geo_point"},
                    "search_keywords": {"type": "text"}
                }
            }
        }
        
        # Create products index
        await self.es.indices.create(
            index=f"{self.index_prefix}products",
            body=products_mapping,
            ignore=400  # Ignore if already exists
        )
        
        # Categories index mapping
        categories_mapping = {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {
                        "type": "text",
                        "fields": {
                            "autocomplete": {
                                "type": "text",
                                "analyzer": "autocomplete",
                                "search_analyzer": "autocomplete_search"
                            },
                            "keyword": {"type": "keyword"}
                        }
                    },
                    "path": {"type": "text"},
                    "parent_id": {"type": "keyword"},
                    "level": {"type": "integer"},
                    "product_count": {"type": "integer"}
                }
            }
        }
        
        await self.es.indices.create(
            index=f"{self.index_prefix}categories",
            body=categories_mapping,
            ignore=400
        )
        
        logger.info("Elasticsearch indices initialized")
        
    async def search_products(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "relevance",
        page: int = 1,
        size: int = 20,
        user_id: Optional[str] = None,
        include_facets: bool = True
    ) -> Dict[str, Any]:
        """Advanced product search"""
        try:
            # Build search query
            search_body = self._build_search_query(query, filters, sort_by)
            
            # Add personalization
            if user_id:
                search_body = await self._personalize_search(search_body, user_id)
                
            # Add facets/aggregations
            if include_facets:
                search_body["aggs"] = self._build_aggregations()
                
            # Execute search
            response = await self.es.search(
                index=f"{self.index_prefix}products",
                body=search_body,
                from_=(page - 1) * size,
                size=size,
                track_total_hits=True
            )
            
            # Process results
            results = self._process_search_results(response, include_facets)
            
            # Log search for analytics
            await self._log_search(user_id, query, results["total"])
            
            # Get suggestions if few results
            if results["total"] < 5 and query:
                results["did_you_mean"] = await self.get_search_suggestions(query)
                
            return results
            
        except Exception as e:
            logger.error(f"Elasticsearch error: {str(e)}")
            # Fallback to database search
            return await self._fallback_database_search(query, filters, page, size)
            
    def _build_search_query(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        sort_by: str
    ) -> Dict[str, Any]:
        """Build Elasticsearch query with advanced features"""
        # Base query
        must_queries = []
        should_queries = []
        
        if query:
            # Multi-match with boosting
            must_queries.append({
                "multi_match": {
                    "query": query,
                    "fields": [
                        "title^3",
                        "title.autocomplete^2",
                        "brand^2",
                        "category^2",
                        "description",
                        "tags",
                        "search_keywords"
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "prefix_length": 2
                }
            })
            
            # Phrase matching for exact matches
            should_queries.append({
                "match_phrase": {
                    "title": {
                        "query": query,
                        "boost": 2
                    }
                }
            })
            
        # Filters
        filter_queries = [{"term": {"is_active": True}}]
        
        if filters:
            # Category filter with hierarchy
            if filters.get("category_id"):
                category_ids = await self._get_category_hierarchy(filters["category_id"])
                filter_queries.append({
                    "terms": {"category_id": category_ids}
                })
                
            # Price range
            price_filter = {}
            if filters.get("min_price"):
                price_filter["gte"] = filters["min_price"]
            if filters.get("max_price"):
                price_filter["lte"] = filters["max_price"]
            if price_filter:
                filter_queries.append({"range": {"price": price_filter}})
                
            # Brands
            if filters.get("brands"):
                filter_queries.append({
                    "terms": {"brand.keyword": filters["brands"]}
                })
                
            # Rating
            if filters.get("min_rating"):
                filter_queries.append({
                    "range": {"rating": {"gte": filters["min_rating"]}}
                })
                
            # Stock
            if filters.get("in_stock"):
                filter_queries.append({
                    "range": {"stock": {"gt": 0}}
                })
                
            # Location-based search
            if filters.get("location") and filters.get("radius"):
                filter_queries.append({
                    "geo_distance": {
                        "distance": f"{filters['radius']}km",
                        "location": filters["location"]
                    }
                })
                
            # Attributes
            if filters.get("attributes"):
                for attr_key, attr_value in filters["attributes"].items():
                    filter_queries.append({
                        "term": {f"attributes.{attr_key}": attr_value}
                    })
                    
        # Build final query
        search_body = {
            "query": {
                "bool": {
                    "must": must_queries,
                    "should": should_queries,
                    "filter": filter_queries,
                    "minimum_should_match": 0 if must_queries else 1
                }
            }
        }
        
        # Function score for relevance tuning
        search_body = {
            "query": {
                "function_score": {
                    "query": search_body["query"],
                    "functions": [
                        {
                            "field_value_factor": {
                                "field": "rating",
                                "factor": 1.2,
                                "modifier": "sqrt",
                                "missing": 1
                            }
                        },
                        {
                            "field_value_factor": {
                                "field": "purchase_count",
                                "factor": 1.1,
                                "modifier": "log1p",
                                "missing": 0
                            }
                        }
                    ],
                    "score_mode": "sum",
                    "boost_mode": "multiply"
                }
            }
        }
        
        # Sorting
        sort_options = {
            "relevance": ["_score", {"rating": "desc"}],
            "price_low": [{"price": "asc"}, "_score"],
            "price_high": [{"price": "desc"}, "_score"],
            "rating": [{"rating": "desc"}, "_score"],
            "newest": [{"created_at": "desc"}, "_score"],
            "trending": [{"trending_score": "desc"}, "_score"],
            "distance": [{"_geo_distance": {"location": filters.get("location", {"lat": 0, "lon": 0}), "order": "asc"}}, "_score"]
        }
        
        search_body["sort"] = sort_options.get(sort_by, sort_options["relevance"])
        
        # Highlighting
        search_body["highlight"] = {
            "fields": {
                "title": {"number_of_fragments": 0},
                "description": {"fragment_size": 150}
            }
        }
        
        return search_body
        
    def _build_aggregations(self) -> Dict[str, Any]:
        """Build search facets/aggregations"""
        return {
            "categories": {
                "terms": {
                    "field": "category_id",
                    "size": 20
                },
                "aggs": {
                    "category_name": {
                        "top_hits": {
                            "size": 1,
                            "_source": ["category"]
                        }
                    }
                }
            },
            "brands": {
                "terms": {
                    "field": "brand.keyword",
                    "size": 20,
                    "min_doc_count": 2
                }
            },
            "price_ranges": {
                "range": {
                    "field": "price",
                    "ranges": [
                        {"key": "Under ₹100", "to": 100},
                        {"key": "₹100-₹500", "from": 100, "to": 500},
                        {"key": "₹500-₹1000", "from": 500, "to": 1000},
                        {"key": "₹1000-₹5000", "from": 1000, "to": 5000},
                        {"key": "Above ₹5000", "from": 5000}
                    ]
                }
            },
            "price_stats": {
                "stats": {"field": "price"}
            },
            "ratings": {
                "range": {
                    "field": "rating",
                    "ranges": [
                        {"key": "4★ & above", "from": 4},
                        {"key": "3★ & above", "from": 3},
                        {"key": "2★ & above", "from": 2}
                    ]
                }
            },
            "discount_ranges": {
                "range": {
                    "field": "discount_percentage",
                    "ranges": [
                        {"key": "10% & above", "from": 10},
                        {"key": "20% & above", "from": 20},
                        {"key": "30% & above", "from": 30},
                        {"key": "50% & above", "from": 50}
                    ]
                }
            }
        }
        
    def _process_search_results(
        self,
        response: Dict[str, Any],
        include_facets: bool
    ) -> Dict[str, Any]:
        """Process Elasticsearch response"""
        results = {
            "total": response["hits"]["total"]["value"],
            "products": [],
            "took_ms": response["took"]
        }
        
        # Process hits
        for hit in response["hits"]["hits"]:
            product = hit["_source"]
            product["_score"] = hit["_score"]
            
            # Add highlights
            if "highlight" in hit:
                product["_highlights"] = hit["highlight"]
                
            results["products"].append(product)
            
        # Process facets
        if include_facets and "aggregations" in response:
            facets = {}
            
            # Categories
            if "categories" in response["aggregations"]:
                facets["categories"] = []
                for bucket in response["aggregations"]["categories"]["buckets"]:
                    category_name = bucket["category_name"]["hits"]["hits"][0]["_source"]["category"] if bucket["category_name"]["hits"]["hits"] else "Unknown"
                    facets["categories"].append({
                        "id": bucket["key"],
                        "name": category_name,
                        "count": bucket["doc_count"]
                    })
                    
            # Brands
            if "brands" in response["aggregations"]:
                facets["brands"] = [
                    {"name": b["key"], "count": b["doc_count"]}
                    for b in response["aggregations"]["brands"]["buckets"]
                ]
                
            # Price ranges
            if "price_ranges" in response["aggregations"]:
                facets["price_ranges"] = [
                    {"range": b["key"], "count": b["doc_count"]}
                    for b in response["aggregations"]["price_ranges"]["buckets"]
                    if b["doc_count"] > 0
                ]
                
            # Price stats
            if "price_stats" in response["aggregations"]:
                facets["price_stats"] = response["aggregations"]["price_stats"]
                
            # Ratings
            if "ratings" in response["aggregations"]:
                facets["ratings"] = [
                    {"range": b["key"], "count": b["doc_count"]}
                    for b in response["aggregations"]["ratings"]["buckets"]
                    if b["doc_count"] > 0
                ]
                
            results["facets"] = facets
            
        return results
        
    async def autocomplete(
        self,
        prefix: str,
        max_results: int = 10,
        include_categories: bool = True
    ) -> List[Dict[str, Any]]:
        """Autocomplete suggestions"""
        try:
            # Product suggestions
            product_query = {
                "multi_match": {
                    "query": prefix,
                    "type": "bool_prefix",
                    "fields": [
                        "title^3",
                        "title.autocomplete^2",
                        "brand^2",
                        "category"
                    ]
                }
            }
            
            search_body = {
                "query": {
                    "bool": {
                        "must": [product_query],
                        "filter": [{"term": {"is_active": True}}]
                    }
                },
                "_source": ["title", "category", "brand", "primary_image", "price"],
                "size": max_results
            }
            
            # Add suggestion aggregation
            search_body["suggest"] = {
                "title_suggest": {
                    "prefix": prefix,
                    "completion": {
                        "field": "title.suggest",
                        "size": 5,
                        "skip_duplicates": True
                    }
                }
            }
            
            response = await self.es.search(
                index=f"{self.index_prefix}products",
                body=search_body
            )
            
            suggestions = []
            
            # Add product results
            for hit in response["hits"]["hits"]:
                suggestions.append({
                    "type": "product",
                    "id": hit["_source"].get("id", hit["_id"]),
                    "title": hit["_source"]["title"],
                    "category": hit["_source"].get("category"),
                    "brand": hit["_source"].get("brand"),
                    "image": hit["_source"].get("primary_image"),
                    "price": hit["_source"].get("price")
                })
                
            # Add category suggestions
            if include_categories:
                category_suggestions = await self._autocomplete_categories(prefix)
                suggestions.extend(category_suggestions[:3])
                
            # Add completion suggestions
            if "suggest" in response and "title_suggest" in response["suggest"]:
                for suggestion in response["suggest"]["title_suggest"][0]["options"]:
                    suggestions.append({
                        "type": "search",
                        "text": suggestion["text"],
                        "score": suggestion["_score"]
                    })
                    
            return suggestions[:max_results]
            
        except Exception as e:
            logger.error(f"Autocomplete error: {str(e)}")
            return []
            
    async def _autocomplete_categories(self, prefix: str) -> List[Dict[str, Any]]:
        """Get category autocomplete suggestions"""
        try:
            search_body = {
                "query": {
                    "match": {
                        "name.autocomplete": {
                            "query": prefix,
                            "analyzer": "autocomplete_search"
                        }
                    }
                },
                "_source": ["name", "path", "product_count"],
                "size": 5
            }
            
            response = await self.es.search(
                index=f"{self.index_prefix}categories",
                body=search_body
            )
            
            categories = []
            for hit in response["hits"]["hits"]:
                categories.append({
                    "type": "category",
                    "id": hit["_id"],
                    "name": hit["_source"]["name"],
                    "path": hit["_source"].get("path"),
                    "product_count": hit["_source"].get("product_count", 0)
                })
                
            return categories
            
        except Exception as e:
            logger.error(f"Category autocomplete error: {str(e)}")
            return []



# """Advanced search service with Elasticsearch"""

# from typing import List, Dict, Any, Optional
# from elasticsearch import AsyncElasticsearch
# from elasticsearch.helpers import async_bulk
# import asyncio
# from datetime import datetime

# from app.core.config import settings
# from app.models import Product

# class SearchService:
#     """Elasticsearch service for advanced search"""
    
#     def __init__(self):
#         self.es = AsyncElasticsearch([settings.ELASTICSEARCH_URL])
#         self.index_name = "quickcart_products"
        
#     async def create_index(self):
#         """Create Elasticsearch index with mappings"""
#         mappings = {
#             "properties": {
#                 "id": {"type": "keyword"},
#                 "title": {
#                     "type": "text",
#                     "analyzer": "standard",
#                     "fields": {
#                         "keyword": {"type": "keyword"},
#                         "suggest": {"type": "completion"}
#                     }
#                 },
#                 "description": {"type": "text"},
#                 "category": {"type": "keyword"},
#                 "brand": {"type": "keyword"},
#                 "tags": {"type": "keyword"},
#                 "price": {"type": "float"},
#                 "rating": {"type": "float"},
#                 "features": {"type": "nested"},
#                 "created_at": {"type": "date"},
#                 "popularity_score": {"type": "float"},
#                 "embedding": {
#                     "type": "dense_vector",
#                     "dims": 384  # For semantic search
#                 }
#             }
#         }
        
#         if not await self.es.indices.exists(index=self.index_name):
#             await self.es.indices.create(
#                 index=self.index_name,
#                 mappings=mappings
#             )
            
#     async def index_product(self, product: Product):
#         """Index a single product"""
#         doc = {
#             "id": str(product.id),
#             "title": product.title,
#             "description": product.description,
#             "category": product.category.name if product.category else None,
#             "brand": product.brand.name if product.brand else None,
#             "tags": product.tags,
#             "price": float(product.price),
#             "rating": float(product.rating) if product.rating else 0,
#             "created_at": product.created_at,
#             "popularity_score": self._calculate_popularity(product)
#         }
        
#         await self.es.index(
#             index=self.index_name,
#             id=str(product.id),
#             document=doc
#         )
        
#     async def search_products(
#         self,
#         query: str,
#         filters: Optional[Dict[str, Any]] = None,
#         size: int = 20,
#         from_: int = 0,
#         sort_by: Optional[str] = None
#     ) -> Dict[str, Any]:
#         """Advanced product search"""
#         # Build query
#         must_conditions = []
        
#         # Multi-match query for text search
#         if query:
#             must_conditions.append({
#                 "multi_match": {
#                     "query": query,
#                     "fields": ["title^3", "description", "tags^2", "brand^2"],
#                     "type": "best_fields",
#                     "fuzziness": "AUTO"
#                 }
#             })
            
#         # Apply filters
#         if filters:
#             if filters.get("category"):
#                 must_conditions.append({"term": {"category": filters["category"]}})
#             if filters.get("brand"):
#                 must_conditions.append({"term": {"brand": filters["brand"]}})
#             if filters.get("min_price") or filters.get("max_price"):
#                 price_range = {}
#                 if filters.get("min_price"):
#                     price_range["gte"] = filters["min_price"]
#                 if filters.get("max_price"):
#                     price_range["lte"] = filters["max_price"]
#                 must_conditions.append({"range": {"price": price_range}})
#             if filters.get("min_rating"):
#                 must_conditions.append({"range": {"rating": {"gte": filters["min_rating"]}}})
                
#         # Build final query
#         search_query = {
#             "bool": {
#                 "must": must_conditions
#             }
#         } if must_conditions else {"match_all": {}}
        
#         # Sorting
#         sort = []
#         if sort_by == "price_asc":
#             sort.append({"price": "asc"})
#         elif sort_by == "price_desc":
#             sort.append({"price": "desc"})
#         elif sort_by == "rating":
#             sort.append({"rating": "desc"})
#         elif sort_by == "newest":
#             sort.append({"created_at": "desc"})
#         else:
#             # Default: relevance + popularity
#             sort.append("_score")
#             sort.append({"popularity_score": "desc"})
            
#         # Execute search
#         result = await self.es.search(
#             index=self.index_name,
#             query=search_query,
#             sort=sort,
#             size=size,
#             from_=from_,
#             highlight={
#                 "fields": {
#                     "title": {},
#                     "description": {"fragment_size": 150}
#                 }
#             },
#             aggs={
#                 "categories": {"terms": {"field": "category", "size": 10}},
#                 "brands": {"terms": {"field": "brand", "size": 10}},
#                 "price_ranges": {
#                     "range": {
#                         "field": "price",
#                         "ranges": [
#                             {"to": 1000},
#                             {"from": 1000, "to": 5000},
#                             {"from": 5000, "to": 10000},
#                             {"from": 10000}
#                         ]
#                     }
#                 }
#             }
#         )
        
#         return {
#             "total": result["hits"]["total"]["value"],
#             "products": [hit["_source"] for hit in result["hits"]["hits"]],
#             "aggregations": result["aggregations"]
#         }
        
#     async def suggest_products(self, prefix: str, size: int = 5) -> List[str]:
#         """Product title suggestions for autocomplete"""
#         result = await self.es.search(
#             index=self.index_name,
#             suggest={
#                 "product_suggest": {
#                     "prefix": prefix,
#                     "completion": {
#                         "field": "title.suggest",
#                         "size": size
#                     }
#                 }
#             }
#         )
        
#         suggestions = []
#         for option in result["suggest"]["product_suggest"][0]["options"]:
#             suggestions.append(option["text"])
            
#         return suggestions
        
#     async def semantic_search(
#         self,
#         query_embedding: List[float],
#         size: int = 20
#     ) -> List[Dict[str, Any]]:
#         """Semantic search using embeddings"""
#         result = await self.es.search(
#             index=self.index_name,
#             knn={
#                 "field": "embedding",
#                 "query_vector": query_embedding,
#                 "k": size,
#                 "num_candidates": 100
#             }
#         )
        
#         return [hit["_source"] for hit in result["hits"]["hits"]]
        
#     def _calculate_popularity(self, product: Product) -> float:
#         """Calculate product popularity score"""
#         # Factors: views, purchases, rating, recency
#         view_score = min(product.view_count / 1000, 1.0) * 0.3
#         purchase_score = min(product.purchase_count / 100, 1.0) * 0.4
#         rating_score = (product.rating or 0) / 5 * 0.2
        
#         # Recency boost
#         days_old = (datetime.utcnow() - product.created_at).days
#         recency_score = max(0, 1 - (days_old / 365)) * 0.1
        
#         return view_score + purchase_score + rating_score + recency_score
