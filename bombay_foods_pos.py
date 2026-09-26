import datetime
import os
import random
import sqlite3
from PIL import Image
import streamlit as st

# ----------------- 0. PASSWORD PROTECTION -----------------
if 'authenticated' not in st.session_state:
  st.session_state.authenticated = False

if not st.session_state.authenticated:
  st.title('🔒 Bombay Foods POS - Login')
  password = st.text_input('Enter Access PIN / Password', type='password')
  if st.button('Login'):
    if password == '1234':  # Aapka password
      st.session_state.authenticated = True
      st.rerun()
    else:
      st.error('Incorrect Password!')
  st.stop()

# Thermal Printer Setup
try:
  from escpos.printer import Usb

  HAS_PRINTER = True
except ImportError:
  HAS_PRINTER = False

# Image Folder Setup
IMAGE_FOLDER = 'product_images'
if not os.path.exists(IMAGE_FOLDER):
  os.makedirs(IMAGE_FOLDER)

# ----------------- DATABASE SETUP -----------------
conn = sqlite3.connect('bombay_foods.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS categories (
    name TEXT PRIMARY KEY,
    image_path TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    barcode TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'General',
    price REAL NOT NULL,
    stock INTEGER NOT NULL,
    image_path TEXT,
    is_weighted INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_date TEXT NOT NULL,
    total_amount REAL NOT NULL
)
""")
conn.commit()

# ----------------- PAGE CONFIG & TOUCH COMPACT THEME -----------------
st.set_page_config(
    page_title='Bombay Foods - Touch POS',
    layout='wide',
    initial_sidebar_state='collapsed',
)

st.markdown(
    """
