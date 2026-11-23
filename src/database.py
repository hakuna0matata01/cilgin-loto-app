"""
database.py
-----------
SQLite tabanli veri katmani. Orijinal tasarimdaki PostgreSQL semasinin
Streamlit Community Cloud + GitHub Actions gibi hafif/sunucusuz ortamlarda
calisacak sekilde sadelestirilmis halidir. Dosya tabanli oldugu icin ekstra
bir veritabani sunucusu kurmaya gerek yoktur; veritabani dosyasi repo icinde
`data/loto.db` yolunda tutulur ve GitHub Actions calistiginda commit'lenerek
kalici hale getirilebilir.
"""
import csv
import io
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = os.environ.get(
    "LOTO_DB_PATH",
    str(Path(__file__).resolve().parent.parent / "data" / "loto.db"),
)

DAY_NAMES_TR = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]


def get_connection():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_date TEXT NOT NULL UNIQUE,
            day_of_week TEXT,
            numbers TEXT NOT NULL,
            joker_number INTEGER,
            jackpot_amount REAL,
            winner_count INTEGER,
            source TEXT DEFAULT 'manual'
        );

        CREATE TABLE IF NOT EXISTS predictions (
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

        CREATE TABLE IF NOT EXISTS model_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_version TEXT,
            evaluation_date TEXT,
            avg_matches REAL,
            total_predictions INTEGER,
            notes TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def _numbers_to_str(numbers):
    return ",".join(str(int(n)) for n in numbers)


def _str_to_numbers(s):
    if not s:
        return []
    return [int(x) for x in s.split(",") if x != ""]


def _day_of_week(draw_date_str):
    d = datetime.strptime(draw_date_str, "%Y-%m-%d")
    return DAY_NAMES_TR[d.weekday()]


def insert_draw(draw_date, numbers, joker_number, jackpot_amount=None, winner_count=None, source="manual"):
    """Yeni bir cekilis sonucu ekler. draw_date zaten varsa (UNIQUE) False doner."""
    if len(set(numbers)) != 6 or any(not (1 <= n <= 90) for n in numbers):
        raise ValueError("numbers alani 1-90 arasinda 6 farkli sayi icermelidir.")
    if joker_number is not None and not (1 <= joker_number <= 90):
        raise ValueError("joker_number 1-90 arasinda olmalidir.")

    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO draws (draw_date, day_of_week, numbers, joker_number,
                                   jackpot_amount, winner_count, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                draw_date,
                _day_of_week(draw_date),
                _numbers_to_str(numbers),
                joker_number,
                jackpot_amount,
                winner_count,
                source,
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_all_draws():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM draws ORDER BY draw_date ASC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["numbers"] = _str_to_numbers(d["numbers"])
        result.append(d)
    return result


def import_draws_csv(file_obj, source="csv-import"):
    """
    file_obj: dosya benzeri nesne (Streamlit'in st.file_uploader'i veya acik dosya).
    Beklenen basliklar: draw_date,n1,n2,n3,n4,n5,n6,joker[,jackpot_amount,winner_count]
    draw_date formati: YYYY-MM-DD
    Doner: (eklenen_sayisi, atlanan_sayisi, hata_listesi)
    """
    content = file_obj.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    added, skipped, errors = 0, 0, []
    for i, row in enumerate(reader, start=2):
        try:
            numbers = [int(row[f"n{k}"]) for k in range(1, 7)]
            joker = int(row["joker"]) if row.get("joker") else None
            jackpot = float(row["jackpot_amount"]) if row.get("jackpot_amount") else None
            winners = int(row["winner_count"]) if row.get("winner_count") else None
            ok = insert_draw(
                row["draw_date"].strip(),
                numbers,
                joker,
                jackpot_amount=jackpot,
                winner_count=winners,
                source=source,
            )
            if ok:
                added += 1
            else:
                skipped += 1
        except Exception as e:
            errors.append(f"Satir {i}: {e}")
    return added, skipped, errors


def insert_prediction(prediction_date, draw_date, predicted_numbers, predicted_joker, confidence_score, model_version):
    conn = get_connection()
    conn.execute(
        """INSERT INTO predictions (prediction_date, draw_date, predicted_numbers,
                                     predicted_joker, confidence_score, model_version)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            prediction_date,
            draw_date,
            _numbers_to_str(predicted_numbers),
            predicted_joker,
            confidence_score,
            model_version,
        ),
    )
    conn.commit()
    conn.close()


def get_predictions():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM predictions ORDER BY prediction_date DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["predicted_numbers"] = _str_to_numbers(d["predicted_numbers"])
        result.append(d)
    return result


def update_prediction_draw_date(prediction_id, new_draw_date):
    """Bekleyen (draw_date='TBD') bir tahmine, gerceklesen cekilis tarihini
    atar. Boylece Kendi Kendini Gelistirme Agenti bir sonraki calismada bu
    tahmini ilgili cekilisle otomatik eslestirip degerlendirebilir."""
    conn = get_connection()
    conn.execute(
        "UPDATE predictions SET draw_date = ? WHERE id = ?",
        (new_draw_date, prediction_id),
    )
    conn.commit()
    conn.close()


def update_prediction_result(prediction_id, actual_matches, actual_joker_match):
    conn = get_connection()
    conn.execute(
        "UPDATE predictions SET actual_matches = ?, actual_joker_match = ? WHERE id = ?",
        (actual_matches, actual_joker_match, prediction_id),
    )
    conn.commit()
    conn.close()


def insert_metric(model_version, evaluation_date, avg_matches, total_predictions, notes=""):
    conn = get_connection()
    conn.execute(
        """INSERT INTO model_metrics (model_version, evaluation_date, avg_matches,
                                       total_predictions, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (model_version, evaluation_date, avg_matches, total_predictions, notes),
    )
    conn.commit()
    conn.close()


def get_metrics():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM model_metrics ORDER BY evaluation_date DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def draw_count():
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) as c FROM draws").fetchone()["c"]
    conn.close()
    return n
