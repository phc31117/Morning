import streamlit as st
import feedparser
from datetime import datetime, date, timedelta
import json
import os
import pandas as pd
import plotly.graph_objects as go
import re
import sqlite3

# ==================== 1. 基礎設定與資料處理 ====================

# 設定頁面配置為寬版面
st.set_page_config(layout="wide", page_title="Morning Dashboard")

# 資料庫檔案路徑（用於儲存專案資料）
DB_FILE = "projects.db"

# 初始化資料庫
def init_db():
    """初始化 SQLite 資料庫"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            key TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            progress INTEGER DEFAULT 0,
            url TEXT
        )
    ''')
    conn.commit()
    conn.close()

# 載入專案資料的函數
def load_projects():
    """從資料庫載入專案資料"""
    try:
        init_db()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT * FROM projects')
        rows = c.fetchall()
        conn.close()
        
        projects = {}
        for row in rows:
            key, name, start_date, end_date, progress, url = row
            projects[key] = {
                'name': name,
                'start_date': start_date or '',
                'end_date': end_date or '',
                'progress': progress or 0,
                'url': url or ''
            }
        return projects
    except Exception as e:
        st.error(f"載入專案資料時發生錯誤：{str(e)}")
        return {}

# 儲存專案資料的函數
def save_projects(projects):
    """將專案資料儲存到資料庫"""
    try:
        init_db()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # 清空現有資料
        c.execute('DELETE FROM projects')
        
        # 插入新資料
        for key, data in projects.items():
            c.execute('''
                INSERT OR REPLACE INTO projects (key, name, start_date, end_date, progress, url)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                key,
                data.get('name', ''),
                data.get('start_date', ''),
                data.get('end_date', ''),
                data.get('progress', 0),
                data.get('url', '')
            ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"儲存專案資料時發生錯誤：{str(e)}")

# 初始化專案資料的 session_state
if 'projects' not in st.session_state:
    st.session_state.projects = load_projects()

# --- Callback: 專門處理表格內直接修改進度 ---
def update_progress_callback(project_key):
    """當表格內的數字輸入框變動時，觸發此函數儲存資料"""
    # 取得該輸入框的最新值 (key 為 "prog_input_{project_key}")
    new_value = st.session_state[f"prog_input_{project_key}"]
    
    # 更新 session_state 中的專案資料
    if project_key in st.session_state.projects:
        st.session_state.projects[project_key]['progress'] = new_value
        # 立即存檔
        save_projects(st.session_state.projects)

# 取得今天的日期和星期
today = datetime.now()
today_date = date.today()
date_str = today.strftime("%Y-%m-%d")
weekday_str = today.strftime("%a")

# ==================== 2. 全域 CSS 樣式 ====================
st.markdown("""
<style>
    /* 引入 Calibri 字體 */
    @import url('https://fonts.googleapis.com/css2?family=Calibri:wght@400;600;700&display=swap');
    
    /* 全域字體設定 */
    html, body, [class*="css"] {
        font-family: 'Calibri', sans-serif;
    }

    /* 置中大標題 */
    .centered-title {
        text-align: center;
        font-family: 'Calibri', sans-serif;
    }
    
    /* 左側追蹤表的通用文字樣式 */
    .calibri-text {
        font-family: 'Calibri', sans-serif;
        font-size: 12px;
        line-height: 1 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* Section 標題 */
    .header-18-bold {
        font-family: 'Calibri', sans-serif;
        font-size: 18px;
        font-weight: bold;
    }
    
    /* 表格行樣式 */
    .table-row {
        line-height: 1 !important;
        margin: 0 !important;
        padding: 0 !important;
        height: 12px !important;
        display: inline-block;
        vertical-align: top;
    }
    
    /* 縮小按鈕 */
    button[kind="secondary"] {
        font-size: 0.5em !important;
        padding: 0.05em 0.1em !important;
        min-height: 18px !important;
        height: 18px !important;
    }
    
    /* 減少分隔線間距 */
    hr {
        margin: 0.2rem 0 !important;
    }

    /* --- 新增：優化表格內的 Number Input 樣式 --- */
    /* 讓輸入框變矮一點，適應表格高度 */
    div[data-testid="stNumberInput"] input {
        min-height: 25px !important;
        height: 25px !important;
        font-size: 12px !important;
        padding: 0px 5px !important;
    }
    /* 移除輸入框外圍多餘的 margin */
    div[data-testid="stNumberInput"] {
        margin-top: -5px !important; /* 微調垂直位置，讓它跟文字對齊 */
    }
</style>
""", unsafe_allow_html=True)

# ==================== 3. 頁面標題區塊 ====================
st.markdown(f'<div class="centered-title"><h1>🌅 Morning! It\'s {date_str} {weekday_str}.</h1></div>', unsafe_allow_html=True)
st.markdown("---")

# 建立主要布局：左側 40%，右側 60%
left_col, right_col = st.columns([0.4, 0.6])

# ==================== 4. 左側欄位：專案管理與追蹤 ====================
with left_col:
    # --- 4.1 上半部：Gantt 圖 ---
    if len(st.session_state.projects) > 0:
        gantt_data = []
        for project_key, project_data in st.session_state.projects.items():
            project_name = project_data.get('name', '未命名專案')
            start_date_str = project_data.get('start_date', '')
            end_date_str = project_data.get('end_date', '')
            progress = project_data.get('progress', 0)
            
            if start_date_str and end_date_str:
                try:
                    start_date_obj = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                    duration = (end_date_obj - start_date_obj).days
                    completed_days = int(duration * progress / 100)
                    completed_end_date = start_date_obj + timedelta(days=completed_days)
                    
                    gantt_data.append({
                        'Task': project_name,
                        'Start': datetime.combine(start_date_obj, datetime.min.time()),
                        'End': datetime.combine(end_date_obj, datetime.min.time()),
                        'Completed': datetime.combine(completed_end_date, datetime.min.time()),
                        'Progress': progress
                    })
                except:
                    pass
        
        if gantt_data:
            df_gantt = pd.DataFrame(gantt_data)
            fig = go.Figure()
            for idx, row in df_gantt.iterrows():
                # 進度條（綠色）
                fig.add_trace(go.Scatter(
                    x=[row['Start'], row['Completed']],
                    y=[row['Task'], row['Task']],
                    mode='lines',
                    line=dict(width=20, color='#4CAF50'),
                    showlegend=False,
                    hoverinfo='skip'
                ))
                # 剩餘條（灰色）
                if row['Completed'] < row['End']:
                    fig.add_trace(go.Scatter(
                        x=[row['Completed'], row['End']],
                        y=[row['Task'], row['Task']],
                        mode='lines',
                        line=dict(width=20, color='#E0E0E0'),
                        showlegend=False,
                        hoverinfo='skip'
                    ))
                
                # 進度百分比文字
                time_diff = row['End'] - row['Start']
                mid_date = row['Start'] + time_diff / 2
                fig.add_annotation(
                    x=mid_date, y=row['Task'], text=f"{row['Progress']}%",
                    showarrow=False, font=dict(size=10, color='black')
                )
            
            # Today 虛線
            today_datetime = datetime.combine(today_date, datetime.min.time())
            fig.update_layout(
                height=max(300, len(gantt_data) * 40),
                showlegend=False,
                xaxis=dict(showgrid=True, gridcolor='lightgray', type='date'),
                yaxis=dict(showgrid=False),
                plot_bgcolor='white',
                font=dict(family='Calibri', size=12),
                margin=dict(l=0, r=0, t=0, b=0)
            )
            fig.add_shape(type="line", x0=today_datetime, x1=today_datetime, y0=-0.5, y1=len(gantt_data) - 0.5, line=dict(color="blue", width=2, dash="dash"))
            fig.add_annotation(x=today_datetime, y=len(gantt_data) - 0.5, text="Today", showarrow=False, font=dict(size=10, color='blue'), bgcolor="white", bordercolor="blue", borderwidth=1)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("沒有有效的專案日期資料")
    else:
        st.info("目前沒有專案")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- 4.2 下半部：Tracking 表格 ---
    st.markdown('<div class="header-18-bold">Tracking</div>', unsafe_allow_html=True)
    
    if len(st.session_state.projects) > 0:
        # 排序：依結束日期
        sorted_projects = sorted(
            st.session_state.projects.items(),
            key=lambda x: (
                datetime.strptime(x[1].get('end_date', '9999-12-31'), "%Y-%m-%d").date() 
                if x[1].get('end_date') else date(9999, 12, 31)
            )
        )
        
        # 表頭
        col_header = st.columns([3, 1.2, 1.2, 0.8, 0.8])
        col_header[0].markdown('<div class="calibri-text table-row"><strong>Project</strong></div>', unsafe_allow_html=True)
        col_header[1].markdown('<div class="calibri-text table-row"><strong>Start Day</strong></div>', unsafe_allow_html=True)
        col_header[2].markdown('<div class="calibri-text table-row"><strong>End Date</strong></div>', unsafe_allow_html=True)
        col_header[3].markdown('<div class="calibri-text table-row"><strong>ACH%</strong></div>', unsafe_allow_html=True)
        st.markdown("---")
        
        items_to_remove = []
        for project_key, project_data in sorted_projects:
            project_name = project_data.get('name', '未命名專案')
            project_url = project_data.get('url', '').strip()
            start_date = project_data.get('start_date', '')
            end_date = project_data.get('end_date', '')
            progress = project_data.get('progress', 0)
            
            # 每一行的欄位配置
            col_row = st.columns([3, 1.2, 1.2, 0.8, 0.8])
            
            # Project Name (Link)
            with col_row[0]:
                if project_url:
                    url = project_url if project_url.startswith(('http://', 'https://')) else 'https://' + project_url
                    st.markdown(f'<div class="calibri-text table-row"><a href="{url}" target="_blank" style="text-decoration: none; color: #1f77b4;">{project_name}</a></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="calibri-text table-row">{project_name}</div>', unsafe_allow_html=True)
            
            # Dates
            with col_row[1]: st.markdown(f'<div class="calibri-text table-row">{start_date}</div>', unsafe_allow_html=True)
            with col_row[2]: st.markdown(f'<div class="calibri-text table-row">{end_date}</div>', unsafe_allow_html=True)
            
            # ACH% (改為輸入框！)
            with col_row[3]: 
                st.number_input(
                    "progress",
                    min_value=0, 
                    max_value=100, 
                    value=int(progress), 
                    step=5,
                    key=f"prog_input_{project_key}", # 給予每個輸入框唯一的 ID
                    label_visibility="collapsed",    # 隱藏標籤
                    on_change=update_progress_callback, # 綁定 callback 自動儲存
                    args=(project_key,)              # 傳遞參數給 callback
                )
            
            # Buttons
            with col_row[4]:
                col_edit, col_delete = st.columns(2)
                with col_edit:
                    if st.button("✏️", key=f"edit_{project_key}", help="編輯"):
                        st.session_state[f'editing_{project_key}'] = True
                        st.rerun()
                with col_delete:
                    if st.button("🗑️", key=f"delete_{project_key}", help="刪除"):
                        items_to_remove.append(project_key)

            # 編輯模式 (修正：使用數字輸入框)
            if st.session_state.get(f'editing_{project_key}', False):
                with st.expander(f"✏️ 編輯：{project_name}", expanded=True):
                    with st.form(f"edit_form_{project_key}"):
                        new_name = st.text_input("專案名稱", value=project_name)
                        new_url = st.text_input("專案連結（選填）", value=project_url)
                        
                        s_date = None
                        e_date = None
                        if start_date:
                            try: s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                            except: pass
                        if end_date:
                            try: e_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                            except: pass
                            
                        new_start_edit = st.date_input("Start Day", value=s_date)
                        new_end_edit = st.date_input("End Date", value=e_date)
                        
                        # 改為 Number Input
                        new_progress = st.number_input("進度 (%)", min_value=0, max_value=100, value=progress, step=5)
                        
                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.form_submit_button("💾 保存"):
                                # 更新資料
                                st.session_state.projects[project_key]['name'] = new_name
                                st.session_state.projects[project_key]['start_date'] = str(new_start_edit)
                                st.session_state.projects[project_key]['end_date'] = str(new_end_edit)
                                st.session_state.projects[project_key]['progress'] = new_progress
                                
                                if new_url.strip():
                                    st.session_state.projects[project_key]['url'] = new_url.strip()
                                else:
                                    st.session_state.projects[project_key].pop('url', None)
                                    
                                save_projects(st.session_state.projects)
                                st.session_state[f'editing_{project_key}'] = False
                                st.rerun()
                        with col_cancel:
                            if st.form_submit_button("❌ 取消"):
                                st.session_state[f'editing_{project_key}'] = False
                                st.rerun()
            st.markdown("---")
            
        # 刪除處理
        if items_to_remove:
            for key in items_to_remove:
                del st.session_state.projects[key]
            save_projects(st.session_state.projects)
            st.rerun()
            
    # 新增專案表單 (修正：使用數字輸入框)
    with st.expander("➕ 新增專案"):
        with st.form("add_project"):
            new_name = st.text_input("專案名稱")
            new_url = st.text_input("專案連結（選填）", placeholder="https://...")
            new_start = st.date_input("開始日期")
            new_end = st.date_input("結束日期")
            # 改為 Number Input
            new_ach = st.number_input("進度 (%)", min_value=0, max_value=100, value=0, step=5)
            
            if st.form_submit_button("新增"):
                key = f"project_{int(datetime.now().timestamp())}"
                
                project_data = {
                    "name": new_name,
                    "start_date": str(new_start),
                    "end_date": str(new_end),
                    "progress": new_ach
                }
                
                if new_url.strip():
                    project_data['url'] = new_url.strip()
                    
                st.session_state.projects[key] = project_data
                save_projects(st.session_state.projects)
                st.rerun()

# ==================== 5. 右側欄位：News Feed (HTML 零間距版) ====================
with right_col:
    st.markdown('<div class="header-18-bold">News Feed</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 定義新聞來源
    news_sources_map = {
        'top_left': { 'name': 'BBC 中文', 'url': 'https://feeds.bbci.co.uk/zhongwen/trad/rss.xml' },
        'top_right': { 'name': '德國之聲 (DW)', 'url': 'https://rss.dw.com/rdf/rss-chi-all' },
        'bottom_left': { 'name': '報導者 (The Reporter)', 'url': 'https://www.twreporter.org/a/rss2.xml' },
        'bottom_right': { 'name': '公視新聞 (PTS)', 'url': 'https://news.pts.org.tw/xml/newsfeed.xml' }
    }
    
    col1, col2 = st.columns(2)
    
    # 快取新聞，避免重複請求
    @st.cache_data(ttl=3600)
    def fetch_news(rss_url):
        try:
            feed = feedparser.parse(rss_url)
            return feed.entries[:10]  # 限制抓取 10 則
        except Exception:
            return []

    # 渲染新聞區塊 (去除多餘空格以避免 Markdown 誤判)
    def show_news_block(container, source_info):
        with container:
            # 顯示來源標題
            st.markdown(f'<div style="font-family:Calibri; font-size:14px; font-weight:bold; margin-bottom:5px; padding-top:10px;">{source_info["name"]}</div>', unsafe_allow_html=True)
            
            entries = fetch_news(source_info['url'])
            
            if entries:
                # 組合 HTML 字串
                html_items = ""
                
                for entry in entries:
                    # 處理摘要內容 (移除 HTML tag)
                    summary = "點擊閱讀更多..."
                    if hasattr(entry, 'summary'):
                        clean_summary = re.sub('<[^<]+?>', '', entry.summary)
                        summary = clean_summary[:60] + "..." if len(clean_summary) > 60 else clean_summary
                    
                    # 每一條新聞的 HTML (details 標籤)
                    # 修正：font-weight: 600 -> normal (去粗體)
                    item_html = f"""
                    <details style="border-bottom: 1px solid #f0f0f0; margin: 0; padding: 4px 0; background-color: white;">
                        <summary style="font-family: 'Calibri', sans-serif; font-size: 10pt; font-weight: normal; cursor: pointer; outline: none; color: #333; list-style: none;">
                            <span style="margin-right: 5px;">➤</span> {entry.title}
                        </summary>
                        <div style="font-family: 'Calibri', sans-serif; font-size: 10px; color: #666; padding: 4px 0 4px 18px; line-height: 1.4;">
                            <a href="{entry.link}" target="_blank" style="color: #1f77b4; text-decoration: none; font-weight: bold;">🔗 閱讀全文</a><br>
                            {summary}
                        </div>
                    </details>
                    """
                    # 將多行字串壓扁成一行
                    html_items += "".join([line.strip() for line in item_html.split('\n')])

                # 包裹在外層 div
                full_html = f'<div style="border-top: 1px solid #f0f0f0;">{html_items}</div>'
                
                # 一次性渲染整塊 HTML
                st.markdown(full_html, unsafe_allow_html=True)
            else:
                st.markdown('<div class="calibri-text" style="color: #999;">暫無資料</div>', unsafe_allow_html=True)

    # 放置四個象限
    with col1:
        show_news_block(st.container(), news_sources_map['top_left'])
        show_news_block(st.container(), news_sources_map['bottom_left'])
        
    with col2:
        show_news_block(st.container(), news_sources_map['top_right'])
        show_news_block(st.container(), news_sources_map['bottom_right'])

st.markdown("<br><br>", unsafe_allow_html=True)