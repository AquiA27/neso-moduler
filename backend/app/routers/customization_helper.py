"""Helper functions for customization endpoints to handle new assistant-specific columns."""
from typing import Dict, Any, List, Optional, Tuple
from ..db.database import db


async def check_assistant_columns() -> Dict[str, bool]:
    """Check which assistant-specific columns exist in the database."""
    try:
        rows = await db.fetch_all(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tenant_customizations' 
            AND column_name LIKE '%assistant%'
            """
        )
        existing_columns = {row["column_name"] for row in rows}
        
        return {
            "customer_assistant_openai_api_key": "customer_assistant_openai_api_key" in existing_columns,
            "customer_assistant_openai_model": "customer_assistant_openai_model" in existing_columns,
            "customer_assistant_tts_voice_id": "customer_assistant_tts_voice_id" in existing_columns,
            "customer_assistant_tts_speech_rate": "customer_assistant_tts_speech_rate" in existing_columns,
            "customer_assistant_tts_provider": "customer_assistant_tts_provider" in existing_columns,
            "business_assistant_openai_api_key": "business_assistant_openai_api_key" in existing_columns,
            "business_assistant_openai_model": "business_assistant_openai_model" in existing_columns,
            "business_assistant_tts_voice_id": "business_assistant_tts_voice_id" in existing_columns,
            "business_assistant_tts_speech_rate": "business_assistant_tts_speech_rate" in existing_columns,
            "business_assistant_tts_provider": "business_assistant_tts_provider" in existing_columns,
        }
    except Exception:
        return {}


async def get_select_fields(has_openai_columns: bool, has_assistant_columns: Dict[str, bool]) -> str:
    """Get SELECT fields for customization query."""
    base_fields = "id, isletme_id, domain, app_name, logo_url, primary_color, secondary_color, footer_text, email, telefon, adres"
    
    fields = [base_fields]
    
    if has_openai_columns:
        fields.append("openai_api_key, openai_model")
    
    if has_assistant_columns.get("customer_assistant_openai_api_key"):
        fields.append("customer_assistant_openai_api_key, customer_assistant_openai_model")
    if has_assistant_columns.get("customer_assistant_tts_voice_id"):
        fields.append("customer_assistant_tts_voice_id, customer_assistant_tts_speech_rate, customer_assistant_tts_provider")
    
    if has_assistant_columns.get("business_assistant_openai_api_key"):
        fields.append("business_assistant_openai_api_key, business_assistant_openai_model")
    if has_assistant_columns.get("business_assistant_tts_voice_id"):
        fields.append("business_assistant_tts_voice_id, business_assistant_tts_speech_rate, business_assistant_tts_provider")
    
    fields.append("meta_settings, created_at, updated_at")
    return ", ".join(fields)


def add_default_assistant_fields(row_dict: Dict[str, Any], has_assistant_columns: Dict[str, bool]) -> Dict[str, Any]:
    """Add default values for missing assistant columns."""
    defaults = {
        "customer_assistant_openai_api_key": None,
        "customer_assistant_openai_model": "gpt-4o-mini",
        "customer_assistant_tts_voice_id": None,
        "customer_assistant_tts_speech_rate": 1.0,
        "customer_assistant_tts_provider": "system",
        "business_assistant_openai_api_key": None,
        "business_assistant_openai_model": "gpt-4o-mini",
        "business_assistant_tts_voice_id": None,
        "business_assistant_tts_speech_rate": 1.0,
        "business_assistant_tts_provider": "system",
    }
    
    for key, default_value in defaults.items():
        if key not in row_dict:
            row_dict[key] = default_value
    
    return row_dict

