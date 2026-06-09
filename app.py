import os
from flask import Flask, jsonify, render_template, request
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if not DATABASE_URL:
        raise ValueError("環境變數 DATABASE_URL 未設定，請檢查 Vercel 後台設定！")
    return psycopg2.connect(DATABASE_URL, sslmode='require')

@app.route('/')
def index():
    return render_template('index.html')

# ==========================================
# 🎖️ 負責人績效考核與偏好追蹤 API 模組 (動態選單與加強防錯版)
# ==========================================

@app.route('/api/get-all-staffs')
def get_all_staffs():
    """動態撈取資料庫內所有真正的業務員名單"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT DISTINCT "負責人姓名" 
                    FROM "負責人清單" 
                    WHERE "負責人姓名" IS NOT NULL AND "負責人姓名" <> ''
                    ORDER BY "負責人姓名" ASC;
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"無法讀取業務負責人名冊：{str(e)}"}), 500

@app.route('/api/sales-detail-by-staff')
def get_sales_detail_by_staff():
    staff_name = request.args.get('staff_name', '').strip()
    if not staff_name:
        return jsonify({"error": "請提供業務負責人姓名 (?staff_name=X)", "sales_detail": []}), 400
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 撈取銷售明細
                query = """
                    SELECT 
                        s."傳票編號", 
                        s."處理日", 
                        p."商品名稱", 
                        p."販賣單價", 
                        s."數量", 
                        (p."販賣單價" * s."數量") AS "流水小計", 
                        c."顧客名稱"
                    FROM "販賣資料" AS s
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID"
                    INNER JOIN "顧客清單" AS c ON s."顧客ID" = c."顧客ID"
                    WHERE e."負責人姓名" = %s
                    ORDER BY s."處理日" DESC, s."傳票編號" DESC;
                """
                cur.execute(query, (staff_name,))
                sales_detail = cur.fetchall()

                # 撈取商品群組偏好排行
                preference_query = """
                    SELECT 
                        p."群組名稱",
                        SUM(s."數量") AS "總銷售數量",
                        SUM(p."販賣單價" * s."數量") AS "總銷售金額"
                    FROM "販賣資料" AS s
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID"
                    WHERE e."負責人姓名" = %s
                    GROUP BY p."群組名稱"
                    ORDER BY "總銷售金額" DESC;
                """
                cur.execute(preference_query, (staff_name,))
                preference_data = cur.fetchall()

        return jsonify({
            "sales_detail": sales_detail,
            "preference": preference_data
        })
    except Exception as e:
        return jsonify({"error": f"讀取該業務資料失敗：{str(e)}", "sales_detail": []}), 500

# --- 🚀 修正版：熱門組合商品交叉銷售分析 API ---
@app.route('/api/cross-selling-analysis')
def get_cross_selling_analysis():
    target_product_id = request.args.get('target_product_id')
    if not target_product_id:
        return jsonify({"error": "請提供基準商品 ID (?target_product_id=X)"}), 400
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    WITH TargetBuyers AS (
                        SELECT DISTINCT "顧客ID" FROM "販賣資料" WHERE "商品ID" = %s
                    )
                    SELECT 
                        p."商品ID",
                        p."商品名稱",
                        p."群組名稱",
                        p."販賣單價",
                        COUNT(DISTINCT s."傳票編號") AS "同時購買訂單數",
                        SUM(s."數量") AS "累計加購總數量"
                    FROM "販賣資料" AS s
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    WHERE s."顧客ID" IN (SELECT "顧客ID" FROM TargetBuyers)
                      AND s."商品ID" <> %s
                    GROUP BY p."商品ID", p."商品名稱", p."群組名稱", p."販賣單價"
                    ORDER BY "同時購買訂單數" DESC, "累計加購總數量" DESC
                    LIMIT 10;
                """
                cur.execute(query, (target_product_id, target_product_id))
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"交叉銷售分析失敗：{str(e)}"}), 500

