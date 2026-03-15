import FinanceDataReader as fdr
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

# --- [설정 부분] ---
TELEGRAM_TOKEN = '8714582588:AAEq4h3_CfAPaLKkVmqxv8AqRJ3ym2XgGeI'
CHAT_ID = '8613977068'
# ------------------

def send_msg(text):
    """메시지가 길 경우 분할하여 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            requests.get(url, params={'chat_id': CHAT_ID, 'text': text[i:i+4000]})
    else:
        requests.get(url, params={'chat_id': CHAT_ID, 'text': text})

def check_us_news_hot(symbol):
    """영문 뉴스 호재 키워드 스캔 및 한글 변환"""
    try:
        url = f"https://www.google.com/search?q={symbol}+stock+news+bullish&tbm=nws"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 탐지할 키워드와 대응하는 한글 메시지
        keywords_map = {
            'Bullish': '상승신호', 'Surge': '급등', 'Breakout': '돌파', 
            'Buy': '매수추천', 'Growth': '성장세', 'Positive': '긍정적', 
            'Upgraded': '등급상향', 'Higher': '고가경신', 'Jump': '도약'
        }
        
        news_content = soup.get_text().lower()
        for eng, kor in keywords_map.items():
            if eng.lower() in news_content:
                return f"🔥뉴스({kor})"
        return ""
    except:
        return ""

def run_nasdaq_top40_korean():
    print("🔍 나스닥 상위 1,000개 종목 분석 및 한글화 리포트 생성 중...")
    df_nasdaq = fdr.StockListing('NASDAQ').head(1000)
    
    candidate_list = []
    total = len(df_nasdaq)

    for index, row in df_nasdaq.iterrows():
        symbol, name = row['Symbol'], row['Name']
        if (index + 1) % 100 == 0:
            print(f"📊 분석 진행 중: {index + 1}/{total} 완료...")

        try:
            df = fdr.DataReader(symbol).tail(40)
            if len(df) < 30: continue
            
            df['MA5'] = df['Close'].rolling(window=5).mean()
            df['MA20'] = df['Close'].rolling(window=20).mean()
            curr, prev = df.iloc[-1], df.iloc[-2]
            
            # 골든크로스 임박 조건 (2.5% 이내)
            gap = (curr['MA20'] - curr['MA5']) / curr['MA20']
            is_potential_gold = 0 < gap < 0.025 and (curr['MA5'] > prev['MA5'])
            change_rate = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            
            news_tag = ""
            if is_potential_gold or change_rate > 5:
                news_tag = check_us_news_hot(symbol)
            
            if is_potential_gold or news_tag:
                status_list = []
                score = change_rate
                
                if is_potential_gold:
                    status_list.append("✨골든크로스 임박")
                    score += 15
                if news_tag:
                    status_list.append(news_tag)
                    score += 10
                
                candidate_list.append({
                    '티커': symbol,
                    '기업명': name,
                    '현재가($)': round(curr['Close'], 2),
                    '등락률(%)': round(change_rate, 2),
                    '상태': " / ".join(status_list),
                    'Score': score
                })
        except:
            continue

    # 상위 40개 정렬 및 추출
    final_df = pd.DataFrame(candidate_list).sort_values(by='Score', ascending=False).head(40)
    
    if not final_df.empty:
        final_df.drop('Score', axis=1, inplace=True)
        
        # 1. 엑셀 파일 저장
        excel_file = "나스닥_핵심_TOP40.xlsx"
        final_df.to_excel(excel_file, index=False)

        # 2. 텔레그램 메시지 작성 (한글 항목명 적용)
        report_text = f"🇺🇸 나스닥 핵심 공략주 TOP 40\n"
        report_text += f"━━━━━━━━━━━━━━━━━━\n"
        for i, (_, row) in enumerate(final_df.iterrows(), 1):
            report_text += f"{i:2d}. {row['티커']} ({row['등락률(%)']:+.2f}%)\n   👉 {row['상태']}\n"
        report_text += f"━━━━━━━━━━━━━━━━━━\n"

        # 3. 전송
        send_msg(report_text)
        with open(excel_file, 'rb') as f:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                          data={'chat_id': CHAT_ID}, files={'document': f})
        
        print(f"✅ 분석 완료! 총 {len(final_df)}개 종목 전송 성공.")
    else:
        print("❌ 조건에 부합하는 종목이 없습니다.")

if __name__ == "__main__":
    run_nasdaq_top40_korean()
