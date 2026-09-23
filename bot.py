import time
import requests
import pandas as pd
import ta
import yfinance as yf
from datetime import datetime
import pytz

# ใส่ URL Firebase ของคุณ (อย่าลืมเติม /current_trade.json ต่อท้าย)
FIREBASE_URL = "https://iqoo-signal-bot-default-rtdb.firebaseio.com/current_trade.json"

def analyze_and_send():
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)
    
    # ทำงานเฉพาะเวลา 09:00 - 20:00 น. (เวลาไทย)
    if 9 <= now.hour < 20:
        # ดึงข้อมูลราคาทองคำ (GC=F) ไทม์เฟรม 15 นาที
        df = yf.download(tickers='GC=F', period='5d', interval='15m', progress=False)
        
        if not df.empty:
            # คำนวณ EMA 50 และ EMA 200
            df['ema50'] = ta.trend.ema_indicator(df['Close'], window=50)
            df['ema200'] = ta.trend.ema_indicator(df['Close'], window=200)
            
            last_close = float(df['Close'].iloc[-1])
            last_ema50 = float(df['ema50'].iloc[-1])
            last_ema200 = float(df['ema200'].iloc[-1])
            
            signal_type = None
            if last_ema50 > last_ema200 and last_close > last_ema50:
                signal_type = "BUY"
            elif last_ema50 < last_ema200 and last_close < last_ema50:
                signal_type = "SELL"
                
            if signal_type:
                payload = {
                    "symbol": "XAUUSD / GOLD",
                    "type": signal_type,
                    "entry": round(last_close, 2),
                    "tp": round(last_close + 10.0 if signal_type == "BUY" else last_close - 10.0, 2),
                    "sl": round(last_close - 3.3 if signal_type == "BUY" else last_close + 3.3, 2),
                    "trend": "* HIGH CONFIRM *",
                    "status": "RUNNING",
                    "opened_at": int(time.time() * 1000)
                }
                requests.put(FIREBASE_URL, json=payload)
                print(f"[{now.strftime('%H:%M:%S')}] ส่งสัญญาณ {signal_type} เข้า Firebase เรียบร้อย!")

print("เริ่มทำงานบอทวิเคราะห์กราฟ...")
while True:
    try:
        analyze_and_send()
    except Exception as e:
        print("Error:", e)
    time.sleep(60)  # เช็คราคาทุกๆ 1 นาที