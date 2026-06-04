"""
王長發商號 - 顧客線上點餐系統
使用 requests 直接呼叫 Supabase REST API（相容 Python 3.14）
"""
import streamlit as st
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# ── 讀取金鑰 ──────────────────────────────
def get_cfg():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        st.error("⚠️ 找不到資料庫設定")
        st.stop()
    return url.rstrip("/"), key

SUPA_URL, SUPA_KEY = get_cfg()

def headers():
    return {
        "apikey": SUPA_KEY,
        "Authorization": f"Bearer {SUPA_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def rest(path, method="GET", params=None, json=None):
    url = f"{SUPA_URL}/rest/v1/{path}"
    r = requests.request(method, url, headers=headers(), params=params, json=json, timeout=10)
    r.raise_for_status()
    return r.json() if r.text else []

# ── 菜單快取 ──────────────────────────────
@st.cache_data(ttl=60)
def fetch_menu():
    cats  = rest("menu_categories", params={"select":"*","order":"display_order"})
    items = rest("menu_items",       params={"select":"*","is_available":"eq.true","order":"display_order"})
    menu = {}
    for c in cats:
        ci = [i for i in items if i["category_id"] == c["id"]]
        if ci:
            menu[c["name"]] = ci
    return menu

def get_order_status(order_id):
    rows = rest("orders", params={"select":"status,created_at", "id": f"eq.{order_id}"})
    return rows[0] if rows else None

def insert_order(table_num, total, note):
    rows = rest("orders", "POST", json={
        "table_number": table_num,
        "status": "pending",
        "total_amount": total,
        "note": note or None,
    })
    return rows[0]["id"]

def insert_order_items(order_id, cart):
    items = [
        {"order_id": order_id,
         "menu_item_id": v["item"]["id"],
         "item_name": v["item"]["name"],
         "item_price": v["item"]["price"],
         "quantity": v["qty"],
         "note": v["note"] or None}
        for v in cart.values()
    ]
    rest("order_items", "POST", json=items)

# ── 狀態對應 ──────────────────────────────
STATUS_LABELS = {
    "pending":   ("🟡", "等待確認中"),
    "confirmed": ("🔵", "已確認，準備結帳"),
    "paid":      ("🟣", "已結帳，備餐中"),
    "completed": ("🟢", "完成！請取餐"),
    "cancelled": ("🔴", "已取消"),
}

# ── Session State ─────────────────────────
for k, v in [("cart",{}),("order_id",None),("order_submitted",False)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── 頁面設定 ──────────────────────────────
st.set_page_config(page_title="王長發商號 - 線上點餐", page_icon="🍽️", layout="centered")
st.markdown("""
<style>
.main-title{font-size:2.2rem;font-weight:800;color:#2c3e50}
.cat-header{font-size:1.3rem;font-weight:700;color:#e67e22;
            border-left:5px solid #e67e22;padding-left:10px;margin-top:20px}
.status-box{border-radius:10px;padding:20px;text-align:center;background:#f0f4ff;margin-top:20px}
</style>
""", unsafe_allow_html=True)

# ── 訂單追蹤頁 ────────────────────────────
if st.session_state.order_submitted and st.session_state.order_id:
    st.markdown('<div class="main-title">🍽️ 王長發商號</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.subheader(f"訂單追蹤 #{st.session_state.order_id}")
    try:
        order = get_order_status(st.session_state.order_id)
        if order:
            status = order["status"]
            icon, label = STATUS_LABELS.get(status, ("⚪","未知"))
            st.markdown(f"""
            <div class="status-box">
                <div style="font-size:3rem">{icon}</div>
                <div style="font-size:1.5rem;font-weight:700;margin-top:8px">{label}</div>
            </div>""", unsafe_allow_html=True)
            if status == "completed": st.balloons()
        else:
            st.warning("找不到訂單資訊")
    except Exception as e:
        st.error(f"查詢失敗：{e}")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 更新狀態", use_container_width=True): st.rerun()
    with col2:
        if st.button("🛍️ 再點一次", use_container_width=True, type="primary"):
            st.session_state.update(cart={}, order_id=None, order_submitted=False)
            st.rerun()
    st.stop()

# ── 點餐主頁面 ────────────────────────────
st.markdown('<div class="main-title">🍽️ 王長發商號 - 線上點餐</div>', unsafe_allow_html=True)
st.markdown("---")

table_num  = st.selectbox("📍 請選擇桌號", ["桌號 1","桌號 2","桌號 3","外帶"])
order_note = st.text_input("📝 整單備註（選填）", placeholder="例如：對花生過敏")
st.markdown("---")

with st.spinner("載入菜單中..."):
    try:
        menu = fetch_menu()
    except Exception as e:
        st.error(f"菜單載入失敗：{e}")
        st.stop()

for category, items in menu.items():
    if not items: continue
    st.markdown(f'<div class="cat-header">{category}</div>', unsafe_allow_html=True)
    for item in items:
        iid = item["id"]
        with st.container():
            c1, c2, c3 = st.columns([4,2,2])
            with c1:
                desc = f" — {item['description']}" if item.get("description") else ""
                st.markdown(f"**{item['name']}**{desc}")
                st.caption(f"$ {item['price']}")
            with c2:
                qty = st.number_input("數量", 0, 20, 0,
                    key=f"qty_{iid}", label_visibility="collapsed")
            with c3:
                note = st.text_input("備註", placeholder="備註",
                    key=f"note_{iid}", label_visibility="collapsed")
            if qty > 0:
                st.session_state.cart[iid] = {"item":item,"qty":qty,"note":note}
            elif iid in st.session_state.cart:
                del st.session_state.cart[iid]

st.markdown("---")

cart = st.session_state.cart
if not cart:
    st.info("還沒有選擇餐點，請在上方選擇喔！")
else:
    total = sum(v["item"]["price"]*v["qty"] for v in cart.values())
    st.markdown("### 🛒 購物車")
    for v in cart.values():
        note_str = f"（{v['note']}）" if v["note"] else ""
        st.write(f"• {v['item']['name']} × {v['qty']} = **${v['item']['price']*v['qty']}** {note_str}")
    st.markdown(f"**合計：${total}**")

    if st.button("🚀 送出訂單", type="primary", use_container_width=True):
        try:
            oid = insert_order(table_num, total, order_note)
            insert_order_items(oid, cart)
            st.session_state.order_id = oid
            st.session_state.order_submitted = True
            st.rerun()
        except Exception as e:
            st.error(f"❌ 送出失敗：{e}")
