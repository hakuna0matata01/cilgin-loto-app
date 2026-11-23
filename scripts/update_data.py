"""
update_data.py
----------------
Haftalik otomatik guncelleme akisi (bkz. .github/workflows/weekly_update.yml).
Celery/APScheduler yerine GitHub Actions'in zamanlanmis (cron) tetikleyicisi
kullanilir; bu, Streamlit Community Cloud gibi surekli calismayan/serverless
ortamlar icin daha uygundur.

Akis (orijinal spesifikasyon bolum 5 ile birebir):
1. Veri Toplayici Agent: yeni cekilis sonuclarini toplamayi dener (best-effort)
2. Kendi Kendini Gelistirme Agent: gecmis tahminleri degerlendirir
3. Istatistik + ML Agent: skorlari yeniden hesaplar
4. Kupon Optimizasyon Agent: yeni kuponu uretir ve kaydeder
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import database as db  # noqa: E402
from src import data_collector as collector  # noqa: E402
from src import self_improvement as improver  # noqa: E402
from src import coupon_optimizer as optimizer  # noqa: E402

DRAW_WEEKDAYS = (0, 2, 5)  # Pazartesi, Carsamba, Cumartesi


def _next_draw_date(today=None):
    d = (today or date.today()) + timedelta(days=1)
    while d.weekday() not in DRAW_WEEKDAYS:
        d += timedelta(days=1)
    return d.isoformat()


def main():
    db.init_db()

    print("[1/4] Yeni cekilis sonuclari toplaniyor (best-effort scraper)...")
    try:
        new_results = collector.collect_recent_results()
    except Exception as e:
        print(f"  -> Toplama basarisiz oldu, atlaniyor: {e}")
        new_results = []

    added = 0
    for r in new_results:
        try:
            if db.insert_draw(r["draw_date"], r["numbers"], r["joker_number"]):
                added += 1
        except ValueError as e:
            print(f"  -> Gecersiz veri atlandi: {e}")
    print(f"  -> {added} yeni cekilis eklendi.")

    print("[2/4] Gecmis tahminler degerlendiriliyor (Kendi Kendini Gelistirme Agenti)...")
    eval_result = improver.evaluate_and_log()
    print(f"  -> {eval_result}")

    print("[3/4] Guncel veri ile skorlar yeniden hesaplaniyor...")
    draws = db.get_all_draws()
    print(f"  -> Veritabaninda toplam {len(draws)} cekilis var.")

    if len(draws) < 5:
        print("  -> Yeterli veri yok (en az 5 cekilis gerekli). Kupon uretimi atlandi.")
        print("     Lutfen 'python scripts/generate_sample_data.py' calistirin ya da")
        print("     gercek verileri app.py > Veri Yonetimi sekmesinden ekleyin.")
        return

    print("[4/4] Kupon Optimizasyon Agenti yeni kuponu uretiyor...")
    coupon = optimizer.generate_coupon(draws)
    db.insert_prediction(
        prediction_date=date.today().isoformat(),
        draw_date=_next_draw_date(),
        predicted_numbers=coupon["numbers"],
        predicted_joker=coupon["joker"],
        confidence_score=coupon["confidence_score"],
        model_version=coupon["model_version"],
    )
    print(f"  -> Yeni kupon ({coupon['model_version']}): {coupon['numbers']} + Joker {coupon['joker']}")
    print("Tamamlandi.")


if __name__ == "__main__":
    main()
