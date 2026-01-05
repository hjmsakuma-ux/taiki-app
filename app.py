import streamlit as st
import pandas as pd
import datetime
import calendar
import gspread
import os
import random
import jpholiday
import streamlit.components.v1 as components
from google.oauth2.service_account import Credentials
from datetime import timedelta

# ==========================================
# 0. 設定とスタイル
# ==========================================
st.set_page_config(
    page_title="待機表メーカー(完成版)", 
    layout="wide", 
    initial_sidebar_state="auto"
)

st.markdown("""
    <style>
    /* ---------------------------------------------------
       ★ 共通UI設定
    --------------------------------------------------- */
    /* タブの余白調整 */
    div[data-baseweb="tab-list"] { gap: 10px; }
    button[data-baseweb="tab"] { height: 4.5rem !important; padding: 0 20px !important; }
    button[data-baseweb="tab"] div p, button[data-baseweb="tab"] div {
        font-size: 1.2rem !important; font-weight: bold !important;
    }

    /* カラムの余白調整 */
    [data-testid="column"] { padding: 0px 5px !important; }

    /* ---------------------------------------------------
       ★ カレンダーボタンのデザイン（標準）
    --------------------------------------------------- */
    div[data-testid="stPopover"] button {
        height: 6.5rem !important;
        width: 100% !important;
        border: 2px solid #ddd !important;
        border-radius: 8px !important;
        background-color: white;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        padding: 0px !important;
    }
    div[data-testid="stPopover"] button p {
        font-size: 1.5rem !important;
        font-weight: 900 !important;
        color: #333 !important;
        margin: 0px !important;
        line-height: 1.3 !important;
        font-family: "Segoe UI Emoji", sans-serif !important;
    }
    div[data-testid="stPopoverBody"] button {
        height: 3.5rem !important;
        background-color: #f0f2f6 !important;
    }

    /* ---------------------------------------------------
       ★ 印刷プレビュー（標準）
    --------------------------------------------------- */
    .cal-box {
        width: 100%;
        border: 1px solid #ddd;
        border-radius: 4px;
        background-color: white;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        align-items: center;
        padding-top: 2px;
        margin-top: 1px;
        color: #333;
        height: 7.0rem; 
    }
    .cal-date {
        font-size: 1.4rem;
        font-weight: 900;
        color: #333;
        margin-bottom: 0px;
        line-height: 1.1;
    }
    .cal-mark {
        font-size: 1.3rem;
        font-weight: bold;
        color: #333;
        line-height: 1.2;
        font-family: "Segoe UI Emoji", sans-serif;
    }
    .cal-box.sat { background-color: #f0f8ff; border-color: #99c2ff; color: #0044cc; }
    .cal-box.sun { background-color: #fff0f5; border-color: #ff9999; color: #cc0000; }
    .week-header {
        text-align: center; font-weight: bold; margin-bottom: 5px; font-size: 1.1rem;
    }

    /* ---------------------------------------------------
       ★ 印刷用スタイル
    --------------------------------------------------- */
    .print-month-title {
        font-size: 1.6rem; font-weight: bold; color: #333;
        margin-top: 10px; margin-bottom: 10px; padding-left: 10px;
        border-left: 6px solid #008CBA;
    }
    .status-badge-agree { background-color: #d4edda; color: #155724; padding: 4px 8px; border-radius: 4px; font-weight: bold; border: 1px solid #c3e6cb; }
    .status-badge-reject { background-color: #f8d7da; color: #721c24; padding: 4px 8px; border-radius: 4px; font-weight: bold; border: 1px solid #f5c6cb; }
    .status-badge-pending { background-color: #fff3cd; color: #856404; padding: 4px 8px; border-radius: 4px; font-weight: bold; border: 1px solid #ffeeba; }

    @media print {
        @page { size: landscape; margin: 5mm; }
        section[data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"],
        [data-testid="stDataEditor"], [data-testid="stMetric"], [data-testid="stDataFrame"],
        .stAlert, [data-testid="stSelectbox"], [data-testid="stDateInput"], button, hr, 
        .stCaption, footer, h1, h2, h3, h4, h5, h6, .stTabs, .stExpander,
        [data-testid="stRadio"]
        { display: none !important; }

        html, body {
            height: 100%; margin: 0 !important; padding: 0 !important;
            background-color: white !important;
            -webkit-print-color-adjust: exact; print-color-adjust: exact;
            font-family: "Helvetica Neue", Arial, "Hiragino Kaku Gothic ProN", "Hiragino Sans", Meiryo, sans-serif;
        }
        .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; width: 100% !important; }
        
        .print-month-container {
            display: block !important; page-break-inside: avoid !important;
            width: 100% !important;
            page-break-after: always;
        }
        .print-month-container:last-child {
            page-break-after: auto;
        }

        .print-month-title {
            display: block !important; font-size: 2.0rem !important; border: none !important;
            text-align: center !important; margin-top: 0 !important; margin-bottom: 5mm !important;
            color: black !important;
        }
        .week-header {
            display: block !important; font-size: 1.2rem !important; color: black !important; margin-bottom: 1mm !important;
        }
        .cal-box { 
            height: 5.8rem !important; border: 1px solid #444 !important;
        }
        .cal-date { font-size: 1.3rem !important; color: black !important; }
        .cal-mark { font-size: 1.3rem !important; color: black !important; margin-top: 3px !important; }
        [data-testid="column"] { padding: 0 1px !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# ------------------------------------
# ユーザー定義
# ------------------------------------
DOCTORS = ["三浦医師", "伊藤医師", "宮崎医師", "佐久間医師"]

# ★ 管理者権限を持つユーザーのリスト
ADMIN_USERS = ["管理者", "佐久間医師"]

USER_CREDENTIALS = {
    "管理者": "ikyoku2026",
    "三浦医師": "miura",
    "伊藤医師": "ito",
    "宮崎医師": "miyazaki",
    "佐久間医師": "sakuma"
}

FIXED_SCHEDULE = {
    0: "佐久間医師", 
    1: "宮崎医師",     
    3: "伊藤医師"      
}

HANDICAP = {
    "三浦医師": 10,
    "伊藤医師": 0,
    "宮崎医師": 0,
    "佐久間医師": 0
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

def get_all_records_raw():
    try:
        ws = get_worksheet()
        return ws.get_all_records()
    except:
        return []

def load_data():
    records = get_all_records_raw()
    if not records: return {}
    prefs = {}
    for r in records:
        key = str(r['key'])
        if key.startswith("HISTORY"):
            continue
        prefs[key] = r['status']
    return prefs

def load_history():
    records = get_all_records_raw()
    history = []
    for r in records:
        key = str(r['key'])
        if key.startswith("HISTORY"):
            parts = key.split("_")
            if len(parts) >= 2:
                date_part = parts[1]
                history.append({
                    "日付": date_part,
                    "内容": r['status'],
                    "更新日時": r['timestamp']
                })
    history.reverse()
    return history

def save_pref(key, status):
    try:
        ws = get_worksheet()
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ws.append_row([key, status, now])
    except Exception as e:
        st.error(f"保存エラー: {e}")

def save_history_log(date_str, old_val, new_val, user):
    try:
        ws = get_worksheet()
        now_dt = datetime.datetime.now()
        now_str = now_dt.strftime('%Y-%m-%d %H:%M:%S')
        uniq_key = f"HISTORY_{date_str}_{now_dt.strftime('%H%M%S%f')}"
        log_text = f"{old_val} ➡ {new_val} (変更者: {user})"
        ws.append_row([uniq_key, log_text, now_str])
    except Exception as e:
        print(f"Log Error: {e}")

if 'prefs' not in st.session_state:
    st.session_state['prefs'] = load_data()

def get_pref_key(doc, date_str):
    return f"{doc}_{date_str}"

def get_protect_key(date_str):
    return f"PROTECT_{date_str}"

def get_done_key(doc, year, period_label):
    return f"DONE_{doc}_{year}_{period_label}"

def get_agree_key(doc, year, period_label):
    return f"AGREE_{doc}_{year}_{period_label}"

def get_comment_key(doc, year, period_label):
    return f"COMMENT_{doc}_{year}_{period_label}"

def get_lock_key(year, period_label):
    return f"LOCKED_{year}_{period_label}"

def update_pref(doc, date_str, new_status):
    key = get_pref_key(doc, date_str)
    if new_status:
        st.session_state['prefs'][key] = new_status
        save_pref(key, new_status)
    else:
        if key in st.session_state['prefs']:
            del st.session_state['prefs'][key]
            save_pref(key, "DELETE")

def check_is_holiday(date_obj):
    if (date_obj.month == 12 and date_obj.day >= 30) or (date_obj.month == 1 and date_obj.day <= 3):
        return True
    return jpholiday.is_holiday(date_obj)

# ==========================================
# 2. 自動割り当てロジック (最終完全版: 三浦医師優先ロジック追加)
# ==========================================
def get_weighted_count(doc, current_count):
    return current_count + HANDICAP.get(doc, 0)

def get_target_months(year, period_label):
    if period_label == "3月～5月":
        return [(year, 3), (year, 4), (year, 5)]
    elif period_label == "6月～8月":
        return [(year, 6), (year, 7), (year, 8)]
    elif period_label == "9月～11月":
        return [(year, 9), (year, 10), (year, 11)]
    elif period_label == "12月～2月":
        return [(year, 12), (year + 1, 1), (year + 1, 2)]
     
    if period_label.endswith("月") and "～" not in period_label:
        try:
            m_str = period_label.replace("月", "")
            m = int(m_str)
            if 3 <= m <= 12:
                return [(year, m)]
            elif 1 <= m <= 2:
                return [(year + 1, m)]
        except:
            return []
    return []

def auto_generate_schedule_data(year_months, prefs):
    counts = {doc: 0 for doc in DOCTORS}
    holiday_streak = {doc: 0 for doc in DOCTORS}
     
    # 3ヶ月通算の週末回数
    weekend_counts = {doc: 0 for doc in DOCTORS}
     
    # 月ごとの週末回数管理 {(year, month): {doc: count}}
    monthly_weekend_counts = {}

    # 三浦医師の月間セット回数管理
    miura_monthly_sets = {}

    schedule_result = {}
     
    dates = []
    for y, m in year_months:
        if (y, m) not in monthly_weekend_counts:
            monthly_weekend_counts[(y, m)] = {doc: 0 for doc in DOCTORS}
        if (y, m) not in miura_monthly_sets:
            miura_monthly_sets[(y, m)] = 0
             
        num_days = calendar.monthrange(y, m)[1]
        for day in range(1, num_days + 1):
            d_obj = datetime.date(y, m, day)
            is_holiday = check_is_holiday(d_obj) or d_obj.weekday() >= 5
            dates.append({"str": d_obj.strftime('%Y-%m-%d'), "obj": d_obj, "is_off": is_holiday})

    # 連休ブロック情報の作成
    holiday_info = {}
    current_chain = []
    for d in dates:
        if d["is_off"]:
            current_chain.append(d)
        else:
            if current_chain:
                length = len(current_chain)
                for idx, hd in enumerate(current_chain):
                    holiday_info[hd["str"]] = {"length": length, "index": idx + 1}
                current_chain = []
    if current_chain:
        length = len(current_chain)
        for idx, hd in enumerate(current_chain):
            holiday_info[hd["str"]] = {"length": length, "index": idx + 1}

    for i, d in enumerate(dates):
        date_str = d["str"]
        dt = d["obj"]
        weekday = dt.weekday() # 0=月...5=土, 6=日
        is_holiday = d["is_off"]
        is_sat = (weekday == 5)
        is_sun = (weekday == 6)
        
        current_ym = (dt.year, dt.month)
        
        # 前月のキー
        if current_ym[1] == 1:
            prev_ym = (current_ym[0] - 1, 12)
        else:
            prev_ym = (current_ym[0], current_ym[1] - 1)
        
        if not is_holiday:
            for doc in DOCTORS:
                holiday_streak[doc] = 0

        winner = "人員不足"
        prev_doc = schedule_result.get(dates[i-1]["str"]) if i > 0 else None

        # 1. 「当直」設定の確認
        duty_doc = None
        for doc in DOCTORS:
            key = get_pref_key(doc, date_str)
            status = prefs.get(key, "")
            if status == "当直":
                duty_doc = doc
                break
        
        if duty_doc:
            winner = duty_doc
        else:
            # 2. 平日固定枠の確認
            fixed_doc = FIXED_SCHEDULE.get(weekday)
            is_fixed_assigned = False
            
            # 三浦医師の平日固定は無視して独自ルールを適用
            if not is_holiday and fixed_doc and fixed_doc != "三浦医師":
                key = get_pref_key(fixed_doc, date_str)
                status = prefs.get(key, "")
                if status != "NG" and status != "当直":
                    winner = fixed_doc
                    is_fixed_assigned = True

            if not is_fixed_assigned:
                candidates_normal = []
                candidates_backup = []
                hope_candidates = []
                
                # 連休ロジック
                force_change = False
                prefer_continue = False
                
                # 大型連休判定
                is_long_holiday_block = False
                if date_str in holiday_info:
                    info = holiday_info[date_str]
                    L = info["length"]
                    idx = info["index"]
                    
                    if L >= 4:
                        is_long_holiday_block = True

                    if L <= 3:
                        prefer_continue = True
                    elif 4 <= L <= 6:
                        if idx == (L // 2) + 1:
                            force_change = True
                        else:
                            prefer_continue = True
                    else:
                        p1 = (L // 3) + 1
                        p2 = 2 * (L // 3) + 1
                        if idx == p1 or idx == p2:
                            force_change = True
                        else:
                            prefer_continue = True

                # 前の週末に担当した医師
                prev_weekend_docs = set()
                d_prev_sat = (dt - timedelta(days=7)).strftime('%Y-%m-%d')
                d_prev_sun = (dt - timedelta(days=6)).strftime('%Y-%m-%d')
                if d_prev_sat in schedule_result: prev_weekend_docs.add(schedule_result[d_prev_sat])
                if d_prev_sun in schedule_result: prev_weekend_docs.add(schedule_result[d_prev_sun])

                for doc in DOCTORS:
                    is_backup = False
                    key = get_pref_key(doc, date_str)
                    status = prefs.get(key, "")
                    
                    if status == "NG" or status == "当直": continue
                    # 三浦医師の火曜NGルール（念のため残す）
                    if weekday == 2 and doc == "三浦医師" and status != "HOPE": continue
                    if force_change and doc == prev_doc: continue
                    
                    is_continuity_candidate = (prefer_continue and doc == prev_doc)

                    # ---------------------------------------------------------
                    # ★ 三浦医師の特別ルール (HOPE以外の場合に適用)
                    # ---------------------------------------------------------
                    if doc == "三浦医師" and status != "HOPE":
                        # 4連休以上の大型連休ブロックならOK
                        if is_long_holiday_block:
                            pass # 通常の候補として扱う
                        else:
                            # それ以外は「金・土・日」の特定パターンのみ許可
                            valid_miura_day = False
                            
                            if weekday == 4: # 金曜日
                                # 今月まだセットを担当していない場合のみOK
                                if miura_monthly_sets.get(current_ym, 0) == 0:
                                    valid_miura_day = True
                            elif weekday == 5: # 土曜日
                                # 前日（金）が三浦医師の場合のみOK
                                if prev_doc == "三浦医師":
                                    valid_miura_day = True
                            elif weekday == 6: # 日曜日
                                # 前日（土）が三浦医師の場合のみOK
                                if prev_doc == "三浦医師":
                                    valid_miura_day = True
                            
                            if not valid_miura_day:
                                continue # パターンに合わなければ除外

                    # ---------------------------------------------------------
                    # 共通制限チェック (継続候補なら免除)
                    # ---------------------------------------------------------
                    if not is_continuity_candidate:
                        if is_holiday and holiday_streak[doc] >= 3 and status != "HOPE": continue
                        
                        # 2週間連続待機の防止
                        if (is_sat or is_sun) and (doc in prev_weekend_docs) and status != "HOPE":
                            continue

                        # 4週間で2セット制限
                        if is_sat and status != "HOPE":
                             past_sets = 0
                             for w in [1, 2, 3]:
                                 d_past = (dt - timedelta(weeks=w)).strftime('%Y-%m-%d')
                                 if schedule_result.get(d_past) == doc:
                                     past_sets += 1
                             if past_sets >= 2:
                                 continue

                        # 月間回数厳守 (絶対ルール)
                        if is_sat and status != "HOPE":
                            if monthly_weekend_counts[current_ym][doc] >= 2:
                                continue
                            if prev_ym in monthly_weekend_counts and monthly_weekend_counts[prev_ym][doc] >= 2:
                                if monthly_weekend_counts[current_ym][doc] >= 1:
                                    continue

                        # 通算セット数の制限
                        if is_sat and status != "HOPE":
                            if weekend_counts[doc] >= 5:
                                continue
                            elif weekend_counts[doc] >= 4:
                                is_backup = True

                    if status == "HOPE":
                        hope_candidates.append(doc)
                    else:
                        if is_backup:
                            candidates_backup.append(doc)
                        else:
                            candidates_normal.append(doc)

                # --- 決定ロジック ---
                def get_sort_key(doc_id):
                    # ★修正: 三浦医師が金曜日の候補に入っていて、今月まだセット未担当なら最優先(-99999)にする
                    if weekday == 4 and doc_id == "三浦医師" and miura_monthly_sets.get(current_ym, 0) == 0:
                        return -99999

                    if is_sat:
                        return (
                            monthly_weekend_counts[current_ym][doc_id],
                            weekend_counts[doc_id], 
                            get_weighted_count(doc_id, counts[doc_id])
                        )
                    else:
                        return (get_weighted_count(doc_id, counts[doc_id]))

                if hope_candidates:
                    winner = min(hope_candidates, key=get_sort_key)
                else:
                    if prefer_continue and prev_doc:
                        if (prev_doc in candidates_normal) or (prev_doc in candidates_backup):
                            winner = prev_doc
                    
                    if winner == "人員不足":
                        final_candidates = []
                        if candidates_normal:
                            final_candidates = candidates_normal
                        elif candidates_backup:
                            final_candidates = candidates_backup
                        
                        if final_candidates:
                            min_val = min(get_sort_key(d) for d in final_candidates)
                            min_candidates = [d for d in final_candidates if get_sort_key(d) == min_val]
                            winner = random.choice(min_candidates)
        
        if winner != "人員不足":
            schedule_result[date_str] = winner
            counts[winner] += 1
            
            # 三浦医師の金曜セットカウント
            if winner == "三浦医師" and weekday == 4:
                is_long = False
                if date_str in holiday_info and holiday_info[date_str]["length"] >= 4:
                    is_long = True
                if not is_long:
                    miura_monthly_sets[current_ym] += 1

            if winner in DOCTORS and is_sat:
                weekend_counts[winner] += 1
                monthly_weekend_counts[current_ym][winner] += 1
                
            if is_holiday:
                holiday_streak[winner] += 1
                for doc in DOCTORS:
                    if doc != winner:
                        holiday_streak[doc] = 0
        else:
            schedule_result[date_str] = "人員不足"
            for doc in DOCTORS:
                holiday_streak[doc] = 0

    return schedule_result

# ==========================================
# 3. カレンダー描画 UI
# ==========================================
def render_calendar_selector(year_months, period_label, current_year, doctor_name, login_user):
    done_key = get_done_key(doctor_name, current_year, period_label)
    is_done = st.session_state['prefs'].get(done_key) == "DONE"
    
    col_info, col_btn = st.columns([2, 2])
    
    with col_info:
        st.info(f"📝 **{doctor_name}** の入力画面 ({period_label})")
        st.markdown("""
        <div class="legend-box">
            <div style="margin-bottom:8px; font-weight:bold;">【記号の意味】</div>
            <table style="width:100%; border-collapse:collapse; border:none;">
                <tr style="border:none;">
                    <td style="border:none; text-align:center; font-weight:bold; font-size:1.5rem; width:40px;">〇</td>
                    <td style="border:none; text-align:center; width:20px;">：</td>
                    <td style="border:none; text-align:left;">待機希望</td>
                </tr>
                <tr style="border:none;">
                    <td style="border:none; text-align:center; font-weight:bold; font-size:1.5rem;">✖</td>
                    <td style="border:none; text-align:center;">：</td>
                    <td style="border:none; text-align:left;">待機不可</td>
                </tr>
                <tr style="border:none;">
                    <td style="border:none; text-align:center; font-weight:bold; font-size:1.5rem;">☆</td>
                    <td style="border:none; text-align:center;">：</td>
                    <td style="border:none; text-align:left;">当直</td>
                </tr>
            </table>
            <div style="font-size:0.8rem; color:#666; margin-top:8px;">※日付をクリックして選択してください</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_btn:
        if login_user in ADMIN_USERS or login_user == doctor_name:
            if is_done:
                st.success("✅ 入力完了済み")
                if st.button("修正する（完了を取り消し）", key=f"undo_{done_key}"):
                    if done_key in st.session_state['prefs']:
                        del st.session_state['prefs'][done_key]
                        save_pref(done_key, "DELETE")
                        st.rerun()
            else:
                if st.button("🚀 この期間の入力を完了する", key=f"do_{done_key}", type="primary", use_container_width=True):
                    st.session_state['prefs'][done_key] = "DONE"
                    save_pref(done_key, "DONE")
                    st.rerun()
        else:
            if is_done:
                st.success("✅ 入力完了")
            else:
                st.caption("未完了")

    st.write("---")

    if (login_user in ADMIN_USERS or login_user == doctor_name) and not is_done:
        with st.expander("📆 期間を指定して一括入力", expanded=False):
            st.markdown("##### まとめて設定する")
            start_y, start_m = year_months[0]
            end_y, end_m = year_months[-1]
            _, last_day = calendar.monthrange(end_y, end_m)
            min_date = datetime.date(start_y, start_m, 1)
            max_date = datetime.date(end_y, end_m, last_day)
            
            c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
            with c1:
                batch_start = st.date_input("開始日", min_date, min_value=min_date, max_value=max_date, key=f"b_start_{doctor_name}")
            with c2:
                batch_end = st.date_input("終了日", min_date, min_value=min_date, max_value=max_date, key=f"b_end_{doctor_name}")
            with c3:
                batch_type = st.selectbox("設定内容", ["〇 待機希望", "✖ 待機不可", "☆ 当直", "⚪ 解除"], key=f"b_type_{doctor_name}")
            with c4:
                st.write("") 
                st.write("") 
                if st.button("一括反映", key=f"b_btn_{doctor_name}", type="primary"):
                    if batch_start > batch_end:
                        st.error("開始日が終了日より後になっています")
                    else:
                        current_date = batch_start
                        while current_date <= batch_end:
                            d_str = current_date.strftime('%Y-%m-%d')
                            val = None
                            if "希望" in batch_type: val = "HOPE"
                            elif "不可" in batch_type: val = "NG"
                            elif "当直" in batch_type: val = "当直"
                            key = get_pref_key(doctor_name, d_str)
                            if val:
                                st.session_state['prefs'][key] = val
                                save_pref(key, val)
                            else:
                                if key in st.session_state['prefs']:
                                    del st.session_state['prefs'][key]
                                    save_pref(key, "DELETE")
                            current_date += timedelta(days=1)
                        st.success("一括反映しました！")
                        st.rerun()
        st.write("---")

    for y, m in year_months:
        st.markdown(f"### 📅 {y}年 {m}月")
        cal = calendar.monthcalendar(y, m)
        cols = st.columns(7)
        weeks = ["月", "火", "水", "木", "金", "土", "日"]
        for i, w in enumerate(weeks):
            color = "black"
            if i == 5: color = "blue"
            if i == 6: color = "red"
            cols[i].markdown(f"<p class='week-header' style='color:{color};'>{w}</p>", unsafe_allow_html=True)

        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                if day == 0:
                    cols[i].write("")
                    continue
                date_obj = datetime.date(y, m, day)
                date_str = date_obj.strftime('%Y-%m-%d')
                is_holiday = check_is_holiday(date_obj)
                
                key = get_pref_key(doctor_name, date_str)
                # ★修正: status変数の定義漏れを防止
                status = st.session_state['prefs'].get(key, None)
                
                day_label = str(day)
                if is_holiday: day_label = f"{day}(祝)"
                
                mark = "　"
                if status == "NG": mark = "✖"
                elif status == "HOPE": mark = "〇"
                elif status == "当直": mark = "☆"
                
                label = f"{day_label}\n\n{mark}"
                
                if login_user in ADMIN_USERS or login_user == doctor_name:
                    popover = cols[i].popover(label, use_container_width=True, disabled=is_done)
                    with popover:
                        st.markdown(f"**{date_str} の設定**")
                        st.button("〇 待機希望", key=f"hope_{key}", 
                                  on_click=update_pref, args=(doctor_name, date_str, "HOPE"), 
                                  use_container_width=True)
                        st.button("✖ 待機不可", key=f"ng_{key}", 
                                  on_click=update_pref, args=(doctor_name, date_str, "NG"), 
                                  use_container_width=True)
                        st.button("☆ 当直", key=f"duty_{key}", 
                                  on_click=update_pref, args=(doctor_name, date_str, "当直"), 
                                  use_container_width=True)
                        st.button("⚪ 解除", key=f"clr_{key}", 
                                  on_click=update_pref, args=(doctor_name, date_str, None), 
                                  use_container_width=True)
                else:
                    cols[i].button(label, key=f"btn_{key}", use_container_width=True, disabled=True)
        st.write("")

# ==========================================
# 4. 集計＆作成画面
# ==========================================
def render_summary_and_generate(year_months, period_label, current_year, login_user):
    session_key = f"schedule_df_{current_year}_{period_label}"
    def create_initial_df():
        schedule_dict = auto_generate_schedule_data(year_months, st.session_state['prefs'])
        table_data = []
        for y, m in year_months:
            num_days = calendar.monthrange(y, m)[1]
            for day in range(1, num_days + 1):
                d_obj = datetime.date(y, m, day)
                d_str = d_obj.strftime('%Y-%m-%d')
                wd_num = d_obj.weekday()
                wd_list = ["月", "火", "水", "木", "金", "土", "日"]
                wd_str = wd_list[wd_num]
                if check_is_holiday(d_obj): wd_str += "(祝)"
                p_key = get_protect_key(d_str)
                is_protected = (st.session_state['prefs'].get(p_key) == "ON")
                row = {
                    "日付": d_str, "曜日": wd_str, "🔒固定": is_protected
                }
                for doc in DOCTORS:
                    key = get_pref_key(doc, d_str)
                    status = st.session_state['prefs'].get(key, "")
                    mark = ""
                    if status == "NG": mark = "✖"
                    elif status == "HOPE": mark = "〇"
                    elif status == "当直": mark = "☆"
                    row[doc] = mark
                row["★担当者"] = schedule_dict.get(d_str, "")
                table_data.append(row)
        return pd.DataFrame(table_data)
    
    if session_key not in st.session_state:
        st.session_state[session_key] = create_initial_df()

    lock_key = get_lock_key(current_year, period_label)
    is_locked = st.session_state['prefs'].get(lock_key) == "LOCKED"

    header_text = "待機表 (完成版)" if is_locked else "待機表 (提案)"
    st.markdown(f"### 📅 {header_text}")
    
    schedule_map = dict(zip(st.session_state[session_key]["日付"], st.session_state[session_key]["★担当者"]))
    
    is_multi_month = len(year_months) > 1
    months_to_render = []

    col_ctrl, col_print = st.columns([2, 1])

    with col_ctrl:
        if is_multi_month:
            view_mode = st.radio("表示モード", ["👁️ 全体表示", "🖨️ 印刷モード (月指定)"], horizontal=True, label_visibility="collapsed")
            if view_mode == "👁️ 全体表示":
                months_to_render = year_months
                st.caption("※ すべての月を表示しています。印刷ボタンを押すとすべて印刷されます。")
            else:
                month_options = [f"{y}年 {m}月" for y, m in year_months]
                selected_month_str = st.selectbox("表示・印刷する月", month_options)
                target_idx = month_options.index(selected_month_str)
                months_to_render = [year_months[target_idx]]
        else:
            months_to_render = year_months
            st.caption(f"{year_months[0][0]}年 {year_months[0][1]}月 を表示中")

    with col_print:
        components.html("""
        <script>function printPage() {parent.window.print();}</script>
        <div style="display: flex; justify-content: flex-end; align-items: center; height: 100%;">
            <button onclick="printPage()" style="background-color: #008CBA; color: white; padding: 10px 24px; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; font-weight: bold;">🖨️ 印刷プレビュー</button>
        </div>""", height=50)

    st.write("---")

    for target_y, target_m in months_to_render:
        st.markdown(f'<div class="print-month-container">', unsafe_allow_html=True)
        st.markdown(f"""<div class="print-month-title">📅 {target_y}年 {target_m}月</div>""", unsafe_allow_html=True)
        
        cal = calendar.monthcalendar(target_y, target_m)
        cols = st.columns(7)
        weeks = ["月", "火", "水", "木", "金", "土", "日"]
        for i, w in enumerate(weeks):
            color = "black"
            if i == 5: color = "blue"
            if i == 6: color = "red"
            cols[i].markdown(f"<p class='week-header' style='color:{color};'>{w}</p>", unsafe_allow_html=True)
        
        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                if day == 0:
                    cols[i].write("")
                    continue
                date_obj = datetime.date(target_y, target_m, day)
                date_str = date_obj.strftime('%Y-%m-%d')
                is_holiday = check_is_holiday(date_obj)
                
                day_label = str(day)
                if is_holiday: 
                    day_label = f"{day}<span style='color: #e60000; font-size: 0.9em;'>(祝)</span>"
                
                assigned_doc = schedule_map.get(date_str, "")
                short_name = assigned_doc.replace("医師", "")
                if not short_name: short_name = "　"
                
                day_class = ""
                if i == 5: day_class = "sat"
                elif i == 6 or is_holiday: day_class = "sun"
                
                html_content = f"""<div class="cal-box {day_class}"><div class="cal-date">{day_label}</div><div class="cal-mark">{short_name}</div></div>"""
                cols[i].markdown(html_content, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        if len(months_to_render) > 1:
            st.write("")
            st.divider()
            st.write("")

    st.write("---")

    if login_user in DOCTORS:
        st.markdown(f"#### 👮 {login_user} の確認アクション")
        my_agree_key = get_agree_key(login_user, current_year, period_label)
        my_comment_key = get_comment_key(login_user, current_year, period_label)
        current_status = st.session_state['prefs'].get(my_agree_key)
        
        if is_locked:
            st.info("🔒 この待機表は確定されています。")
        else:
            vote_tabs = st.tabs(["👍 賛同する", "✋ 修正を依頼する"])
            with vote_tabs[0]:
                st.write("")
                if current_status == "AGREED":
                    st.success("✅ **賛同済みです**")
                    if st.button("取り消す", key="btn_cancel_agree"):
                        del st.session_state['prefs'][my_agree_key]
                        save_pref(my_agree_key, "DELETE")
                        st.rerun()
                else:
                    st.write("内容に問題がなければ、賛同ボタンを押してください。")
                    if st.button("賛同する", key="btn_do_agree", type="primary"):
                        st.session_state['prefs'][my_agree_key] = "AGREED"
                        save_pref(my_agree_key, "AGREED")
                        if my_comment_key in st.session_state['prefs']:
                            del st.session_state['prefs'][my_comment_key]
                            save_pref(my_comment_key, "DELETE")
                        st.rerun()
            with vote_tabs[1]:
                st.write("")
                if current_status == "REJECTED":
                    st.warning("⚠️ **修正依頼を出しています**")
                    comment = st.session_state['prefs'].get(my_comment_key, "")
                    st.write(f"理由: {comment}")
                    if st.button("依頼を取り消す", key="btn_cancel_reject"):
                        del st.session_state['prefs'][my_agree_key]
                        if my_comment_key in st.session_state['prefs']:
                            del st.session_state['prefs'][my_comment_key]
                            save_pref(my_comment_key, "DELETE")
                        save_pref(my_agree_key, "DELETE")
                        st.rerun()
                else:
                    st.write("修正が必要な場合は、理由を入力して依頼してください。")
                    reason = st.text_input("修正依頼の理由（必須）")
                    if st.button("修正を依頼する", key="btn_do_reject"):
                        if reason:
                            st.session_state['prefs'][my_agree_key] = "REJECTED"
                            st.session_state['prefs'][my_comment_key] = reason
                            save_pref(my_agree_key, "REJECTED")
                            save_pref(my_comment_key, reason)
                            st.rerun()
                        else:
                            st.error("理由を入力してください")

    if login_user in ADMIN_USERS:
        st.divider()
        st.markdown("#### 🔧 管理者ツール")
        st.write("**現在の賛同状況**")
        status_cols = st.columns(len(DOCTORS))
        all_agreed = True
        
        for i, doc in enumerate(DOCTORS):
            a_key = get_agree_key(doc, current_year, period_label)
            c_key = get_comment_key(doc, current_year, period_label)
            status = st.session_state['prefs'].get(a_key)
            with status_cols[i]:
                st.write(f"**{doc}**")
                if status == "AGREED":
                    st.markdown('<div class="status-badge-agree">賛同済</div>', unsafe_allow_html=True)
                elif status == "REJECTED":
                    all_agreed = False
                    st.markdown('<div class="status-badge-reject">修正依頼</div>', unsafe_allow_html=True)
                    reason = st.session_state['prefs'].get(c_key, "理由なし")
                    st.caption(f"理由: {reason}")
                else:
                    all_agreed = False
                    st.markdown('<div class="status-badge-pending">未確認</div>', unsafe_allow_html=True)
        
        st.write("---")
        
        if is_locked:
            st.error("🔒 **確定済み**")
            if st.button("確定を解除して編集に戻る"):
                del st.session_state['prefs'][lock_key]
                save_pref(lock_key, "DELETE")
                st.rerun()
        else:
            with st.expander("🤖 AI自動生成ツール (範囲指定)", expanded=True):
                st.info("💡 **「🔒固定」** チェックが入っていない行のみ再生成されます。")
                if st.button("🤖 AI案を再生成", type="primary", use_container_width=True):
                    new_full_schedule = auto_generate_schedule_data(year_months, st.session_state['prefs'])
                    current_df = st.session_state[session_key]
                    updated_count = 0
                    for idx, row in current_df.iterrows():
                        if not row['🔒固定']:
                            new_val = new_full_schedule.get(row['日付'], "")
                            current_df.at[idx, '★担当者'] = new_val
                            updated_count += 1
                    st.session_state[session_key] = current_df
                    st.success(f"{updated_count}日分を再生成しました！")
                    st.rerun()

            st.markdown("##### 📝 スケジュール手動編集")
            doctor_options = DOCTORS + ["人員不足", "その他"]
            
            def highlight_locked_rows(row):
                if row['🔒固定']:
                    return ['background-color: #d1e7dd; color: black'] * len(row)
                return [''] * len(row)

            styled_df = st.session_state[session_key].style.apply(highlight_locked_rows, axis=1)

            edited_df = st.data_editor(
                styled_df,
                use_container_width=True,
                hide_index=True,
                height=400,
                column_config={
                    "🔒固定": st.column_config.CheckboxColumn("🔒固定", default=False, width="small"),
                    "日付": st.column_config.TextColumn(disabled=True),
                    "曜日": st.column_config.TextColumn(disabled=True),
                    "★担当者": st.column_config.SelectboxColumn("★担当者", width="medium", options=doctor_options, required=True)
                },
                key=f"editor_{session_key}"
            )
            
            if not edited_df.equals(st.session_state[session_key]):
                for index, row in edited_df.iterrows():
                    old_row = st.session_state[session_key].iloc[index]
                    if old_row['★担当者'] != row['★担当者']:
                        save_history_log(row['日付'], old_row['★担当者'], row['★担当者'], login_user)
                    if old_row['🔒固定'] != row['🔒固定']:
                        p_key = get_protect_key(row['日付'])
                        status_str = "ON" if row['🔒固定'] else "OFF"
                        st.session_state['prefs'][p_key] = status_str
                        save_pref(p_key, status_str)
                st.session_state[session_key] = edited_df
                st.rerun()

            st.write("---")
            
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                if st.button("🔄 修正案を再提示する (全員のステータスをリセット)", use_container_width=True):
                    for doc in DOCTORS:
                        ak = get_agree_key(doc, current_year, period_label)
                        ck = get_comment_key(doc, current_year, period_label)
                        if ak in st.session_state['prefs']:
                            del st.session_state['prefs'][ak]
                            save_pref(ak, "DELETE")
                        if ck in st.session_state['prefs']:
                            del st.session_state['prefs'][ck]
                            save_pref(ck, "DELETE")
                    st.success("ステータスをリセットしました。各医師に再度確認を依頼してください。")
                    st.rerun()
            
            with c_btn2:
                if all_agreed:
                    if st.button("🔒 全員の賛同が得られたので確定する", type="primary", use_container_width=True):
                        st.session_state['prefs'][lock_key] = "LOCKED"
                        save_pref(lock_key, "LOCKED")
                        st.rerun()
                else:
                    st.button("🔒 確定する (全員の賛同が必要です)", disabled=True, use_container_width=True)

    st.write("---")
    st.markdown("#### 📊 待機担当回数（当直☆を除く）")
    total_counts = st.session_state[session_key]["★担当者"].value_counts()
    duty_counts = {doc: 0 for doc in DOCTORS}
    for index, row in st.session_state[session_key].iterrows():
        assigned_doc = row["★担当者"]
        if assigned_doc in DOCTORS and row[assigned_doc] == "☆":
            duty_counts[assigned_doc] += 1
    cols = st.columns(len(DOCTORS))
    for i, doc in enumerate(DOCTORS):
        total = total_counts.get(doc, 0)
        duty = duty_counts.get(doc, 0)
        cols[i].metric(label=doc, value=f"{total - duty}回", delta=f"当直 {duty}回", delta_color="off")

    st.write("---")
    st.markdown("#### 📜 変更履歴")
    if st.button("🔄"): st.rerun()
    history_logs = load_history()
    if history_logs:
        period_dates = [d.strftime('%Y-%m-%d') for y, m in year_months for d in [datetime.date(y, m, day) for day in range(1, calendar.monthrange(y, m)[1] + 1)]]
        filtered_logs = [log for log in history_logs if log['日付'] in period_dates]
        if filtered_logs:
            st.dataframe(pd.DataFrame(filtered_logs), use_container_width=True, hide_index=True)
        else:
            st.caption("変更履歴なし")
    else:
        st.caption("変更履歴なし")

# ==========================================
# 6. アプリの使い方ページ
# ==========================================
def render_algorithm_page():
    st.title("⚖️ 待機医師の決定方法")
    st.markdown("当システムでは、以下の優先順位とルールに基づいてAIが担当医を提案します。")
    st.markdown("#### 1. 確定事項の優先")
    st.write("- **当直 (☆)**: すでに決まっている当直担当者は最優先されます。")
    st.write("- **固定担当**: 平日の特定の曜日（月・火・木）は、決まった医師が優先されます（祝日などを除く）。")
    st.markdown("#### 2. 希望の考慮")
    st.write("- **待機希望 (〇)**: 希望を出している医師がいれば、その中から優先して割り当てます。")
    st.write("- **待機不可 (✖)**: 不可の日は割り当てられません。")
    st.markdown("#### 3. 負担の公平化")
    st.write("- これまでの担当回数を集計し、**回数が少ない医師**が選ばれやすくなるように調整します。")
    st.markdown("#### 4. 連休の扱い")
    st.write("- 3日以内の連休の場合、**直前の担当者が継続** して担当することを優先します。")
    st.markdown("#### 5. 週末待機の制限")
    st.write("- **2週連続の週末待機** は避けるようにします。")
    st.write("- 3ヶ月間で土日の担当は **原則4回、最大でも5回** までとします。")
    st.write("- **【厳守】** 月間の土日担当は **2回まで** とし、2回担当した翌月は **1回まで** とします。")

def render_manual_page():
    st.title("📖 アプリの使い方")
    st.markdown("### 1. 入力方法")
    st.info("""
    1.  画面左のサイドバーから **自分のユーザー名** を選び、パスワードを入力してログインします。
    2.  **「対象期間」** を確認し、自分の名前のタブをクリックします。
    3.  カレンダーの日付をクリックして、希望を入力します。
        * **〇 (待機希望)**: 待機できる日
        * **✖ (待機不可)**: 都合が悪い日
        * **☆ (当直)**: 既に当直が決まっている日
    4.  入力が終わったら、右上にある **「🚀 この期間の入力を完了する」** ボタンを押します。
    """)
    st.markdown("### 2. 賛同の方法")
    st.warning("""
    1.  全員の入力が終わると、管理者が待機表を作成します。
    2.  **「📊 作成結果」** タブを開き、作成されたカレンダー（案）を確認します。
    3.  内容に問題なければ、カレンダーの下にある **「👍 賛同する」** タブを選び、ボタンを押してください。
    4.  修正が必要な場合は、**「✋ 修正を依頼する」** タブを選び、理由を入力して送信してください。
    """)
    st.markdown("### 3. 完成カレンダーの閲覧・印刷")
    st.success("""
    1.  **「表示・印刷する月」** を選択し、**「🖨️ 印刷プレビュー」** ボタンを押します。
    2.  1ヶ月分だけがきれいに印刷されます。
    """)

def render_admin_manual_page():
    st.title("🔧 管理者マニュアル")
    st.markdown("このページは管理者のみに表示されます。")
    st.markdown("### 📅 待機表作成フロー")
    st.write("""
    1.  **入力状況の確認**: サイドバーの「入力状況」を見て、全員の入力（✅）が完了したか確認します。
    2.  **AI作成**: 「📊 作成結果」タブの **「🤖 AI案を再生成」** ボタンを押して、初期案を作成します。
    3.  **手動調整**: 
        * 表の「★担当者」列をクリックして、必要に応じて担当医を変更します。
        * **「🔒固定」** 列にチェックを入れると、その行はAI再生成時に上書きされなくなります。
    4.  **再調整**: 固定したい部分以外を作り直したい場合は、再度「🤖 AI案を再生成」を押します。
    5.  **再提示**: 修正が完了したら、**「🔄 修正案を再提示する」** ボタンを押して、各医師に確認を依頼します。
    6.  **確定**: 全員の賛同が得られたら、**「🔒 全員の賛同が得られたので確定する」** ボタンを押してロックします。
    """)
    st.markdown("### 🔑 パスワード確認")
    st.write("各医師のログインパスワードは以下の通りです。（忘れた場合の案内用）")
    df_creds = pd.DataFrame(list(USER_CREDENTIALS.items()), columns=["ユーザー名", "パスワード"])
    st.table(df_creds)

# ==========================================
# 5. メイン画面構成 (メニュー切り替え)
# ==========================================
st.title("🏥 待機表メーカー")

# --- ★スマホ対応修正: メイン画面にもログイン案内を表示 ---
st.sidebar.header("ログイン")
login_user = st.sidebar.selectbox("ユーザー名", ["管理者"] + DOCTORS)
password = st.sidebar.text_input("パスワード", type="password")

if USER_CREDENTIALS.get(login_user) != password:
    # メイン画面に大きく表示
    st.info("📱 スマホの方は、左上の「 > 」マークを押してログインしてください。")
    st.warning("👈 左のサイドバーでユーザー名とパスワードを入力してください")
    
    st.sidebar.divider()
    if st.sidebar.button("📖 アプリの使い方を見る"):
        render_manual_page()
    st.stop()

st.sidebar.success(f"ようこそ、{login_user} さん")

# メニュー定義
if login_user in ADMIN_USERS:
    menu_options = ["📅 スケジュール作成", "📖 アプリの使い方", "⚖️ 待機医師の決定方法", "🔧 管理者マニュアル"]
else:
    menu_options = ["📅 スケジュール作成", "📖 アプリの使い方", "⚖️ 待機医師の決定方法"]

menu = st.sidebar.radio("メニュー", menu_options)

if menu == "📖 アプリの使い方":
    render_manual_page()
    st.stop()
elif menu == "⚖️ 待機医師の決定方法":
    render_algorithm_page()
    st.stop()
elif menu == "🔧 管理者マニュアル":
    render_admin_manual_page()
    st.stop()

# --- 以下、スケジュール作成画面 ---

if st.sidebar.button("🔄"):
    st.cache_data.clear()
    st.session_state['prefs'] = load_data()
    for key in list(st.session_state.keys()):
        if key.startswith("schedule_df_"):
            del st.session_state[key]
    st.rerun()

st.sidebar.divider()

target_year = st.sidebar.number_input("年度（開始年）", 2025, 2030, 2025)

input_unit = st.sidebar.radio("期間単位", ["3ヶ月 (標準)", "1ヶ月"], horizontal=True)

if input_unit == "3ヶ月 (標準)":
    period_options = ["3月～5月", "6月～8月", "9月～11月", "12月～2月"]
else:
    period_options = [f"{m}月" for m in range(3, 13)] + ["1月", "2月"]

selected_period = st.sidebar.selectbox("対象期間", period_options)

target_months = get_target_months(target_year, selected_period)

st.sidebar.divider()
st.sidebar.markdown(f"#### 📝 入力状況 ({selected_period})")
for doc in DOCTORS:
    d_key = get_done_key(doc, target_year, selected_period)
    is_done = st.session_state['prefs'].get(d_key) == "DONE"
    status_icon = "✅" if is_done else "⬜"
    st.sidebar.write(f"{status_icon} {doc}")

tab_names = DOCTORS + ["📊 作成結果"]
tabs = st.tabs(tab_names)

for i, doctor in enumerate(DOCTORS):
    with tabs[i]:
        render_calendar_selector(target_months, selected_period, target_year, doctor, login_user)

with tabs[-1]:
    render_summary_and_generate(target_months, selected_period, target_year, login_user)