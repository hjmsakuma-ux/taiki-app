import streamlit as st
import pandas as pd
import datetime
import calendar
import gspread
import os
import random
from google.oauth2.service_account import Credentials

# ==========================================
# 0. 設定とスタイル
# ==========================================
st.set_page_config(page_title="待機表メーカー(自動作成版)", layout="wide")

st.markdown("""
    <style>
    /* スマホ用レイアウト調整 */
    [data-testid="column"] { flex: 1 1 0% !important; min-width: 0 !important; padding: 0px 1px !important; }
    div.stButton > button { padding: 0rem 0rem !important; font-size: 0.8rem !important; height: 2.8rem !important; width: 100% !important; margin-top: 2px !important; }
    div[data-testid="column"] > div > div > div > p { font-size: 0.8rem; text-align: center; margin-bottom: 0px; }
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    /* 確定列を目立たせる */
    table td:last-child { font-weight: bold; background-color: #f0f2f6; }
    </style>
    """, unsafe_allow_html=True)

DOCTORS = ["三浦医師", "伊藤医師", "宮崎医師", "佐久間医師"]

# ==========================================
# 1. データ接続・操作
# ==========================================
def get_worksheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if os.path.exists("secrets.json"):
        credentials = Credentials.from_service_account_file("secrets.json", scopes=scopes)
    else:
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(credentials)
    return gc.open("待機表データ").sheet1

def load_data():
    try:
        ws = get_worksheet()
        records = ws.get_all_records()
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
# 2. 自動割り当てロジック (NEW!)
# ==========================================
def auto_generate_schedule(year, month, prefs):
    # 各医師の担当回数カウンター
    counts = {doc: 0 for doc in DOCTORS}
    
    num_days = calendar.monthrange(year, month)[1]
    dates = [datetime.date(year, month, day).strftime('%Y-%m-%d') for day in range(1, num_days + 1)]
    
    schedule_result = {}

    for d in dates:
        # その日の状況を整理
        candidates = []      # NGじゃない人リスト
        hope_candidates = [] # HOPEの人リスト
        
        for doc in DOCTORS:
            key = get_pref_key(doc, d)
            status = prefs.get(key, "")
            
            if status != "NG":
                candidates.append(doc)
                if status == "HOPE":
                    hope_candidates.append(doc)
        
        # --- 決定ロジック ---
        winner = "⚠️人員不足" # デフォルト
        
        if hope_candidates:
            # HOPEがいる場合、その中で一番回数が少ない人を選ぶ
            # (minのkeyにcounts.getを使うことで、回数が最小の人を取得)
            winner = min(hope_candidates, key=lambda x: counts[x])
        
        elif candidates:
            # HOPEがいない場合、NGじゃない人の中で一番回数が少ない人を選ぶ
            # もし回数が同じならランダムで偏りを防ぐ
            min_count = min(counts[doc] for doc in candidates)
            min_candidates = [doc for doc in candidates if counts[doc] == min_count]
            winner = random.choice(min_candidates)
            
        # 決定者を記録
        if winner != "⚠️人員不足":
            counts[winner] += 1
            schedule_result[d] = winner
        else:
            schedule_result[d] = "誰もいません"

    return schedule_result, counts

# ==========================================
# 3. カレンダー描画 UI
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
            if status == "NG": label, btn_type = f"{day}✖", "primary"
            elif status == "HOPE": label = f"{day}〇"
            
            if cols[i].button(label, key=f"btn_{key}", use_container_width=True):
                toggle_pref(doctor_name, date_str)
                st.rerun()

# ==========================================
# 4. 集計＆作成画面
# ==========================================
def render_summary_and_generate(year, month):
    st.markdown("### 🤖 待機表の自動作成")
    
    # 自動生成を実行
    schedule, counts = auto_generate_schedule(year, month, st.session_state['prefs'])
    
    # テーブルデータ作成
    num_days = calendar.monthrange(year, month)[1]
    dates = [datetime.date(year, month, day).strftime('%Y-%m-%d') for day in range(1, num_days + 1)]
    
    table_data = []
    for d in dates:
        dt = datetime.datetime.strptime(d, '%Y-%m-%d')
        wd = ["月", "火", "水", "木", "金", "土", "日"][dt.weekday()]
        
        row = {"日付": d, "曜日": wd}
        
        # 各医師の状況表示
        for doc in DOCTORS:
            key = get_pref_key(doc, d)
            status = st.session_state['prefs'].get(key, "")
            mark = ""
            if status == "NG": mark = "✖"
            elif status == "HOPE": mark = "〇"
            row[doc] = mark
            
        # ★確定者列を追加
        winner = schedule.get(d, "")
        row["★担当者"] = winner
        table_data.append(row)

    # データフレーム表示
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # 回数カウント表示
    st.write("---")
    st.markdown("#### 📊 担当回数の内訳")
    cols = st.columns(len(DOCTORS))
    for i, doc in enumerate(DOCTORS):
        cols[i].metric(label=doc, value=f"{counts[doc]}回")

# ==========================================
# 5. メイン画面構成
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

tab_names = DOCTORS + ["📊 作成結果"]
tabs = st.tabs(tab_names)

for i, doctor in enumerate(DOCTORS):
    with tabs[i]:
        render_calendar_selector(target_year, start_month, doctor)

with tabs[-1]:
    render_summary_and_generate(target_year, start_month)