# --- 🚀 修正版：產品線營運狀況分析 API ---
@app.route('/api/product-line-analysis')
def get_product_line_analysis():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT 
                        p."群組名稱",
                        SUM(s."數量") AS "總銷售數量",
                        SUM(p."販賣單價" * s."數量") AS "總營業額",
                        SUM((p."販賣單價" - p."進貨單價") * s."數量") AS "總利潤總計"
                    FROM "販賣資料" AS s
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    GROUP BY p."群組名稱"
                    ORDER BY "總營業額" DESC;
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"產品線分析失敗：{str(e)}"}), 500

# --- 🚀 修正版：CRM 客戶價值標籤與沉睡預警 API ---
@app.route('/api/crm-analysis')
def get_crm_analysis():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT 
                        c."顧客名稱",
                        c."聯絡電話",
                        COUNT(DISTINCT s."傳票編號") AS "總消費次數",
                        SUM(s."數量") AS "購買總數量",
                        SUM(p."販賣單價" * s."數量") AS "總消費金額",
                        MAX(s."處理日") AS "最後消費日期"
                    FROM "顧客清單" AS c
                    LEFT JOIN "販賣資料" AS s ON c."顧客ID" = s."顧客ID"
                    LEFT JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    GROUP BY c."顧客ID", c."顧客名稱", c."聯絡電話"
                    ORDER BY "總消費金額" DESC NULLS LAST;
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"CRM數據分析失敗：{str(e)}"}), 500

@app.route('/api/dashboard')
def get_dashboard():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT COUNT(DISTINCT "傳票編號") AS orders, SUM("數量") AS qty FROM "販賣資料";')
                v1 = cur.fetchone()
                cur.execute('SELECT SUM(s."數量" * p."販賣單價") AS rev FROM "販賣資料" s JOIN "商品清單" p ON s."商品ID" = p."商品ID";')
                v2 = cur.fetchone()
                cur.execute('SELECT COUNT(*) AS cust FROM "顧客清單";')
                v3 = cur.fetchone()
                
                cur.execute('SELECT p."群組名稱" AS label, SUM(s."數量" * p."販賣單價") AS value FROM "販賣資料" s JOIN "商品清單" p ON s."商品ID" = p."商品ID" GROUP BY p."群組名稱" ORDER BY value DESC LIMIT 5;')
                top_p = cur.fetchall()
                
                cur.execute('SELECT s."處理日" AS date, SUM(s."數量" * p."販賣單價") AS value FROM "販賣資料" s JOIN "商品清單" p ON s."商品ID" = p."商品ID" GROUP BY s."處理日" ORDER BY s."處理日" ASC LIMIT 15;')
                trend = cur.fetchall()

        return jsonify({
            "total_orders": v1['orders'] if v1 else 0,
            "total_qty": v1['qty'] if v1 else 0,
            "total_revenue": v2['rev'] if v2 else 0,
            "total_customers": v3['cust'] if v3 else 0,
            "top_products": top_p,
            "sales_trend": trend
        })
    except Exception as e:
        return jsonify({"error": f"儀表板失敗：{str(e)}"}), 500

@app.route('/api/sales')
def get_sales():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT s."傳票編號", s."列編號", s."處理日", p."商品名稱", p."販賣單價", s."數量", (p."販賣單價" * s."數量") AS "流水小計", e.\"負責人姓名\", c.\"顧客名稱\" 
                    FROM "販賣資料" AS s 
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID" 
                    INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID" 
                    INNER JOIN "顧客清單" AS c ON s."顧客ID" = c."顧客ID" 
                    ORDER BY s."傳票編號" ASC, s."列編號" ASC;
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"銷售流水帳失敗：{str(e)}"}), 500

@app.route('/api/products')
def get_products():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT "商品ID" AS "商品id", "商品名稱", "群組名稱", "進貨單價", "販賣單價" FROM "商品清單" ORDER BY "商品ID";')
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"商品資料失敗：{str(e)}"}), 500

@app.route('/api/customers')
def get_customers():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT "顧客ID" AS "顧客id", "顧客名稱", "群組名稱", "聯絡電話", "地址" FROM "顧客清單" ORDER BY "顧客ID";')
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"顧客資料失敗：{str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)