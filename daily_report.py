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

# ── 국내 주요 지수 ─────────────────────────────────────────────
INDICES = {
    "KOSPI (한국 종합)":   "^KS11",
    "KOSDAQ (한국 성장)":  "^KQ11",
    "S&P 500 (미국 대형)": "^GSPC",
    "NASDAQ (미국 기술)":  "^IXIC",
    "다우존스":            "^DJI",
}

# ── 글로벌 증시 + 핵심 지표 ───────────────────────────────────
GLOBAL = {
    "니케이225 (일본)":      "^N225",
    "항셍지수 (홍콩)":       "^HSI",
    "상하이종합 (중국)":     "000001.SS",
    "DAX (독일)":           "^GDAXI",
    "FTSE100 (영국)":       "^FTSE",
}

MACRO = {
    "달러/원 환율":   "KRW=X",
    "금 (온스당$)":   "GC=F",
    "WTI 원유 ($/배럴)": "CL=F",
    "미국 10년 국채금리": "^TNX",
}

# ── ISA + 연금저축 추천 ETF ───────────────────────────────────
ETFS = {
    "TIGER 미국S&P500":    "360750.KS",
    "TIGER 미국나스닥100":  "133690.KS",
    "KODEX 200":           "069500.KS",
    "KODEX TDF2045":       "315960.KS",
}

# ── 뉴스 피드 (요약 포함) ─────────────────────────────────────
NEWS_FEEDS = [
    ("한국경제", "https://www.hankyung.com/feed/finance"),
    ("매일경제", "https://www.mk.co.kr/rss/30200030/"),   # 증권
    ("연합인포맥스", "https://news.einfomax.co.kr/rss/allArticle.xml"),
]

TIPS = [
    ("ETF란?", "과일 바구니예요. 사과 하나 사는 대신 사과·배·포도가 다 든 바구니를 사는 것. 하나가 망해도 나머지가 살아있어요."),
    ("ISA 서민형이란?", "나라가 만든 절세 계좌예요. 이 안에서 번 돈은 400만원까지 세금 0원. 초과분도 9.9% 저율과세 (일반 세율 15.4%의 절반)."),
    ("ISA vs 연금저축 차이", "ISA: 번 돈에 세금 안 냄. 연금저축: 넣는 돈에서 세금 돌려받음. 둘 다 하면 최강 절세 콤보!"),
    ("복리의 마법", "월 25만원씩 연 7% 수익으로 20년 → 약 1억 3천만원 (원금 6천만원). 나머지 7천만원은 이자가 만든 것."),
    ("적립식 투자", "매달 같은 날 같은 금액 투자. 비쌀 때도 사고 쌀 때도 사면 평균 매입가가 낮아져요."),
    ("ISA 납입 한도", "1년에 최대 2,000만원 (총 1억원). 안 채운 한도는 다음 해로 이월돼요. 월 25만원이면 연 300만원 납입."),
    ("환율과 미국 ETF", "원/달러 환율이 높으면 미국 ETF 수익이 더 커요. 달러 가치가 오르면 원화 환산 수익도 올라요."),
    ("MDD(최대 낙폭)", "투자 중 겪을 수 있는 최대 손실폭. S&P500은 코로나 때 -34% 떨어졌지만 5개월 만에 회복했어요."),
    ("PER이란?", "주가수익비율. 이 회사 1년 이익의 몇 배로 주식을 사는지. S&P500 평균 20~25배. 낮을수록 저평가."),
    ("배당금이란?", "회사가 이익의 일부를 주주에게 나눠주는 돈. ISA 안에서 받으면 세금 0원!"),
    ("리밸런싱", "1년에 한 번 비율 점검. S&P500이 많이 올라서 70%가 됐으면 팔아서 다시 40%로 맞추는 것."),
    ("연금저축 세액공제", "1년에 600만원 넣으면 최대 99만원 세금 환급 (소득에 따라 다름)."),
    ("달러 자산 보유 이유", "원화 가치가 떨어지면 달러 자산은 자동으로 수익. 미국 ETF는 환율 방어 효과도 있어요."),
    ("장기투자 마인드", "10년 이상 보유하면 S&P500이 손실을 본 적이 역사적으로 단 한 번도 없어요."),
    ("ISA 출금 전략", "만기 9999년으로 설정하면 원할 때 해지 가능. 해지하면 비과세 혜택 정산 후 지급."),
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


def clean_text(text: str, max_len: int = 120) -> str:
    """HTML 태그 제거, 공백 정리, 길이 제한"""
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len] + "…"
    return text


