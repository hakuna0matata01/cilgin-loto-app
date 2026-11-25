"""
generate_sample_data.py
-------------------------
Uygulamayi ilk kez calistiran kullanicilarin dashboard'u BOS gormemesi icin
SENTETIK (uydurma/rastgele) ornek cekilis verisi uretir.

*** BU VERI GERCEK MPI / SISAL SANS CEKILIS SONUCU DEGILDIR. ***
Sadece arayuzu ve analizleri demo etmek icindir. Gercek analiz icin
lutfen app.py > "Veri Yonetimi" sekmesinden gercek sonuclari CSV ile
disa aktarin/iceri aktarin ya da resmi kaynaktan elle girin.

Kullanim:
    python scripts/generate_sample_data.py
"""
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import database as db  # noqa: E402

DRAW_WEEKDAYS = (0, 2, 5)  # Pazartesi, Carsamba, Cumartesi (Python: Mon=0)


def _draw_dates(n_draws, end_date=None):
    end_date = end_date or datetime.today()
    dates = []
    d = end_date
    while len(dates) < n_draws:
        if d.weekday() in DRAW_WEEKDAYS:
            dates.append(d)
        d -= timedelta(days=1)
    return list(reversed(dates))


def generate(n_draws=312, seed=42):
    random.seed(seed)
    db.init_db()

    dates = _draw_dates(n_draws)
    added = 0
    for d in dates:
        numbers = sorted(random.sample(range(1, 91), 6))
        joker = random.randint(1, 90)
        superstar = random.randint(1, 90)
        ok = db.insert_draw(
            d.strftime("%Y-%m-%d"),
            numbers,
            joker,
            superstar_number=superstar,
            jackpot_amount=round(random.uniform(20_000_000, 500_000_000), 2),
            winner_count=random.choice([0, 0, 0, 1, 2]),
            source="sample-synthetic",
        )
        if ok:
            added += 1

    print(f"{added} adet SENTETIK ornek cekilis eklendi (toplam istenen: {n_draws}).")
    print("UYARI: Bu veriler gercek degildir, sadece demo amaclidir.")


if __name__ == "__main__":
    generate()
