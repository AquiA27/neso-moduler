# backend/app/services/api_usage_tracker.py
"""API kullanım takibi servisi"""
from typing import Optional, Dict, Any
from datetime import datetime
from ..db.database import db
import logging


async def log_api_usage(
    isletme_id: int,
    api_type: str,
    model: Optional[str] = None,
    endpoint: Optional[str] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    cost_usd: float = 0.0,
    request_count: int = 1,
    response_time_ms: Optional[int] = None,
    status: str = "success",
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """API kullanımını logla"""
    try:
        await db.execute(
            """
            INSERT INTO api_usage_logs (
                isletme_id, api_type, model, endpoint,
                prompt_tokens, completion_tokens, total_tokens, cost_usd,
                request_count, response_time_ms, status, error_message, metadata
            )
            VALUES (
                :isletme_id, :api_type, :model, :endpoint,
                :prompt_tokens, :completion_tokens, :total_tokens, :cost_usd,
                :request_count, :response_time_ms, :status, :error_message, CAST(:metadata AS JSONB)
            )
            """,
            {
                "isletme_id": isletme_id,
                "api_type": api_type,
                "model": model,
                "endpoint": endpoint or "/v1/chat/completions",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": cost_usd,
                "request_count": request_count,
                "response_time_ms": response_time_ms,
                "status": status,
                "error_message": error_message,
                "metadata": metadata or {},
            },
        )
    except Exception as e:
        logging.error(f"Failed to log API usage: {e}", exc_info=True)


async def get_api_usage_stats(
    isletme_id: Optional[int] = None,
    days: int = 30,
    api_type: Optional[str] = None,
) -> Dict[str, Any]:
    """API kullanım istatistiklerini getir"""
    try:
        from datetime import timedelta
        start_date = datetime.now() - timedelta(days=days)
        
        query = """
            SELECT 
                isletme_id,
                api_type,
                model,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(cost_usd) as total_cost_usd,
                SUM(request_count) as total_requests,
                AVG(response_time_ms) as avg_response_time_ms,
                COUNT(*) FILTER (WHERE status = 'success') as success_count,
                COUNT(*) FILTER (WHERE status = 'error') as error_count
            FROM api_usage_logs
            WHERE created_at >= :start_date
        """
        params = {"start_date": start_date}
        
        if isletme_id:
            query += " AND isletme_id = :isletme_id"
            params["isletme_id"] = isletme_id
        
        if api_type:
            query += " AND api_type = :api_type"
            params["api_type"] = api_type
        
        query += """
            GROUP BY isletme_id, api_type, model
            ORDER BY total_cost_usd DESC
        """
        
        rows = await db.fetch_all(query, params)
        return [dict(row) for row in rows]
    except Exception as e:
        logging.error(f"Failed to get API usage stats: {e}", exc_info=True)
        return []

