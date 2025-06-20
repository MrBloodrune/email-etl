import logging
from typing import List, Dict, Any, Optional
import numpy as np
from openai import OpenAI
import tiktoken
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import config

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings for email content using OpenAI"""
    
    def __init__(self):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.EMBEDDING_MODEL
        self.dimension = config.EMBEDDING_DIMENSION
        self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")  # Good approximation for embeddings
        self.max_tokens = 8191  # Max for text-embedding-3-small
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60)
    )
    def generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text with retry logic"""
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return np.zeros(self.dimension)
        
        # Truncate if too long
        text = self._truncate_text(text)
        
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )
            
            embedding = response.data[0].embedding
            return np.array(embedding)
        
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def generate_batch_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings for multiple texts"""
        if not texts:
            return []
        
        # Filter and truncate texts
        processed_texts = []
        empty_indices = []
        
        for i, text in enumerate(texts):
            if text and text.strip():
                processed_texts.append(self._truncate_text(text))
            else:
                empty_indices.append(i)
        
        if not processed_texts:
            return [np.zeros(self.dimension) for _ in texts]
        
        try:
            # OpenAI supports batch embedding
            response = self.client.embeddings.create(
                model=self.model,
                input=processed_texts,
                encoding_format="float"
            )
            
            embeddings = [np.array(data.embedding) for data in response.data]
            
            # Reinsert zero vectors for empty texts
            result = []
            processed_idx = 0
            for i in range(len(texts)):
                if i in empty_indices:
                    result.append(np.zeros(self.dimension))
                else:
                    result.append(embeddings[processed_idx])
                    processed_idx += 1
            
            return result
        
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            # Fall back to individual generation
            return [self.generate_embedding(text) for text in texts]
    
    def _truncate_text(self, text: str) -> str:
        """Truncate text to fit within token limits"""
        tokens = self.encoding.encode(text)
        
        if len(tokens) <= self.max_tokens:
            return text
        
        # Truncate and decode
        truncated_tokens = tokens[:self.max_tokens]
        truncated_text = self.encoding.decode(truncated_tokens)
        
        logger.warning(f"Text truncated from {len(tokens)} to {self.max_tokens} tokens")
        return truncated_text
    
    def prepare_email_text(self, email_data: Dict[str, Any]) -> str:
        """Prepare email text for embedding generation"""
        # Combine relevant fields for embedding
        parts = []
        
        # Subject is important for semantic search
        if email_data.get('subject'):
            parts.append(f"Subject: {email_data['subject']}")
        
        # Sender information
        if email_data.get('sender_name'):
            parts.append(f"From: {email_data['sender_name']} ({email_data.get('sender', '')})")
        elif email_data.get('sender'):
            parts.append(f"From: {email_data['sender']}")
        
        # Recipients (limited to avoid token overflow)
        recipients = email_data.get('recipients', [])[:5]  # Limit to 5
        if recipients:
            parts.append(f"To: {', '.join(recipients)}")
        
        # Date
        if email_data.get('date'):
            parts.append(f"Date: {email_data['date'].strftime('%Y-%m-%d')}")
        
        # Body content
        body = email_data.get('body_markdown') or email_data.get('body_plain', '')
        if body:
            # Clean and truncate body
            body = body.strip()
            if len(body) > 10000:  # Rough character limit
                body = body[:10000] + "..."
            parts.append(f"\nContent:\n{body}")
        
        # Labels can provide context
        if email_data.get('labels'):
            important_labels = [l for l in email_data['labels'] 
                              if l.upper() not in ['INBOX', 'SENT', 'UNREAD']]
            if important_labels:
                parts.append(f"Labels: {', '.join(important_labels)}")
        
        return "\n".join(parts)
    
    def calculate_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings"""
        if embedding1.size == 0 or embedding2.size == 0:
            return 0.0
        
        # Normalize vectors
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        # Calculate cosine similarity
        similarity = np.dot(embedding1, embedding2) / (norm1 * norm2)
        
        return float(similarity)
    
    def find_similar_emails(self, 
                           query_embedding: np.ndarray,
                           email_embeddings: List[Tuple[int, np.ndarray]],
                           top_k: int = 10,
                           threshold: float = 0.7) -> List[Tuple[int, float]]:
        """Find similar emails based on embedding similarity"""
        similarities = []
        
        for email_id, embedding in email_embeddings:
            if embedding.size > 0:
                similarity = self.calculate_similarity(query_embedding, embedding)
                if similarity >= threshold:
                    similarities.append((email_id, similarity))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def get_token_count(self, text: str) -> int:
        """Get token count for text"""
        return len(self.encoding.encode(text))
    
    def estimate_cost(self, text_count: int, avg_tokens_per_text: int = 500) -> Dict[str, float]:
        """Estimate embedding generation cost"""
        # Pricing for text-embedding-3-small as of 2024
        price_per_million_tokens = 0.02  # $0.02 per 1M tokens
        
        total_tokens = text_count * avg_tokens_per_text
        cost = (total_tokens / 1_000_000) * price_per_million_tokens
        
        return {
            'text_count': text_count,
            'estimated_tokens': total_tokens,
            'estimated_cost_usd': round(cost, 4)
        }


# Global embedding generator
embedding_generator = EmbeddingGenerator()