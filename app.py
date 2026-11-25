import streamlit as st
import pandas as pd
import requests
import yfinance as yf
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="XAU Macro Portal", page_icon="🥇", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .main-header {font-size: 2.2rem; font-weight: 700; margin-bottom: 0.2rem;}
    .bias-box {padding: 1.2rem; border-radius: 12px; text-align: center; margin: 1rem 0;}
    .strong-bull {background: linear-gradient(135deg, #0f9d58, #34a853); color: white;}
    .mild-bull {background: linear-gradient(135deg, #81c995, #a8dab5); color: #0d652d;}
    .neutral {background: linear-gradient(135deg, #f1f3f4, #e8eaed); color: #3c4043;}
    .mild-bear {background: linear-gradient(135deg, #fdd663, #fbbc04); color: #7a5c00;}
    .strong-bear {background: linear-gradient(135deg, #d93025, #ea4335); color: white;}
    .metric-card {background: #f8f9fa; color: #202124; padding: 1rem; border-radius: 10px; border: 1px solid #e0e0e0;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60)
def get_gold_price():
    try:
        r = requests.get("https://api.gold-api.com/price/XAU", timeout=8)
        data = r.json()
        return {"price": float(data.get("price", 0)), "updated": data.get("updatedAtReadable", "N/A")}
    except Exception:
        return {"price": None, "updated": "Error"}


@st.cache_data(ttl=90)
def get_market_data():
    symbols = {"DXY": "DX-Y.NYB", "US10Y": "^TNX", "Silver": "SI=F", "VIX": "^VIX", "Gold_Futures": "GC=F"}
    result = {}
    for name, ticker in symbols.items():
        try:
            t = yf.Ticker(ticker)
            try:
                price = t.fast_info.last_price
                prev = t.fast_info.previous_close
            except Exception:
                hist = t.history(period="5d")
                if len(hist) >= 2:
                    price = float(hist["Close"].iloc[-1])
                    prev = float(hist["Close"].iloc[-2])
                else:
                    price = prev = None
            change = price - prev if price and prev else None
            change_pct = (change / prev * 100) if change is not None and prev else None
            result[name] = {"price": price, "change": change, "change_pct": change_pct}
        except Exception:
            result[name] = {"price": None, "change": None, "change_pct": None}
    return result


@st.cache_data(ttl=300)
def get_high_impact_news(days=2):
    try:
        url = f"https://showmytrades.com/api/public/calendar/v1?currency=USD&impact=high&days={days}"
        r = requests.get(url, timeout=10)
        data = r.json()
        events = data.get("events", [])
        now = datetime.now(timezone.utc)
        cleaned = []
        for e in events:
            try:
                t = datetime.fromisoformat(e["time"].replace("Z", "+00:00"))
                if t > now - timedelta(hours=6):
                    cleaned.append({
                        "time": t,
                        "title": e.get("title", ""),
                        "forecast": e.get("forecast", ""),
                        "previous": e.get("previous", ""),
                        "actual": e.get("actual", ""),
                    })
            except Exception:
                continue
        cleaned.sort(key=lambda x: x["time"])
        return cleaned[:12]
    except Exception:
        return []


def calculate_bias(market):
    score = 0
    reasons = []

    dxy = market.get("DXY", {})
    if dxy.get("change_pct") is not None:
        if dxy["change_pct"] < -0.15:
            score += 2
            reasons.append("DXY falling → Gold support (+2)")
        elif dxy["change_pct"] > 0.15:
            score -= 2
            reasons.append("DXY rising → Gold pressure (−2)")
        else:
            reasons.append("DXY flat (0)")

    yld = market.get("US10Y", {})
    if yld.get("change") is not None:
        if yld["change"] < -0.03:
            score += 1.5
            reasons.append("10Y Yield falling → Gold support (+1.5)")
        elif yld["change"] > 0.03:
            score -= 1.5
            reasons.append("10Y Yield rising → Gold pressure (−1.5)")
        else:
            reasons.append("10Y Yield flat (0)")

    sil = market.get("Silver", {})
    gold_fut = market.get("Gold_Futures", {})
    if sil.get("change_pct") is not None and gold_fut.get("change_pct") is not None:
        if sil["change_pct"] * gold_fut["change_pct"] > 0 and abs(sil["change_pct"]) > 0.3:
            if sil["change_pct"] > 0:
                score += 1
                reasons.append("Silver confirming upside (+1)")
            else:
                score -= 1
                reasons.append("Silver confirming downside (−1)")

    vix = market.get("VIX", {})
    if vix.get("change_pct") is not None:
        if vix["change_pct"] > 5:
            score += 0.5
            reasons.append("VIX rising (risk-off) mild gold support (+0.5)")
        elif vix["change_pct"] < -5:
            score -= 0.5
            reasons.append("VIX falling (risk-on) mild gold pressure (−0.5)")

    if score >= 3:
        label, css = "STRONG BULL", "strong-bull"
    elif score >= 1:
        label, css = "MILD BULL", "mild-bull"
    elif score <= -3:
        label, css = "STRONG BEAR", "strong-bear"
    elif score <= -1:
        label, css = "MILD BEAR", "mild-bear"
    else:
        label, css = "NEUTRAL / RANGE", "neutral"

    return {"score": round(score, 1), "label": label, "css": css, "reasons": reasons}


st.markdown('<p class="main-header">🥇 XAU Macro Portal</p>', unsafe_allow_html=True)
st.caption("Automatic intermarket + news filter for Gold (XAUUSD).")

col_r1, col_r2 = st.columns([3, 1])
with col_r2:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with st.spinner("Loading live market data..."):
    gold = get_gold_price()
    market = get_market_data()
    news = get_high_impact_news()
    bias = calculate_bias(market)

m1, m2, m3, m4 = st.columns(4)

with m1:
    price = gold["price"]
    st.metric("XAUUSD (Spot)", f"${price:,.2f}" if price else "—")

with m2:
    dxy = market.get("DXY", {})
    if dxy.get("price"):
        delta = f"{dxy['change_pct']:+.2f}%" if dxy.get("change_pct") is not None else None
        st.metric("DXY", f"{dxy['price']:.2f}", delta=delta)
    else:
        st.metric("DXY", "—")

with m3:
    yld = market.get("US10Y", {})
    if yld.get("price"):
        delta = f"{yld['change']*100:+.1f} bp" if yld.get("change") is not None else None
        st.metric("US 10Y Yield", f"{yld['price']:.2f}%", delta=delta)
    else:
        st.metric("US 10Y Yield", "—")

with m4:
    sil = market.get("Silver", {})
    if sil.get("price"):
        delta = f"{sil['change_pct']:+.2f}%" if sil.get("change_pct") is not None else None
        st.metric("Silver", f"${sil['price']:.2f}", delta=delta)
    else:
        st.metric("Silver", "—")

st.markdown(f"""
<div class="bias-box {bias['css']}">
    <div style="font-size: 1.1rem; opacity: 0.9;">Current Macro Bias for Gold</div>
    <div style="font-size: 2.4rem; font-weight: 800; margin: 0.3rem 0;">{bias['label']}</div>
    <div style="font-size: 1.1rem;">Score: {bias['score']:+.1f}</div>
</div>
""", unsafe_allow_html=True)

if bias["reasons"]:
    with st.expander("Why this bias?", expanded=True):
        for r in bias["reasons"]:
            st.write("• " + r)

st.subheader("Key Drivers")
d1, d2, d3, d4 = st.columns(4)


def driver_card(title, data):
    price = data.get("price")
    chg = data.get("change_pct")
    if price is None or chg is None:
        st.info(f"{title}\n—")
        return
    arrow = "↑" if chg > 0 else "↓" if chg < 0 else "→"
    color = "green" if chg > 0 else "red" if chg < 0 else "gray"
    price_str = f"{price:.2f}" if price < 1000 else f"{price:,.2f}"
    st.markdown(f"""
    <div class="metric-card">
        <b>{title}</b><br>
        <span style="font-size:1.4rem">{price_str}</span><br>
        <span style="color:{color}">{arrow} {chg:+.2f}% </span>
    </div>
    """, unsafe_allow_html=True)


with d1:
    driver_card("DXY (Dollar)", market.get("DXY", {}))
with d2:
    driver_card("US 10Y Yield", market.get("US10Y", {}))
with d3:
    driver_card("Silver", market.get("Silver", {}))
with d4:
    driver_card("VIX", market.get("VIX", {}))

st.subheader("Upcoming High-Impact USD News")
if news:
    news_df = pd.DataFrame([{
        "Time (UTC)": e["time"].strftime("%d %b %H:%M"),
        "Event": e["title"],
        "Forecast": e["forecast"] or "—",
        "Previous": e["previous"] or "—",
        "Actual": e["actual"] or "—"
    } for e in news])
    st.dataframe(news_df, use_container_width=True, hide_index=True)
else:
    st.info("No high-impact USD events in the next ~48 hours or calendar temporarily unavailable.")

st.markdown("---")
st.markdown("""
**How to use this portal**
1. Look at the **Bias** first.
2. Check the drivers and news.
3. Then open the XAUUSD chart and look for confirmation in the direction of the bias.
4. If the chart disagrees with a strong bias, stand aside or reduce size.

This is a **filter**, not a trading signal. Always manage risk.
""")

st.caption(f"Data refreshed • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
st.caption("Not financial advice. For educational / personal use only.")
