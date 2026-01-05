import streamlit as st
import pandas as pd
import datetime
import calendar
import gspread
import os
from google.oauth2.service_account import Credentials

# ==========================================
# 0. 設定とスプレッドシート接続機能
# ==========================================
st.set_page_config(page_title="待機表メーカー(クラウド版)", layout="wide")

# 医師リスト
DOCTORS = ["三浦医師(A)", "伊藤医師(B)", "宮崎医師(C)", "佐久間医師(D)"]

# スプレッドシートへの接続関数
def get_worksheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # PC上の secrets.json があればそれを使い、なければクラウドの鍵を使う
    if os.path.exists("secrets.json"):
        credentials = Credentials.from_service_account_file("secrets.json", scopes=scopes)
    else:
        # クラウド（Streamlit Cloud）上の設定
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scopes
        )
        
    gc = gspread.authorize(credentials)
    return gc.open("待機表データ").sheet1

# データを読み込む
def load_data():
    try:
        ws = get_worksheet()
        records = ws.get_all_records()
        if not records: return {}
        
        prefs = {}
        for r in records:
            prefs[str(r['key'])] = r['status']
        return prefs
    except Exception as e:
        st.error(f"接続エラー: {e}")
        return {}

# データを保存する
def save_pref(key, status):
    try:
        ws = get_worksheet()
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ws.append_row([key, status, now])
    except Exception as e:
        st.error(f"保存エラー: {e}")

# ==========================================
# 1. セッション初期化
# ==========================================
if 'prefs' not in st.session_state:
    st.session_state['prefs'] = load_data()

def get_pref_key(doc, date_str):
    return f"{doc}_{date_str}"

def toggle_pref(doc, date_str):
    key = get_pref_key(doc, date_str)
    current = st.session_state['prefs'].get(key, None)
    
    new_status = None
    if current is None:
        new_status = "NG"
    elif current == "NG":
        new_status = "HOPE"
    else:
        new_status = None 

    if new_status:
        st.session_state['prefs'][key] = new_status
        save_pref(key, new_status)
    else:
        if key in st.session_state['prefs']:
            del st.session_state['prefs'][key]
            save_pref(key, "DELETE")

# ==========================================
# 2. カレンダー描画 UI
# ==========================================
def render_calendar_selector(year, month, doctor_name):
    cal = calendar.monthcalendar(year, month)
    st.markdown(f"### 📅 {year}年{month}月 - {doctor_name}")
    
    cols = st.columns(7)
    weeks = ["月", "火", "水", "木", "金", "土", "日"]
    for i, w in enumerate(weeks):
        cols[i].markdown(f"**<center>{w}</center>**", unsafe_allow_html=True)

    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                cols[i].write("")
                continue
            
            date_str = datetime.date(year, month, day).strftime('%Y-%m-%d')
            key = get_pref_key(doctor_name, date_str)
            status = st.session_state['prefs'].get(key, None)
            
            # --- ここを修正：より安全な書き方に変更しました ---
            label = f"{day}"
            btn_type = "secondary"

            if status == "NG":
                label = f"{day} 🟥"
                btn_type = "primary"
            elif status == "HOPE":
                label = f"{day} 🟦"
            # ------------------------------------------------
            
            if cols[i].button(label, key=f"btn_{key}", use_container_width=True):
                toggle_pref(doctor_name, date_str)
                st.rerun()

# ==========================================
# 3. メイン画面
# ==========================================
st.title("🏥 待機表 (スプレッドシート連携版)")

password = st.sidebar.text_input("パスワード", type="password")
if password != "ikyoku2026":
    st.warning("パスワードを入力してください")
    st.stop()

with st.sidebar:
    st.success("ログイン成功・同期中")
    if st.button("🔄 最新データを再読込"):
        st.cache_data.clear()
        st.session_state['prefs'] = load_data()
        st.rerun()
    
    st.divider()
    target_year = st.number_input("年", 2025, 2030, 2026)
    start_month = st.selectbox("開始月", range(1, 13), index=1)

tabs = st.tabs([d.split("(")[0] for d in DOCTORS])
for i, doctor in enumerate(DOCTORS):
    with tabs[i]:
        render_calendar_selector(target_year, start_month, doctor)