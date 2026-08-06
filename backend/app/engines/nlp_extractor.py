import json
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ValidationError

from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)

class StructuredNews(BaseModel):
    event_type: str = Field(description="Kategori berita (misal: REGULATORY, MACRO, HACK, ADOPTION, SENTIMENT)")
    sentiment_score: float = Field(description="Skor sentimen dari -1.0 (sangat negatif) ke 1.0 (sangat positif)")
    impact_level: str = Field(description="Tingkat dampak: LOW, MEDIUM, HIGH, atau CRITICAL")
    summary: str = Field(description="Ringkasan 1 kalimat yang sudah bersih dari noise/link")

def _get_nvidia_client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=settings.NVIDIA_API_KEY,
    )

async def extract_news_structure(title: str, source: str) -> Optional[StructuredNews]:
    """
    Ekstrak metadata berita menggunakan model Nemotron via API terpisah.
    Fallback: Jika gagal parsing, kembalikan None (caller akan handle fallback).
    """
    if not title:
        return None
        
    client = _get_nvidia_client()
    system_prompt = (
        "You are a strict financial news NLP parser. "
        "Extract the event_type, sentiment_score (-1.0 to 1.0), impact_level (LOW, MEDIUM, HIGH, CRITICAL), "
        "and a clean 1-sentence summary from the provided news headline. "
        "You MUST output ONLY a valid JSON object matching this schema, with no markdown formatting or backticks:\n"
        '{"event_type": "str", "sentiment_score": "float", "impact_level": "str", "summary": "str"}'
    )
    
    user_prompt = f"Source: {source}\nHeadline: {title}"
    
    try:
        # Panggilan API terpisah dari reasoner utama
        response = await client.chat.completions.create(
            model="nvidia/nemotron-3-ultra-550b-a55b", # Bisa diganti model lebih kecil jika ada
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            max_tokens=150,
        )
        
        raw_text = response.choices[0].message.content.strip()
        
        # Bersihkan markdown if present
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`").replace("json", "", 1).strip()
            
        data = json.loads(raw_text)
        
        # Validasi Pydantic
        parsed = StructuredNews(**data)
        return parsed
        
    except ValidationError as ve:
        logger.warning(f"NLP Extractor Pydantic validation failed for '{title}': {ve}")
        return None
    except json.JSONDecodeError as je:
        logger.warning(f"NLP Extractor JSON decode failed for '{title}': {je}")
        return None
    except Exception as e:
        logger.error(f"NLP Extractor API call failed: {e}")
        return None
