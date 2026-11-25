"""
statistics_analyzer.py
-----------------------
Istatistik Analiz Agenti. Orijinal spesifikasyondaki 4.2 bolumunde tanimlanan
tum analizleri (frekans, sicak/soguk, gecikme, cift/tek orani, aralik
dagilimi, ardisiklik, toplam deger) uygular.

ONEMLI: Cilgin Sayisal Loto'da her cekilis matematiksel olarak bagimsiz bir
rastgele olaydir. Buradaki analizler sadece GECMISI betimler; gelecekteki
cekilisi ONGOREMEZ. Adil bir cekiliste her sayinin her cekiliste cikma
olasiligi esittir, gecmis frekans bunu degistirmez (bkz. "kumarbaz yanilgisi").
"""
from collections import Counter

ALL_NUMBERS = list(range(1, 91))


def frequency_analysis(draws):
    """Her sayinin (1-90) kac cekiliste ciktigini dondurur."""
    counter = Counter()
    for d in draws:
        counter.update(d["numbers"])
    return {n: counter.get(n, 0) for n in ALL_NUMBERS}


def hot_cold_numbers(draws, last_n=50, top_n=10):
    """Son `last_n` cekilise gore en sik (sicak) ve en az (soguk) cikan sayilar."""
    sorted_draws = sorted(draws, key=lambda d: d["draw_date"])
    recent = sorted_draws[-last_n:] if last_n else sorted_draws
    freq = frequency_analysis(recent)
    ranked = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    hot = ranked[:top_n]
    cold = list(reversed(ranked[-top_n:]))
    return hot, cold


def gap_analysis(draws):
    """Her sayinin en son kac cekilis once ciktigini (gecikme) dondurur.
    Hic cikmamis sayilar icin toplam cekilis sayisi donulur."""
    sorted_draws = sorted(draws, key=lambda d: d["draw_date"])
    total = len(sorted_draws)
    last_seen_idx = {}
    for idx, d in enumerate(sorted_draws):
        for n in d["numbers"]:
            last_seen_idx[n] = idx
    gaps = {}
    for n in ALL_NUMBERS:
        if n in last_seen_idx:
            gaps[n] = (total - 1) - last_seen_idx[n]
        else:
            gaps[n] = total
    return gaps


def odd_even_ratio(draws):
    odd = sum(1 for d in draws for n in d["numbers"] if n % 2 == 1)
    even = sum(1 for d in draws for n in d["numbers"] if n % 2 == 0)
    return {"tek": odd, "cift": even}


def range_distribution(draws):
    """Sayilarin 1-30 / 31-60 / 61-90 araliklarindaki dagilimi."""
    buckets = {"1-30": 0, "31-60": 0, "61-90": 0}
    for d in draws:
        for n in d["numbers"]:
            if n <= 30:
                buckets["1-30"] += 1
            elif n <= 60:
                buckets["31-60"] += 1
            else:
                buckets["61-90"] += 1
    return buckets


def consecutive_analysis(draws):
    """Ardisik sayi ciftlerinin (ör. 23-24) toplam cekilislerdeki gorulme sayisi."""
    count = 0
    for d in draws:
        nums = sorted(d["numbers"])
        for i in range(len(nums) - 1):
            if nums[i + 1] - nums[i] == 1:
                count += 1
    return count


def sum_distribution(draws):
    """Her cekilisteki 6 sayinin toplamini, ilgili cekilis tarihiyle birlikte
    dondurur: [(draw_date, toplam), ...]. Boylece grafikte anlamli/kronolojik
    bir x ekseni (tarih) kullanilabilir."""
    sorted_draws = sorted(draws, key=lambda d: d["draw_date"])
    return [(d["draw_date"], sum(d["numbers"])) for d in sorted_draws]


def jackpot_trend(draws):
    """Devreden/kazanilan ikramiye (jackpot_amount) girilmis cekilisleri,
    tarih sirasiyla [(draw_date, jackpot_amount), ...] seklinde dondurur.
    Bu bilgi veritabaninda zaten tutuluyordu ama Dashboard'da hic
    gosterilmiyordu; manuel giriste jackpot alani doldurulmussa burada
    ortaya cikar (otomatik toplanan cekilislerde bu alan su an icin bos
    kalabilir, cunku veri toplayici bu bilgiyi ayristirmiyor)."""
    sorted_draws = sorted(draws, key=lambda d: d["draw_date"])
    return [
        (d["draw_date"], d["jackpot_amount"])
        for d in sorted_draws
        if d.get("jackpot_amount") is not None
    ]


def joker_frequency(draws):
    counter = Counter(d["joker_number"] for d in draws if d.get("joker_number"))
    return {n: counter.get(n, 0) for n in ALL_NUMBERS}


def superstar_frequency(draws):
    """Joker_frequency ile ayni mantik, ama SuperStar icin. Joker ve
    SuperStar resmi sonuclarda birbirinden bagimsiz iki ayri kuredendir;
    bu yuzden ayri bir frekans tablosu gerekir (biri digerinin yerine
    kullanilamaz). SuperStar 2021'de eklendigi icin daha eski veya
    doldurulmamis cekilislerde bu alan bos (None) olabilir; bu kayitlar
    sayima dahil edilmez."""
    counter = Counter(d["superstar_number"] for d in draws if d.get("superstar_number"))
    return {n: counter.get(n, 0) for n in ALL_NUMBERS}


def summary(draws):
    """Dashboard icin tek seferde kullanilabilecek ozet paket."""
    hot, cold = hot_cold_numbers(draws)
    return {
        "toplam_cekilis": len(draws),
        "frekans": frequency_analysis(draws),
        "sicak": hot,
        "soguk": cold,
        "gecikme": gap_analysis(draws),
        "tek_cift": odd_even_ratio(draws),
        "aralik_dagilimi": range_distribution(draws),
        "ardisik_sayisi": consecutive_analysis(draws),
        "toplam_dagilimi": sum_distribution(draws),
        "ikramiye_gecmisi": jackpot_trend(draws),
        "joker_frekans": joker_frequency(draws),
        "superstar_frekans": superstar_frequency(draws),
    }
