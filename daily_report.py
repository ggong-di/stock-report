"""
주린이 탈출 프로젝트 - 매일 아침 주식 리포트
대상: 40대 중반, 월 20~30만원 투자, 노후 준비 목적
"""

import yfinance as yf
from datetime import datetime, date
import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Windows 콘솔 UTF-8 출력 강제
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 설정 ──────────────────────────────────────────────────────────────────────
REPORT_DIR = os.path.dirname(os.path.abspath(__file__))

# 주요 지수
INDICES = {
    "KOSPI (한국 종합)":  "^KS11",
    "KOSDAQ (한국 성장)": "^KQ11",
    "S&P 500 (미국 대형)": "^GSPC",
    "NASDAQ (미국 기술)": "^IXIC",
    "다우존스":           "^DJI",
}

# 40대 노후 준비에 적합한 ETF (월 20~30만원 분산 추천)
ETFS = {
    # 한국 ETF (국내 거래소)
    "TIGER 미국S&P500":    "360750.KS",   # 핵심 - S&P500 추종
    "TIGER 미국나스닥100": "133690.KS",   # 성장 - 나스닥 추종
    "KODEX 200":           "069500.KS",   # 국내 - KOSPI200 추종
    "TIGER 차이나항셍테크":"371460.KS",   # 신흥국 다양화
    # 미국 ETF
    "VOO (S&P500 ETF)":   "VOO",          # 뱅가드 S&P500
    "QQQ (나스닥100)":    "QQQ",          # 나스닥100
    "VTV (가치주)":       "VTV",          # 방어적 가치주
}

# 참고 링크
LINKS = {
    "인베스팅닷컴 (시세)": "https://kr.investing.com",
    "토스 증권 (시세+커뮤니티)": "https://tossinvest.com",
    "프로탁트 AI (종목발굴 참고)": "https://protact-ai.com",
}

