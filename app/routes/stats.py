from fastapi import APIRouter, HTTPException
from app.models import Article
import time

router = APIRouter()

# ---------------------
# 🔹 Estadísticas de la colección
# ---------------------
@router.get("/overview")
async def stats_overview():
    """
    Total de artículos, procesados y no procesados.
    """
    try:
        total = await Article.count_documents({})
        processed = await Article.count_documents({"processed": True})
        unprocessed = total - processed
        return {"total": total, "processed": processed, "unprocessed": unprocessed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener overview: {e}")

@router.get("/by-tag")
async def stats_by_tag():
    """
    Contar cuántos artículos tienen cada tag.
    """
    try:
        tags = await Article.aggregate([
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]).to_list()
        return {"tags": tags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al contar por tags: {e}")

@router.get("/by-month")
async def stats_by_month():
    """
    Mostrar cuántos artículos se han agregado cada mes.
    """
    try:
        monthly = await Article.aggregate([
            {"$group": {
                "_id": {"year": {"$year": "$created_at"}, "month": {"$month": "$created_at"}},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id.year": 1, "_id.month": 1}}
        ]).to_list()
        return {"monthly": monthly}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al contar por mes: {e}")

@router.get("/oldest-unprocessed")
async def oldest_unprocessed(limit: int = 10):
    """
    Retorna los artículos no procesados más antiguos.
    """
    try:
        articles = await Article.find({"processed": False}).sort("created_at", 1).limit(limit).to_list()
        return {"oldest_unprocessed": articles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener antiguos no procesados: {e}")
