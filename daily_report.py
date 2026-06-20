"""
주린이 탈출 프로젝트 - 매일 아침 주식 리포트
대상: 40대 중반, 월 20~30만원 투자, 노후 준비 목적
보유 계좌: ISA 서민형 (작년 말 개설, 만기 9999년)
"""

import yfinance as yf
from datetime import datetime, date
import os
import sys
import smtplib
import feedparser
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPORT_DIR = os.path.dirname(os.path.abspath(__file__))

INDICES = {
    "KOSPI (한국 종합)":   "^KS11",
    "KOSDAQ (한국 성장)":  "^KQ11",
    "S&P 500 (미국 대형)": "^GSPC",
    "NASDAQ (미국 기술)":  "^IXIC",
    "다우존스":            "^DJI",
}

# ISA 계좌용 국내 ETF + 연금저축용 구분
ETFS = {
    # ★ ISA 서민형 계좌에서 사세요 (국내 ETF → 비과세 혜택)
    "TIGER 미국S&P500 [ISA추천]":    "360750.KS",
    "TIGER 미국나스닥100 [ISA추천]":  "133690.KS",
    "KODEX 200 [ISA추천]":           "069500.KS",
    # ★ 연금저축펀드 계좌에서 사세요 (세액공제 혜택)
    "TIGER 미국S&P500 [연금추천]":    "360750.KS",
    "KODEX TDF2045 [연금추천]":       "315960.KS",
}

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
    ("배당금이란?", "회사가 이익의 일부를 주주에게 나눠주는 돈. 예: KODEX 200은 1년에 약 1~2% 배당. ISA 안에서 받으면 세금 0원!"),
    ("리밸런싱", "1년에 한 번 비율 점검. S&P500이 많이 올라서 70%가 됐으면 팔아서 다시 40%로 맞추는 것."),
    ("연금저축 세액공제", "1년에 600만원 넣으면 최대 99만원 세금 환급 (소득에 따라 다름). 월 25만원 = 연 300만원 납입."),
    ("달러 자산 보유 이유", "원화 가치가 떨어지면 달러 자산은 자동으로 수익. 미국 ETF는 환율 방어 효과도 있어요."),
    ("장기투자 마인드", "10년 이상 보유하면 S&P500이 손실을 본 적이 역사적으로 단 한 번도 없어요."),
    ("ISA 출금 전략", "만기 9999년으로 설정하면 원할 때 해지 가능. 해지하면 비과세 혜택 정산 후 지급. 급할 때 꺼낼 수 있어요."),
]