def get_news(max_per_feed: int = 3) -> list:
    """뉴스 제목 + 요약 수집"""
    news = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for source, url in NEWS_FEEDS:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read()
            feed = feedparser.parse(content)
            count = 0
            for entry in feed.entries:
                title = clean_text(entry.get("title", ""), 60)
                summary = clean_text(
                    entry.get("summary", "") or entry.get("description", ""), 150
                )
                if not title:
                    continue
                # 증시·경제 관련 키워드 필터
                keywords = ["증시","주식","코스피","코스닥","환율","금리","연준","Fed",
                            "반도체","수출","GDP","물가","인플레","달러","채권","ETF",
                            "미국","중국","일본","유럽","원자재","금","유가","경기"]
                combined = title + summary
                if any(k in combined for k in keywords):
                    news.append((source, title, summary))
                    count += 1
                    if count >= max_per_feed:
                        break
        except Exception:
            pass
    return news


def macro_comment(macro_data: dict) -> list:
    """핵심 거시 지표 해설"""
    comments = []

    krw = macro_data.get("달러/원 환율")
    if krw:
        p = krw["price"]
        pct = krw["pct"]
        if pct > 0.5:
            comments.append(f"달러/원 환율 {p:,.0f}원 (▲{pct:.1f}%) → 원화 약세. 수출 기업엔 호재, 미국 ETF 보유자엔 추가 수익 발생.")
        elif pct < -0.5:
            comments.append(f"달러/원 환율 {p:,.0f}원 (▼{abs(pct):.1f}%) → 원화 강세. 미국 ETF 환차손 주의.")
        else:
            comments.append(f"달러/원 환율 {p:,.0f}원 (보합). 환율 안정적.")

    gold = macro_data.get("금 (온스당$)")
    if gold:
        p = gold["price"]
        pct = gold["pct"]
        direction = f"▲{pct:.1f}%" if pct > 0 else f"▼{abs(pct):.1f}%"
        if pct > 1:
            comments.append(f"금 ${p:,.0f} ({direction}) → 안전자산 선호 심리 강해졌어요. 글로벌 불확실성 경계.")
        elif pct < -1:
            comments.append(f"금 ${p:,.0f} ({direction}) → 위험자산 선호 심리. 주식 시장엔 보통 긍정 신호.")
        else:
            comments.append(f"금 ${p:,.0f} (보합).")

    oil = macro_data.get("WTI 원유 ($/배럴)")
    if oil:
        p = oil["price"]
        pct = oil["pct"]
        if pct > 2:
            comments.append(f"유가 ${p:.1f} (▲{pct:.1f}%) → 에너지 비용 상승. 물가 자극 가능성. 항공·운송주 주의.")
        elif pct < -2:
            comments.append(f"유가 ${p:.1f} (▼{abs(pct):.1f}%) → 에너지 비용 하락. 소비 여력 증가, 물가 안정 신호.")

    tnx = macro_data.get("미국 10년 국채금리")
    if tnx:
        p = tnx["price"]
        pct = tnx["pct"]
        if pct > 2:
            comments.append(f"미국 10년 국채금리 {p:.2f}% (▲) → 금리 상승. 성장주(나스닥) 부담. 대출 비용 증가.")
        elif pct < -2:
            comments.append(f"미국 10년 국채금리 {p:.2f}% (▼) → 금리 하락. 주식 시장엔 긍정. 성장주 유리.")
        else:
            comments.append(f"미국 10년 국채금리 {p:.2f}% (보합).")

    return comments


