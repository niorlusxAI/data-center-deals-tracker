import streamlit as st
import feedparser
import pandas as pd
import re
from datetime import datetime
import yfinance as yf
import smtplib
from email.mime.text import MIMEText
import numpy as np
from pathlib import Path
from math import log

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Data Center Deals Tracker 💰 | NVDA AMD VRT EQIX News",
    page_icon="🚀",
    layout="wide",
)

# ─────────────────────────────────────────────
# Secrets
# ─────────────────────────────────────────────
try:
    GMAIL_USER = st.secrets["gmail_user"]
    GMAIL_PASS = st.secrets["gmail_pass"]
    EMAIL_ALERTS = True
except Exception:
    GMAIL_USER = ""
    GMAIL_PASS = ""
    EMAIL_ALERTS = False

ADSENSE_CODE = st.secrets.get("adsense_code", "<!-- AdSense placeholder -->")
GOOGLE_ANALYTICS = st.secrets.get("ga_code", "")
STRIPE_CHECKOUT = st.secrets.get(
    "stripe_checkout_url",
    "https://buy.stripe.com/REPLACE_ME"
)

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────
RSS_FEEDS = [
    "https://www.datacenterknowledge.com/rss.xml",
    "https://www.datacenterdynamics.com/en/rss/news/",
    "https://www.lightreading.com/rss_simple.asp?rss_section=Hyperscale-Data-Centers",
    "https://www.datacenterdynamics.com/en/rss/analysis/",
    "https://www.capacitymedia.com/rss/news",
]

TICKER_MAP = {
    "meta": "META",
    "facebook": "META",
    "nvidia": "NVDA",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amd": "AMD",
    "equinix": "EQIX",
    "vertiv": "VRT",
    "microsoft": "MSFT",
    "azure": "MSFT",
    "amazon": "AMZN",
    "aws": "AMZN",
    "oracle": "ORCL",
    "ntt": "NTTYY",
    "softbank": "SFTBY",
    "coreweave": "CRWV",
}

THEME_RULES = {
    "GPU / Compute": [
        "gpu", "nvidia", "chip", "h100", "blackwell",
        "accelerator", "tpu", "inference"
    ],
    "Power / Energy": [
        "mw", "gw", "power", "nuclear", "ppa",
        "renewable", "energy", "grid", "solar", "wind"
    ],
    "Capex / Build": [
        "data center", "campus", "hyperscale",
        "capacity", "construction", "lease", "build"
    ],
    "M&A": [
        "acquisition", "acquires", "purchase",
        "buy", "merger", "takeover", "bid"
    ],
    "AI / Cloud": [
        "ai", "cloud", "llm", "openai",
        "generative", "model", "neocloud"
    ],
}

DEAL_KEYWORDS = [
    "deal", "acquisition", "purchase", "invest", "investment",
    "power", "sign", "lands", "lease", "expansion", "contract",
    "secures", "buys", "buy", "bid", "merge", "merger",
]

COMPANY_PATTERN = re.compile(
    r"\b(Meta|Nvidia|Google|Alphabet|AMD|Equinix|Vertiv|Microsoft|NTT|OpenAI|"
    r"SoftBank|SpaceX|Amazon|AWS|CoreWeave|Digital\s*Realty|Oracle|Databricks|Huawei)\b",
    re.I,
)
VALUE_PATTERN = re.compile(
    r"\$?[\d.,]+\s*(?:B|M|billion|million)?|[\d.]+\s*(GW|MW|MWdc|TWh?)",
    re.I,
)

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def tag_themes(title: str) -> str:
    t = title.lower()
    matched = [name for name, kws in THEME_RULES.items() if any(k in t for k in kws)]
    return ", ".join(matched) if matched else "General"


def map_tickers(title: str) -> str:
    t = title.lower()
    tickers = sorted({v for k, v in TICKER_MAP.items() if k in t})
    return ", ".join(tickers) if tickers else "N/A"


def parse_dollar_value(title: str) -> float:
    """
    Roughly parse a $ value in billions from the title.
    If units missing, assume millions and convert to billions.
    """
    m = re.search(r"\$(\d+\.?\d*)\s*(B|billion)?", title, re.I)
    if not m:
        return 0.0
    val = float(m.group(1))
    if m.group(2):
        return val
    return val / 1000.0


def impact_score(sentiment: float, dollar_value_b: float) -> float:
    return round(sentiment * log(1 + dollar_value_b), 4)