NEWS_FEEDS = [
    ("한국경제", "https://www.hankyung.com/feed/economy"),
    ("매일경제", "https://www.mk.co.kr/rss/30000001/"),
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


def get_news(max_per_feed: int = 3) -> list:
    """경제 뉴스 RSS 수집"""
    news = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for source, url in NEWS_FEEDS:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read()
            feed = feedparser.parse(content)
            for entry in feed.entries[:max_per_feed]:
                title = entry.get("title", "").strip()
                if title:
                    news.append((source, title))
        except Exception:
            pass
    return news


def market_comment(indices: dict) -> str:
    """지수 등락을 보고 오늘 시장 상황 한 줄 해설"""
    kospi = indices.get("KOSPI (한국 종합)")
    sp500 = indices.get("S&P 500 (미국 대형)")

    comments = []

    if kospi:
        if kospi["pct"] > 1:
            comments.append(f"한국 증시는 KOSPI +{kospi['pct']:.1f}%로 강하게 상승했어요. 외국인 매수 또는 반도체·대형주 강세일 가능성이 높아요.")
        elif kospi["pct"] > 0:
            comments.append(f"한국 증시는 KOSPI +{kospi['pct']:.1f}%로 소폭 상승했어요. 뚜렷한 방향성 없이 눈치 보는 장이에요.")
        elif kospi["pct"] > -1:
            comments.append(f"한국 증시는 KOSPI {kospi['pct']:.1f}%로 소폭 하락했어요. 관망세가 강하거나 외국인 매도가 있었을 수 있어요.")
        else:
            comments.append(f"한국 증시는 KOSPI {kospi['pct']:.1f}%로 크게 하락했어요. 글로벌 악재나 환율 급등, 지정학적 이슈를 체크해보세요.")

    if sp500:
        if sp500["pct"] > 1:
            comments.append(f"미국 S&P500은 +{sp500['pct']:.1f}%로 강세예요. 고용지표 호조, 기업 실적 서프라이즈, 또는 금리 인하 기대감일 수 있어요.")
        elif sp500["pct"] > 0:
            comments.append(f"미국 S&P500은 +{sp500['pct']:.1f}%로 소폭 올랐어요.")
        elif sp500["pct"] > -1:
            comments.append(f"미국 S&P500은 {sp500['pct']:.1f}%로 소폭 내렸어요.")
        else:
            comments.append(f"미국 S&P500은 {sp500['pct']:.1f}%로 하락했어요. 인플레이션 우려, 금리 인상 신호, 또는 기업 실적 실망일 수 있어요.")

    return " / ".join(comments) if comments else "시장 데이터를 불러오는 중이에요."


def arrow(pct):
    return "▲" if pct > 0 else ("▼" if pct < 0 else "─")


def sign(pct):
    return "+" if pct >= 0 else ""


def color_tag(pct):
    return "🔴" if pct > 0 else ("🔵" if pct < 0 else "⚪")


def build_report() -> str:
    today = datetime.now()
    tip_idx = today.timetuple().tm_yday % len(TIPS)
    tip_title, tip_body = TIPS[tip_idx]

    # 데이터 수집
    index_data = {name: get_quote(sym) for name, sym in INDICES.items()}
    news_list = get_news(3)

    lines = []
    lines.append("=" * 62)
    lines.append("  📈 주린이 탈출 프로젝트 - 일일 주식 리포트")
    lines.append(f"  {today.strftime('%Y년 %m월 %d일')} ({['월','화','수','목','금','토','일'][today.weekday()]}요일)")
    lines.append("=" * 62)

    # ── 오늘 시장 한줄 해설 ─────────────────────────────────────
    lines.append("\n【 오늘의 시장 해설 🗞️ 】")
    lines.append("-" * 55)
    lines.append(f"  {market_comment(index_data)}")

    # ── 주요 지수 ──────────────────────────────────────────────
    lines.append("\n【 주요 지수 】")
    lines.append("-" * 55)
    lines.append("  🔴 빨강 = 상승  🔵 파랑 = 하락  (한국 주식 기준)")
    lines.append("")
    for name, q in index_data.items():
        if q:
            lines.append(
                f"  {color_tag(q['pct'])} {name:<24}"
                f"{q['price']:>12,.2f}  "
                f"{arrow(q['pct'])} {sign(q['pct'])}{q['pct']:.2f}%"
            )
        else:
            lines.append(f"  ⚪ {name:<24}  데이터 없음")

    # ── 경제 뉴스 ──────────────────────────────────────────────
    lines.append("\n【 오늘의 경제 뉴스 📰 】")
    lines.append("-" * 55)
    lines.append("  ※ 뉴스 제목을 보고 '왜 시장이 움직였는지' 연결해보세요")
    lines.append("")
    if news_list:
        for source, title in news_list:
            lines.append(f"  [{source}] {title}")
    else:
        lines.append("  뉴스를 불러오지 못했어요. 직접 한경·매경 확인해주세요.")

    # ── ISA 서민형 활용법 ───────────────────────────────────────
    lines.append("\n【 내 ISA 서민형 계좌 활용법 💰 】")
    lines.append("-" * 55)
    lines.append("  ✅ ISA 서민형은 국내 ETF 수익 400만원까지 세금 0원!")
    lines.append("     (일반 계좌였으면 15.4% 세금 냈을 것)")
    lines.append("")
    lines.append("  📌 지금 당장 해야 할 것:")
    lines.append("  1. ISA 계좌에 이번 달 납입 (월 최대 167만원, 연 2000만원 한도)")
    lines.append("  2. 납입 후 아래 ETF 매수:")
    lines.append("")
    lines.append("  ┌──────────────────────────────────────────────┐")
    lines.append("  │  ISA 계좌 (세금 0원 혜택)                    │")
    lines.append("  │  TIGER 미국S&P500   → 월 납입금의 50%        │")
    lines.append("  │  TIGER 미국나스닥100 → 월 납입금의 30%        │")
    lines.append("  │  KODEX 200          → 월 납입금의 20%        │")
    lines.append("  ├──────────────────────────────────────────────┤")
    lines.append("  │  연금저축펀드 계좌 (세금 환급 혜택)           │")
    lines.append("  │  TIGER 미국S&P500   → 월 25만원 중 15만원    │")
    lines.append("  │  (연 180만원 납입 → 세금 환급 약 27~30만원)   │")
    lines.append("  └──────────────────────────────────────────────┘")
    lines.append("")
    lines.append("  💡 두 계좌 함께 쓰는 이유:")
    lines.append("     ISA = 번 돈에 세금 안 냄")
    lines.append("     연금저축 = 넣는 돈에서 세금 돌려받음")
    lines.append("     → 둘 다 하면 앞으로도 뒤로도 절세!")

    # ── 추천 ETF 시세 ──────────────────────────────────────────
    lines.append("\n【 추천 ETF 시세 】")
    lines.append("-" * 55)
    seen = set()
    for name, sym in ETFS.items():
        if sym in seen:
            continue
        seen.add(sym)
        q = get_quote(sym)
        display = name.split(" [")[0]
        if q:
            lines.append(
                f"  {color_tag(q['pct'])} {display:<24}"
                f"{q['price']:>10,.0f}원  "
                f"{arrow(q['pct'])} {sign(q['pct'])}{q['pct']:.2f}%"
            )
        else:
            lines.append(f"  ⚪ {display:<24}  데이터 없음")

    # ── 왜 이 ETF를 추천하나 ────────────────────────────────────
    lines.append("\n【 왜 이 ETF를 추천하나요? 🤔 】")
    lines.append("-" * 55)
    lines.append("  ■ TIGER 미국S&P500")
    lines.append("    미국 대기업 500개 (애플, 마이크로소프트, 아마존 등)")
    lines.append("    에 한 번에 투자. 역사적으로 연평균 10% 수익.")
    lines.append("    40대 노후 준비의 핵심. 20년 후 은퇴 시점에 딱 맞음.")
    lines.append("")
    lines.append("  ■ TIGER 미국나스닥100")
    lines.append("    AI, 반도체, 빅테크 중심. S&P500보다 변동성 크지만")
    lines.append("    장기 성장성도 더 높음. 소액 비중으로 성장 가속.")
    lines.append("")
    lines.append("  ■ KODEX 200")
    lines.append("    삼성전자, SK하이닉스 등 한국 대기업 200개 묶음.")
    lines.append("    원화 자산으로 환율 리스크 분산. 배당도 나옴.")

    # ── 오늘의 공부 팁 ─────────────────────────────────────────
    lines.append(f"\n【 오늘의 주식 공부 💡 : {tip_title} 】")
    lines.append("-" * 55)
    lines.append(f"  {tip_body}")

    # ── 이달 체크리스트 ────────────────────────────────────────
    lines.append("\n【 이번 달 체크리스트 ✅ 】")
    lines.append("-" * 55)
    lines.append("  □ ISA 계좌 이번 달 납입 완료?")
    lines.append("  □ ISA 계좌에서 ETF 매수 완료?")
    lines.append("  □ 연금저축펀드 계좌 개설 (아직 안 했으면 지금!)")
    lines.append("  □ 연금저축 계좌에 이번 달 납입 완료?")
    lines.append("  □ 오늘 뉴스 1개 읽고 시장 연결해보기")

    lines.append("\n" + "=" * 62)
    lines.append("  ⚠️  투자 판단은 본인 책임 | 이 리포트는 참고용입니다")
    lines.append("=" * 62 + "\n")

    return "\n".join(lines)


def save_report(content: str):
    filename = os.path.join(
        REPORT_DIR,
        f"리포트_{date.today().strftime('%Y%m%d')}.txt"
    )
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
        print("❌ 로그인 실패: 아이디/비밀번호를 확인해주세요")
    except Exception as e:
        print(f"❌ 메일 전송 실패: {e}")


if __name__ == "__main__":
    print("📊 데이터 수집 중...")
    report = build_report()
    print(report)
    saved = save_report(report)
    print(f"💾 저장 완료: {saved}")
    send_email(report)
