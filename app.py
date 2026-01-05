import streamlit as st
import pandas as pd
import datetime
import calendar
import gspread
import os
import random
import jpholiday
from google.oauth2.service_account import Credentials

# ==========================================
# 0. 設定とスタイル
# ==========================================
st.set_page_config(page_title="待機表メーカー(編集機能付)", layout="wide")

st.markdown("""
    <style>
    [data-testid="column"] { flex: 1 1 0% !important; min-width: 0 !important; padding: 0px 1px !important; }
    div.stButton > button { padding: 0rem 0rem !important; font-size: 0.8rem !important; height: 2.8rem !important; width: 100% !important; margin-top: 2px !important; }
    div[data-testid="column"] > div > div > div > p { font-size: 0.8rem; text-align: center; margin-bottom: 0px; }
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

DOCTORS = ["三浦医師", "伊藤医師", "宮崎医師", "佐久間医師"]

# 曜日固定設定 (0:月, 1:火, ... 6:日)
FIXED_SCHEDULE = {
    0: "佐久間医師", 
    1: "宮崎医師",   
    3: "伊藤医師"    
}

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
# 2. 自動割り当てロジック
# ==========================================
def auto_generate_schedule_data(year, month, prefs):
    # ロジックのみを実行し、辞書型で返す関数
    counts = {doc: 0 for doc in DOCTORS}
    schedule_result = {}
    
    num_days = calendar.monthrange(year, month)[1]
    dates = []
    for day in range(1, num_days + 1):
        d_obj = datetime.date(year, month, day)
        is_holiday = jpholiday.is_holiday(d_obj) or d_obj.weekday() >= 5
        dates.append({"str": d_obj.strftime('%Y-%m-%d'), "obj": d_obj, "is_off": is_holiday})

    # --- ① 連休ブロック化 ---
    holiday_blocks = []
    current_block = []
    for d in dates:
        if d["is_off"]:
            current_block.append(d["str"])
        else:
            if current_block:
                holiday_blocks.append(current_block)
                current_block = []
    if current_block: holiday_blocks.append(current_block)

    # --- ② 連休割り当て ---
    for block in holiday_blocks:
        candidates = []
        hope_candidates = []
        for doc in DOCTORS:
            is_ok = True
            has_hope = False
            for date_str in block:
                key = get_pref_key(doc, date_str)
                status = prefs.get(key, "")
                if status == "NG":
                    is_ok = False
                    break
                if status == "HOPE": has_hope = True
            if is_ok:
                candidates.append(doc)
                if has_hope: hope_candidates.append(doc)

        winner = "人員不足"
        if hope_candidates:
            winner = min(hope_candidates, key=lambda x: counts[x])
        elif candidates:
            min_count = min(counts[doc] for doc in candidates)
            min_candidates = [doc for doc in candidates if counts[doc] == min_count]
            winner = random.choice(min_candidates)
            
        for date_str in block:
            if winner != "人員不足":
                schedule_result[date_str] = winner
                counts[winner] += 1
            else:
                schedule_result[date_str] = "人員不足"

    # --- ③ 平日割り当て ---
    for d in dates:
        date_str = d["str"]
        if date_str in schedule_result: continue 

        dt = d["obj"]
        weekday = dt.weekday()
        winner = "人員不足"
        
        fixed_doc = FIXED_SCHEDULE.get(weekday)
        if fixed_doc:
            key = get_pref_key(fixed_doc, date_str)
            if prefs.get(key, "") != "NG":
                winner = fixed_doc
        
        if winner == "人員不足":
            candidates = []
            hope_candidates = []
            for doc in DOCTORS:
                key = get_pref_key(doc, date_str)
                status = prefs.get(key, "")
                if status != "NG":
                    candidates.append(doc)
                    if status == "HOPE": hope_candidates.append(doc)
            
            if hope_candidates:
                winner = min(hope_candidates, key=lambda x: counts[x])
            elif candidates:
                min_count = min(counts[doc] for doc in candidates)
                min_candidates = [doc for doc in candidates if counts[doc] == min_count]
                winner = random.choice(min_candidates)
        
        if winner != "人員不足":
            schedule_result[date_str] = winner
            counts[winner] += 1
        else:
            schedule_result[date_str] = "人員不足"

    return schedule_result

# ==========================================
# 3. カレンダー描画 UI
# ==========================================
def render_calendar_selector(year, month, doctor_name):
    cal = calendar.monthcalendar(year, month)
    st.markdown(f"##### 📅 {month}月 - {doctor_name}")
    cols = st.columns(7)
    weeks = ["月", "火", "水", "木", "金", "土", "日"]
    for i, w in enumerate(weeks):
        color = "black"
        if i == 5: color = "blue"
        if i == 6: color = "red"
        cols[i].markdown(f"<p style='text-align:center; color:{color};'><b>{w}</b></p>", unsafe_allow_html=True)

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
# 4. 集計＆作成画面 (編集機能付き)
# ==========================================
def render_summary_and_generate(year, month):
    st.markdown("### 🤖 待機表の自動作成・編集")
    
    # --- データフレームの準備関数 ---
    def create_initial_df():
        schedule_dict = auto_generate_schedule_data(year, month, st.session_state['prefs'])
        num_days = calendar.monthrange(year, month)[1]
        dates = [datetime.date(year, month, day).strftime('%Y-%m-%d') for day in range(1, num_days + 1)]
        
        table_data = []
        for d in dates:
            dt = datetime.datetime.strptime(d, '%Y-%m-%d')
            wd_num = dt.weekday()
            wd_str = ["月", "火", "水", "木", "金", "土", "日"][wd_num]
            if jpholiday.is_holiday(dt): wd_str += "(祝)"
            
            row = {"日付": d, "曜日": wd_str}
            
            # 各医師の希望状況
            for doc in DOCTORS:
                key = get_pref_key(doc, d)
                status = st.session_state['prefs'].get(key, "")
                mark = ""
                if status == "NG": mark = "✖"
                elif status == "HOPE": mark = "〇"
                row[doc] = mark
            
            # AIが提案した担当者
            row["★担当者"] = schedule_dict.get(d, "")
            table_data.append(row)
        
        return pd.DataFrame(table_data)

    # --- セッションステートで編集中のデータを保持 ---
    session_key = f"schedule_df_{year}_{month}"
    
    # 「再生成」ボタン または データがまだ無い場合に作成
    col1, col2 = st.columns([1, 4])
    if col1.button("🤖 AI案を再生成"):
        st.session_state[session_key] = create_initial_df()
        st.rerun()

    if session_key not in st.session_state:
        st.session_state[session_key] = create_initial_df()

    # --- データエディタの表示 ---
    st.info("👇 **「★担当者」のセルは変更可能です。** 変更すると下の回数に即座に反映されます。")
    
    # 医師の選択肢リスト
    doctor_options = DOCTORS + ["人員不足", "その他"]

    edited_df = st.data_editor(
        st.session_state[session_key],
        use_container_width=True,
        hide_index=True,
        column_config={
            "日付": st.column_config.TextColumn(disabled=True),
            "曜日": st.column_config.TextColumn(disabled=True),
            "★担当者": st.column_config.SelectboxColumn(
                "★担当者 (クリックで編集)",
                help="クリックして担当者を変更できます",
                width="medium",
                options=doctor_options,
                required=True
            )
        },
        disabled=[d for d in DOCTORS] # 医師ごとの〇✖列は編集不可
    )

    # --- 編集結果に基づいて回数を再集計 ---
    st.write("---")
    st.markdown("#### 📊 担当回数（手動修正反映済み）")
    
    # 担当者列の出現回数をカウント
    counts = edited_df["★担当者"].value_counts()
    
    cols = st.columns(len(DOCTORS))
    for i, doc in enumerate(DOCTORS):
        count = counts.get(doc, 0)
        cols[i].metric(label=doc, value=f"{count}回")

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
        for key in list(st.session_state.keys()):
            if key.startswith("schedule_df_"):
                del st.session_state[key]
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