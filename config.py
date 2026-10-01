"""System Bot ayarları. Değiştirmek istediğin her şey burada."""

# BIST 30 bileşenleri, 1 Ekim - 31 Aralık 2026 dönemi.
# Endeks her 3 ayda bir güncellenir; dönem değişince bu listeyi güncelle.
TICKERS = [
    "AEFES", "AKBNK", "ASELS", "ASTOR", "BIMAS", "EKGYO", "ENKAI", "EREGL",
    "FROTO", "GARAN", "GUBRF", "ISCTR", "KCHOL", "KRDMD", "MGROS", "PETKM",
    "PGSUS", "SAHOL", "SASA", "SISE", "TAVHL", "TCELL", "THYAO", "TOASO",
    "TRALT", "TRMET", "TTKOM", "TUPRS", "VAKBN", "YKBNK",
]

# Karşılaştırma için endeks (BIST 30)
BENCHMARK = "XU030"

# Hayali portföy
CAPITAL = 5000.0            # TL, 5 stratejiye eşit bölünür (her biri 1.000 TL)
COMMISSION_RATE = 0.0       # Midas BIST komisyonsuz
SLIPPAGE = 0.001            # alış ve satışta %0,1 fiyat kayması varsayımı
MAX_POS_PER_SLEEVE = 2      # her stratejide aynı anda en fazla 2 pozisyon
MAX_POS_FRACTION = 0.5      # bir pozisyon, stratejinin parasının en fazla yarısı
RISK_PER_TRADE = 0.05       # stop olunursa stratejinin parasının en fazla %5'i gider

# Veri
HISTORY_PERIOD = "3y"       # göstergeler ve geçmiş test için
MIN_BARS = 120              # bundan kısa geçmişi olan hisse atlanır
TZ = "Europe/Istanbul"

# Bildirimler
MOVE_ALERT_PCT = 4.0        # elde tutulan hisse gün içinde bu kadar oynarsa haber ver
NEWS_PER_TICKER = 2         # gün sonu raporunda hisse başına haber başlığı
CANDIDATES_PER_STRATEGY = 3 # gün sonu raporunda vade başına gösterilen fırsat sayısı
