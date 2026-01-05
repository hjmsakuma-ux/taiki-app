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

st.markdown("""
    <style>
    /* スマホ用レイアウト調整 */
    [data-testid="column"] { flex: 1 1 0% !important; min-width: 0 !important; padding: 0px 1px !important; }
    div.stButton > button { padding: 0rem 0rem !important; font-size: 0.8rem !important; height: 2.8rem !important; width: 100% !important; margin-top: 2px !important; }
    div[data-testid="column"] > div > div > div > p { font-size: 0.8rem; text-align: center; margin-bottom: 0px; }
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

DOCTORS = ["三浦医師", "伊藤医師", "宮崎医師", "佐久間医師"]

def get_worksheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if os.path.exists("secrets.json"):
        credentials = Credentials.from_service_account_file("secrets.json", scopes=scopes)
    else:
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(credentials)
    return gc.open("待機表データ").sheet1

def load_data_raw():
    # データ処理用に生データを取得する関数
    try:
        ws = get_worksheet()
        records = ws.get_all_records()
        return records
    except:
        return []

def load_data():
    try:
        records = load_data_raw()
        if not records: return {}
        prefs = {}
        for r in records:
            prefs[str(r['key'])] = r['status']
        return prefs
    except:
        return {}

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
    
    new_status = "NG" if current is None else ("HOPE" if current == "NG" else None)
    
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
    st.markdown(f"##### 📅 {month}月 - {doctor_name}")
    cols = st.columns(7)
    weeks = ["月", "火", "水", "木", "金", "土", "日"]
    for i, w in enumerate(weeks):
        cols[i].markdown(f"<p style='text-align:center;'><b>{w}</b></p>", unsafe_allow_html=True)

    for week in cal:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day == 0:
                cols[i].write("")
                continue
            date_str = datetime.date(year, month, day).strftime('%Y-%m-%d')
            key = get_pref_key(doctor_name, date_str)
            status = st.session_state['prefs'].get(key, None)
            
            label = f"{day}"
            btn_type = "secondary"
            if status == "NG":
                label, btn_type = f"{day}✖", "primary"
            elif status == "HOPE":
                label = f"{day}〇"
            
            if cols[i].button(label, key=f"btn_{key}", use_container_width=True):
                toggle_pref(doctor_name, date_str)
                st.rerun()

# ==========================================
# 3. 集計テーブル作成機能 (New!)
# ==========================================
def render_summary_table(year, month):
    st.markdown("### 📋 全員の希望一覧表")
    
    # データを取得して加工
    prefs = st.session_state['prefs']
    
    # その月の日付リストを作成
    num_days = calendar.monthrange(year, month)[1]
    dates = [datetime.date(year, month, day).strftime('%Y-%m-%d') for day in range(1, num_days + 1)]
    
    # データフレームを作成
    data = []
    for d in dates:
        row = {"日付": d}
        # 曜日を追加
        dt = datetime.datetime.strptime(d, '%Y-%m-%d')
        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        row["曜日"] = weekdays[dt.weekday()]

        for doc in DOCTORS:
            key = get_pref_key(doc, d)
            status = prefs.get(key, "")
            # 表示記号に変換
            if status == "NG": row[doc] = "✖"
            elif status == "HOPE": row[doc] = "〇"
            else: row[doc] = ""
        data.append(row)
        
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

# ==========================================
# 4. メイン画面
# ==========================================
st.title("🏥 待機表")
password = st.sidebar.text_input("パスワード", type="password")
if password != "ikyoku2026":
    st.warning("パスワードを入力してください")
    st.stop()

with st.sidebar:
    st.success("ログイン中")
    if st.button("🔄 更新"):
        st.cache_data.clear()
        st.session_state['prefs'] = load_data()
        st.rerun()
    st.divider()
    target_year = st.number_input("年", 2025, 2030, 2026)
    start_month = st.selectbox("月", range(1, 13), index=1)

# ★タブに「一覧表」を追加しました
tab_names = DOCTORS + ["📊 一覧表"]
tabs = st.tabs(tab_names)

# 各医師の入力タブ
for i, doctor in enumerate(DOCTORS):
    with tabs[i]:
        render_calendar_selector(target_year, start_month, doctor)

# ★一覧表タブの中身
with tabs[-1]:
    render_summary_table(target_year, start_month)