# 오늘의 주식 공부 팁 (순환)
TIPS = [
    ("ETF란?", "여러 주식을 한 바구니에 담은 상품. 삼성전자 1주 살 돈으로 미국 500개 기업에 투자 가능!"),
    ("복리의 마법", "월 25만원씩 연 7% 수익으로 20년 투자 → 약 1억 3천만원 (원금 6천만원)"),
    ("분산투자", "한 종목에 몰빵 금지. ETF 자체가 수백 개 주식 분산이라 초보에게 최적"),
    ("장기투자 마인드", "단기 등락에 흔들리지 말 것. S&P500은 역사적으로 연평균 10% 수익"),
    ("환율 체크", "미국 ETF 투자 시 원/달러 환율도 수익에 영향. 환율 1300원 이하면 유리"),
    ("적립식 투자", "매달 같은 날 같은 금액 투자 = 코스트 에버리징. 고점/저점 리스크 줄여줌"),
    ("재투자의 힘", "배당금은 무조건 재투자. 복리 효과 극대화"),
    ("세금 기초", "국내 ETF: 매매차익 비과세(금융투자소득세 유예). 해외ETF: 양도세 22%"),
    ("PER이란?", "주가수익비율. 낮을수록 저평가. S&P500 평균 PER ~20~25배"),
    ("MDD(최대 낙폭)", "투자 중 겪을 수 있는 최대 손실폭. S&P500은 코로나 때 -34%, 회복 5개월"),
    ("연금저축펀드", "세액공제 최대 66만원! ETF 투자하면서 세금도 아끼는 노후 계좌"),
    ("IRP(개인형 퇴직연금)", "추가 세액공제 가능. 연금저축+IRP 합산 900만원까지 공제"),
    ("달러 자산", "원화만 갖고 있으면 원화 가치 하락 리스크. 달러 자산(미국ETF) 보유로 헤지"),
    ("주식 시장 시간", "미국 주식: 한국 시간 밤 11:30~새벽 6:00 (서머타임 1시간 앞당겨짐)"),
    ("공황 대비", "주식이 폭락해도 ETF는 0이 안 됨. 기업이 망해도 지수 ETF는 종목 교체됨"),
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


def arrow(pct: float) -> str:
    if pct > 0:
        return "▲"
    elif pct < 0:
        return "▼"
    return "─"


def color_tag(pct: float) -> str:
    if pct > 0:
        return "🔴"   # 한국 주식은 빨강이 상승
    elif pct < 0:
        return "🔵"
    return "⚪"


def build_report() -> str:
    today = datetime.now()
    tip_idx = today.timetuple().tm_yday % len(TIPS)  # 날짜별 순환
    tip_title, tip_body = TIPS[tip_idx]

    lines = []
    lines.append("=" * 60)
    lines.append(f"  📈 주린이 탈출 프로젝트 - 일일 주식 리포트")
    lines.append(f"  {today.strftime('%Y년 %m월 %d일 (%A)')}")
    lines.append("=" * 60)

    # ── 주요 지수 ──────────────────────────────────────────────
    lines.append("\n【 주요 지수 】")
    lines.append("-" * 50)
    for name, sym in INDICES.items():
        q = get_quote(sym)
        if q:
            sign = "+" if q["change"] >= 0 else ""
            lines.append(
                f"  {color_tag(q['pct'])} {name:<22} "
                f"{q['price']:>10,.2f}  "
                f"{arrow(q['pct'])} {sign}{q['pct']:.2f}%"
            )
        else:
            lines.append(f"  ⚪ {name:<22}  데이터 없음")

    # ── 추천 ETF ───────────────────────────────────────────────
    lines.append("\n【 노후 준비 추천 ETF (월 20~30만원 분산) 】")
    lines.append("-" * 50)
    lines.append("  ※ 한국 ETF는 국내 거래소 / 미국 ETF는 해외 거래")
    lines.append("")
    for name, sym in ETFS.items():
        q = get_quote(sym)
        if q:
            sign = "+" if q["change"] >= 0 else ""
            lines.append(
                f"  {color_tag(q['pct'])} {name:<24} "
                f"{q['price']:>10,.2f}  "
                f"{arrow(q['pct'])} {sign}{q['pct']:.2f}%"
            )
        else:
            lines.append(f"  ⚪ {name:<24}  데이터 없음")

    # ── 추천 포트폴리오 ────────────────────────────────────────
    lines.append("\n【 월 25만원 추천 포트폴리오 (초보용) 】")
    lines.append("-" * 50)
    lines.append("  1순위: 연금저축펀드 계좌 개설 후 ETF 매수!")
    lines.append("         → 세액공제 최대 66만원 혜택")
    lines.append("")
    lines.append("  ┌─────────────────────────────────────────┐")
    lines.append("  │ TIGER 미국S&P500    10만원 (40%)  핵심  │")
    lines.append("  │ TIGER 미국나스닥100  8만원 (32%)  성장  │")
    lines.append("  │ KODEX 200           5만원 (20%)  국내  │")
    lines.append("  │ 현금 유보            2만원  (8%)  비상금 │")
    lines.append("  └─────────────────────────────────────────┘")
    lines.append("  * 매달 같은 날 자동이체 + 자동매수 설정 추천")

    # ── 오늘의 공부 팁 ─────────────────────────────────────────
    lines.append(f"\n【 오늘의 주식 공부 💡 : {tip_title} 】")
    lines.append("-" * 50)
    lines.append(f"  {tip_body}")

    # ── 유용한 링크 ────────────────────────────────────────────
    lines.append("\n【 유용한 링크 】")
    lines.append("-" * 50)
    for name, url in LINKS.items():
        lines.append(f"  • {name}")
        lines.append(f"    {url}")

    # ── 주린이 체크리스트 ──────────────────────────────────────
    lines.append("\n【 오늘 할 일 체크리스트 ✅ 】")
    lines.append("-" * 50)
    lines.append("  □ 지수 확인 (위 표 참고)")
    lines.append("  □ 보유 ETF 현황 확인")
    lines.append("  □ 이달 적립 여부 확인")
    lines.append("  □ 경제 뉴스 헤드라인 1개 읽기")
    lines.append("  □ 오늘의 팁 숙지")

    lines.append("\n" + "=" * 60)
    lines.append("  ⚠️  투자 판단은 본인 책임 | 이 리포트는 참고용입니다")
    lines.append("=" * 60 + "\n")

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
    # GitHub Actions 환경변수 우선, 없으면 config.py 사용
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

    if not EMAIL_ADDRESS or "여기에" in EMAIL_PASSWORD:
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
