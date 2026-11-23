"""
ml_predictor.py
----------------
Makine Ogrenmesi Agenti. Orijinal tasarimda LSTM/derin ogrenme onerilmisti;
bu surum, Streamlit Community Cloud gibi ucretsiz/hafif kaynakli ortamlarda
saniyeler icinde egitilebilmesi icin scikit-learn RandomForestClassifier
kullanir (TensorFlow/PyTorch kurulumu ve egitim suresi bu tur ortamlar icin
pratik degildir). Istenirse `train_and_predict` fonksiyonu daha agir bir
modelle degistirilebilir; geri kalan agent'lar sadece donen skor sozlugune
(1-90 -> 0..1 olasilik) bagimlidir.

ONEMLI (dogruluk uyarisi): Cilgin Sayisal Loto adil/rastgele bir cekilistir.
Bu model, GECMIS frekans ve gecikme oruntulerinden istatistiksel bir skor
uretir; bu skorun gercek cekilis olasiligini degistirdigine dair HICBIR
matematiksel garanti yoktur. Model, uygulamanin "eglence ve bilgilendirme"
amacli kupon onerisi icin bir siralama araci olarak kullanilmalidir.
"""
import numpy as np

try:
    from sklearn.ensemble import RandomForestClassifier
except ImportError:  # scikit-learn kurulu degilse zarif fallback
    RandomForestClassifier = None

from .statistics_analyzer import frequency_analysis

WINDOW_SIZES = (5, 10, 20)
# _build_training_set, ozellik penceresi (max(WINDOW_SIZES)) kadar gecmisi
# atladiktan sonra kalan cekilislerden egitim satiri uretir; en az 10 satir
# uretebilmek icin gereken minimum cekilis sayisi max(WINDOW_SIZES) + 11'dir.
# Bu deger dusuk secilirse (ornegin sabit 30), egitim seti asagida
# "len(X) < 10" kontrolune takilip yine de frekans fallback'ine duser --
# yani MIN_DRAWS_FOR_ML'nin vaat ettigi esikte ML aslinda hic devreye
# girmemis olurdu.
MIN_DRAWS_FOR_ML = max(WINDOW_SIZES) + 11


def _feature_vector_at(sorted_draws, t, window_sizes=WINDOW_SIZES):
    """draws[0..t] (dahil) gecmisini kullanarak draws[t+1]'i tahmin etmek icin
    bir ozellik vektoru uretir."""
    history = sorted_draws[: t + 1]
    n_hist = len(history)
    feat = []

    for w in window_sizes:
        recent = history[-w:]
        counts = np.zeros(90)
        for d in recent:
            for n in d["numbers"]:
                counts[n - 1] += 1
        feat.extend((counts / w).tolist())

    last_seen_gap = np.full(90, n_hist, dtype=float)
    for idx, d in enumerate(history):
        for n in d["numbers"]:
            last_seen_gap[n - 1] = (n_hist - 1) - idx
    feat.extend((last_seen_gap / max(1, n_hist)).tolist())

    return feat


def _build_training_set(sorted_draws, window_sizes=WINDOW_SIZES):
    n_draws = len(sorted_draws)
    start = max(window_sizes)
    rows, targets = [], []
    for t in range(start, n_draws - 1):
        rows.append(_feature_vector_at(sorted_draws, t, window_sizes))
        target_vec = np.zeros(90, dtype=int)
        for n in sorted_draws[t + 1]["numbers"]:
            target_vec[n - 1] = 1
        targets.append(target_vec)
    return np.array(rows), np.array(targets)


def _fallback_frequency_scores(draws):
    freq = frequency_analysis(draws)
    total = sum(freq.values()) or 1
    return {n: freq[n] / total for n in freq}


def train_and_predict(draws, model_version="rf-v1", min_draws=MIN_DRAWS_FOR_ML):
    """
    Her sayi (1-90) icin bir sonraki cekiliste cikma olasilik SKORU (0-1) uretir.
    Yeterli veri yoksa veya scikit-learn kurulu degilse, basit frekans
    oranina geri doner ve bunu model_version="frequency-fallback" ile belirtir.
    """
    sorted_draws = sorted(draws, key=lambda d: d["draw_date"])

    if RandomForestClassifier is None or len(sorted_draws) < min_draws:
        return _fallback_frequency_scores(draws), "frequency-fallback"

    X, Y = _build_training_set(sorted_draws)
    if len(X) < 10:
        return _fallback_frequency_scores(draws), "frequency-fallback"

    clf = RandomForestClassifier(
        n_estimators=80,
        max_depth=6,
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X, Y)

    x_latest = np.array(
        _feature_vector_at(sorted_draws, len(sorted_draws) - 1)
    ).reshape(1, -1)
    raw_pred = clf.predict_proba(x_latest)

    scores = np.zeros(90)
    for i, class_probs in enumerate(raw_pred):
        if class_probs.shape[1] == 2:
            scores[i] = class_probs[0][1]
        else:
            only_class = clf.classes_[i][0]
            scores[i] = 1.0 if only_class == 1 else 0.0

    return {n + 1: float(scores[n]) for n in range(90)}, model_version
