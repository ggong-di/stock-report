"""
주린이 탈출 프로젝트 - 매일 아침 주식 리포트
대상: 40대 중반, 월 20~30만원 투자, 노후 준비 목적
보유 계좌: ISA 서민형 (작년 말 개설, 만기 9999년)
"""

import yfinance as yf
from datetime import datetime, date
import os, sys, smtplib, feedparser, urllib.request, re, html
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPORT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 국내 지수 ──────────────────────────────────────────────────
INDICES = {
    "KOSPI":   "^KS11",
    "KOSDAQ":  "^KQ11",
    "S&P 500": "^GSPC",
    "NASDAQ":  "^IXIC",
    "다우존스": "^DJI",
}

# ── 글로벌 증시 ────────────────────────────────────────────────
GLOBAL = {
    "니케이225 (일본)":  "^N225",
    "항셍 (홍콩)":       "^HSI",
    "상하이 (중국)":     "000001.SS",
    "DAX (독일)":       "^GDAXI",
    "FTSE (영국)":      "^FTSE",
}

# ── 거시 지표 ──────────────────────────────────────────────────
MACRO = {
    "달러/원":          "KRW=X",
    "금 ($/온스)":      "GC=F",
    "WTI 유가 ($/배럴)":"CL=F",
    "미국 10년 금리(%)": "^TNX",
    "비트코인 (USD)":   "BTC-USD",
    "이더리움 (USD)":   "ETH-USD",
}

# ── 추천 ETF ───────────────────────────────────────────────────
ETFS = {
    "TIGER 미국S&P500":   "360750.KS",
    "TIGER 미국나스닥100": "133690.KS",
    "KODEX 200":          "069500.KS",
    "KODEX TDF2045":      "315960.KS",
}

# ── 국내 주요 종목 (급등락 추적) ────────────────────────────────
STOCKS_KR = {
    "삼성전자":   "005930.KS",
    "SK하이닉스": "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "삼성바이오로직스": "207940.KS",
    "현대차":    "005380.KS",
    "NAVER":    "035420.KS",
    "카카오":   "035720.KS",
    "셀트리온":  "068270.KS",
}

# ── 미국 주요 종목 ────────────────────────────────────────────
STOCKS_US = {
    "엔비디아": "NVDA",
    "애플":    "AAPL",
    "마이크로소프트": "MSFT",
    "테슬라":  "TSLA",
    "아마존":  "AMZN",
    "메타":    "META",
}

# ── 뉴스 피드 ─────────────────────────────────────────────────
NEWS_FEEDS = [
    ("한국경제", "https://www.hankyung.com/feed/finance"),
    ("매일경제", "https://www.mk.co.kr/rss/30200030/"),
    ("연합인포맥스", "https://news.einfomax.co.kr/rss/allArticle.xml"),
]

# 증시 영향 키워드 (이것만 통과)
MARKET_KEYWORDS = [
    "증시","주가","코스피","코스닥","나스닥","S&P","반도체","금리","연준","Fed","FOMC",
    "환율","달러","수출","GDP","물가","인플레","채권","ETF","유가","원자재","금",
    "이란","이스라엘","전쟁","중동","관세","무역","AI","반도체","엔비디아","삼성","하이닉스",
    "실적","어닝","경기침체","침체","매출","영업이익","수익","파산","IPO","상장",
    "중국","미국","일본","유럽","OPEC","원유","에너지","배당","자사주","분기"
]

# 걸러낼 키워드 (정치·사회 뉴스)
NOISE_KEYWORDS = [
    "대통령","교황","G7","한반도","북한","DMZ","트럼프 방한","이재명","윤석열",
    "총선","정치","청와대","국회","법안","판결","사건","사고","날씨","스포츠","야구","축구"
]

