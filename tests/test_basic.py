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
        # Birkac kaydi bilerek SuperStar'siz birakiyoruz (ör. 2021 oncesi
        # cekilis ya da doldurulmamis manuel kayit senaryosunu simule eder).
        superstar = random.randint(1, 90) if i % 5 != 0 else None
        db.insert_draw(
            d.isoformat(), numbers, joker,
            superstar_number=superstar,
            jackpot_amount=50_000_000.0 if i % 3 == 0 else None,
        )
        d += timedelta(days=2)


def test_insert_and_fetch_draws():
    """NOT: Bu dosyadaki baska testler (ornegin CSV/SuperStar testleri)
    paylasilan ayni test veritabanina ek kayitlar yazabilir. setup_module
    HER ZAMAN tam 40 kayit ekledigi ve hicbir test kayit SILMEDIGI icin,
    kayit sayisi calisma sirasina gore 40'tan BUYUK olabilir ama hicbir
    zaman 40'tan AZ olamaz. `== 40` yerine `>= 40` kullanmak, testin
    pytest'in varsayilan calisma sirasina (ya da olasi bir rastgele/paralel
    calisma siralamasina) baglimli kalmasini onler."""
    draws = db.get_all_draws()
    assert len(draws) >= 40
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
    """`>= 40` icin gerekce: bkz. test_insert_and_fetch_draws docstring'i."""
    draws = db.get_all_draws()
    s = stats.summary(draws)
    assert len(s["frekans"]) == 90
    assert s["toplam_cekilis"] >= 40
    assert s["toplam_cekilis"] == len(draws)


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


def test_joker_varies_without_fixed_seed():
    """Regresyon testi: onceki surumde Joker, tohum sabitlenmemis olsa bile
    HER ZAMAN en sik cikan sayiya esitleniyordu (gercek bir rastgelelik
    kaynagi hic devreye girmiyordu), bu da arayuzdeki '(tohum sabitlenmezse
    her tiklamada farkli bir rastgele Joker kullanilir)' aciklamasiyla
    celisiyordu. Yeterli cekilis + joker cesitliligi oldugunda, tohumsuz
    coklu uretimde en az 2 farkli Joker degeri gorulmelidir."""
    draws = db.get_all_draws()
    jokers = {optimizer.generate_coupon(draws)["joker"] for _ in range(25)}
    assert len(jokers) >= 2, "Joker hep ayni cikiyor; agirlikli rastgelelik calismiyor olabilir"


def test_joker_reproducible_with_fixed_seed():
    draws = db.get_all_draws()
    c1 = optimizer.generate_coupon(draws, seed=99)
    c2 = optimizer.generate_coupon(draws, seed=99)
    assert c1 == c2


def test_jackpot_trend_only_includes_filled_entries():
    draws = db.get_all_draws()
    trend = stats.jackpot_trend(draws)
    assert all(amount is not None for _, amount in trend)
    assert len(trend) <= len(draws)


def test_superstar_is_independent_field_from_joker():
    """Regresyon testi: Joker ve SuperStar, Cilgin Sayisal Loto'nun resmi
    sonuclarinda birbirinden BAGIMSIZ iki ayri kureden gelir (6 ana sayidan
    sonra once Joker, sonra SuperStar gosterilir). Onceki surumde
    uygulamanin hem veritabani semasinda hem arayuzde bu ikisi tek bir
    alanmis gibi ele aliniyordu ve SuperStar hic kaydedilmiyordu. Bu test,
    ikisinin birbirinden farkli degerler olarak saklanip okunabildigini
    dogrular."""
    ok = db.insert_draw("2031-01-01", [2, 4, 6, 8, 10, 12], joker_number=55, superstar_number=77)
    assert ok is True
    draws = db.get_all_draws()
    row = next(d for d in draws if d["draw_date"] == "2031-01-01")
    assert row["joker_number"] == 55
    assert row["superstar_number"] == 77
    assert row["joker_number"] != row["superstar_number"]


def test_superstar_number_validated_like_joker():
    try:
        db.insert_draw("2031-01-02", [1, 2, 3, 4, 5, 6], joker_number=10, superstar_number=91)
        assert False, "1-90 disindaki SuperStar kabul edilmemeliydi"
    except ValueError:
        pass


def test_superstar_optional_none_allowed():
    """SuperStar 2021'de eklendigi icin daha eski/bilinmeyen cekilislerde
    bu alan None olabilmelidir (zorunlu degildir)."""
    ok = db.insert_draw("2031-01-03", [11, 22, 33, 44, 55, 66], joker_number=20, superstar_number=None)
    assert ok is True
    draws = db.get_all_draws()
    row = next(d for d in draws if d["draw_date"] == "2031-01-03")
    assert row["superstar_number"] is None