<style>
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        max-width: 99% !important;
    }
    
    .stApp {
        background-color: #f8fafc;
        border: 3px solid #1e293b;
        border-radius: 12px;
    }
    
    h1, h2, h3 {
        font-size: 1.1rem !important;
        margin-bottom: 0.2rem !important;
        color: #0f172a;
    }
    
    .stButton>button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        margin-bottom: 2px !important;
    }

    div[data-testid="stVerticalBlock"] > div {
        gap: 0.2rem !important;
    }

    div[data-testid="stColumn"] button {
        white-space: normal !important;
        word-wrap: break-word !important;
    }

    /* Product & Category Image Compact Sizing */
    .stImage img {
        max-height: 90px !important;
        object-fit: contain !important;
        margin: 0 auto !important;
        display: block !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

if 'cart' not in st.session_state:
  st.session_state.cart = []

if 'selected_category' not in st.session_state:
  st.session_state.selected_category = 'ALL'


# Helper: Save Image
def save_uploaded_image(file_obj, prefix_str):
  try:
    img = Image.open(file_obj)
    if img.mode in ('RGBA', 'P'):
      img = img.convert('RGBA')
    else:
      img = img.convert('RGB')

    clean_prefix = (
        ''.join(e for e in prefix_str if e.isalnum() or e in ('_', '-'))
        .strip()
        .lower()
    )
    save_path = os.path.join(IMAGE_FOLDER, f'{clean_prefix}.png')
    img.save(save_path, 'PNG')
    return save_path
  except Exception as e:
    st.error(f'Image save error: {e}')
    return ''


# Helper: Thermal Print
def print_thermal_receipt(cart_items, total_amount):
  if not HAS_PRINTER:
    st.warning('Thermal Printer Library Missing!')
    return

  try:
    p = Usb(0x04B8, 0x0E03, 0, 0x81, 0x02)
    p.text('\n--------------------------------\n')
    p.text('         BOMBAY FOODS          \n')
    p.text('    Spices & Fast Food Store   \n')
    p.text(f" Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    p.text('--------------------------------\n')

    for item in cart_items:
      if item.get('is_weighted', 0) == 1:
        qty_str = f"{item['weight_val']:.0f}{'g' if item['unit_type']=='Grams' else 'kg'}"
        p.text(f"{item['name'][:15]:<15} {qty_str:<7} Rs {item['total']:.2f}\n")
      else:
        p.text(
            f"{item['name'][:15]:<15} x{item['qty']:<6} Rs {item['total']:.2f}\n"
        )

    p.text('--------------------------------\n')
    p.text(f' TOTAL AMOUNT:     Rs {total_amount:.2f}\n')
    p.text('--------------------------------\n')
    p.text('     Thank You For Shopping!    \n\n\n')
    p.cut()
    st.success('🖨️ Thermal Receipt Printed!')
  except Exception as e:
    st.error(f'Printer error: {str(e)}')


# Receipt Preview Dialog
@st.dialog('🧾 Receipt Print Preview')
def show_receipt_preview(cart_items, total_amount):
  st.markdown('### 🌶️ **BOMBAY FOODS**')
  st.caption('Spices & Fast Food Store')
  st.write(f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
  st.markdown('---')

  for item in cart_items:
    c1, c2, c3 = st.columns([3, 2, 1.5])
    c1.write(item['name'])
    if item.get('is_weighted', 0) == 1:
      c2.write(
          f"{item['weight_val']:.0f} {'Grams' if item['unit_type']=='Grams' else 'KG'}"
      )
    else:
      c2.write(f"x{item['qty']}")
    c3.write(f"Rs {item['total']:.2f}")

  st.markdown('---')
  st.markdown(f'### **Grand Total: Rs {total_amount:.2f}**')
  st.markdown('---')

  col_p, col_c = st.columns(2)

  with col_p:
    if st.button('🖨️ Confirm & Print', type='primary', use_container_width=True):
      for item in cart_items:
        if item.get('is_weighted', 0) == 1:
          kg_used = (
              item['weight_val'] / 1000.0
              if item['unit_type'] == 'Grams'
              else item['weight_val']
          )
          cursor.execute(
              'UPDATE products SET stock = stock - ? WHERE barcode = ?',
              (kg_used, item['barcode']),
          )
        else:
          cursor.execute(
              'UPDATE products SET stock = stock - ? WHERE barcode = ?',
              (item['qty'], item['barcode']),
          )

      today_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
      cursor.execute(
          'INSERT INTO sales (bill_date, total_amount) VALUES (?, ?)',
          (today_str, total_amount),
      )
      conn.commit()

      print_thermal_receipt(cart_items, total_amount)

      st.balloons()
      st.success('✅ Order Completed!')
      st.session_state.cart = []
      st.rerun()

  with col_c:
    if st.button('❌ Back to Order', use_container_width=True):
      st.rerun()


# Helper: Add to Cart
def add_to_cart(b_code, p_name, p_price, p_stock, is_weighted):
  if p_stock <= 0:
    st.error('Out of Stock!')
    return

  found = False
  for item in st.session_state.cart:
    if item['barcode'] == b_code:
      if not is_weighted:
        if item['qty'] + 1 <= p_stock:
          item['qty'] += 1
          item['total'] = item['qty'] * item['price']
          st.toast(f'Added +1 {p_name}', icon='➕')
        else:
          st.error('Stock Limit Reached!')
      else:
        st.toast(f'{p_name} Cart me pehle se hai!', icon='⚠️')
      found = True
      break

  if not found:
    if is_weighted:
      default_val = 250.0
      calc_total = (p_price / 1000.0) * default_val
      st.session_state.cart.append({
          'barcode': b_code,
          'name': p_name,
          'price': p_price,
          'qty': 1,
          'unit_type': 'Grams',
          'weight_val': default_val,
          'is_weighted': 1,
          'stock': p_stock,
          'total': calc_total,
      })
    else:
      st.session_state.cart.append({
          'barcode': b_code,
          'name': p_name,
          'price': p_price,
          'qty': 1,
          'unit_type': 'Piece',
          'weight_val': 0,
          'is_weighted': 0,
          'stock': p_stock,
          'total': p_price,
      })
    st.toast(f'{p_name} Added!', icon='🛒')


# Callback: Auto Process Barcode Scan / Enter
def process_barcode_scan():
  scanned_code = st.session_state.fast_barcode_scan.strip()
  if scanned_code:
    cursor.execute(
        'SELECT barcode, name, price, stock, is_weighted FROM products WHERE'
        ' barcode=?',
        (scanned_code,),
    )
    found_prod = cursor.fetchone()
    if found_prod:
      add_to_cart(
          found_prod[0],
          found_prod[1],
          found_prod[2],
          found_prod[3],
          found_prod[4],
      )
    else:
      st.toast('Product Not Found!', icon='❌')
    st.session_state.fast_barcode_scan = ''


# Header with Logout
header_col1, header_col2 = st.columns([6, 1])
with header_col1:
  top_tab = st.radio(
      '',
      ['🛒 Touch Screen Billing (Main Menu)', '⚙️ Manage Items & Categories'],
      horizontal=True,
  )
with header_col2:
  if st.button('🔒 Logout'):
    st.session_state.authenticated = False
    st.rerun()

# =========================================================
# 1. TOUCH SCREEN BILLING LAYOUT
# =========================================================
if top_tab == '🛒 Touch Screen Billing (Main Menu)':

  col_categories, col_products, col_cart = st.columns([1.3, 3.7, 2.5])

  # ---------------- LEFT SIDE: CATEGORIES ----------------
  with col_categories:
    st.markdown('### 🖼️ Categories')

    cursor.execute('SELECT name, image_path FROM categories')
    cat_rows = cursor.fetchall()
    categories_map = {'ALL': None}
    for c_name, c_img in cat_rows:
      categories_map[c_name] = c_img

    cursor.execute(
        "SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND"
        " category != ''"
    )
    prod_cats = cursor.fetchall()
    for (p_cname,) in prod_cats:
      if p_cname not in categories_map:
        categories_map[p_cname] = None

    for cat_name, cat_img in categories_map.items():
      is_selected = st.session_state.selected_category == cat_name
      btn_type = 'primary' if is_selected else 'secondary'

      if cat_img and os.path.exists(cat_img):
        st.image(cat_img, width=70)

      if st.button(
          f'📂 {cat_name}',
          key=f'side_cat_{cat_name}',
          use_container_width=True,
          type=btn_type,
      ):
        st.session_state.selected_category = cat_name
        st.rerun()

  # ---------------- MIDDLE: PRODUCTS GRID ----------------
  with col_products:
    st.markdown(f'### 🎯 Products: **{st.session_state.selected_category}**')

    # Fast Auto Barcode Scanner / Manual Type Input Field
    st.text_input(
        '📷 Scan Barcode / Type Code & Press Enter',
        key='fast_barcode_scan',
        placeholder='Scan barcode or type & press Enter...',
        on_change=process_barcode_scan,
    )

    if st.session_state.selected_category == 'ALL':
      cursor.execute(
          'SELECT barcode, name, category, price, stock, image_path, is_weighted'
          ' FROM products'
      )
    else:
      cursor.execute(
          'SELECT barcode, name, category, price, stock, image_path, is_weighted'
          ' FROM products WHERE category=?',
          (st.session_state.selected_category,),
      )

    products = cursor.fetchall()

    if products:
      grid_cols = st.columns(3)
      for idx, item in enumerate(products):
        b_code, p_name, p_cat, p_price, p_stock, p_img, is_w = item

        with grid_cols[idx % 3]:
          with st.container(border=True):
            if p_img and os.path.exists(p_img):
              st.image(p_img, width=80)
            else:
              st.caption('🖼️ No Image')

            st.markdown(f'**{p_name}**')
            price_text = (
                f'Rs {p_price:.0f} / KG' if is_w == 1 else f'Rs {p_price:.0f}'
            )
            st.caption(price_text)

            if st.button(
                '➕ Add',
                key=f'prod_click_{b_code}_{idx}',
                use_container_width=True,
                type='primary',
            ):
              add_to_cart(b_code, p_name, p_price, p_stock, is_w)
              st.rerun()
    else:
      st.info('Is category me koi products nahi mile.')

  # ---------------- RIGHT SIDE: CART SYSTEM ----------------
  with col_cart:
    st.markdown('### 🛒 Bill Cart')

    if st.session_state.cart:
      items_to_remove = []

      for idx, item in enumerate(st.session_state.cart):
        st.markdown(
            f"<b style='font-size:13px;'>{item['name']}</b>",
            unsafe_allow_html=True,
        )

        if item.get('is_weighted', 0) == 1:
          col_unit, col_val, col_pr, col_del = st.columns([1.1, 1.4, 1.4, 0.5])

          u_type = col_unit.selectbox(
              'Unit',
              ['Grams', 'KG'],
              index=0 if item['unit_type'] == 'Grams' else 1,
              key=f'utype_{idx}',
              label_visibility='collapsed',
          )
          item['unit_type'] = u_type

          if u_type == 'Grams':
            w_val = col_val.number_input(
                'Grams',
                min_value=1.0,
                max_value=float(item['stock'] * 1000.0),
                value=float(item['weight_val']),
                step=50.0,
                key=f'wval_{idx}',
                label_visibility='collapsed',
            )
            item['weight_val'] = w_val

            calc_p = (item['price'] / 1000.0) * w_val
            user_p = col_pr.number_input(
                'Price',
                min_value=0.0,
                value=float(calc_p),
                step=10.0,
                key=f'pr_val_{idx}',
                label_visibility='collapsed',
            )

            if abs(user_p - calc_p) > 0.01:
              item['total'] = user_p
              if item['price'] > 0:
                item['weight_val'] = (user_p / item['price']) * 1000.0
            else:
              item['total'] = calc_p

          else:
            w_val = col_val.number_input(
                'KG',
                min_value=0.01,
                max_value=float(item['stock']),
                value=float(
                    item['weight_val'] / 1000.0
                    if item['unit_type'] == 'Grams'
                    else item['weight_val']
                ),
                step=0.25,
                key=f'wval_kg_{idx}',
                label_visibility='collapsed',
            )
            item['weight_val'] = w_val

            calc_p = item['price'] * w_val
            user_p = col_pr.number_input(
                'Price',
                min_value=0.0,
                value=float(calc_p),
                step=10.0,
                key=f'pr_val_kg_{idx}',
                label_visibility='collapsed',
            )

            if abs(user_p - calc_p) > 0.01:
              item['total'] = user_p
              if item['price'] > 0:
                item['weight_val'] = user_p / item['price']
            else:
              item['total'] = calc_p

        else:
          col_qty, col_pr, col_del = st.columns([1.8, 1.8, 0.5])

          new_q = col_qty.number_input(
              'Qty',
              min_value=1,
              max_value=int(item['stock']),
              value=item['qty'],
              key=f'qty_{idx}',
              label_visibility='collapsed',
          )
          item['qty'] = new_q

          calc_p = item['qty'] * item['price']
          user_p = col_pr.number_input(
              'Price',
              min_value=0.0,
              value=float(calc_p),
              step=10.0,
              key=f'pr_pcs_{idx}',
              label_visibility='collapsed',
          )
          item['total'] = user_p

        if col_del.button('❌', key=f'del_{idx}'):
          items_to_remove.append(idx)

      if items_to_remove:
        for i in sorted(items_to_remove, reverse=True):
          st.session_state.cart.pop(i)
        st.rerun()

      total = sum(i['total'] for i in st.session_state.cart)
      st.markdown(f'### Total: **Rs {total:.2f}**')

      btn_col1, btn_col2 = st.columns(2)

      with btn_col1:
        if st.button(
            '🧾 Print Preview', use_container_width=True, type='primary'
        ):
          show_receipt_preview(st.session_state.cart, total)

      with btn_col2:
        if st.button('🗑️ Clear', use_container_width=True):
          st.session_state.cart = []
          st.rerun()
    else:
      st.caption('Cart Khali Hai.')


# =========================================================
# 2. MANAGE PRODUCTS & CATEGORIES
# =========================================================
elif top_tab == '⚙️ Manage Items & Categories':

  tab_cat, tab_prod = st.tabs(['📂 1. Manage Categories', '📦 2. Manage Products'])

  # --- TAB 1: ADD & EDIT CATEGORIES WITH IMAGE ---
  with tab_cat:
    st.subheader('➕ Add New Category')
    with st.form('add_category_form', clear_on_submit=True):
      cat_name_input = st.text_input('Category Name (e.g. Drinks, Masala)')
      cat_img_input = st.file_uploader(
          'Category Image Upload (JPG, PNG)', type=None
      )

      if st.form_submit_button('Save Category'):
        if cat_name_input.strip():
          c_name = cat_name_input.strip().title()
          c_path = ''
          if cat_img_input is not None:
            c_path = save_uploaded_image(cat_img_input, f'cat_{c_name}')

          cursor.execute(
              'INSERT OR REPLACE INTO categories (name, image_path) VALUES (?, ?)',
              (c_name, c_path),
          )
          conn.commit()
          st.success(f"Category '{c_name}' Saved Successfully!")
          st.rerun()
        else:
          st.error('Category name likhna zaroori hai!')

    st.markdown('---')
    st.subheader('✏️ Edit / Delete Existing Categories')

    cursor.execute('SELECT name, image_path FROM categories')
    all_cats = cursor.fetchall()

    if all_cats:
      cat_to_edit = st.selectbox(
          'Select Category to Edit / Delete', options=[c[0] for c in all_cats]
      )

      current_img = ''
      for c_name, c_img in all_cats:
        if c_name == cat_to_edit:
          current_img = c_img
          break

      col_e1, col_e2 = st.columns(2)

      with col_e1:
        new_cat_name = st.text_input('Edit Category Name', value=cat_to_edit)
        new_cat_img = st.file_uploader(
            'Change Category Image (Optional)',
            type=None,
            key='edit_cat_img_upload',
        )

        if current_img and os.path.exists(current_img):
          st.image(current_img, caption='Current Category Image', width=100)

      with col_e2:
        st.write('### Actions')
        if st.button('💾 Update Category', type='primary'):
          final_img_path = current_img
          if new_cat_img is not None:
            final_img_path = save_uploaded_image(
                new_cat_img, f'cat_{new_cat_name}'
            )

          if new_cat_name != cat_to_edit:
            cursor.execute(
                'DELETE FROM categories WHERE name = ?', (cat_to_edit,)
            )
            cursor.execute(
                'UPDATE products SET category = ? WHERE category = ?',
                (new_cat_name, cat_to_edit),
            )

          cursor.execute(
              'INSERT OR REPLACE INTO categories (name, image_path) VALUES (?, ?)',
              (new_cat_name, final_img_path),
          )
          conn.commit()
          st.success('Category updated successfully!')
          st.rerun()

        if st.button('🗑️ Delete Category'):
          cursor.execute(
              'DELETE FROM categories WHERE name = ?', (cat_to_edit,)
          )
          cursor.execute(
              "UPDATE products SET category = 'General' WHERE category = ?",
              (cat_to_edit,),
          )
          conn.commit()
          st.warning(f"Category '{cat_to_edit}' Deleted!")
          st.rerun()
    else:
      st.info('Abhi koi categories save nahi hain.')

  # --- TAB 2: MANAGE PRODUCTS (ADD / EDIT / DELETE) ---
  with tab_prod:
    sub_tab_add, sub_tab_edit = st.tabs(
        ['➕ Add New Product', '✏️ Edit / Delete Products']
    )

    cursor.execute('SELECT name FROM categories')
    available_cats = [r[0] for r in cursor.fetchall()]
    if not available_cats:
      cursor.execute(
          'SELECT DISTINCT category FROM products WHERE category IS NOT NULL'
      )
      available_cats = [r[0] for r in cursor.fetchall()]

    # 1. ADD NEW PRODUCT
    with sub_tab_add:
      st.subheader('➕ Add New Product')

      if not available_cats:
        st.warning(
            "Pehle '1. Manage Categories' me jaakar kam se kam ek Category add"
            ' karein!'
        )
      else:
        with st.form('add_item_form', clear_on_submit=True):
          col1, col2 = st.columns(2)
          with col1:
            barcode_input = st.text_input(
                'Product ID / Barcode (Optional - Scan or Type manually)'
            )
            name = st.text_input('Product Name')
            selected_cat = st.selectbox(
                'Select Category', options=available_cats
            )
            is_weighted_val = st.checkbox(
                'Loose Item (Price per KG / Grams option)'
            )
          with col2:
            price = st.number_input('Price (Rs)', min_value=1.0)
            stock = st.number_input(
                'Stock Qty (Pcs or KG)', min_value=1, value=50
            )
            uploaded_img = st.file_uploader(
                'Product Image Upload (Optional)', type=None
            )

          submitted = st.form_submit_button('Save Product')
          if submitted:
            if name:
              # Auto-generate barcode if left empty
              final_barcode = barcode_input.strip()
              if not final_barcode:
                final_barcode = f'BF{random.randint(100000, 999999)}'

              img_path = ''
              if uploaded_img is not None:
                img_path = save_uploaded_image(
                    uploaded_img, f'prod_{final_barcode}'
                )

              w_flag = 1 if is_weighted_val else 0
              cursor.execute(
                  'INSERT OR REPLACE INTO products (barcode, name, category,'
                  ' price, stock, image_path, is_weighted) VALUES (?, ?, ?, ?,'
                  ' ?, ?, ?)',
                  (
                      final_barcode,
                      name,
                      selected_cat,
                      price,
                      stock,
                      img_path,
                      w_flag,
                  ),
              )
              conn.commit()
              st.success(
                  f"Product '{name}' Saved! (Barcode/ID: {final_barcode})"
              )
              st.rerun()
            else:
              st.error('Product Name likhna zaroori hai!')

    # 2. EDIT / DELETE EXISTING PRODUCT
    with sub_tab_edit:
      st.subheader('✏️ Edit or Delete Existing Product')

      cursor.execute(
          'SELECT barcode, name, category, price, stock, image_path, is_weighted'
          ' FROM products'
      )
      all_products = cursor.fetchall()

      if all_products:
        prod_options = {f"{p[1]} (ID: {p[0]})": p for p in all_products}
        selected_prod_label = st.selectbox(
            'Select Product to Edit/Delete', options=list(prod_options.keys())
        )
        p_data = prod_options[selected_prod_label]

        p_barcode, p_name, p_cat, p_price, p_stock, p_img, p_is_w = p_data

        with st.form('edit_product_form'):
          col_ep1, col_ep2 = st.columns(2)

          with col_ep1:
            st.text_input('Product Barcode / ID', value=p_barcode, disabled=True)
            edit_name = st.text_input('Product Name', value=p_name)

            cat_index = 0
            if available_cats and p_cat in available_cats:
              cat_index = available_cats.index(p_cat)

            edit_cat = st.selectbox(
                'Category',
                options=available_cats if available_cats else [p_cat],
                index=cat_index,
            )
            edit_is_w = st.checkbox(
                'Loose Item (KG/Grams)', value=bool(p_is_w)
            )

          with col_ep2:
            edit_price = st.number_input('Price (Rs)', value=float(p_price))
            edit_stock = st.number_input('Stock Qty', value=int(p_stock))
            edit_img = st.file_uploader(
                'Change Image (Optional)',
                type=None,
                key='edit_prod_img_upload',
            )

            if p_img and os.path.exists(p_img):
              st.image(p_img, caption='Current Image', width=100)

          st.markdown('---')
          btn_update, btn_delete = st.columns(2)

          with btn_update:
            update_btn = st.form_submit_button(
                '💾 Update Product', type='primary'
            )
          with btn_delete:
            delete_btn = st.form_submit_button('🗑️ Delete Product')

          if update_btn:
            final_img = p_img
            if edit_img is not None:
              final_img = save_uploaded_image(edit_img, f'prod_{p_barcode}')

            w_flag = 1 if edit_is_w else 0
            cursor.execute(
                'UPDATE products SET name=?, category=?, price=?, stock=?,'
                ' image_path=?, is_weighted=? WHERE barcode=?',
                (
                    edit_name,
                    edit_cat,
                    edit_price,
                    edit_stock,
                    final_img,
                    w_flag,
                    p_barcode,
                ),
            )
            conn.commit()
            st.success(f"Product '{edit_name}' updated successfully!")
            st.rerun()

          if delete_btn:
            cursor.execute(
                'DELETE FROM products WHERE barcode=?', (p_barcode,)
            )
            conn.commit()
            st.warning(f"Product '{p_name}' deleted!")
            st.rerun()
      else:
        st.info('Database me koi products mojood nahi hain.')