TIPS = [
    ("ETF란?", "과일 바구니예요. 사과 하나 사는 대신 사과·배·포도가 다 든 바구니를 한 번에 사는 것. 하나가 망해도 나머지가 살아있어요."),
    ("ISA 서민형이란?", "나라가 만든 절세 계좌예요. 이 안에서 번 돈은 400만원까지 세금 0원. 초과분도 9.9% 저율과세 (일반 15.4%의 절반)."),
    ("ISA vs 연금저축 차이", "ISA: 번 돈에 세금 안 냄. 연금저축: 넣는 돈에서 세금 돌려받음. 둘 다 하면 최강 절세 콤보!"),
    ("복리의 마법", "월 25만원씩 연 7% 수익으로 20년 → 약 1억 3천만원 (원금 6천만원). 나머지 7천만원은 이자가 만든 것."),
    ("적립식 투자", "매달 같은 날 같은 금액 투자. 비쌀 때도 사고 쌀 때도 사면 평균 매입가가 낮아져요. 이걸 코스트 에버리징이라 해요."),
    ("ISA 납입 한도", "1년에 최대 2,000만원. 안 채운 한도는 다음 해로 이월돼요. 월 25만원이면 연 300만원 납입."),
    ("환율과 미국 ETF", "원/달러 환율이 높으면 미국 ETF 수익이 더 커요. 달러 강세 = 미국 ETF 보유자에게 추가 수익."),
    ("MDD(최대 낙폭)", "투자 중 겪을 수 있는 최대 손실폭. S&P500은 코로나 때 -34% 떨어졌지만 5개월 만에 회복했어요."),
    ("PER이란?", "주가수익비율. 이 회사 1년 이익의 몇 배로 주식을 사는지. S&P500 평균 20~25배. 낮을수록 저평가."),
    ("배당금이란?", "회사가 이익의 일부를 주주에게 나눠주는 돈. ISA 안에서 받으면 세금 0원!"),
    ("리밸런싱", "1년에 한 번 비율 점검. S&P500이 많이 올라서 70%가 됐으면 팔아서 다시 40%로 맞추는 것."),
    ("연금저축 세액공제", "1년에 600만원 넣으면 최대 99만원 세금 환급. 월 25만원 = 연 300만원 납입 → 약 50만원 환급."),
    ("달러 자산 보유 이유", "원화 가치가 떨어지면 달러 자산은 자동으로 수익. 미국 ETF는 환율 방어 효과도 있어요."),
    ("장기투자 마인드", "10년 이상 보유하면 S&P500이 손실을 본 적이 역사적으로 단 한 번도 없어요."),
    ("ISA 출금 전략", "만기 9999년으로 설정하면 원할 때 해지 가능. 해지 시 비과세 혜택 정산 후 지급."),
]


def get_quote(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d")
        if len(hist) < 1:
            return None
        last = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2] if len(hist) >= 2 else last
        chg = last - prev
        pct = (chg / prev) * 100
        return {"price": last, "change": chg, "pct": pct}
    except Exception:
        return None


def clean_text(text: str, max_len: int = 100) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len] + "…"
    return text


def is_market_news(title: str, summary: str) -> bool:
    """증시 관련 뉴스인지 판별"""
    combined = title + summary
    # 노이즈 키워드가 있으면 제외
    if any(k in combined for k in NOISE_KEYWORDS):
        return False
    # 시장 키워드가 있으면 통과
    return any(k in combined for k in MARKET_KEYWORDS)


def summarize_news(title: str, summary: str) -> str:
    """제목+요약을 1~2줄 시장 영향 중심으로 정리"""
    # 제목이 이미 충분히 명확하면 그냥 제목 활용
    combined = (title + " " + summary).strip()
    combined = clean_text(combined, 130)
    return combined


def get_news() -> list:
    """증시 관련 뉴스만 필터링해서 반환"""
    results = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for source, url in NEWS_FEEDS:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read()
            feed = feedparser.parse(content)
            for entry in feed.entries:
                title = clean_text(entry.get("title", ""), 60)
                summary = clean_text(
                    entry.get("summary", "") or entry.get("description", ""), 120
                )
                if not title:
                    continue
                if is_market_news(title, summary):
                    results.append((source, title, summary))
                if len(results) >= 8:
                    break
        except Exception:
            pass
        if len(results) >= 8:
            break
    return results[:8]


