import os
import sqlite3
import streamlit as st
from google import genai

st.set_page_config(page_title="ReMemory - 手機聊天室版", layout="centered")

# --- SQLite 資料庫初始化 ---
def init_db():
    conn = sqlite3.connect("chat_history.db", check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    return conn, c

conn, cursor = init_db()

def load_messages():
    cursor.execute("SELECT role, content FROM messages")
    rows = cursor.fetchall()
    return [{"role": row[0], "content": row[1]} for row in rows]

def save_message(role, content):
    cursor.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))
    conn.commit()

def clear_messages():
    cursor.execute("DELETE FROM messages")
    conn.commit()

# --- 仿手機 LINE 介面專屬 CSS 樣式 ---
st.markdown("""
<style>
/* 整個網頁背景改成深色質感 */
.stApp {
    background-color: #2b2b2b !important;
}

/* 將中央區塊變成手機外框的寬度與樣式 */
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 480px !important;
    background-color: #7494C0 !important; /* LINE 經典聊天室藍灰色背景 */
    border-radius: 25px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    margin-top: 20px;
    margin-bottom: 20px;
}

/* 標題文字改為白色以適應深色背景 */
h1, p, label {
    color: #ffffff !important;
}

/* 對方（Assistant / 左側）訊息樣式 */
div[data-testid="stChatMessage-assistant"] {
    background-color: #ffffff !important;
    border-radius: 0px 15px 15px 15px !important;
    padding: 10px 14px;
    margin-bottom: 8px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    width: fit-content;
    max-width: 85%;
}

/* 使用者（User / 右側）訊息樣式：LINE 萊姆綠並靠右 */
div[data-testid="stChatMessage-user"] {
    background-color: #85E21F !important;
    border-radius: 15px 0px 15px 15px !important;
    padding: 10px 14px;
    margin-bottom: 8px;
    margin-left: auto !important;
    width: fit-content;
    max-width: 85%;
}

/* 確保對話框內文字顏色為黑色 */
div[data-testid="stChatMessage-user"] p, div[data-testid="stChatMessage-assistant"] p {
    color: #111111 !important;
    margin: 0;
}
</style>
""", unsafe_allow_html=True)

st.title("💬 ReMemory")
st.caption("📱 手機聊天室擬真模式（具備永久記憶）")

# --- 側邊欄：設定與資料輸入 ---
st.sidebar.header("1. 設定與匯入")
api_key_input = st.sidebar.text_input("輸入 Google Gemini API Key", type="password")

current_api_key = api_key_input if api_key_input else os.environ.get("GEMINI_API_KEY")

client = None
if current_api_key:
    try:
        client = genai.Client(api_key=current_api_key)
    except Exception as e:
        st.sidebar.error(f"API Key 初始化失敗: {e}")

# 貼上 LINE 導出對話文字
chat_input_text = st.sidebar.text_area(
    "貼上 LINE 導出對話文字", 
    height=150,
    placeholder="直接將 LINE 聊天紀錄複製並貼到這裡..."
)

# 角色名稱設定
target_name = st.sidebar.text_input("對方稱呼（例如：前任名字）", value="TA")
user_name = st.sidebar.text_input("你的稱呼", value="我")

chat_context = ""
if chat_input_text:
    raw_lines = chat_input_text.splitlines()
    cleaned_lines = []
    ignore_keywords = ["[貼圖]", "[照片]", "[影片]", "語音通話", "已收回訊息", "建立通話", "通話時間"]
    
    for line in raw_lines:
        if any(keyword in line for keyword in ignore_keywords):
            continue
        if not line.strip():
            continue
        cleaned_lines.append(line)
        
    sample_lines = "\n".join(cleaned_lines[-500:]) 
    chat_context = sample_lines
    st.sidebar.success(f"成功載入對話紀錄！有效對話共 {len(cleaned_lines)} 行。")

# --- 主畫面：從資料庫載入對話並渲染 ---
messages = load_messages()

if st.sidebar.button("清除對話紀錄"):
    clear_messages()
    st.rerun()

for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

def check_crisis_keywords(text):
    crisis_words = ["不想活", "去死", "想死", "自殺", "陪你走", "活不下去了", "結束生命", "再見了世界"]
    return any(word in text for word in crisis_words)

if prompt := st.chat_input(f"說點什麼吧，對 {target_name}說..."):
    if not current_api_key or not client:
        st.error("請先在左側欄位輸入你的 Google Gemini API Key！")
    else:
        # 儲存使用者訊息進資料庫
        save_message("user", prompt)
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
            save_message("assistant", crisis_reply)
            with st.chat_message("assistant"):
                st.markdown(crisis_reply)
        
        else:
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

            # 組合歷史對話給 Gemini 參考
            full_conversation = system_prompt + "\n\n--- 對話開始 ---\n"
            for m in messages:
                role_label = target_name if m["role"] == "assistant" else user_name
                full_conversation += f"{role_label}: {m['content']}\n"
            full_conversation += f"{user_name}: {prompt}\n{target_name}:"

            try:
                with st.chat_message("assistant"):
                    with st.spinner("思考中..."):
                        response = client.models.generate_content(
                            model='gemini-2.0-flash',
                            contents=full_conversation,
                        )
                        reply = response.text
                        save_message("assistant", reply)
                        st.markdown(reply)
            except Exception as e:
                st.error(f"發生錯誤: {e}")