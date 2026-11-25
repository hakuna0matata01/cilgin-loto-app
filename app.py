"""
app.py
-------
Cilgin Sayisal Loto AI Agent Sistemi - Streamlit Arayuzu

Calistirmak icin:
    streamlit run app.py

Bu dosya, orijinal spesifikasyondaki React/Vue + FastAPI/Django mimarisinin
yerine, GitHub + Streamlit Community Cloud ile tek parca halinde
calisabilecek sekilde tasarlanmis surumdur.
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import database as db
from src import statistics_analyzer as stats
from src import coupon_optimizer as optimizer
from src import self_improvement as improver
from src import github_sync

st.set_page_config(
    page_title="Cilgin Sayisal Loto AI Agent",
    page_icon="🎱",
    layout="wide",
)

db.init_db()

DISCLAIMER = (
    "⚠️ **Bu uygulama yalnizca eglence ve bilgilendirme amaclidir.** "
    "Cilgin Sayisal Loto tamamen sansa dayali bir oyundur; her cekilis "
    "matematiksel olarak BAGIMSIZDIR. Hicbir istatistiksel analiz ya da "
    "yapay zeka modeli gelecekteki cekilisi tahmin edemez ya da kazanma "
    "olasiligini artiramaz. 6 sayinin tamamini dogru bilme olasiligi "
    "622.614.630'da 1'dir ve bu, secilen sayilardan bagimsizdir. Lutfen "
    "sorumlu oyun ilkeleri cercevesinde hareket edin."
)


def render_disclaimer():
    st.warning(DISCLAIMER)


def page_home():
    st.title("🎱 Cilgin Sayisal Loto AI Agent Sistemi")
    render_disclaimer()

    draws = db.get_all_draws()
    st.metric("Veritabanindaki toplam cekilis sayisi", len(draws))

    if len(draws) < 5:
        st.info(
            "Kupon onerisi uretmek icin en az 5 gecmis cekilis gerekiyor. "
            "Sol menudeki **Veri Yonetimi** sekmesinden gercek sonuclari "
            "ekleyin, ya da demo icin `python scripts/generate_sample_data.py` "
            "komutunu calistirin (bu SENTETIK/uydurma veri uretir, gercek "
            "cekilis sonucu degildir)."
        )
        return

    col1, col2 = st.columns([2, 1])
    with col2:
        st.subheader("Kupon ayarlari")
        freq_w = st.slider("Frekans agirligi", 0.0, 1.0, 0.4, 0.05)
        ml_w = 1.0 - freq_w
        st.caption(f"ML (RandomForest) agirligi: {ml_w:.2f}")
        use_seed = st.checkbox("Sabit tohum kullan (ayni ayarlarla ayni kupon)")
        seed = st.number_input(
            "Rastgelelik tohumu", value=0, step=1, disabled=not use_seed,
            help="Isaretlenmezse her 'Yeni kupon uret' tiklamasinda Joker ve "
                 "SuperStar icin farkli bir rastgele deger kullanilir (0 "
                 "dahil her deger gecerli bir tohumdur).",
        )
        generate = st.button("🔄 Yeni kupon uret", type="primary", use_container_width=True)

    with col1:
        st.subheader("Onerilen Kupon")
        cache_key = "current_coupon"
        if generate or cache_key not in st.session_state:
            with st.spinner("Agent'lar calisiyor: istatistik + ML + optimizasyon..."):
                coupon = optimizer.generate_coupon(
                    draws, freq_weight=freq_w, ml_weight=ml_w,
                    seed=(seed if use_seed else None),
                )
                st.session_state[cache_key] = coupon
        coupon = st.session_state[cache_key]

        # DUZELTME: Onceki surumde burada tek bir deger "Joker (SuperStar)"
        # diye TEK bir alan gibi gosteriliyordu. Oysa resmi cekiliste
        # bunlar birbirinden bagimsiz, ayri birer kureden cekilen iki ayri
        # sayidir (Joker: 5+1 kategorisini belirler; SuperStar: kupona
        # ekstra ucretle eklenen, ayri bir ikramiye zinciri). Artik ikisi
        # ayri ayri gosteriliyor ve ayri ayri tahmin ediliyor.
        balls = " ".join(f"**`{n:02d}`**" for n in coupon["numbers"])
        st.markdown(f"### Ana Numaralar: {balls}")
        jk_col, ss_col = st.columns(2)
        jk_col.markdown(f"### Joker: `{coupon['joker']:02d}`")
        ss_col.markdown(f"### SuperStar: `{coupon['superstar']:02d}`")
        st.progress(min(coupon["confidence_score"], 1.0))
        st.caption(
            f"Guven skoru: {coupon['confidence_score']:.3f} · "
            f"Model: {coupon['model_version']} · "
            "(Not: bu skor bir siralama/eglence metrigidir, gercek "
            "kazanma olasiligini yansitmaz.)"
        )

        if st.button("💾 Bu kuponu 'Gecmis Tahminler' listesine kaydet"):
            db.insert_prediction(
                prediction_date=date.today().isoformat(),
                draw_date="TBD",
                predicted_numbers=coupon["numbers"],
                predicted_joker=coupon["joker"],
                predicted_superstar=coupon["superstar"],
                confidence_score=coupon["confidence_score"],
                model_version=coupon["model_version"],
            )
            st.success("Kupon kaydedildi. Gercek cekilis tarihini 'Gecmis Tahminler' sekmesinde guncelleyebilirsiniz.")


def page_dashboard():
    st.title("📊 Istatistik Dashboard")
    render_disclaimer()

    draws = db.get_all_draws()
    if not draws:
        st.info("Henuz veri yok. Once 'Veri Yonetimi' sekmesinden cekilis ekleyin.")
        return

    s = stats.summary(draws)

    col1, col2, col3 = st.columns(3)
    col1.metric("Toplam cekilis", s["toplam_cekilis"])
    col2.metric("Tek / Cift orani", f"{s['tek_cift']['tek']} / {s['tek_cift']['cift']}")
    col3.metric("Ardisik sayi cifti gorulme sayisi", s["ardisik_sayisi"])

    st.subheader("🔥 Sicak sayilar (son 50 cekiliste en sik)")
    hot_df = pd.DataFrame(s["sicak"], columns=["Sayi", "Cikma Sayisi"])
    st.bar_chart(hot_df.set_index("Sayi"))

    st.subheader("🧊 Soguk sayilar (son 50 cekiliste en az)")
    cold_df = pd.DataFrame(s["soguk"], columns=["Sayi", "Cikma Sayisi"])
    st.bar_chart(cold_df.set_index("Sayi"))

    st.subheader("📈 Tum sayilarin frekans dagilimi (1-90)")
    freq_df = pd.DataFrame(
        {"Sayi": list(s["frekans"].keys()), "Frekans": list(s["frekans"].values())}
    ).set_index("Sayi")
    st.bar_chart(freq_df)

    st.subheader("⏳ Gecikme analizi (kac cekilistir cikmadi)")
    gap_df = pd.DataFrame(
        {"Sayi": list(s["gecikme"].keys()), "Gecikme": list(s["gecikme"].values())}
    ).sort_values("Gecikme", ascending=False).head(15).set_index("Sayi")
    st.bar_chart(gap_df)

    col4, col5 = st.columns(2)
    with col4:
        st.subheader("Aralik dagilimi")
        st.bar_chart(pd.DataFrame(s["aralik_dagilimi"], index=["adet"]).T)
    with col5:
        st.subheader("Cekilis toplam-deger dagilimi")
        sum_df = pd.DataFrame(s["toplam_dagilimi"], columns=["Tarih", "Toplam"]).set_index("Tarih")
        st.line_chart(sum_df)

    col6, col7 = st.columns(2)
    with col6:
        st.subheader("🃏 Joker frekansi (1-90)")
        joker_df = pd.DataFrame(
            {"Sayi": list(s["joker_frekans"].keys()), "Frekans": list(s["joker_frekans"].values())}
        ).set_index("Sayi")
        st.bar_chart(joker_df)
    with col7:
        st.subheader("⭐ SuperStar frekansi (1-90)")
        superstar_df = pd.DataFrame(
            {"Sayi": list(s["superstar_frekans"].keys()), "Frekans": list(s["superstar_frekans"].values())}
        ).set_index("Sayi")
        st.bar_chart(superstar_df)
    st.caption(
        "Joker ve SuperStar birbirinden bagimsiz ayri kurelerden cekilir; "
        "bu yuzden ayri ayri gosterilir (bkz. proje incelemesi notlari)."
    )

    if s["ikramiye_gecmisi"]:
        st.subheader("💰 Devreden/kazanilan ikramiye gecmisi (TL)")
        jackpot_df = pd.DataFrame(
            s["ikramiye_gecmisi"], columns=["Tarih", "Ikramiye (TL)"]
        ).set_index("Tarih")
        st.line_chart(jackpot_df)
        st.caption(
            "Not: Bu veri yalnizca ilgili alan doldurularak girilmis "
            "cekilisler icin mevcuttur (ornegin otomatik toplanan "
            "cekilislerde su an bu bilgi ayristirilmiyor)."
        )


def page_predictions():
    st.title("📜 Gecmis Tahminler")
    render_disclaimer()

    if st.button("🔁 Sonuclanmis tahminleri degerlendir (Kendi Kendini Gelistirme Agenti)"):
        result = improver.evaluate_and_log()
        st.success(f"Degerlendirme tamamlandi: {result}")

    predictions = db.get_predictions()
    if not predictions:
        st.info("Henuz kaydedilmis tahmin yok.")
        return

    df = pd.DataFrame(predictions)
    df["predicted_numbers"] = df["predicted_numbers"].apply(
        lambda nums: " ".join(f"{n:02d}" for n in nums)
    )
    display_cols = [
        "prediction_date", "draw_date", "predicted_numbers", "predicted_joker",
        "predicted_superstar", "confidence_score", "model_version",
        "actual_matches", "actual_joker_match", "actual_superstar_match",
    ]
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

    st.download_button(
        "⬇️ Tahminleri CSV olarak indir",
        data=df[display_cols].to_csv(index=False).encode("utf-8-sig"),
        file_name="gecmis_tahminler.csv",
        mime="text/csv",
    )

    # YENI: actual_joker_match / actual_superstar_match her satirda
    # tutuluyordu ama hicbir yerde ozet/toplu oran olarak gosterilmiyordu
    # (jackpot_amount ve joker_frekans icin daha once bulunan durumla ayni
    # oruntu -- bkz. proje incelemesi notlari). Degerlendirilmis (gercek
    # sonucla eslesmis) tahminler varsa burada ozetleniyor.
    evaluated = [p for p in predictions if p["actual_matches"] is not None]
    if evaluated:
        st.subheader("Ozet (degerlendirilmis tahminler)")
        joker_known = [p for p in evaluated if p.get("actual_joker_match") is not None]
        superstar_known = [p for p in evaluated if p.get("actual_superstar_match") is not None]

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Degerlendirilen tahmin sayisi", len(evaluated))
        if joker_known:
            joker_rate = sum(p["actual_joker_match"] for p in joker_known) / len(joker_known)
            col_b.metric(
                "Joker isabet orani", f"{joker_rate:.1%}",
                help="Adil/rastgele bir cekiliste istatistiksel olarak "
                     "beklenen oran ~%1,1'dir (1/90). Bu deger yuksek "
                     "ciksa bile gelecekteki cekilisi ONGOREMEZ.",
            )
        if superstar_known:
            ss_rate = sum(p["actual_superstar_match"] for p in superstar_known) / len(superstar_known)
            col_c.metric(
                "SuperStar isabet orani", f"{ss_rate:.1%}",
                help="Adil/rastgele bir cekiliste istatistiksel olarak "
                     "beklenen oran ~%1,1'dir (1/90). Bu deger yuksek "
                     "ciksa bile gelecekteki cekilisi ONGOREMEZ.",
            )
        if not joker_known and not superstar_known:
            st.caption(
                "Joker/SuperStar isabet orani hesaplanamadi: degerlendirilen "
                "tahminlerin hicbirinde bu alanlar dolu degil."
            )

    st.subheader("Bekleyen bir tahminin gercek cekilis tarihini gir")
    pending = [p for p in predictions if p["draw_date"] == "TBD"]
    if pending:
        options = {f"#{p['id']} - {p['prediction_date']} - {p['predicted_numbers']}": p["id"] for p in pending}
        label = st.selectbox("Tahmin sec", list(options.keys()))
        new_date = st.date_input("Gercek cekilis tarihi")
        if st.button("Guncelle"):
            db.update_prediction_draw_date(options[label], new_date.isoformat())
            st.success("Guncellendi. Artik bu tahmin, ilgili cekilis eklendiginde otomatik degerlendirilebilir.")
    else:
        st.caption("Bekleyen (TBD) tahmin yok.")


def _persist_after_write(action_label):
    """Manuel/CSV/scraper ile veri eklendikten sonra cagrilir. GitHub
    senkronizasyonu yapilandirilmissa degisikligi hemen GitHub'a commit'ler
    (boylece Streamlit Cloud yeniden basladiginda veri KAYBOLMAZ).
    Yapilandirilmamissa kullaniciyi bilgilendirir ama hata FIRLATMAZ."""
    if github_sync.is_configured():
        with st.spinner("Kalicilik icin GitHub'a kaydediliyor..."):
            ok, msg = github_sync.push_db_to_github(commit_message=f"chore: {action_label}")
        if ok:
            st.success(msg)
        else:
            st.warning(f"Veri yerel olarak kaydedildi ancak GitHub senkronizasyonu basarisiz oldu: {msg}")
    else:
        st.info(
            "ℹ️ Veri bu oturumun diskine kaydedildi. **Streamlit Cloud'da "
            "calisiyorsaniz**, uygulama yeniden baslatildiginda bu veri "
            "kaybolabilir -- kalici olmasi icin asagidaki 'Kalicilik "
            "(GitHub Senkronizasyonu)' bolumunu yapilandirin. **Kendi "
            "bilgisayarinizda calistiriyorsaniz** bu adima gerek yoktur, "
            "veri zaten diskinizde kalicidir."
        )


def page_data_management():
    st.title("🗂️ Veri Yonetimi")
    st.caption(
        "Veri Toplayici Agent: gercek cekilis sonuclarini buradan elle girebilir, "
        "CSV ile toplu yukleyebilir ya da (deneysel/best-effort) otomatik "
        "toplamayi deneyebilirsiniz."
    )

    # --- Kalicilik durumu ---
    with st.container(border=True):
        if github_sync.is_configured():
            st.success(
                "☁️ GitHub senkronizasyonu **aktif**. Bu sekmede yaptiginiz her "
                "ekleme, otomatik olarak repo'ya commit'lenir -- yani kalicidir."
            )
        else:
            st.warning(
                "☁️ GitHub senkronizasyonu **yapilandirilmamis**. Yerelde "
                "calistiriyorsaniz sorun degil (veri diskinizde kalici kalir). "
                "Streamlit Cloud'da calistiriyorsaniz, veri yeniden baslatmada "
                "kaybolmasin diye kurulum icin README > 'Manuel girislerin "
                "kalici olmasi' bolumune bakin."
            )
        col_a, col_b = st.columns([1, 3])
        with col_a:
            if st.button("☁️ Simdi GitHub'a kaydet", disabled=not github_sync.is_configured()):
                ok, msg = github_sync.push_db_to_github(commit_message="chore: manuel senkronizasyon")
                (st.success if ok else st.error)(msg)
        with col_b:
            if st.button("🔌 Baglantiyi test et", disabled=not github_sync.is_configured()):
                ok, msg = github_sync.test_connection()
                (st.success if ok else st.error)(msg)

    tab1, tab2, tab3, tab4 = st.tabs([
        "✍️ Manuel Giris", "📤 CSV Yukle", "🌐 Otomatik Toplama (deneysel)", "🗄️ Yedekle / Geri Yukle",
    ])

    with tab1:
        # DUZELTME: Onceki surumde tek bir alan "Joker (SuperStar)" diye
        # etiketlenmisti ve tek bir sayi kaydediliyordu. Oysa resmi
        # sonuclarda bunlar birbirinden bagimsiz iki ayri sayidir (bkz.
        # proje incelemesi notlari). Artik ayri ayri giriliyor.
        with st.form("manual_entry"):
            draw_date = st.date_input("Cekilis tarihi")
            cols = st.columns(6)
            numbers = [cols[i].number_input(f"N{i+1}", 1, 90, i + 1, key=f"n{i}") for i in range(6)]
            jk_col, ss_col = st.columns(2)
            joker = jk_col.number_input("Joker", 1, 90, 1)
            superstar_unknown = ss_col.checkbox(
                "SuperStar bilinmiyor/yok (ör. 2021 oncesi cekilis)"
            )
            superstar = ss_col.number_input(
                "SuperStar", 1, 90, 1, disabled=superstar_unknown,
            )
            jackpot = st.number_input("Devreden/kazanilan ikramiye (TL, opsiyonel)", min_value=0.0, value=0.0)
            submitted = st.form_submit_button("Kaydet")
            if submitted:
                try:
                    ok = db.insert_draw(
                        draw_date.isoformat(), list(numbers), int(joker),
                        superstar_number=(None if superstar_unknown else int(superstar)),
                        jackpot_amount=jackpot or None, source="manual",
                    )
                    if ok:
                        st.success("Cekilis kaydedildi.")
                        _persist_after_write(f"{draw_date.isoformat()} cekilisi manuel eklendi")
                    else:
                        st.warning("Bu tarih icin zaten bir kayit var.")
                except ValueError as e:
                    st.error(str(e))

    with tab2:
        st.markdown(
            "Beklenen basliklar: `draw_date,n1,n2,n3,n4,n5,n6,joker"
            "[,superstar,jackpot_amount,winner_count]` (draw_date formati: "
            "`YYYY-MM-DD`). `superstar` sutunu opsiyoneldir; yoksa veya "
            "bossa o kayit icin SuperStar bilinmiyor kabul edilir."
        )
        uploaded = st.file_uploader("CSV dosyasi sec", type=["csv"])
        if uploaded is not None and st.button("CSV'yi ice aktar"):
            added, skipped, errors = db.import_draws_csv(uploaded)
            st.success(f"{added} kayit eklendi, {skipped} kayit atlandi (zaten mevcut).")
            if errors:
                st.error("Bazi satirlarda hata olustu:")
                for e in errors:
                    st.write(f"- {e}")
            if added:
                _persist_after_write(f"{added} kayit CSV ile eklendi")

    with tab3:
        st.markdown(
            "⚠️ Bu ozellik **deneyseldir** ve haber sitesi HTML yapisina baglidir; "
            "yapisi degisirse calismayabilir. Kullanmadan once hedef sitenin "
            "robots.txt ve kullanim sartlarini kontrol edin."
        )
        if st.button("Otomatik toplamayi dene"):
            from src import data_collector as collector
            with st.spinner("Deneniyor..."):
                try:
                    results = collector.collect_recent_results()
                except Exception as e:
                    st.error(f"Toplama basarisiz: {e}")
                    results = []
            if results:
                added = 0
                for r in results:
                    if db.insert_draw(
                        r["draw_date"], r["numbers"], r["joker_number"],
                        superstar_number=r.get("superstar_number"), source="scraper",
                    ):
                        added += 1
                st.success(f"{added} yeni cekilis eklendi.")
                if added:
                    _persist_after_write(f"{added} kayit otomatik toplama ile eklendi")
            else:
                st.warning(
                    "Sonuc bulunamadi. Site yapisi degismis olabilir "
                    "(src/data_collector.py icindeki seciciler guncellenmeli) "
                    "ya da bu ortamdan hedef siteye erisim engellenmis olabilir."
                )

    with tab4:
        st.markdown(
            "GitHub senkronizasyonu kurmak istemiyorsaniz, veritabanini elle "
            "**indirip** bir sonraki oturumda geri **yukleyerek** de veriyi "
            "koruyabilirsiniz (basit ama manuel bir yontem)."
        )
        try:
            with open(db.DB_PATH, "rb") as f:
                db_bytes = f.read()
            st.download_button(
                "⬇️ Veritabanini indir (loto.db)",
                data=db_bytes,
                file_name="loto.db",
                mime="application/octet-stream",
            )
        except FileNotFoundError:
            st.info("Henuz olusturulmus bir veritabani yok.")

        st.divider()
        restore_file = st.file_uploader("Daha once indirdiginiz bir loto.db dosyasini geri yukleyin", type=["db"])
        if restore_file is not None and st.button("Geri yukle (mevcut verinin USTUNE YAZAR)"):
            with open(db.DB_PATH, "wb") as f:
                f.write(restore_file.read())
            st.success("Veritabani geri yuklendi. Sayfayi yenileyin.")

    st.divider()
    st.subheader("Tum cekilisler")
    draws = db.get_all_draws()
    if draws:
        df = pd.DataFrame(draws)
        display_df = df[["draw_date", "day_of_week", "numbers", "joker_number",
                          "superstar_number", "jackpot_amount", "winner_count",
                          "source"]].copy()
        display_df["numbers"] = display_df["numbers"].apply(
            lambda nums: " ".join(f"{n:02d}" for n in nums)
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.download_button(
            "⬇️ Tum cekilisleri CSV olarak indir",
            data=display_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="cekilisler.csv",
            mime="text/csv",
            help="loto.db'nin aksine, bu dosya Excel/Sheets gibi "
                 "programlarda dogrudan acilabilir; ayni formatta geri "
                 "ice aktarmak icin 'CSV Yukle' sekmesini kullanabilirsiniz.",
        )
    else:
        st.info("Henuz cekilis eklenmedi.")


def page_agent_status():
    st.title("🤖 Agent Durumu")
    render_disclaimer()

    draws = db.get_all_draws()
    predictions = db.get_predictions()
    metrics = db.get_metrics()

    agents = [
        ("Veri Toplayici Agent", f"{len(draws)} cekilis kayitli", draws[-1]["draw_date"] if draws else "—"),
        ("Istatistik Analiz Agenti", "Her sayfa yuklemesinde calisir", "Anlik (on-demand)"),
        ("Makine Ogrenmesi Agenti", "RandomForestClassifier (fallback: frekans)", "Kupon uretiminde calisir"),
        ("Kupon Optimizasyon Agenti", f"{len(predictions)} kupon uretildi", predictions[0]["prediction_date"] if predictions else "—"),
        ("Kendi Kendini Gelistirme Agenti", f"{len(metrics)} degerlendirme kaydi", metrics[0]["evaluation_date"] if metrics else "—"),
    ]
    status_df = pd.DataFrame(agents, columns=["Agent", "Durum", "Son Islem"])
    st.dataframe(status_df, use_container_width=True, hide_index=True)

    if metrics:
        st.subheader("Model dogruluk metrikleri (zaman icinde)")
        m_df = pd.DataFrame(metrics)
        st.line_chart(m_df.set_index("evaluation_date")["avg_matches"])
        st.caption(
            "avg_matches: onerilen kuponlarin, gerceklesen cekilislerle "
            "ortalama kac sayi eslestigi (0-6 arasi). Bu deger zamanla "
            "yukselse bile, adil bir cekiliste beklenen ortalama sabit "
            "kalir (yaklasik 6 * 6/90 = 0.4); buyuk sapmalar veri/ornek "
            "kucuklugunden kaynaklanabilir."
        )
    else:
        st.info("Henuz metrik yok. Bir kupon sonuclandiginda 'Gecmis Tahminler' sekmesinden degerlendirin.")


PAGES = {
    "🏠 Ana Sayfa": page_home,
    "📊 Istatistik Dashboard": page_dashboard,
    "📜 Gecmis Tahminler": page_predictions,
    "🗂️ Veri Yonetimi": page_data_management,
    "🤖 Agent Durumu": page_agent_status,
}

st.sidebar.title("🎱 Loto AI Agent")
choice = st.sidebar.radio("Sayfa sec", list(PAGES.keys()))
st.sidebar.divider()
st.sidebar.caption(
    "Çılgın Sayısal Loto AI Agent Sistemi\n\n"
    "GitHub + Streamlit surumu. Kaynak: orijinal proje spesifikasyonu."
)

PAGES[choice]()