def test_superstar_frequency_shape_and_excludes_none():
    draws = db.get_all_draws()
    freq = stats.superstar_frequency(draws)
    assert len(freq) == 90
    assert sum(freq.values()) == sum(1 for d in draws if d.get("superstar_number"))


def test_coupon_includes_valid_superstar():
    draws = db.get_all_draws()
    coupon = optimizer.generate_coupon(draws, seed=11)
    assert "superstar" in coupon
    assert 1 <= coupon["superstar"] <= 90
    # Joker ve SuperStar ayri agirlik tablolarindan geldigi icin ayni
    # cagrida farkli olabilirler; testte esitlik ZORUNLU degildir, sadece
    # her ikisinin de gecerli araliga dustugu dogrulanir.


def test_superstar_varies_without_fixed_seed():
    draws = db.get_all_draws()
    superstars = {optimizer.generate_coupon(draws)["superstar"] for _ in range(25)}
    assert len(superstars) >= 2


def test_old_schema_database_migrates_without_data_loss(tmp_path):
    """Bu proje ile birlikte gelen (ya da daha once olusturulmus) eski
    semali bir loto.db dosyasinda `superstar_number` / `predicted_superstar`
    / `actual_superstar_match` sutunlari BULUNMAZ. init_db(), bu sutunlari
    mevcut veriyi SILMEDEN sonradan eklemelidir (bkz. database.py
    _migrate_add_missing_columns)."""
    import sqlite3
    import importlib

    old_db_path = str(tmp_path / "old_schema.db")
    conn = sqlite3.connect(old_db_path)
    conn.executescript(
        """
        CREATE TABLE draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_date TEXT NOT NULL UNIQUE,
            day_of_week TEXT,
            numbers TEXT NOT NULL,
            joker_number INTEGER,
            jackpot_amount REAL,
            winner_count INTEGER,
            source TEXT DEFAULT 'manual'
        );
        CREATE TABLE predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_date TEXT NOT NULL,
            draw_date TEXT NOT NULL,
            predicted_numbers TEXT NOT NULL,
            predicted_joker INTEGER,
            confidence_score REAL,
            model_version TEXT,
            actual_matches INTEGER,
            actual_joker_match INTEGER
        );
        """
    )
    conn.execute(
        "INSERT INTO draws (draw_date, day_of_week, numbers, joker_number) VALUES (?, ?, ?, ?)",
        ("2020-01-01", "Carsamba", "1,2,3,4,5,6", 9),
    )
    conn.commit()
    conn.close()

    old_env = os.environ.get("LOTO_DB_PATH")
    os.environ["LOTO_DB_PATH"] = old_db_path
    try:
        import src.database as db_module
        importlib.reload(db_module)
        db_module.init_db()
        draws = db_module.get_all_draws()
        assert len(draws) == 1, "Migrasyon sirasinda veri kaybi yasandi"
        assert draws[0]["joker_number"] == 9
        assert draws[0]["superstar_number"] is None
    finally:
        if old_env is not None:
            os.environ["LOTO_DB_PATH"] = old_env
        else:
            del os.environ["LOTO_DB_PATH"]
        import src.database as db_module
        importlib.reload(db_module)


def test_csv_import_reads_superstar_column():
    """ornek_sablon.csv uzerinden uctan uca: CSV'deki 'superstar' sutunu
    gercekten okunup superstar_number olarak kaydediliyor mu?"""
    import io

    csv_text = (
        "draw_date,n1,n2,n3,n4,n5,n6,joker,superstar,jackpot_amount,winner_count\n"
        "2032-05-05,5,15,25,35,45,55,12,34,1000.0,0\n"
    )
    added, skipped, errors = db.import_draws_csv(io.StringIO(csv_text))
    assert errors == []
    assert added == 1
    row = next(d for d in db.get_all_draws() if d["draw_date"] == "2032-05-05")
    assert row["joker_number"] == 12
    assert row["superstar_number"] == 34


def test_csv_import_without_superstar_column_still_works():
    """Eski (superstar sutunu olmayan) bir CSV sablonu da hala calismali;
    bu durumda superstar_number None olarak kaydedilmelidir."""
    import io

    csv_text = (
        "draw_date,n1,n2,n3,n4,n5,n6,joker,jackpot_amount,winner_count\n"
        "2032-06-06,2,4,6,8,10,12,20,1000.0,0\n"
    )
    added, skipped, errors = db.import_draws_csv(io.StringIO(csv_text))
    assert errors == []
    assert added == 1
    row = next(d for d in db.get_all_draws() if d["draw_date"] == "2032-06-06")
    assert row["joker_number"] == 20
    assert row["superstar_number"] is None


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
