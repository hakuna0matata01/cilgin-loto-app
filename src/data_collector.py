"""
data_collector.py
-------------------
Veri Toplayici Agent (best-effort web scraper).

ONEMLI SINIRLAMALAR - LUTFEN OKUYUN:
1. Bu, ucuncu taraf bir haber sitesinin (varsayilan: milliyet.com.tr) HTML
   yapisina dayanan bir "best-effort" scraper'dir. Siteler HTML yapilarini
   onceden haber vermeden degistirebilir; bu durumda asagidaki CSS
   secicilerini tarayicinizin "Elemani incele" (Inspect) araciyla kontrol
   edip guncellemeniz gerekir.
2. Bu kod, uretildigi ortamin ag erisimi soz konusu sitelere kapali oldugu
   icin CANLI SITEYE KARSI TEST EDILEMEMISTIR. Kullanmadan once kendi
   ortaminizda mutlaka test edin.
3. Kullanmadan once hedef sitenin robots.txt dosyasini ve kullanim
   sartlarini/telif politikasini kontrol edin; istekler arasinda makul bir
   bekleme suresi (rate limit) birakin (asagida REQUEST_DELAY_SECONDS).
4. EN GUVENILIR YONTEM: Sonuclari resmi kaynaktan (millipiyangoonline.com)
   veya Milli Piyango uygulamasindan kontrol ederek app.py > "Veri Yonetimi"
   sekmesinden CSV/manuel giris ile eklemektir. Bu scraper, o akisin YERINE
   degil, EK bir kolaylik/otomasyon denemesi olarak sunulur.
"""
import logging
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; LotoStatsBot/1.0; +https://github.com/)"
REQUEST_DELAY_SECONDS = 3
DEFAULT_LISTING_URL = "https://www.milliyet.com.tr/sans-oyunlari/cilgin-sayisal-loto-sonuclari/"

TURKISH_MONTHS = {
    "ocak": 1, "subat": 2, "şubat": 2, "mart": 3, "nisan": 4,
    "mayis": 5, "mayıs": 5, "haziran": 6, "temmuz": 7,
    "agustos": 8, "ağustos": 8, "eylul": 9, "eylül": 9,
    "ekim": 10, "kasim": 11, "kasım": 11, "aralik": 12, "aralık": 12,
}


def _parse_turkish_date(text):
    parts = text.lower().split("-")
    if len(parts) != 3:
        return None
    day, month_name, year = parts
    month = TURKISH_MONTHS.get(month_name)
    if not month:
        return None
    try:
        return datetime(int(year), month, int(day)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def fetch_listing_page(url=DEFAULT_LISTING_URL):
    """Sonuc listesi sayfasini indirir, cekilis detay linklerini dondurur."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    links, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "cilgin-sayisal-loto-sonucu" in href and href not in seen:
            seen.add(href)
            links.append(href)
    return links


def parse_draw_detail(url):
    """
    Tek bir cekilis detay sayfasini ayristirir.
    Donen deger:
        {"draw_date": "YYYY-MM-DD", "numbers": [6 adet int],
         "joker_number": int, "superstar_number": int ya da None}
    ya da ayristirma basarisiz olursa None.

    ONEMLI (duzeltme): Resmi sonuc sayfalarinda 6 ana sayidan SONRA iki ayri
    deger daha gosterilir: once Joker, sonra SuperStar (ikisi de ayri birer
    kureden 1-90 arasinda cekilir, biri digerinin yerine gecmez). Onceki
    surum, basliktan sonraki sayisal elemanlardan sadece ILK 7'sini
    topluyor ve 7.'sini kosulsuz "joker_number" sayiyordu; SuperStar hic
    aranmiyordu. Simdi 8 degere kadar toplaniyor: numbers[6] -> Joker,
    numbers[7] -> SuperStar (varsa). SuperStar, 2021'de oyuna eklendigi
    icin bazi cok eski cekilislerde sayfada hic yer almayabilir; bu yuzden
    minimum kabul kosulu hala 7'dir (Joker zorunlu, SuperStar opsiyonel).

    NOT: Asagidaki secici mantigi orneklayicidir; siteler her "top" sayisini
    genelde ayri bir <li>/<span> icinde tutar. Yapisi degisirse bu fonksiyonu
    guncellemeniz gerekecektir.
    """
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    date_match = re.search(r"(\d{1,2})-([a-zA-ZçğıöşüÇĞİÖŞÜ]+)-(\d{4})", url)
    draw_date = _parse_turkish_date(date_match.group(0)) if date_match else None

    numbers = []
    header = soup.find(string=re.compile("Kazanan Numaralar", re.IGNORECASE))
    if header:
        container = header.find_parent()
        if container:
            candidates = container.find_all_next(["li", "span", "div"], limit=70)
            for el in candidates:
                text = el.get_text(strip=True)
                if text.isdigit() and 1 <= int(text) <= 90:
                    numbers.append(int(text))
                if len(numbers) >= 8:
                    break

    if len(numbers) < 7 or not draw_date:
        logger.warning(
            "Ayristirma basarisiz oldu (site yapisi degismis olabilir, "
            "selector guncellemesi gerekebilir): %s", url,
        )
        return None

    return {
        "draw_date": draw_date,
        "numbers": numbers[:6],
        "joker_number": numbers[6],
        "superstar_number": numbers[7] if len(numbers) >= 8 else None,
    }


def collect_recent_results(max_pages=5):
    """Liste sayfasindan en guncel sonuclari toplamayi DENER (best-effort).
    Basarisiz olursa bos liste doner; hata gunlukte (log) belirtilir."""
    results = []
    try:
        links = fetch_listing_page()
    except Exception as e:
        logger.error("Liste sayfasi alinamadi: %s", e)
        return results

    for link in links[:max_pages]:
        try:
            time.sleep(REQUEST_DELAY_SECONDS)
            parsed = parse_draw_detail(link)
            if parsed:
                results.append(parsed)
        except Exception as e:
            logger.error("Detay sayfasi alinamadi (%s): %s", link, e)
            continue

    return results
