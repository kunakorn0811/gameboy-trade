import os
import time
import requests
import pandas as pd
import ta
import yfinance as yf
from datetime import datetime
import pytz

FIREBASE_URL = "https://iqoo-signal-bot-default-rtdb.firebaseio.com/current_trade.json"

# ตั้งค่าโทเคนสำหรับการแจ้งเตือน
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_TOKEN", "kunakorn.pdg")
LINE_USER_ID = os.environ.get("LINE_USER_ID", "kunakorn.pdg")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

SYMBOLS = {
    'XAUUSD / GOLD': 'GC=F',
    'EURUSD': 'EURUSD=X'
}

def send_notifications(msg_text):
    """ ส่งแจ้งเตือนทั้ง LINE และ Telegram """
    # LINE Notification
    if "ใส่_" not in LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_ACCESS_TOKEN:
        try:
            requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
                },
                json={"to": LINE_USER_ID, "messages": [{"type": "text", "text": msg_text}]},
                timeout=8
            )
        except Exception as e:
            print("LINE Send Error:", e)

    # Telegram Notification (ตัวสำรอง)
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": msg_text},
                timeout=8
            )
        except Exception as e:
            print("Telegram Send Error:", e)

def check_engulfing(open_s, close_s):
    prev_open = float(open_s.iloc[-2])
    prev_close = float(close_s.iloc[-2])
    curr_open = float(open_s.iloc[-1])
    curr_close = float(close_s.iloc[-1])
    
    bullish = (prev_close < prev_open) and (curr_close > curr_open) and (curr_close >= prev_open) and (curr_open <= prev_close)
    bearish = (prev_close > prev_open) and (curr_close < curr_open) and (curr_close <= prev_open) and (curr_open >= prev_close)
    return bullish, bearish

def run_bot():
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] เริ่มการวิเคราะห์กราฟ...")

    for name, ticker in SYMBOLS.items():
        df = yf.download(tickers=ticker, period='5d', interval='15m', progress=False)
        if df.empty or len(df) < 200:
            continue
        
        # --- จัดการแปลงมิติข้อมูลของ yfinance ให้เป็น 1D Series ป้องกัน ValueError ---
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        close_s = df['Close'].squeeze()
        high_s = df['High'].squeeze()
        low_s = df['Low'].squeeze()
        open_s = df['Open'].squeeze()
        
        # คำนวณ Indicators
        ema50_s = ta.trend.ema_indicator(close_s, window=50)
        ema200_s = ta.trend.ema_indicator(close_s, window=200)
        atr_s = ta.volatility.average_true_range(high_s, low_s, close_s, window=14)
        
        last_close = float(close_s.iloc[-1])
        last_ema50 = float(ema50_s.iloc[-1])
        last_ema200 = float(ema200_s.iloc[-1])
        last_atr = float(atr_s.iloc[-1])
        
        is_bull_engulf, is_bear_engulf = check_engulfing(open_s, close_s)
        signal_type = None

        # BUY Signal: EMA50 > EMA200 + Close > EMA50 + Bullish Engulfing
        if (last_ema50 > last_ema200) and (last_close > last_ema50) and is_bull_engulf:
            signal_type = "BUY"
        # SELL Signal: EMA50 < EMA200 + Close < EMA50 + Bearish Engulfing
        elif (last_ema50 < last_ema200) and (last_close < last_ema50) and is_bear_engulf:
            signal_type = "SELL"
            
        if signal_type:
            sl_distance = last_atr * 1.5
            tp_distance = sl_distance * 3.0
            
            sl_price = last_close - sl_distance if signal_type == "BUY" else last_close + sl_distance
            tp_price = last_close + tp_distance if signal_type == "BUY" else last_close - tp_distance
            
            decimals = 4 if "EUR" in name else 2
            entry_p = round(last_close, decimals)
            tp_p = round(tp_price, decimals)
            sl_p = round(sl_price, decimals)

            payload = {
                "symbol": name,
                "type": signal_type,
                "entry": entry_p,
                "tp": tp_p,
                "sl": sl_p,
                "trend": "* HIGH CONFIRM *",
                "status": "RUNNING",
                "opened_at": int(time.time() * 1000)
            }
            
            # 1. อัปเดตข้อมูลเข้า Firebase
            requests.put(FIREBASE_URL, json=payload, timeout=10)
            
            # 2. ส่งแจ้งเตือน
            line_msg = (
                f"🎮 GAMEBOY TRADING SIGNAL!\n"
                f"-------------------------\n"
                f"คู่เงิน: {name}\n"
                f"คำสั่ง: {signal_type} {'🟢' if signal_type == 'BUY' else '🔴'}\n"
                f"ราคาเข้า (Entry): {entry_p}\n"
                f"เป้าหมาย (TP): {tp_p}\n"
                f"จุดตัดขาดทุน (SL): {sl_p}\n"
                f"-------------------------\n"
                f"เปิดแอป Game Boy บนมือถือเพื่อดูสถานะ!"
            )
            send_notifications(line_msg)
            print(f"ยิงสัญญาณสำเร็จ: {name} [{signal_type}]")
            break

if __name__ == "__main__":
    run_bot()