def get_top_movers(stocks: dict, top_n: int = 3):
    """등락률 상위/하위 종목 반환"""
    data = []
    for name, sym in stocks.items():
        q = get_quote(sym)
        if q:
            data.append((name, q["price"], q["pct"]))
    data.sort(key=lambda x: x[2], reverse=True)
    gainers = data[:top_n]
    losers  = data[-top_n:][::-1]
    return gainers, losers


def arrow(pct): return "▲" if pct > 0 else ("▼" if pct < 0 else "─")
def sign(pct):  return "+" if pct >= 0 else ""
def tag(pct):   return "🔴" if pct > 0 else ("🔵" if pct < 0 else "⚪")


def macro_comment(macro_data: dict) -> list:
    comments = []
    krw = macro_data.get("달러/원")
    if krw:
        p, pct = krw["price"], krw["pct"]
        if pct > 0.5:
            comments.append(f"달러/원 {p:,.0f}원 (▲{pct:.1f}%) — 원화 약세. 미국 ETF 보유자에게 환차익 발생. 수출기업 호재.")
        elif pct < -0.5:
            comments.append(f"달러/원 {p:,.0f}원 (▼{abs(pct):.1f}%) — 원화 강세. 미국 ETF 환차손 주의.")
        else:
            comments.append(f"달러/원 {p:,.0f}원 — 보합. 환율 안정적.")

    gold = macro_data.get("금 ($/온스)")
    if gold:
        p, pct = gold["price"], gold["pct"]
        if pct > 1:
            comments.append(f"금 ${p:,.0f} (▲{pct:.1f}%) — 안전자산 선호 급증. 글로벌 불안감 커졌다는 신호.")
        elif pct < -1:
            comments.append(f"금 ${p:,.0f} (▼{abs(pct):.1f}%) — 금값 하락 = 위험자산 선호. 주식 시장엔 긍정 신호.")
        else:
            comments.append(f"금 ${p:,.0f} — 보합.")

    oil = macro_data.get("WTI 유가 ($/배럴)")
    if oil:
        p, pct = oil["price"], oil["pct"]
        if pct > 2:
            comments.append(f"유가 ${p:.1f} (▲{pct:.1f}%) — 에너지 비용 상승. 물가 자극 가능. 중동 이슈 확인 필요.")
        elif pct < -2:
            comments.append(f"유가 ${p:.1f} (▼{abs(pct):.1f}%) — 유가 하락. 물가 안정 신호. 소비주·항공주에 긍정.")
        else:
            comments.append(f"유가 ${p:.1f} — 보합.")

    tnx = macro_data.get("미국 10년 금리(%)")
    if tnx:
        p, pct = tnx["price"], tnx["pct"]
        if pct > 2:
            comments.append(f"미국 10년 금리 {p:.2f}% (▲) — 금리 상승. 나스닥·성장주에 부담. 대출 비용 증가.")
        elif pct < -2:
            comments.append(f"미국 10년 금리 {p:.2f}% (▼) — 금리 하락. 주식 시장 긍정. 성장주·기술주에 유리.")
        else:
            comments.append(f"미국 10년 금리 {p:.2f}% — 보합.")

    return comments


