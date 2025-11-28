# backend/app/services/api_tracking.py
"""
API kullanım takibi ve maliyet hesaplama servisi
"""
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

from ..db.database import db


async def log_api_usage(
    isletme_id: int,
    api_key_id: Optional[int],
    api_type: str,  # 'rest_api', 'openai', vb.
    endpoint: str,
    method: str = "POST",
    status: str = "success",
    status_code: int = 200,
    response_time_ms: Optional[int] = None,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    cost_tl: float = 0.0,  # TL cinsinden maliyet (sipariş başına ücret)
    cost_usd: float = 0.0,  # USD cinsinden maliyet (LLM için)
    model: Optional[str] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
) -> None:
    """
    API kullanımını loglar.
    """
    try:
        await db.execute(
            """
            INSERT INTO api_usage_logs (
                isletme_id, api_key_id, api_type, endpoint, method,
                status, status_code, response_time_ms, error_message,
                metadata, cost_tl, cost_usd,
                model, prompt_tokens, completion_tokens, total_tokens,
                request_count, created_at
            )
            VALUES (
                :isletme_id, :api_key_id, :api_type, :endpoint, :method,
                :status, :status_code, :response_time_ms, :error_message,
                CAST(:metadata AS JSONB), :cost_tl, :cost_usd,
                :model, :prompt_tokens, :completion_tokens, :total_tokens,
                1, NOW()
            )
            """,
            {
                "isletme_id": isletme_id,
                "api_key_id": api_key_id,
                "api_type": api_type,
                "endpoint": endpoint,
                "method": method,
                "status": status,
                "status_code": status_code,
                "response_time_ms": response_time_ms,
                "error_message": error_message,
                "metadata": str(metadata) if metadata else "{}",
                "cost_tl": cost_tl,
                "cost_usd": cost_usd,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        )
    except Exception as e:
        logging.error(f"[API_TRACKING] Error logging API usage: {e}", exc_info=True)
        # Hata olsa bile devam et (logging hatası API çağrısını engellememeli)


async def get_api_usage_summary(
    isletme_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    İşletme için API kullanım özeti döner.
    """
    try:
        params: Dict[str, Any] = {"isletme_id": isletme_id}
        date_filter = ""
        
        if start_date and end_date:
            date_filter = "AND created_at BETWEEN :start_date AND :end_date"
            params["start_date"] = start_date
            params["end_date"] = end_date
        elif start_date:
            date_filter = "AND created_at >= :start_date"
            params["start_date"] = start_date
        elif end_date:
            date_filter = "AND created_at <= :end_date"
            params["end_date"] = end_date
        
        # Toplam request sayısı
        total_requests = await db.fetch_one(
            f"""
            SELECT COUNT(*) as total, SUM(request_count) as total_count
            FROM api_usage_logs
            WHERE isletme_id = :isletme_id {date_filter}
            """,
            params,
        )
        
        # Toplam maliyet
        total_cost = await db.fetch_one(
            f"""
            SELECT 
                COALESCE(SUM(cost_tl), 0) as total_cost_tl,
                COALESCE(SUM(cost_usd), 0) as total_cost_usd
            FROM api_usage_logs
            WHERE isletme_id = :isletme_id {date_filter}
            """,
            params,
        )
        
        # Endpoint bazında istatistikler
        endpoint_stats = await db.fetch_all(
            f"""
            SELECT 
                endpoint,
                method,
                COUNT(*) as request_count,
                SUM(request_count) as total_requests,
                COALESCE(SUM(cost_tl), 0) as total_cost_tl,
                AVG(response_time_ms) as avg_response_time_ms
            FROM api_usage_logs
            WHERE isletme_id = :isletme_id {date_filter}
            GROUP BY endpoint, method
            ORDER BY total_requests DESC
            """,
            params,
        )
        
        # Günlük kullanım (son 30 gün)
        daily_usage = await db.fetch_all(
            f"""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as request_count,
                SUM(request_count) as total_requests,
                COALESCE(SUM(cost_tl), 0) as total_cost_tl
            FROM api_usage_logs
            WHERE isletme_id = :isletme_id {date_filter}
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 30
            """,
            params,
        )
        
        return {
            "total_requests": int(total_requests["total"]) if total_requests else 0,
            "total_request_count": int(total_requests["total_count"]) if total_requests and total_requests.get("total_count") else 0,
            "total_cost_tl": float(total_cost["total_cost_tl"]) if total_cost else 0.0,
            "total_cost_usd": float(total_cost["total_cost_usd"]) if total_cost else 0.0,
            "endpoint_stats": [
                {
                    "endpoint": row["endpoint"],
                    "method": row["method"],
                    "request_count": int(row["request_count"]),
                    "total_requests": int(row["total_requests"]) if row.get("total_requests") else int(row["request_count"]),
                    "total_cost_tl": float(row["total_cost_tl"]),
                    "avg_response_time_ms": float(row["avg_response_time_ms"]) if row.get("avg_response_time_ms") else None,
                }
                for row in endpoint_stats
            ],
            "daily_usage": [
                {
                    "date": row["date"].isoformat() if hasattr(row["date"], "isoformat") else str(row["date"]),
                    "request_count": int(row["request_count"]),
                    "total_requests": int(row["total_requests"]) if row.get("total_requests") else int(row["request_count"]),
                    "total_cost_tl": float(row["total_cost_tl"]),
                }
                for row in daily_usage
            ],
        }
    except Exception as e:
        logging.error(f"[API_TRACKING] Error getting API usage summary: {e}", exc_info=True)
        return {
            "total_requests": 0,
            "total_request_count": 0,
            "total_cost_tl": 0.0,
            "total_cost_usd": 0.0,
            "endpoint_stats": [],
            "daily_usage": [],
        }

