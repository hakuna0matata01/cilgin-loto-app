"""
github_sync.py
----------------
NEDEN BU MODUL GEREKLI?
Streamlit Community Cloud (ve benzeri konteyner tabanli platformlar), uygulama
her yeniden baslatildiginda (uykuya dalip uyandiginda, yeniden dagitildiginda,
kaynaklar geri donduruldugunde vb.) disk icerigini GitHub reposundaki SON
COMMIT durumuna sifirlar. Bu yuzden "Veri Yonetimi" sekmesinden yaptiginiz
manuel giris / CSV import, GitHub'a commit'lenmedigi surece KALICI DEGILDIR.

Bu modul, guncel data/loto.db dosyasini GitHub REST API (Contents API)
uzerinden dogrudan repoya commit'leyerek bu sorunu cozer. Boylece manuel
girisler de, haftalik GitHub Actions is akisinin yaptigi gibi kalici hale
gelir.

YEREL KULLANIMDA GEREKLI DEGIL: `streamlit run app.py` ile kendi
bilgisayarinizda calistiriyorsaniz dosya sisteminiz zaten kalicidir; bu
modul yapilandirilmamis olsa bile veriler diskte normal sekilde saklanir.

GEREKLI YAPILANDIRMA (Streamlit Cloud > App settings > Secrets, ya da
yerelde .streamlit/secrets.toml -- ornek icin secrets.toml.example dosyasina
bakin):

    GITHUB_TOKEN     = "ghp_xxx..."     # "repo" (contents) yazma yetkili PAT
    GITHUB_REPO      = "kullanici-adi/repo-adi"
    GITHUB_BRANCH    = "main"           # opsiyonel, varsayilan: main
    DB_PATH_IN_REPO  = "data/loto.db"   # opsiyonel
"""
import base64

import requests
import streamlit as st

from . import database as db

API_ROOT = "https://api.github.com"


def _config():
    """Secrets tanimli degilse None doner (ozellik sessizce devre disi kalir)."""
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["GITHUB_REPO"]
    except Exception:
        return None
    return {
        "token": token,
        "repo": repo,
        "branch": st.secrets.get("GITHUB_BRANCH", "main"),
        "path": st.secrets.get("DB_PATH_IN_REPO", "data/loto.db"),
    }


def _diagnose_403(resp_text):
    """403 hatalarinin buyuk cogunlugu token'in repoya/izne sahip olmamasindan
    kaynaklanir. Kullaniciya en olasi nedenleri ve cozumu tek seferde gosterir."""
    return (
        "403 Forbidden -- token repoya yeterli izinle erisemiyor. En sik nedenler:\n\n"
        "1) **Fine-grained token** kullaniyorsaniz: token olusturulurken "
        "'Repository access' kismindan BU REPO secilmemis olabilir, ya da "
        "'Permissions > Contents' izni 'Read and write' olarak "
        "ayarlanmamis olabilir (varsayilan: No access). Token'i duzenleyip "
        "bu iki ayari kontrol edin.\n"
        "2) **Classic token** kullaniyorsaniz: token'da `repo` scope'u "
        "isaretli olmayabilir (private repo icin sart).\n"
        "3) Repo bir **organizasyona** aitse, organizasyon ayarlari "
        "kisisel erisim token'larini kisitliyor olabilir (Organization "
        "Settings > Personal access tokens > onay bekliyor olabilir).\n"
        "4) `GITHUB_REPO` degeri tam olarak `kullanici-adi/repo-adi` "
        "seklinde mi yazildi, yazim hatasi var mi kontrol edin.\n\n"
        f"GitHub'in ham yaniti: {resp_text[:200]}"
    )


