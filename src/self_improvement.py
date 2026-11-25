"""
self_improvement.py
---------------------
Kendi Kendini Gelistirme Agenti. Cekilis gerceklestikce, daha once uretilmis
tahminlerin dogruluk oranini hesaplar ve model_metrics tablosuna kaydeder.
Bu, orijinal spesifikasyondaki 4.5 ve 9 (Basari Metrikleri) bolumlerinin
karsiligidir.
"""
from datetime import date

from . import database as db


def evaluate_and_log(model_version=None):
    """
    actual_matches henuz hesaplanmamis tahminleri, artik gerceklesmis
    cekilis sonuclariyla karsilastirir ve gunceller. Ardindan genel bir
    ortalama isabet metrigi loglar.
    """
    predictions = db.get_predictions()
    draws_by_date = {d["draw_date"]: d for d in db.get_all_draws()}

    updated = 0
    all_matches = []

    for p in predictions:
        if p["actual_matches"] is not None:
            all_matches.append(p["actual_matches"])
            continue

        draw = draws_by_date.get(p["draw_date"])
        if not draw:
            continue

        predicted_set = set(p["predicted_numbers"])
        actual_set = set(draw["numbers"])
        matches = len(predicted_set & actual_set)

        # NOT: Her iki taraf da None oldugunda `None == None` True donup
        # yanlis bir "isabet" sayilmasin diye, iki deger de mevcutsa
        # karsilastiriyoruz; degilse ilgili alan None (bilinmiyor) kalir.
        joker_match = None
        if p.get("predicted_joker") is not None and draw.get("joker_number") is not None:
            joker_match = int(p["predicted_joker"] == draw["joker_number"])

        # SuperStar, eski cekilislerde (2021 oncesi) veya SuperStar'i
        # doldurmadan girilmis manuel kayitlarda bulunmayabilir; bu
        # durumda eslesme "yanlis" degil "bilinmiyor" (None) olarak kalir.
        superstar_match = None
        if p.get("predicted_superstar") is not None and draw.get("superstar_number") is not None:
            superstar_match = int(p["predicted_superstar"] == draw["superstar_number"])

        db.update_prediction_result(p["id"], matches, joker_match, superstar_match)
        all_matches.append(matches)
        updated += 1

    if all_matches:
        avg_matches = sum(all_matches) / len(all_matches)
        # Bu calismada hicbir tahmin yeni sonuclanmadiysa (updated == 0),
        # onceki degerlendirmeyle BIREBIR AYNI bir metrik satiri eklemenin
        # anlami yok -- model_metrics tablosunu ve zaman icindeki dogruluk
        # grafigini gereksiz/yanilti tekrarlarla sismek yerine, sadece
        # gercekten yeni bir sonuc oldugunda (ya da hic metrik yoksa) kayit
        # atariz.
        if updated > 0 or not db.get_metrics():
            db.insert_metric(
                model_version=model_version or "combined",
                evaluation_date=date.today().isoformat(),
                avg_matches=avg_matches,
                total_predictions=len(all_matches),
                notes=f"{updated} tahmin bu calismada yeni sonuclandi.",
            )
        return {
            "avg_matches": round(avg_matches, 3),
            "total_predictions": len(all_matches),
            "newly_updated": updated,
        }

    return {"avg_matches": None, "total_predictions": 0, "newly_updated": 0}
