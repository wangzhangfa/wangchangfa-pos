"""
王長發商號 - 顧客線上點餐系統 (app.py)
升級內容：
  - 使用 .env / st.secrets 管理金鑰
  - 菜單從資料庫動態讀取
  - 支援分類顯示、單品備註
  - 購物車 UI
  - 訂單送出後可追蹤狀態
"""

import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# ==========================================
# 1. 安全讀取金鑰
# ==========================================
load_dotenv()  # 讀取 .env 檔案（本地開發用）

def get_supabase_client() -> Client:
    # 優先使用 Streamlit Cloud 的 secrets，否則讀 .env
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")

    if not url or not key:
        st.error("⚠️ 找不到資料庫設定，請檢查 .env 或 Streamlit secrets。")
        st.stop()

    return create_client(url, key)

supabase = get_supabase_client()

# ==========================================
# 2. 資料庫讀取函式
# ==========================================
@st.cache_data(ttl=60)  # 快取 60 秒，減少讀取次數
def fetch_menu():
    """從資料庫讀取可用菜單，依分類整理"""
    categories = supabase.table("menu_categories") \
        .select("*").order("display_order").execute().data
    items = supabase.table("menu_items") \
        .select("*").eq("is_available", True).order("display_order").execute().data

    menu = {}
    for cat in categories:
        menu[cat["name"]] = [i for i in items if i["category_id"] == cat["id"]]
    return menu

def get_order_status(order_id: int):
    """查詢訂單狀態"""
    result = supabase.table("orders").select("status, created_at") \
        .eq("id", order_id).execute().data
    return result[0] if result else None

STATUS_LABELS = {
    "pending":    ("🟡", "等待廚房確認"),
    "preparing":  ("🔵", "廚房準備中"),
    "completed":  ("🟢", "完成！請取餐"),
    "cancelled":  ("🔴", "已取消"),
}

# ==========================================
# 3. Session State 初始化
# ==========================================
if "cart" not in st.session_state:
    st.session_state.cart = {}       # {item_id: {"item": {...}, "qty": n, "note": ""}}
if "order_id" not in st.session_state:
    st.session_state.order_id = None
if "order_submitted" not in st.session_state:
    st.session_state.order_submitted = False

# ==========================================
# 4. 頁面設定
# ==========================================
st.set_page_config(page_title="王長發商號 - 線上點餐", page_icon="🍽️", layout="centered")

st.markdown("""
<style>
    .main-title { font-size: 2.2rem; font-weight: 800; color: #2c3e50; }
    .category-header { font-size: 1.3rem; font-weight: 700; color: #e67e22;
                        border-left: 5px solid #e67e22; padding-left: 10px; margin-top: 20px; }
    .item-card { background: #fafafa; border-radius: 10px; padding: 12px 16px;
                  margin: 8px 0; border: 1px solid #eee; }
    .cart-summary { background: #2c3e50; color: white; border-radius: 10px;
                     padding: 16px 20px; margin-top: 20px; }
    .status-box { border-radius: 10px; padding: 20px; text-align: center;
                   background: #f0f4ff; margin-top: 20px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5. 訂單追蹤頁（送出後顯示）
# ==========================================
if st.session_state.order_submitted and st.session_state.order_id:
    st.markdown('<div class="main-title">🍽️ 王長發商號</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.subheader(f"訂單追蹤 #{st.session_state.order_id}")

    order = get_order_status(st.session_state.order_id)
    if order:
        status = order["status"]
        icon, label = STATUS_LABELS.get(status, ("⚪", "未知"))
        st.markdown(f"""
        <div class="status-box">
            <div style="font-size:3rem;">{icon}</div>
            <div style="font-size:1.5rem; font-weight:700; margin-top:8px;">{label}</div>
        </div>
        """, unsafe_allow_html=True)

        if status == "completed":
            st.balloons()
    else:
        st.warning("找不到訂單資訊")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 更新狀態", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("🛍️ 再點一次", use_container_width=True, type="primary"):
            st.session_state.cart = {}
            st.session_state.order_id = None
            st.session_state.order_submitted = False
            st.rerun()
    st.stop()

# ==========================================
# 6. 點餐主頁面
# ==========================================
st.markdown('<div class="main-title">🍽️ 王長發商號 - 線上點餐</div>', unsafe_allow_html=True)
st.markdown("---")

# 選擇桌號
table_num = st.selectbox("📍 請選擇桌號", ["桌號 1", "桌號 2", "桌號 3", "外帶"])

# 備餐備註（整單）
order_note = st.text_input("📝 整單備註（選填，例如：過敏資訊）", placeholder="例如：對花生過敏")

st.markdown("---")

# 讀取菜單
with st.spinner("載入菜單中..."):
    menu = fetch_menu()

# 菜單 + 購物車加入
for category, items in menu.items():
    if not items:
        continue
    st.markdown(f'<div class="category-header">{category}</div>', unsafe_allow_html=True)

    for item in items:
        item_id = item["id"]
        with st.container():
            col1, col2, col3 = st.columns([4, 2, 2])
            with col1:
                desc = f" — {item['description']}" if item.get("description") else ""
                st.markdown(f"**{item['name']}**{desc}")
                st.caption(f"$ {item['price']}")
            with col2:
                qty = st.number_input(
                    "數量", min_value=0, max_value=20, value=0,
                    key=f"qty_{item_id}", label_visibility="collapsed"
                )
            with col3:
                note = st.text_input(
                    "備註", placeholder="備註",
                    key=f"note_{item_id}", label_visibility="collapsed"
                )

            # 同步到購物車
            if qty > 0:
                st.session_state.cart[item_id] = {"item": item, "qty": qty, "note": note}
            elif item_id in st.session_state.cart:
                del st.session_state.cart[item_id]

st.markdown("---")

# ==========================================
# 7. 購物車總覽 + 送出
# ==========================================
cart = st.session_state.cart
if not cart:
    st.info("還沒有選擇餐點，請在上方選擇喔！")
else:
    total = sum(v["item"]["price"] * v["qty"] for v in cart.values())

    st.markdown("### 🛒 購物車")
    for v in cart.values():
        note_str = f"（{v['note']}）" if v["note"] else ""
        st.write(f"• {v['item']['name']} × {v['qty']} = **${v['item']['price'] * v['qty']}** {note_str}")

    st.markdown(f"**合計：${total}**")

    if st.button("🚀 送出訂單", type="primary", use_container_width=True):
        try:
            # 建立訂單主表
            order_resp = supabase.table("orders").insert({
                "table_number": table_num,
                "status": "pending",
                "total_amount": total,
                "note": order_note or None,
            }).execute()

            order_id = order_resp.data[0]["id"]

            # 建立訂單明細
            order_items = [
                {
                    "order_id": order_id,
                    "menu_item_id": v["item"]["id"],
                    "item_name": v["item"]["name"],
                    "item_price": v["item"]["price"],
                    "quantity": v["qty"],
                    "note": v["note"] or None,
                }
                for v in cart.values()
            ]
            supabase.table("order_items").insert(order_items).execute()

            st.session_state.order_id = order_id
            st.session_state.order_submitted = True
            st.rerun()

        except Exception as e:
            st.error(f"❌ 送出失敗，請再試一次：{e}")