def market_comment(index_data: dict) -> str:
    kospi = index_data.get("KOSPI (한국 종합)")
    sp500 = index_data.get("S&P 500 (미국 대형)")
    nasdaq = index_data.get("NASDAQ (미국 기술)")

    lines = []
    if kospi:
        p = kospi["pct"]
        if p > 1:
            lines.append(f"한국 KOSPI +{p:.1f}% 강세. 외국인 순매수 또는 반도체·대형주 상승이 원인일 가능성 높아요.")
        elif p > 0:
            lines.append(f"한국 KOSPI +{p:.1f}% 소폭 상승. 방향성 없이 눈치 보는 장이에요.")
        elif p > -1:
            lines.append(f"한국 KOSPI {p:.1f}% 소폭 하락. 외국인 매도 또는 글로벌 관망세.")
        else:
            lines.append(f"한국 KOSPI {p:.1f}% 급락. 글로벌 악재·환율 급등·지정학 이슈 체크 필요.")

    if sp500 and nasdaq:
        sp = sp500["pct"]
        nq = nasdaq["pct"]
        if sp > 1 and nq > 1:
            lines.append(f"미국 S&P500 +{sp:.1f}%, 나스닥 +{nq:.1f}% 동반 강세. 기업 실적 호조 또는 금리 인하 기대감.")
        elif sp > 0:
            lines.append(f"미국 S&P500 +{sp:.1f}% 상승. 나스닥 {'+' if nq>=0 else ''}{nq:.1f}%.")
        elif sp < -1:
            lines.append(f"미국 S&P500 {sp:.1f}% 하락. 인플레 우려 또는 기업 실적 실망감일 수 있어요.")
        else:
            lines.append(f"미국 S&P500 {sp:.1f}% 소폭 변동.")

    return "\n  ".join(lines) if lines else "시장 데이터를 불러오는 중이에요."


def arrow(pct): return "▲" if pct > 0 else ("▼" if pct < 0 else "─")
def sign(pct):  return "+" if pct >= 0 else ""
def tag(pct):   return "🔴" if pct > 0 else ("🔵" if pct < 0 else "⚪")


