import FinanceDataReader as fdr
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

# --- [설정 부분] ---
TELEGRAM_TOKEN = '8714582588:AAEq4h3_CfAPaLKkVmqxv8AqRJ3ym2XgGeI'
CHAT_ID = '8613977068'
# ------------------

def check_news_hot(stock_name):
    """구글 뉴스에서 해당 종목의 호재 키워드를 스캔합니다."""
    try:
        # 뉴스 검색 속도를 위해 종목명+주가+호재 키워드 조합
        url = f"https://www.google.com/search?q={stock_name}+주가+호재&tbm=nws"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 탐지할 긍정 키워드
        hot_keywords = ['상승', '호재', '돌파', '수혜', '실적', '계약', '유치', '급등', '신고가']
        news_content = soup.get_text()
        
        for kw in hot_keywords:
            if kw in news_content:
                return f"🔥뉴스({kw})"
        return ""
    except:
        return ""

def run_final_top30_scan():
    print("🔍 코스피 전 종목 분석 및 뉴스 스캔 시작 (약 10~15분 소요)...")
    df_kospi = fdr.StockListing('KOSPI')
    
    # 엑셀과 메시지에 담을 최종 후보들을 모을 리스트
    candidate_list = []

    for index, row in df_kospi.iterrows():
        code, name = row['Code'], row['Name']
        try:
            df = fdr.DataReader(code).tail(40)
            if len(df) < 30: continue
            
            # 지표 계산 (5일, 20일 이동평균선)
            df['MA5'] = df['Close'].rolling(window=5).mean()
            df['MA20'] = df['Close'].rolling(window=20).mean()
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 1. 내일 골든크로스 예상 로직 (5일선이 20일선 1.5% 밑까지 바짝 붙었을 때)
            gap = (curr['MA20'] - curr['MA5']) / curr['MA20']
            is_potential_gold = 0 < gap < 0.015 and (curr['MA5'] > prev['MA5'])
            
            # 2. 오늘 등락률
            change_rate = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
            
            # 3. 조건부 뉴스 분석 (기술적 지표가 좋은 종목만 필터링해서 뉴스 검색)
            news_tag = ""
            if is_potential_gold or change_rate > 5:
                news_tag = check_news_hot(name)
            
            # 4. 결과 집계 (신호가 하나라도 있는 경우만 리스트에 넣음)
            if is_potential_gold or news_tag:
                status_list = []
                score = change_rate # 기본 점수는 오늘 등락률
                
                if is_potential_gold:
                    status_list.append("✨골든크로스 임박")
                    score += 15 # 골든크로스 임박 시 가산점
                if news_tag:
                    status_list.append(news_tag)
                    score += 10 # 뉴스 호재 시 가산점
                
                candidate_list.append({
                    '종목명': name,
                    '현재가': int(curr['Close']),
                    '등락률(%)': round(change_rate, 2),
                    '상태': " / ".join(status_list),
                    '우선순위점수': score
                })

            if (index + 1) % 100 == 0:
                print(f"📊 현재 {index + 1}개 종목 분석 중...")

        except:
            continue

    # 5. 핵심: 점수 순으로 정렬하여 '딱 상위 30개'만 남기기
    final_30_df = pd.DataFrame(candidate_list).sort_values(by='우선순위점수', ascending=False).head(30)
    
    # 점수 컬럼은 결과창에서 가독성을 위해 삭제
    if not final_30_df.empty:
        final_30_df.drop('우선순위점수', axis=1, inplace=True)

    # 6. 엑셀 파일 저장 (이제 30개만 들어갑니다)
    excel_file = "내일의_공략주_TOP30.xlsx"
    final_30_df.to_excel(excel_file, index=False)

    # 7. 텔레그램 메시지 작성
    report_text = f"🎯 내일이 기대되는 코스피 TOP 30\n"
    report_text += f"기준: 골든크로스 임박 & 뉴스 호재\n"
    report_text += "━━━━━━━━━━━━━━━━━━\n"
    
    if not final_30_df.empty:
        for i, (_, row) in enumerate(final_30_df.iterrows(), 1):
            report_text += f"{i:2d}. {row['종목명']} ({row['등락률(%)']:+.2f}%)\n   👉 {row['상태']}\n"
    else:
        report_text += "오늘 조건에 맞는 종목을 찾지 못했습니다."

    # 8. 전송
    # 메시지 전송
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", params={'chat_id': CHAT_ID, 'text': report_text})
    # 엑셀 파일 전송 (30개 전용)
    with open(excel_file, 'rb') as f:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument", data={'chat_id': CHAT_ID}, files={'document': f})
    
    print("✅ 분석 완료! 텔레그램으로 TOP 30 메시지와 엑셀을 보냈습니다.")

if __name__ == "__main__":
    run_final_top30_scan()
