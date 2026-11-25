"""
coupon_optimizer.py
--------------------
Kupon Optimizasyon Agenti. Frekans + ML skorlarini birlestirir, en yuksek
skorlu 6 sayiyi secer ve cift/tek - aralik dengesi icin hafif bir ayar yapar.

ONEMLI: Bu modul bir "kazanma stratejisi" degil, bir SIRALAMA/SUNUM
mekanizmasidir. Cilgin Sayisal Loto'da 6 sayinin tamami dogru bilinme
olasiligi C(90,6) = 622.614.630'da 1'dir ve bu, hangi 6 sayi secilirse
secilsin degismez.
"""
import random

from . import statistics_analyzer as stats
from . import ml_predictor as ml

DEFAULT_FREQ_WEIGHT = 0.4
DEFAULT_ML_WEIGHT = 0.6


def _range_bucket(n):
    if n <= 30:
        return "low"
    elif n <= 60:
        return "mid"
    return "high"


def _balance_selection(selected, ranked_numbers, target_odd_range=(2, 4), max_per_bucket=4, max_attempts=30):
    """Secilen 6 sayida asiri cift/tek veya tek-aralik yiginlanmasi varsa,
    siralamadaki en iyi uygun adayla degistirir. Rastgeleligi ARTTIRMAZ ya da
    AZALTMAZ; sadece kupon gorunumunu dengeler.

    Her adimda ONCE hangi kuralin ihlal edildigi (cok fazla/az tek sayi, ya
    da bir aralikta asiri yiginlanma) tespit edilir; SADECE o ihlale sebep
    olan gruptaki en dusuk siralamali ("en zayif") sayi, ayni sorunu
    cozecek nitelikte (dogru tek/cift, asiri olmayan aralik) en iyi
    siralamali aday ile degistirilir. Daha once denenmis (cikan, giren)
    ciftleri tekrar denemeyerek sonsuz ileri-geri degisimi (oscillation)
    engeller.

    NOT: Onceki surumde "weakest" (en zayif) sayi yanlislikla `min(...)` ile
    hesaplaniyordu; ranked_numbers en iyiden en kotuye siralandigi icin bu,
    aslinda secimdeki EN IYI (en guclu) sayiyi cikariyordu ve ayrica
    cikarilan sayi bir sonraki adimda geri eklenebildigi icin degisim
    hicbir zaman sonuclanmadan iki durum arasinda sonsuza dek salinabiliyordu
    (bkz. tests/test_basic.py ve proje incelemesi)."""
    selected = list(selected)
    tried_swaps = set()

    def odd_count(nums):
        return sum(1 for n in nums if n % 2 == 1)

    def bucket_counts_of(nums):
        buckets = [_range_bucket(n) for n in nums]
        return {b: buckets.count(b) for b in ("low", "mid", "high")}

    for _ in range(max_attempts):
        oc = odd_count(selected)
        bucket_counts = bucket_counts_of(selected)
        overloaded_bucket = max(bucket_counts, key=bucket_counts.get)
        bucket_needs_fix = bucket_counts[overloaded_bucket] > max_per_bucket

        too_many_odd = oc > target_odd_range[1]
        too_few_odd = oc < target_odd_range[0]

        if not (too_many_odd or too_few_odd or bucket_needs_fix):
            break

        if too_many_odd:
            pool = [n for n in selected if n % 2 == 1]
        elif too_few_odd:
            pool = [n for n in selected if n % 2 == 0]
        else:
            pool = [n for n in selected if _range_bucket(n) == overloaded_bucket]

        if not pool:
            break
        weakest = max(pool, key=lambda n: ranked_numbers.index(n))

        replacement = None
        for candidate in ranked_numbers:
            if candidate in selected or (weakest, candidate) in tried_swaps:
                continue
            if too_many_odd and candidate % 2 == 1:
                continue
            if too_few_odd and candidate % 2 == 0:
                continue
            if not (too_many_odd or too_few_odd) and _range_bucket(candidate) == overloaded_bucket:
                continue
            replacement = candidate
            break

        if replacement is None:
            break

        tried_swaps.add((weakest, replacement))
        selected = [replacement if c == weakest else c for c in selected]

    return selected


def _weighted_random_pick(frequency_by_number):
    """1-90 araliginda, gecmis frekansla agirliklandirilmis rastgele TEK bir
    sayi secer (sik cikanlar daha olasi, ama tek secenek degil; +1
    duzlestirme sayesinde hic cikmamis bir sayinin da sifir olmayan bir
    secilme sansi vardir). Hem Joker hem SuperStar icin ortak mantik:
    ikisi de ayri birer kureden cekilen, birbirinden bagimsiz sayilardir."""
    numbers = list(frequency_by_number.keys())
    weights = [frequency_by_number[n] + 1 for n in numbers]
    return random.choices(numbers, weights=weights, k=1)[0]


def generate_coupon(draws, freq_weight=DEFAULT_FREQ_WEIGHT, ml_weight=DEFAULT_ML_WEIGHT, seed=None):
    """
    Gecmis cekilislerden bir sonraki hafta icin onerilen 6 ana numara + Joker
    + SuperStar tahmini uretir. Donen sozluk: numbers, joker, superstar,
    confidence_score, model_version.

    Joker ve SuperStar, resmi cekiliste birbirinden BAGIMSIZ iki ayri
    kureden gelir (biri digerinin yerine gecmez), bu yuzden ayri ayri
    tahmin edilir.
    """
    if seed is not None:
        random.seed(seed)

    freq = stats.frequency_analysis(draws)
    max_freq = max(freq.values()) or 1
    freq_scores = {n: freq[n] / max_freq for n in freq}

    ml_scores, used_model_version = ml.train_and_predict(draws)

    combined = {
        n: freq_weight * freq_scores.get(n, 0) + ml_weight * ml_scores.get(n, 0)
        for n in range(1, 91)
    }

    ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    ranked_numbers = [n for n, _ in ranked]

    selected = ranked_numbers[:6]
    selected = _balance_selection(selected, ranked_numbers)

    # NOT (duzeltme): Onceki surumde burada `max(joker_freq, key=...)` ile
    # HER ZAMAN en sik cikan Joker secilirdi -- yani "Yeni kupon uret"
    # butonuna basmak, tohum sabitlenmemis olsa bile Joker'i hicbir zaman
    # DEGISTIRMEZDI (arayuzdeki "her tiklamada farkli bir rastgele deger
    # kullanilir" aciklamasiyla celisiyordu). Simdi, gecmis frekansla
    # agirliklandirilmis rastgele bir secim yapiliyor (bkz. _weighted_random_pick):
    # sik cikan sayilar daha olasi ama tek secenek degil, ve tohum
    # sabitlenmedikce her cagrida farkli sonuc uretilebilir.
    predicted_joker = _weighted_random_pick(stats.joker_frequency(draws))

    # SuperStar, Joker'den TAMAMEN BAGIMSIZ ayri bir kureden cekilir (bkz.
    # README / proje incelemesi notlari); bu yuzden Joker'inkinden ayri bir
    # frekans tablosuyla, ayni agirlikli-rastgele mantikla tahmin edilir.
    predicted_superstar = _weighted_random_pick(stats.superstar_frequency(draws))

    confidence = sum(combined[n] for n in selected) / 6

    return {
        "numbers": sorted(selected),
        "joker": predicted_joker,
        "superstar": predicted_superstar,
        "confidence_score": round(float(confidence), 4),
        "model_version": used_model_version,
    }