def build_report() -> str:
    today = datetime.now()
    tip_idx = today.timetuple().tm_yday % len(TIPS)
    tip_title, tip_body = TIPS[tip_idx]
    weekday = ["월","화","수","목","금","토","일"][today.weekday()]

    print("  → 국내 지수 수집 중...")
    index_data  = {n: get_quote(s) for n, s in INDICES.items()}
    print("  → 글로벌 지수 수집 중...")
    global_data = {n: get_quote(s) for n, s in GLOBAL.items()}
    print("  → 거시 지표 수집 중...")
    macro_data  = {n: get_quote(s) for n, s in MACRO.items()}
    print("  → 뉴스 수집 중...")
    news_list   = get_news(3)

    L = []
    W = 64

    L.append("=" * W)
    L.append("  📈 주린이 탈출 프로젝트 - 일일 주식 리포트")
    L.append(f"  {today.strftime('%Y년 %m월 %d일')} ({weekday}요일)")
    L.append("=" * W)

    # ── 1. 오늘 시장 총평 ────────────────────────────────────────
    L.append("\n【 오늘 시장 총평 🗞️ 】")
    L.append("-" * W)
    L.append(f"  {market_comment(index_data)}")

    # ── 2. 핵심 거시 지표 & 해설 ─────────────────────────────────
    L.append("\n【 주식에 영향 주는 핵심 지표 🔑 】")
    L.append("-" * W)
    L.append("  ※ 이 숫자들이 움직이면 주가도 따라 움직여요\n")
    for name, q in macro_data.items():
        if q:
            L.append(
                f"  {tag(q['pct'])} {name:<22}"
                f"{q['price']:>10,.2f}  "
                f"{arrow(q['pct'])} {sign(q['pct'])}{q['pct']:.2f}%"
            )
        else:
            L.append(f"  ⚪ {name:<22}  데이터 없음")
    L.append("")
    for comment in macro_comment(macro_data):
        L.append(f"  → {comment}")

    # ── 3. 오늘의 경제 뉴스 (제목 + 요약) ───────────────────────
    L.append("\n【 오늘의 증시·경제 뉴스 📰 】")
    L.append("-" * W)
    L.append("  ※ 제목 + 한 줄 요약 → 왜 시장이 움직이는지 연결해보세요\n")
    if news_list:
        for i, (source, title, summary) in enumerate(news_list, 1):
            L.append(f"  {i}. [{source}] {title}")
            if summary and summary != title:
                L.append(f"     └ {summary}")
            L.append("")
    else:
        L.append("  뉴스를 불러오지 못했어요.")
        L.append("  직접 확인: https://www.hankyung.com/finance")

    # ── 4. 국내 주요 지수 ────────────────────────────────────────
    L.append("\n【 국내 주요 지수 】")
    L.append("-" * W)
    L.append("  🔴 빨강=상승  🔵 파랑=하락\n")
    for name, q in index_data.items():
        if q:
            L.append(
                f"  {tag(q['pct'])} {name:<24}"
                f"{q['price']:>12,.2f}  "
                f"{arrow(q['pct'])} {sign(q['pct'])}{q['pct']:.2f}%"
            )
        else:
            L.append(f"  ⚪ {name:<24}  데이터 없음")

    # ── 5. 글로벌 증시 ───────────────────────────────────────────
    L.append("\n【 글로벌 증시 🌏 】")
    L.append("-" * W)
    L.append("  ※ 미국장 전날 밤 결과 → 한국장 오늘 방향에 영향\n")
    for name, q in global_data.items():
        if q:
            L.append(
                f"  {tag(q['pct'])} {name:<22}"
                f"{q['price']:>12,.2f}  "
                f"{arrow(q['pct'])} {sign(q['pct'])}{q['pct']:.2f}%"
            )
        else:
            L.append(f"  ⚪ {name:<22}  데이터 없음")

    # ── 6. ISA + 연금저축 전략 ───────────────────────────────────
    L.append("\n【 내 ISA 서민형 계좌 활용법 💰 】")
    L.append("-" * W)
    L.append("  ✅ ISA 서민형 = 수익 400만원까지 세금 0원")
    L.append("     (일반 계좌라면 15.4% 세금 냈을 것)\n")
    L.append("  ┌─────────────────────────────────────────────────┐")
    L.append("  │  ISA 계좌  → 국내 ETF 매수 (비과세 혜택)       │")
    L.append("  │  TIGER 미국S&P500   50% / 나스닥100 30% / KODEX200 20%  │")
    L.append("  ├─────────────────────────────────────────────────┤")
    L.append("  │  연금저축  → 세액공제용 (아직 없으면 개설 필수) │")
    L.append("  │  월 25만원 납입 → 연말정산 약 30~40만원 환급    │")
    L.append("  └─────────────────────────────────────────────────┘")

    # ── 7. 추천 ETF 시세 ─────────────────────────────────────────
    L.append("\n【 추천 ETF 시세 】")
    L.append("-" * W)
    for name, sym in ETFS.items():
        q = get_quote(sym)
        if q:
            L.append(
                f"  {tag(q['pct'])} {name:<26}"
                f"{q['price']:>10,.0f}원  "
                f"{arrow(q['pct'])} {sign(q['pct'])}{q['pct']:.2f}%"
            )
        else:
            L.append(f"  ⚪ {name:<26}  데이터 없음")

    # ── 8. 오늘의 공부 ───────────────────────────────────────────
    L.append(f"\n【 오늘의 주식 공부 💡 : {tip_title} 】")
    L.append("-" * W)
    L.append(f"  {tip_body}")

    # ── 9. 체크리스트 ────────────────────────────────────────────
    L.append("\n【 이번 달 체크리스트 ✅ 】")
    L.append("-" * W)
    L.append("  □ ISA 계좌 이번 달 납입 & ETF 매수")
    L.append("  □ 연금저축펀드 계좌 개설 (아직 안 했으면 지금!)")
    L.append("  □ 연금저축 계좌 이번 달 납입")
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
            print("⚠️  config.py 파일이 없습니다.")
            return

    if not EMAIL_ADDRESS or "여기에" in str(EMAIL_PASSWORD):
        print("⚠️  이메일 설정을 확인해주세요.")
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
        print("❌ 로그인 실패: 앱 비밀번호를 확인해주세요")
    except Exception as e:
        print(f"❌ 메일 전송 실패: {e}")


if __name__ == "__main__":
    print("📊 데이터 수집 중...")
    report = build_report()
    print(report)
    saved = save_report(report)
    print(f"💾 저장 완료: {saved}")
    send_email(report)