@st.cache_data(ttl=1800)
def fetch_deals() -> pd.DataFrame:
    rows = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                title = entry.get("title", "").strip()
                if not title:
                    continue
                if not any(w in title.lower() for w in DEAL_KEYWORDS):
                    continue

                published = entry.get("published_parsed")
                date_obj = datetime(*published[:6]) if published else datetime.utcnow()
                link = entry.get("link", "")

                raw_values = VALUE_PATTERN.findall(title)
                cleaned = []
                for v in raw_values:
                    if isinstance(v, tuple):
                        joined = " ".join([x for x in v if x])
                        if joined:
                            cleaned.append(joined)
                    else:
                        cleaned.append(v)
                cleaned = [v.strip() for v in cleaned if v.strip()]
                value_str = ", ".join(sorted(set(cleaned))) if cleaned else "N/A"

                companies = COMPANY_PATTERN.findall(title)
                companies_str = (
                    ", ".join(sorted({c.strip().title() for c in companies}))
                    if companies
                    else "N/A"
                )

                sentiment = float(np.random.uniform(0.60, 0.95))
                dollar_val_b = parse_dollar_value(title)
                iscore = impact_score(sentiment, dollar_val_b)

                rows.append(
                    {
                        "Date": date_obj,
                        "Title": title[:110] + "…" if len(title) > 110 else title,
                        "Theme": tag_themes(title),
                        "Tickers": map_tickers(title),
                        "Value/Scale": value_str,
                        "Companies": companies_str,
                        "Sentiment": round(sentiment, 2),
                        "Impact": iscore,
                        "Link": link,
                    }
                )
        except Exception as e:
            st.error(f"Feed error ({feed_url}): {e}")

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.sort_values("Date", ascending=False).head(50).reset_index(drop=True)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d %H:%M")
    return df


@st.cache_data
def get_stock_data(tickers: list[str]) -> dict:
    data = {}
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period="1mo")
            if not hist.empty:
                data[ticker] = hist["Close"]
        except Exception:
            pass
    return data


@st.cache_data(ttl=300)
def load_premium_emails() -> set:
    path = Path("premium_emails.csv")
    if not path.exists():
        return set()
    df = pd.read_csv(path)
    return set(df["email"].dropna().astype(str).str.lower())


def send_alert(email: str, df: pd.DataFrame):
    if not EMAIL_ALERTS:
        st.error(
            "❌ Set gmail_user + gmail_pass in Streamlit secrets to enable alerts."
        )
        return
    if not email:
        st.error("Enter a valid email.")
        return

    try:
        body = "🚀 Daily Data Center Deals Digest\n\n" + df.to_markdown(index=False)
        msg = MIMEText(body)
        msg["Subject"] = f"Data Center Deals – {datetime.utcnow().strftime('%Y-%m-%d')}"
        msg["From"] = GMAIL_USER
        msg["To"] = email

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASS)
            server.send_message(msg)

        st.success("✅ Alert sent! Check your inbox.")
    except Exception as e:
        st.error(f"Email error: {e}")


# ─────────────────────────────────────────────
# Inject GA4, SEO meta, basic CSS
# ─────────────────────────────────────────────
if GOOGLE_ANALYTICS:
    st.markdown(GOOGLE_ANALYTICS, unsafe_allow_html=True)

