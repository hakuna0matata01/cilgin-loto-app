"""
Temel duman testleri (smoke tests). Calistirmak icin:
    pytest tests/
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Testler icin gecici/ayri bir veritabani kullan
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["LOTO_DB_PATH"] = _tmp_db.name

from src import database as db  # noqa: E402
from src import statistics_analyzer as stats  # noqa: E402
from src import coupon_optimizer as optimizer  # noqa: E402


def setup_module(module):
    db.init_db()
    import random
    random.seed(1)
    from datetime import date, timedelta
    d = date(2024, 1, 1)
    for i in range(40):
        numbers = sorted(random.sample(range(1, 91), 6))
        joker = random.randint(1, 90)
        db.insert_draw(d.isoformat(), numbers, joker)
        d += timedelta(days=2)


def test_insert_and_fetch_draws():
    draws = db.get_all_draws()
    assert len(draws) == 40
    assert all(len(d["numbers"]) == 6 for d in draws)


def test_duplicate_draw_date_rejected():
    draws = db.get_all_draws()
    existing_date = draws[0]["draw_date"]
    ok = db.insert_draw(existing_date, [1, 2, 3, 4, 5, 6], 7)
    assert ok is False


def test_invalid_numbers_raise():
    try:
        db.insert_draw("2030-01-01", [1, 1, 2, 3, 4, 5], 6)
        assert False, "Tekrarli sayi kabul edilmemeliydi"
    except ValueError:
        pass


def test_statistics_summary_shape():
    draws = db.get_all_draws()
    s = stats.summary(draws)
    assert len(s["frekans"]) == 90
    assert s["toplam_cekilis"] == 40


def test_coupon_generation():
    draws = db.get_all_draws()
    coupon = optimizer.generate_coupon(draws, seed=7)
    assert len(coupon["numbers"]) == 6
    assert len(set(coupon["numbers"])) == 6
    assert all(1 <= n <= 90 for n in coupon["numbers"])
    assert 1 <= coupon["joker"] <= 90


def test_balance_selection_fixes_extreme_even_bias():
    """Regresyon testi: onceki surumde `weakest` yanlislikla `min(...)` ile
    hesaplaniyordu (en iyi siralanan sayiyi cikariyordu) ve cikarilan sayi
    bir sonraki adimda geri eklenebildigi icin dengeleme hicbir zaman
    sonuclanmiyor, iki durum arasinda sonsuza dek salaniyordu."""
    ranked_numbers = list(range(2, 91, 2)) + list(range(1, 91, 2))
    selected = ranked_numbers[:6]  # ilk 6'si tamamen cift sayi
    result = optimizer._balance_selection(selected, ranked_numbers)

    assert len(result) == 6
    assert len(set(result)) == 6
    odd_count = sum(1 for n in result if n % 2 == 1)
    assert 2 <= odd_count <= 4, "tek/cift dengesi saglanamadi"


def test_balance_selection_many_random_rankings_converge():
    import random as _random

    def bucket(n):
        if n <= 30:
            return "low"
        if n <= 60:
            return "mid"
        return "high"

    for trial in range(100):
        rnd = _random.Random(trial)
        ranked_numbers = list(range(1, 91))
        rnd.shuffle(ranked_numbers)
        selected = ranked_numbers[:6]
        result = optimizer._balance_selection(list(selected), ranked_numbers)

        assert len(set(result)) == 6
        odd_count = sum(1 for n in result if n % 2 == 1)
        bucket_counts = {}
        for n in result:
            bucket_counts[bucket(n)] = bucket_counts.get(bucket(n), 0) + 1
        assert 2 <= odd_count <= 4
        assert max(bucket_counts.values()) <= 4
