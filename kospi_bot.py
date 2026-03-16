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
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            requests.get(url, params={'chat_id': CHAT_ID, 'text': text[i:i+4000]})
    else:
        requests.get(url, params={'chat_id': CHAT_ID, 'text': text})

def check_news_hot(stock_name):
    try:
        url = f"https://www.google.com/search?q={stock_name}+주가+호재&tbm=nws"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        hot_keywords = ['상승', '호재', '돌파', '수혜', '실적', '계약', '유치', '급등', '신고가']
        news_content = soup.get_text()
        for kw in hot_keywords:
            if kw in news_content: return kw
        return ""
    except: return ""

def run_kospi_pro_report():
    print("🔍 코스피 정밀 분석 및 프로 리포트 생성 중...")
    df_kospi = fdr.StockListing('KOSPI')
    candidate_list = []

    for index, row in df_kospi.iterrows():
        code, name = row['Code'], row['Name']
        try:
            df = fdr.DataReader(code).tail(60) # 지지선 계산을 위해 데이터를 조금 더 가져옴
            if len(df) < 30: continue
            
            df['MA5'] = df['Close'].rolling(window=5).mean()
            df['MA20'] = df['Close'].rolling(window=20).mean()
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 1. 가격 계산
            current_price = int(curr['Close'])
            # 하단선(지지선): 최근 20일간의 최저가
            support_line = int(df['Low'].tail(20).min())
            # 상한가(예상): 오늘 종가 대비 +30% (한국 기준 최대치)
            max_price = int(current_price * 1.3)
            
            # 2. 기술적 지표 (골든크로스 임박)
            gap = (curr['MA20'] - curr['MA5']) / curr['MA20']
            is_potential_gold = 0 < gap < 0.025 and (curr['MA5'] > prev['MA5'])
            change_rate = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            
            # 3. 뉴스 분석
            news_keyword = ""
            if is_potential_gold or change_rate > 5:
                news_keyword = check_news_hot(name)
            
            if is_potential_gold or news_keyword:
                score = change_rate + (15 if is_potential_gold else 0) + (10 if news_keyword else 0)
                
                candidate_list.append({
                    '종목명': name,
                    '현재가': current_price,
                    '하단선': support_line,
                    '상한가(예상)': max_price,
                    '등락률(%)': round(change_rate, 2),
                    '호재 뉴스': news_keyword if news_keyword else "없음",
                    '상태': "✨골든크로스 임박" if is_potential_gold else "수급발생",
                    'Score': score
                })
        except: continue

    final_df = pd.DataFrame(candidate_list).sort_values(by='Score', ascending=False).head(30)
    
    if not final_df.empty:
        final_df.drop('Score', axis=1, inplace=True)
        excel_file = "코스피_상세_분석_TOP30.xlsx"
        final_df.to_excel(excel_file, index=False)

        report_text = f"🇰🇷 코스피 프로 상세 분석 TOP 30\n"
        report_text += f"━━━━━━━━━━━━━━━━━━\n"
        for i, (_, row) in enumerate(final_df.iterrows(), 1):
            report_text += f"{i:2d}. {row['종목명']} ({row['등락률(%)']:+.2f}%)\n"
            report_text += f"   💰 현재가: {row['현재가']:,}원\n"
            report_text += f"   📉 하단선: {row['하단선']:,}원\n"
            report_text += f"   🚀 상한가(예): {row['상한가(예상)']:,}원\n"
            report_text += f"   🔥 뉴스: {row['호재 뉴스']}\n"
            report_text += f"   👉 상태: {row['상태']}\n"
            report_text += f"----------------------------------\n"

        send_msg(report_text)
        with open(excel_file, 'rb') as f:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", 
                          data={'chat_id': CHAT_ID}, files={'document': f})
        print("✅ 코스피 프로 리포트 전송 완료!")

if __name__ == "__main__":
    run_kospi_pro_report()
