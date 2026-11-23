# 🎱 Çılgın Sayısal Loto AI Agent Sistemi (GitHub + Streamlit sürümü)

Bu proje, orijinal "AI Agent tabanlı akıllı kupon oluşturma" spesifikasyonunun
**GitHub + Streamlit Community Cloud** üzerinde tek parça olarak çalışacak
şekilde sadeleştirilmiş halidir. Ağır FastAPI/Django + PostgreSQL + Celery +
React yığını yerine; SQLite + Streamlit + GitHub Actions kullanılır.

> ⚠️ **Önemli:** Çılgın Sayısal Loto tamamen şansa dayalı bir oyundur. Her
> çekiliş matematiksel olarak bağımsızdır. Bu uygulamadaki hiçbir istatistik
> veya yapay zeka modeli kazanmayı garanti etmez ya da gerçek olasılığı
> değiştirmez (6 sayının tamamını bilme olasılığı: 622.614.630'da 1). Uygulama
> **yalnızca eğlence ve bilgilendirme** amaçlıdır. Lütfen sorumlu oyun
> ilkeleri çerçevesinde hareket edin.

---

## Mimari değişikliği: neden bu şekilde sadeleştirildi?

| Orijinal tasarım | Bu sürüm | Neden |
|---|---|---|
| FastAPI/Django backend | Streamlit tek dosya (`app.py`) | Streamlit Cloud'da ayrı backend'e gerek yok |
| PostgreSQL | SQLite (`data/loto.db`) | Dosya tabanlı, sunucu kurulumu gerektirmez, repo ile birlikte taşınır |
| Celery / APScheduler | GitHub Actions (cron) | Streamlit Cloud sürekli arka plan görevi çalıştırmaz; GitHub Actions haftada 3 kez tetiklenir |
| React / Vue frontend | Streamlit sayfaları | Tek dilde (Python), hızlı geliştirme |
| Docker / AWS / GCP deployment | Streamlit Community Cloud (ücretsiz) | GitHub reposunu bağlayıp tek tıkla yayınlama |

5 AI Agent rolü (Veri Toplayıcı, İstatistik Analiz, Makine Öğrenmesi, Kupon
Optimizasyon, Kendi Kendini Geliştirme) birebir korunmuştur — her biri
`src/` altında ayrı bir modül olarak yaşar.

---

## Klasör yapısı

```
cilgin-loto-app/
├── app.py                          # Streamlit ana uygulaması (5 sayfa)
├── requirements.txt
├── .streamlit/config.toml          # Tema ayarları
├── src/
│   ├── database.py                 # SQLite veri katmanı
│   ├── data_collector.py           # Veri Toplayıcı Agent (best-effort scraper)
│   ├── statistics_analyzer.py      # İstatistik Analiz Agenti
│   ├── ml_predictor.py             # Makine Öğrenmesi Agenti (RandomForest)
│   ├── coupon_optimizer.py         # Kupon Optimizasyon Agenti
│   ├── self_improvement.py         # Kendi Kendini Geliştirme Agenti
│   └── github_sync.py              # Manuel girişleri GitHub'a commit'leyerek kalıcılaştırır
├── scripts/
│   ├── update_data.py              # Haftalık akışın tamamı (GitHub Actions çalıştırır)
│   └── generate_sample_data.py     # SENTETİK demo verisi üretir (gerçek değildir!)
├── .github/workflows/weekly_update.yml   # Haftalık otomasyon (Celery yerine)
├── .streamlit/secrets.toml.example       # GitHub senkronizasyonu için secrets şablonu
├── data/ornek_sablon.csv           # CSV içe aktarma format örneği
└── tests/test_basic.py
```

---

## Yerel kurulum

```bash
git clone <repo-url>
cd cilgin-loto-app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# (opsiyonel) arayüzü boş görmemek için sentetik demo verisi:
python scripts/generate_sample_data.py

streamlit run app.py
```

Tarayıcıda `http://localhost:8501` açılır.

---

## GitHub'a yükleme

```bash
git init
git add .
git commit -m "İlk sürüm: Çılgın Sayısal Loto AI Agent (Streamlit)"
git branch -M main
git remote add origin https://github.com/<kullanici-adiniz>/<repo-adi>.git
git push -u origin main
```

`data/loto.db` dosyasının repoya dahil edilmesi kasıtlıdır: GitHub Actions
haftalık çalıştıktan sonra bu dosyayı otomatik commit'ler, böylece veri
kalıcı olur ve Streamlit Cloud her yeniden başlattığında sıfırlanmaz.

---

## Streamlit Community Cloud'da yayınlama

1. https://share.streamlit.io adresine GitHub hesabınızla giriş yapın.
2. "New app" → reponuzu seçin → `app.py` dosyasını ana dosya olarak belirtin.
3. Deploy edin. Streamlit otomatik olarak `requirements.txt`'i kurar.
4. Her `git push`'ta uygulama otomatik yeniden dağıtılır (auto-redeploy).

---

## Haftalık otomatik güncelleme (GitHub Actions)

`.github/workflows/weekly_update.yml`, Pazartesi/Çarşamba/Cumartesi akşamları
(çekiliş saati 21:30'dan sonra) otomatik olarak:

1. Veri Toplayıcı Agent ile yeni sonucu toplamayı **dener** (best-effort),
2. Kendi Kendini Geliştirme Agent ile geçmiş tahminlerin isabetini hesaplar,
3. Yeni haftanın kuponunu üretir,
4. `data/loto.db` dosyasını commit'leyip push'lar.

Repo ayarlarında bu workflow'un çalışabilmesi için **Settings → Actions →
General → Workflow permissions** kısmından "Read and write permissions"
seçili olmalıdır. Elle tetiklemek isterseniz Actions sekmesinden
"Run workflow" (workflow_dispatch) kullanabilirsiniz.

### Veri toplama hakkında önemli not

`src/data_collector.py` içindeki web scraper **best-effort** bir denemedir ve
üçüncü taraf bir haber sitesinin (varsayılan: milliyet.com.tr) o anki HTML
yapısına bağlıdır. Bu kod, üretildiği ortamın ağ erişimi ilgili sitelere
kapalı olduğu için **canlı siteye karşı test edilememiştir** — kendi
ortamınızda mutlaka doğrulayın ve gerekirse CSS seçicilerini güncelleyin.
Kullanmadan önce hedef sitenin `robots.txt` ve kullanım şartlarını kontrol
edin. **En güvenilir yöntem**, sonuçları resmi kaynaktan
(millipiyangoonline.com) kontrol ederek uygulamanın "Veri Yönetimi"
sekmesinden CSV veya manuel giriş ile eklemektir.

---

## Manuel girişlerin kalıcı olması (Streamlit Cloud)

**Önemli:** Streamlit Community Cloud gibi konteyner tabanlı platformlar,
uygulama her yeniden başladığında (uykuya dalıp uyanma, yeni bir `git push`
sonrası yeniden dağıtım, kaynakların geri döndürülmesi vb.) disk içeriğini
GitHub reposundaki **son commit** durumuna sıfırlar. Bu yüzden "Veri
Yönetimi" sekmesinden elle girdiğiniz veya CSV ile yüklediğiniz veriler, bir
yere commit'lenmediği sürece bir sonraki yeniden başlatmada **kaybolabilir**.

Bunu çözmek için `src/github_sync.py` modülü eklendi: yapılandırıldığında,
her manuel giriş/CSV import/otomatik toplama sonrası güncel
`data/loto.db` dosyasını GitHub REST API üzerinden doğrudan repoya
commit'ler — tıpkı haftalık GitHub Actions işinin yaptığı gibi, ama anlık.

**Kurulum (yalnızca Streamlit Cloud'da veri girecekseniz gerekli):**

1. GitHub'da **Settings → Developer settings → Personal access tokens**
   üzerinden, reponuza `Contents: Read and write` izni olan bir token
   oluşturun.
2. Streamlit Cloud'da uygulamanızın **⋮ menüsü → Settings → Secrets**
   kısmına şunları ekleyin (`.streamlit/secrets.toml.example` dosyasına
   bakabilirsiniz):

   ```toml
   GITHUB_TOKEN = "ghp_..."
   GITHUB_REPO = "kullanici-adiniz/repo-adiniz"
   GITHUB_BRANCH = "main"
   ```
3. Kaydedin; uygulama otomatik yeniden başlar. "Veri Yönetimi" sekmesinde
   artık "☁️ GitHub senkronizasyonu **aktif**" mesajını göreceksiniz.

**Yerelde `streamlit run app.py` ile çalıştırıyorsanız** bu adıma hiç gerek
yoktur — dosya sisteminiz zaten kalıcıdır, SQLite dosyası normal şekilde
diskinizde saklanır.

**GitHub token kurmak istemiyorsanız:** "Veri Yönetimi → 🗄️ Yedekle / Geri
Yükle" sekmesinden veritabanını `.db` dosyası olarak indirip, bir sonraki
oturumda geri yükleyerek de verinizi koruyabilirsiniz (daha basit ama
manuel bir yöntem).

### "403: Resource not accessible by personal access token" hatası

Bu hata neredeyse her zaman token'ın izin eksikliğinden kaynaklanır. "Veri
Yönetimi" sayfasındaki **🔌 Bağlantıyı test et** butonuyla önce teşhis edin,
sonra şunları kontrol edin:

- **Fine-grained token** (`github_pat_...`): Token ayarlarında "Repository
  access" kısmında bu repo seçili mi? "Permissions → Contents" izni
  **"Read and write"** olarak ayarlanmış mı (varsayılan "No access"tır)?
- **Classic token** (`ghp_...`): Token oluşturulurken `repo` scope'u
  işaretlenmiş mi (private repo'lar için zorunlu)?
- Repo bir **organizasyona** aitse, organizasyon PAT erişimini
  kısıtlıyor olabilir (Organization Settings → Personal access tokens);
  token'ın onaylanması gerekebilir.
- `GITHUB_REPO` değeri tam olarak `kullanici-adi/repo-adi` formatında mı
  yazıldı (yazım hatası, fazladan `.git` uzantısı vb. olmamalı)?

---

## Uygulama sayfaları

- **🏠 Ana Sayfa** — o haftaki önerilen kupon (6 sayı + Joker), güven skoru
- **📊 İstatistik Dashboard** — frekans, sıcak/soğuk sayılar, gecikme, tek/çift ve aralık dağılımları
- **📜 Geçmiş Tahminler** — önceki kuponlar ve gerçekleşen isabet sayıları
- **🗂️ Veri Yönetimi** — manuel giriş, CSV içe aktarma, deneysel otomatik toplama
- **🤖 Agent Durumu** — her agent'ın son çalışma zamanı ve model doğruluk metrikleri

---

## Makine öğrenmesi hakkında not

Orijinal spesifikasyon LSTM/derin öğrenme önermişti. Bu sürüm, Streamlit
Community Cloud gibi ücretsiz/hafif kaynaklı ortamlarda saniyeler içinde
eğitilebilmesi için `RandomForestClassifier` (scikit-learn) kullanır.
Veri az olduğunda (30 çekilişten az) otomatik olarak basit frekans oranına
geri döner. `src/ml_predictor.py` dosyasındaki `train_and_predict`
fonksiyonu, istenirse daha karmaşık bir modelle değiştirilebilir; diğer
tüm agent'lar yalnızca dönen `{sayı: olasılık_skoru}` sözlüğüne bağımlıdır.

---

## Test

```bash
pip install pytest
pytest tests/ -v
```

---

## Yol haritası (orijinal spesifikasyondan uyarlanmıştır)

| Aşama | Bu sürümdeki karşılığı |
|---|---|
| Veri Toplama Altyapısı | `src/database.py`, `src/data_collector.py` |
| Temel İstatistik Analiz | `src/statistics_analyzer.py` |
| ML Model Geliştirme | `src/ml_predictor.py` |
| Agent Entegrasyonu | `scripts/update_data.py` |
| Kendi Kendini Güncelleme | `src/self_improvement.py` + GitHub Actions |
| Frontend Geliştirme | `app.py` (Streamlit) |
| Canlıya Alma | Streamlit Community Cloud + GitHub Actions |

## Sorumlu Oyun

Kumar/şans oyunu bağımlılığı hakkında 7/24 ücretsiz ve gizli destek için
Yeşilay'ın **YEDAM Danışma Hattı'nı (115)** arayabilirsiniz.