def build_report() -> str:
    today = datetime.now()
    tip_idx = today.timetuple().tm_yday % len(TIPS)
    tip_title, tip_body = TIPS[tip_idx]
    weekday = ["월","화","수","목","금","토","일"][today.weekday()]

    print("  → 지수 수집 중...")
    index_data  = {n: get_quote(s) for n, s in INDICES.items()}
    global_data = {n: get_quote(s) for n, s in GLOBAL.items()}
    print("  → 거시 지표 수집 중...")
    macro_data  = {n: get_quote(s) for n, s in MACRO.items()}
    print("  → ETF 수집 중...")
    etf_data    = {n: get_quote(s) for n, s in ETFS.items()}
    print("  → 급등락 종목 수집 중...")
    kr_gain, kr_loss = get_top_movers(STOCKS_KR)
    us_gain, us_loss = get_top_movers(STOCKS_US)
    print("  → 뉴스 수집 중...")
    news_list = get_news()

    W = 64
    L = []

    L.append("=" * W)
    L.append("  📈 주린이 탈출 프로젝트 - 일일 주식 리포트")
    L.append(f"  {today.strftime('%Y년 %m월 %d일')} ({weekday}요일)")
    L.append("=" * W)

    # ── 1. 오늘의 증시 뉴스 요약 ──────────────────────────────────
    L.append("\n【 오늘의 증시 핵심 뉴스 📰 】")
    L.append("-" * W)
    L.append("  ※ 증시에 영향을 주는 뉴스만 골라 1~2줄 요약했어요\n")
    if news_list:
        for i, (source, title, summary) in enumerate(news_list, 1):
            # 제목이 충분하면 제목만, 요약이 다른 내용이면 추가
            if summary and len(summary) > 10 and summary[:20] not in title:
                line = f"  {i}. {title} — {summary}"
            else:
                line = f"  {i}. {title}"
            # 한 줄에 80자 넘으면 줄바꿈
            if len(line) > 82:
                line = line[:82] + "…"
            L.append(line)
    else:
        L.append("  뉴스를 불러오지 못했어요. 한경·매경 직접 확인해주세요.")

    # ── 2. 핵심 거시 지표 ──────────────────────────────────────────
    L.append("\n【 주식에 영향 주는 핵심 지표 🔑 】")
    L.append("-" * W)

    # 환율, 금, 유가, 금리
    for name in ["달러/원", "금 ($/온스)", "WTI 유가 ($/배럴)", "미국 10년 금리(%)"]:
        q = macro_data.get(name)
        if q:
            L.append(f"  {tag(q['pct'])} {name:<22} {q['price']:>10,.2f}  {arrow(q['pct'])} {sign(q['pct'])}{q['pct']:.2f}%")
    L.append("")
    for c in macro_comment(macro_data):
        L.append(f"  → {c}")

    # 코인
    L.append("\n  ─ 코인 ─")
    for name in ["비트코인 (USD)", "이더리움 (USD)"]:
        q = macro_data.get(name)
        if q:
            L.append(f"  {tag(q['pct'])} {name:<22} ${q['price']:>10,.0f}  {arrow(q['pct'])} {sign(q['pct'])}{q['pct']:.2f}%")

    # ── 3. 국내 + 글로벌 지수 ─────────────────────────────────────
    L.append("\n【 국내 주요 지수 】")
    L.append("-" * W)
    for name, q in index_data.items():
        if q:
            L.append(f"  {tag(q['pct'])} {name:<12} {q['price']:>12,.2f}  {arrow(q['pct'])} {sign(q['pct'])}{q['pct']:.2f}%")

    L.append("\n【 글로벌 증시 🌏 】")
    L.append("-" * W)
    L.append("  ※ 전날 밤 미국·유럽 결과가 오늘 한국장에 영향\n")
    for name, q in global_data.items():
        if q:
            L.append(f"  {tag(q['pct'])} {name:<18} {q['price']:>12,.2f}  {arrow(q['pct'])} {sign(q['pct'])}{q['pct']:.2f}%")

    # ── 4. 오늘의 급등주 ─────────────────────────────────────────
    L.append("\n【 오늘의 급등·급락 종목 🚀 】")
    L.append("-" * W)
    L.append("  ▶ 국내 급등 TOP3")
    for name, price, pct in kr_gain:
        L.append(f"    🔴 {name:<16} {price:>10,.0f}원  ▲ +{pct:.2f}%")
    L.append("  ▶ 국내 급락 TOP3")
    for name, price, pct in kr_loss:
        L.append(f"    🔵 {name:<16} {price:>10,.0f}원  ▼ {pct:.2f}%")
    L.append("")
    L.append("  ▶ 미국 급등 TOP3")
    for name, price, pct in us_gain:
        L.append(f"    🔴 {name:<16} ${price:>9,.2f}   ▲ +{pct:.2f}%")
    L.append("  ▶ 미국 급락 TOP3")
    for name, price, pct in us_loss:
        L.append(f"    🔵 {name:<16} ${price:>9,.2f}   ▼ {pct:.2f}%")

    # ── 5. 추천 ETF ──────────────────────────────────────────────
    L.append("\n【 추천 ETF 시세 】")
    L.append("-" * W)
    for name, q in etf_data.items():
        if q:
            L.append(f"  {tag(q['pct'])} {name:<24} {q['price']:>9,.0f}원  {arrow(q['pct'])} {sign(q['pct'])}{q['pct']:.2f}%")

    # ── 6. ISA 활용법 ────────────────────────────────────────────
    L.append("\n【 내 ISA 서민형 계좌 활용법 💰 】")
    L.append("-" * W)
    L.append("  ISA 서민형 = 수익 400만원까지 세금 0원")
    L.append("  ┌──────────────────────────────────────────────────┐")
    L.append("  │ ISA계좌  S&P500 50% / 나스닥100 30% / KODEX200 20%│")
    L.append("  │ 연금저축 월 25만원 납입 → 연말 약 30~40만원 환급 │")
    L.append("  └──────────────────────────────────────────────────┘")

    # ── 7. 오늘의 공부 ───────────────────────────────────────────
    L.append(f"\n【 오늘의 주식 공부 💡 {tip_title} 】")
    L.append("-" * W)
    L.append(f"  {tip_body}")

    # ── 8. 체크리스트 ────────────────────────────────────────────
    L.append("\n【 이번 달 체크리스트 ✅ 】")
    L.append("-" * W)
    L.append("  □ ISA 계좌 납입 & ETF 매수")
    L.append("  □ 연금저축 계좌 개설 (아직 안 했으면 지금!)")
    L.append("  □ 연금저축 납입")
    L.append("  □ 오늘 뉴스 1개 읽고 시장과 연결해보기")

    L.append("\n" + "=" * W)
    L.append("  ⚠️  투자 판단은 본인 책임 | 이 리포트는 참고용입니다")
    L.append("=" * W + "\n")

    return "\n".join(L)