def test_connection():
    """
    Yazma islemi yapmadan, token/repo yapilandirmasinin dogru olup
    olmadigini kontrol eder. 'Veri Yonetimi' sayfasindaki '🔌 Baglantiyi
    Test Et' butonu tarafindan kullanilir. Donen: (basarili_mi, mesaj)
    """
    cfg = _config()
    if cfg is None:
        return False, "GITHUB_TOKEN / GITHUB_REPO secrets olarak tanimlanmamis."

    headers = {
        "Authorization": f"Bearer {cfg['token']}",
        "Accept": "application/vnd.github+json",
    }
    try:
        resp = requests.get(f"{API_ROOT}/repos/{cfg['repo']}", headers=headers, timeout=15)
    except requests.RequestException as e:
        return False, f"Ag hatasi: {e}"

    if resp.status_code == 404:
        return False, (
            f"404: '{cfg['repo']}' bulunamadi. Ya repo adi yanlis yazilmis "
            "ya da token bu private repoyu goremiyor (izin eksikligi de "
            "GitHub tarafindan bazen 404 olarak donebilir)."
        )
    if resp.status_code == 401:
        return False, "401: Token gecersiz/suresi dolmus. Yeni bir token olusturun."
    if resp.status_code == 403:
        return False, _diagnose_403(resp.text)
    if resp.status_code != 200:
        return False, f"Beklenmeyen yanit: {resp.status_code} {resp.text[:200]}"

    perms = resp.json().get("permissions", {})
    if not perms.get("push", False):
        return False, (
            "Repoya erisim var ama YAZMA (push) izni yok. Fine-grained "
            "token ise 'Contents' iznini 'Read and write' yapin; classic "
            "token ise `repo` scope'unun isaretli oldugundan emin olun."
        )
    return True, f"✅ Baglanti basarili -- '{cfg['repo']}' reposuna yazma izniniz var."


def is_configured():
    return _config() is not None


def push_db_to_github(commit_message="chore: Veri Yonetimi uzerinden guncelleme"):
    """
    Guncel data/loto.db dosyasini GitHub'daki karsiligiyla degistirir
    (Contents API). Basarili olursa (True, mesaj), aksi halde (False, hata
    mesaji) doner. Ag/izin hatalarinda uygulamayi CRASH ETTIRMEZ.
    """
    cfg = _config()
    if cfg is None:
        return False, (
            "GitHub senkronizasyonu yapilandirilmamis (bu, yerelde calisirken "
            "SORUN DEGILDIR). Streamlit Cloud'da kalicilik icin App settings > "
            "Secrets kismina GITHUB_TOKEN ve GITHUB_REPO ekleyin -- bkz. "
            "README > 'Manuel girislerin kalici olmasi'."
        )

    headers = {
        "Authorization": f"Bearer {cfg['token']}",
        "Accept": "application/vnd.github+json",
    }
    url = f"{API_ROOT}/repos/{cfg['repo']}/contents/{cfg['path']}"

    try:
        sha = None
        get_resp = requests.get(url, headers=headers, params={"ref": cfg["branch"]}, timeout=15)
        if get_resp.status_code == 200:
            sha = get_resp.json().get("sha")
        elif get_resp.status_code == 403:
            return False, _diagnose_403(get_resp.text)
        elif get_resp.status_code != 404:
            return False, f"GitHub'dan mevcut dosya okunamadi: {get_resp.status_code} {get_resp.text[:200]}"

        with open(db.DB_PATH, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode("utf-8")

        payload = {"message": commit_message, "content": content_b64, "branch": cfg["branch"]}
        if sha:
            payload["sha"] = sha

        put_resp = requests.put(url, headers=headers, json=payload, timeout=30)
        if put_resp.status_code in (200, 201):
            return True, "✅ Degisiklikler GitHub reposuna kaydedildi (kalici)."
        if put_resp.status_code == 403:
            return False, _diagnose_403(put_resp.text)
        return False, f"GitHub'a yazma basarisiz oldu: {put_resp.status_code} {put_resp.text[:300]}"
    except requests.RequestException as e:
        return False, f"GitHub'a baglanirken ag hatasi olustu: {e}"