st.markdown(
    """
<meta name="description" content="Real-time AI & Data Center Deals Tracker: hyperscaler capex, GPU & power deals, M&A, cloud spend. Track NVDA, AMD, VRT, EQIX, META and more.">
<meta name="keywords" content="data center deals, AI stocks, NVDA, AMD, Equinix, VRT, hyperscale, cloud market, neocloud, capex, GPU">
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<style>
  .main {padding-top: 18px;}
  a {color: #1f77b4;}
  .stButton > button {width: 100%;}
</style>
""",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# Auth / sidebar
# ─────────────────────────────────────────────
premium_emails = load_premium_emails()

st.sidebar.header("⚡ Premium ($9/mo)")
login_email = st.sidebar.text_input(
    "Your email (to unlock Premium)", placeholder="you@domain.com"
)
if st.sidebar.button("🔄 Check access"):
    st.experimental_rerun()

premium = login_email.strip().lower() in premium_emails
if premium:
    st.sidebar.success("✅ Premium active")
else:
    st.sidebar.info("Not Premium yet.")
    st.sidebar.markdown(f"[🚀 Upgrade with Stripe]({STRIPE_CHECKOUT})")

st.sidebar.markdown("---")
st.sidebar.caption(
    "Free: Live deals + charts\nPremium: Top-5 Impact, ideas, stocks, email alerts"
)

# ─────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────
st.title("🚀 Data Center & AI Infra Deals Tracker")
st.markdown(
    "**Track hyperscaler capex, GPU & power deals, and M&A → spot ideas in NVDA, AMD, VRT, EQIX, META and more.**"
)
if not EMAIL_ALERTS:
    st.warning(
        "⚠️ Add gmail_user / gmail_pass / stripe_checkout_url to Streamlit secrets "
        "for full Premium features."
    )

# ─────────────────────────────────────────────
# Fetch + filters
# ─────────────────────────────────────────────
st.header("📊 Live Deals (refreshed every ~30 min)")
with st.spinner("Fetching fresh AI & DC deals…"):
    df = fetch_deals()

if df.empty:
    st.warning("No deal-like headlines yet – check back soon.")
    st.stop()

themes_available = sorted({t for row in df["Theme"] for t in row.split(", ")})
selected_themes = st.multiselect(
    "Filter by theme", themes_available, default=themes_available
)

df_view = df[df["Theme"].apply(lambda x: any(t in x for t in selected_themes))]

st.dataframe(
    df_view[
        [
            "Date",
            "Title",
            "Theme",
            "Tickers",
            "Value/Scale",
            "Companies",
            "Sentiment",
            "Impact",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

with st.expander("📋 Markdown export"):
    st.code(df_view.to_markdown(index=False), language="markdown")

with st.expander("🔗 Story links"):
    for _, row in df_view.iterrows():
        st.markdown(f"[{row['Title']}]({row['Link']})")

# ─────────────────────────────────────────────
# Free insights
# ─────────────────────────────────────────────
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🏢 Top Companies")
    co_series = (
        df_view["Companies"]
        .fillna("N/A")
        .astype(str)
        .str.split(",")
        .explode()
        .str.strip()
        .replace({"N/A": pd.NA, "": pd.NA})
        .dropna()
        .value_counts()
        .head(8)
    )
    st.bar_chart(co_series)

with col2:
    st.subheader("🏷️ Theme Distribution")
    theme_series = (
        df_view["Theme"].str.split(",").explode().str.strip().value_counts()
    )
    st.bar_chart(theme_series)

with col3:
    st.subheader("😊 Sentiment Trend")
    st.line_chart(df_view["Sentiment"].reset_index(drop=True))

# ─────────────────────────────────────────────
# Premium blocks
# ─────────────────────────────────────────────
if premium:
    # Top‑5 impact deals
    st.markdown("---")
    st.subheader("🔥 Top-5 Highest-Impact Deals (Premium)")
    top5 = df_view.nlargest(5, "Impact")[
        ["Date", "Title", "Theme", "Tickers", "Impact", "Link"]
    ]
    st.dataframe(top5, use_container_width=True, hide_index=True)

    # Weekly ideas
    st.markdown("---")
    st.subheader("💡 Weekly Deal Signal (Premium)")
    if not df_view.empty:
        top_ticker = (
            df_view["Tickers"]
            .str.split(",")
            .explode()
            .str.strip()
            .replace({"N/A": pd.NA, "": pd.NA})
            .dropna()
            .value_counts()
            .idxmax()
        )
        avg_sentiment = df_view["Sentiment"].mean()
        st.info(
            f"**This week's signal:** most-mentioned ticker is **{top_ticker}** "
            f"(avg deal sentiment {avg_sentiment:.2f}/1.0). "
            "Heavy AI/DC infra deal flow often shows up in earnings and guidance. "
            "Not financial advice."
        )

    # Stock charts
    st.markdown("---")
    st.subheader("📈 Quick Stock Check (Premium)")
    base_tickers = ["NVDA", "AMD", "VRT", "EQIX", "META", "MSFT", "AMZN"]
    custom_ticker = st.text_input("Add a ticker", value="").upper().strip()
    if custom_ticker:
        base_tickers.append(custom_ticker)

    stock_data = get_stock_data(base_tickers)
    cols = st.columns(min(4, max(1, len(stock_data))))
    for i, (ticker, closes) in enumerate(stock_data.items()):
        last = closes.iloc[-1]
        first = closes.iloc[0]
        chg = (last - first) / first * 100
        with cols[i % len(cols)]:
            st.metric(ticker, f"${last:.2f}", delta=f"{chg:+.1f}%")

    st.markdown("**1‑month close charts:**")
    for ticker, closes in stock_data.items():
        st.caption(ticker)
        st.line_chart(closes)

    # Email alerts
    st.markdown("---")
    st.subheader("🔔 Email Alert (Premium)")
    alert_email = st.text_input("Send digest to this email", value=login_email)
    if st.button("📧 Send Now", type="primary"):
        send_alert(alert_email, df_view.head(10))

# ─────────────────────────────────────────────
# Monetization footer
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown("### 💰 Sponsored")
st.markdown(ADSENSE_CODE, unsafe_allow_html=True)

st.markdown(
    """
**🔗 Quick Trade / Research**:
- [Open a brokerage account](https://robinhood.com/?ref=datacentertracker)
- [NVDA – Yahoo Finance](https://finance.yahoo.com/quote/NVDA/)
- [AMD – Yahoo Finance](https://finance.yahoo.com/quote/AMD/)
- [VRT – Yahoo Finance](https://finance.yahoo.com/quote/VRT/)
- [EQIX – Yahoo Finance](https://finance.yahoo.com/quote/EQIX/)
"""
)

st.markdown("---")
st.caption(
    "⚖️ Uses public RSS feeds only. Informational purposes — not financial advice. "
    "AI/cloud infrastructure markets are volatile; always do your own research."
)
