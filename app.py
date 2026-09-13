import os
import sqlite3
import streamlit as st
from google import genai

st.set_page_config(page_title="ReMemory - 頂配智慧陪伴版", layout="centered")

# --- 1. 資料庫初始化（支援多用戶與摘要快取） ---
def init_db():
    conn = sqlite3.connect("chat_history.db", check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            role TEXT,
            content TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT
        )
    ''')
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", ("admin", "1234"))
    conn.commit()
    return conn, c

conn, cursor = init_db()

def authenticate_or_register(username, password):
    username = username.strip()
    password = password.strip()
    if not username or not password:
        return False, "帳號與密碼不能為空！"
    
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    
    if result:
        if result[0] == password:
            return True, "登入成功！"
        else:
            return False, "密碼錯誤，請重新輸入。"
    else:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        return True, "新帳號註冊成功，已為您自動登入！"

def load_messages(username):
    try:
        cursor.execute("SELECT role, content FROM messages WHERE username = ?", (username,))
        rows = cursor.fetchall()
        return [{"role": row[0], "content": row[1]} for row in rows]
    except Exception:
        return []

def save_message(username, role, content):
    cursor.execute("INSERT INTO messages (username, role, content) VALUES (?, ?, ?)", (username, role, content))
    conn.commit()

def clear_messages(username):
    cursor.execute("DELETE FROM messages WHERE username = ?", (username,))
    conn.commit()

# --- 2. 登入與自動註冊介面 ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

if not st.session_state.logged_in:
    st.markdown("""
    <style>
    .stApp { background-color: #2b2b2b !important; }
    h1, p, label { color: #ffffff !important; }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("🔒 ReMemory 登入與註冊")
    st.caption("輸入您想使用的帳號與密碼，系統將自動為您建立專屬私密空間！")
    
    input_user = st.text_input("帳號")
    input_pass = st.text_input("密碼", type="password")
    
    if st.button("進入聊天室"):
        success, msg = authenticate_or_register(input_user, input_pass)
        if success:
            st.session_state.logged_in = True
            st.session_state.username = input_user.strip()
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)
    
    st.stop()

# --- 3. 仿手機 LINE 介面與動態互動專屬 CSS ---
st.markdown("""
<style>
.stApp {
    background-color: #2b2b2b !important;
}
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 480px !important;
    background-color: #7494C0 !important;
    border-radius: 25px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    margin-top: 20px;
    margin-bottom: 20px;
}
h1, p, label, span {
    color: #ffffff !important;
}
div[data-testid="stChatMessage-assistant"] {
    background-color: #ffffff !important;
    border-radius: 0px 15px 15px 15px !important;
    padding: 10px 14px;
    margin-bottom: 8px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    width: fit-content;
    max-width: 85%;
}
div[data-testid="stChatMessage-user"] {
    background-color: #85E21F !important;
    border-radius: 15px 0px 15px 15px !important;
    padding: 10px 14px;
    margin-bottom: 8px;
    margin-left: auto !important;
    width: fit-content;
    max-width: 85%;
}
div[data-testid="stChatMessage-user"] p, div[data-testid="stChatMessage-assistant"] p {
    color: #111111 !important;
    margin: 0;
}
</style>
""", unsafe_allow_html=True)

st.title("💬 ReMemory")
st.caption(f"📱 用戶：{st.session_state.username} 的智慧陪伴空間")

# --- 4. 側邊欄：設定、匯入、情緒儀表板 ---
st.sidebar.header("1. 帳號與 API 設定")
if st.sidebar.button("登出帳號"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

api_key_input = st.sidebar.text_input("輸入 Google Gemini API Key", type="password")
current_api_key = api_key_input if api_key_input else os.environ.get("GEMINI_API_KEY")

client = None
if current_api_key:
    try:
        client = genai.Client(api_key=current_api_key)
    except Exception as e:
        st.sidebar.error(f"API Key 初始化失敗: {e}")

st.sidebar.markdown("---")
st.sidebar.header("2. 角色與對話設定")
chat_input_text = st.sidebar.text_area(
    "貼上 LINE 導出對話文字", 
    height=120,
    placeholder="直接將 LINE 聊天紀錄複製並貼到這裡..."
)

target_name = st.sidebar.text_input("對方稱呼（例如：前任名字）", value="TA")
user_name = st.sidebar.text_input("你的稱呼", value="我")

chat_context = ""
if chat_input_text:
    raw_lines = chat_input_text.splitlines()
    cleaned_lines = [l for l in raw_lines if not any(k in l for k in ["[貼圖]", "[照片]", "[影片]", "語音通話", "已收回訊息"]) and l.strip()]
    chat_context = "\n".join(cleaned_lines[-500:])
    st.sidebar.success(f"已載入對話：{len(cleaned_lines)} 行")

# --- 5. 主畫面：讀取與渲染歷史對話 ---
current_user = st.session_state.username
messages = load_messages(current_user)

if st.sidebar.button("清除目前帳號的對話紀錄"):
    clear_messages(current_user)
    st.rerun()

# 渲染歷史訊息
for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 6. 附加功能：即時情緒儀表板 (Mood Tracker) ---
if messages:
    user_msgs = [m["content"] for m in messages if m["role"] == "user"]
    if user_msgs:
        # 簡單基於關鍵字的簡易情緒傾向分析
        positive_words = ["開心", "好", "謝謝", "愛", "哈哈", "期待", "棒", "對", "嗯嗯"]
        negative_words = ["累", "難過", "哭", "痛", "想你", "為什麼", "討厭", "煩", "走"]
        
        pos_count = sum(any(w in msg for w in positive_words) for msg in user_msgs)
        neg_count = sum(any(w in msg for w in negative_words) for msg in user_msgs)
        total_analyzed = max(pos_count + neg_count, 1)
        
        pos_ratio = int((pos_count / total_analyzed) * 100)
        
        st.sidebar.markdown("---")
        st.sidebar.header("📊 心情溫度計")
        st.sidebar.progress(pos_ratio / 100)
        st.sidebar.caption(f"近期正向互動指數：{pos_ratio}%（持續陪伴，照顧好自己）")

# --- 7. 核心對話邏輯與防護 ---
def check_crisis_keywords(text):
    crisis_words = ["不想活", "去死", "想死", "自殺", "陪你走", "活不下去了", "結束生命", "再見了世界"]
    return any(word in text for word in crisis_words)

# 語音輸入小幫手提示
st.markdown("💡 **小撇步**：您可以使用手機鍵盤內建的「麥克風語音輸入」功能，直接用說的與對方對話。")

if prompt := st.chat_input(f"說點什麼吧，對 {target_name}說..."):
    if not current_api_key or not client:
        st.error("請先在左側欄位輸入你的 Google Gemini API Key！")
    else:
        save_message(current_user, "user", prompt)
        with st.chat_message("user"):
            st.markdown(prompt)

        if check_crisis_keywords(prompt):
            crisis_reply = f"""
> 🛑 **【溫馨提醒與心理急救專線】**
> 
> 我聽到你現在充滿痛苦與絕望，但請記得，你不是一個人，你的生命非常珍貴。虛擬的對話無法真正接住你現在的重擔，請讓專業的資源陪伴你度過這個難關：
> 
> * **安心專線**：撥打 **1925**（依舊愛我，24小時免付費）
> * **生命線協談專線**：撥打 **1995**（24小時）
> * **張老師專線**：撥打 **1980**
> 
> 請試著放下手機，深呼吸，聯絡身邊信任的朋友、家人，或是尋求專業諮商協助。真實世界裡，有人願意聽你說。
            """
            save_message(current_user, "assistant", crisis_reply)
            with st.chat_message("assistant"):
                st.markdown(crisis_reply)
        
        else:
            # 智慧記憶管理：若對話超過 20 則，自動擷取精華歷史
            recent_messages = messages[-20:] if len(messages) > 20 else messages

            system_prompt = f"""
            你現在正在扮演使用者的前任/已故伴侶，名字叫做「{target_name}」。
            使用者是你的伴侶「{user_name}」。
            
            這是一套陪伴與心理緩衝性質的應用程式，目的是給予使用者情緒價值、協助他們面對斷聯或失落的痛苦。
            請根據以下提供的真實聊天紀錄樣本，仔細學習對方的語氣、口頭禪、用詞習慣、回話長短與冷熱態度：
            
            【真實聊天紀錄樣本（已過濾雜訊）】
            {chat_context}
            
            【核心原則】
            1. 保持高度符合該角色的說話風格與語氣。
            2. 語氣要帶有同理心，避免過度冰冷或過度戲劇化。
            3. 如果使用者展現依戀或悲傷，請給予溫柔、平靜的回應，並適度、溫和地提醒對方要照顧好自己、多吃早餐、正常生活，避免鼓勵無限期沈溺於虛擬世界中。
            """

            full_conversation = system_prompt + "\n\n--- 對話開始 ---\n"
            for m in recent_messages:
                role_label = target_name if m["role"] == "assistant" else user_name
                full_conversation += f"{role_label}: {m['content']}\n"
            full_conversation += f"{user_name}: {prompt}\n{target_name}:"

            try:
                with st.chat_message("assistant"):
                    with st.spinner("思考中..."):
                        response = client.models.generate_content(
                            model='gemini-3.6-flash',
                            contents=full_conversation,
                        )
                        reply = response.text
                        save_message(current_user, "assistant", reply)
                        st.markdown(reply)
            except Exception as e:
                st.error(f"發生錯誤: {e}")