def save_report(content: str):
    filename = os.path.join(REPORT_DIR, f"리포트_{date.today().strftime('%Y%m%d')}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    return filename


def send_email(content: str):
    EMAIL_ADDRESS  = os.environ.get("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
    EMAIL_SMTP     = "smtp.gmail.com"
    EMAIL_PORT     = 465

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        try:
            from config import EMAIL_ADDRESS, EMAIL_PASSWORD, EMAIL_SMTP, EMAIL_PORT
        except ImportError:
            print("⚠️  config.py 없음")
            return

    today_str = datetime.now().strftime("%Y년 %m월 %d일")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📈 주린이 탈출 일일 리포트 - {today_str}"
    msg["From"]    = EMAIL_ADDRESS
    msg["To"]      = EMAIL_ADDRESS
    msg.attach(MIMEText(content, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL(EMAIL_SMTP, EMAIL_PORT) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, EMAIL_ADDRESS, msg.as_string())
        print(f"✉️  메일 전송 완료 → {EMAIL_ADDRESS}")
    except smtplib.SMTPAuthenticationError:
        print("❌ 로그인 실패: 앱 비밀번호 확인")
    except Exception as e:
        print(f"❌ 메일 전송 실패: {e}")


if __name__ == "__main__":
    print("📊 데이터 수집 중...")
    report = build_report()
    print(report)
    saved = save_report(report)
    print(f"💾 저장: {saved}")
    send_email(report)
