import os
from flask import Flask, jsonify, render_template, request
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# 確保 Vercel Serverless 能正確識別 WSGI 入口點
app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')

# 從環境變數讀取 Neon PostgreSQL 連線字串
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """建立 Neon 資料庫連線"""
    if not DATABASE_URL:
        raise ValueError("環境變數 DATABASE_URL 未設定，請檢查 Vercel 後台設定！")
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# --- 核心路由：首頁渲染 ---
@app.route('/')
def index():
    return render_template('index.html')

# --- 🚀 熱門組合商品交叉銷售分析 API ---
@app.route('/api/cross-selling-analysis')
def get_cross_selling_analysis():
    target_product_id = request.args.get('target_product_id')
    if not target_product_id:
        return jsonify({"error": "請提供基準商品 ID (?target_product_id=X)"}), 400
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    WITH TargetCustomers AS (
                        SELECT DISTINCT "顧客ID" FROM "販賣資料" WHERE "商品ID" = %s
                    )
                    SELECT 
                        p."商品名稱", p."群組名稱",
                        COUNT(DISTINCT s."顧客ID") AS "購買客戶數",
                        SUM(s."數量") AS "累積購買總數量",
                        SUM(p."販賣單價" * s."數量") AS "交叉貢獻總金額"
                    FROM "販賣資料" AS s
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    WHERE s."顧客ID" IN (SELECT "顧客ID" FROM TargetCustomers)
                      AND s."商品ID" <> %s
                    GROUP BY p."商品ID", p."商品名稱", p."群組名稱"
                    ORDER BY "購買客戶數" DESC, "交叉貢獻總金額" DESC
                    LIMIT 10;
                """
                cur.execute(query, (target_product_id, target_product_id))
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"交叉銷售演算法執行失敗：{str(e)}"}), 500

# --- 📦 特定產品線/群組銷貨營運分析 ---
@app.route('/api/sales-by-group')
def get_sales_by_group():
    group_name = request.args.get('group_name')
    if not group_name:
        return jsonify({"error": "請提供商品群組名稱"}), 400
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if group_name == 'ALL':
                    query = """
                        SELECT s."傳票編號", s."處理日" AS "處理日期", p."群組名稱", p."商品名稱", p."販賣單價", 
                               s."數量" AS "購買數量", (p."販賣單價" * s."數量") AS "銷售小計金額", 
                               c."顧客名稱", e."負責人姓名" AS "經手業務"
                        FROM "販賣資料" s
                        JOIN "商品清單" p ON s."商品ID" = p."商品ID"
                        JOIN "顧客清單" c ON s."顧客ID" = c."顧客ID"
                        JOIN "負責人清單" e ON s."負責人ID" = e."負責人ID"
                        ORDER BY s."數量" DESC, s."處理日" DESC;
                    """
                    cur.execute(query)
                else:
                    query = """
                        SELECT s."傳票編號", s."處理日" AS "處理日期", p."群組名稱", p."商品名稱", p."販賣單價", 
                               s."數量" AS "購買數量", (p."販賣單價" * s."數量") AS "銷售小計金額", 
                               c."顧客名稱", e."負責人姓名" AS "經手業務"
                        FROM "販賣資料" s
                        JOIN "商品清單" p ON s."商品ID" = p."商品ID"
                        JOIN "顧客清單" c ON s."顧客ID" = c."顧客ID"
                        JOIN "負責人清單" e ON s."負責人ID" = e."負責人ID"
                        WHERE p."群組名稱" = %s
                        ORDER BY s."數量" DESC, s."處理日" DESC;
                    """
                    cur.execute(query, (group_name,))
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"讀取產品線資料失敗：{str(e)}"}), 500

# --- 🎖️ 業務考核模組 API 1：特定業務的經手業績明細與 KPI 總計 ---
@app.route('/api/sales-detail-by-staff')
def get_sales_detail_by_staff():
    staff_name = request.args.get('staff_name')
    if not staff_name:
        return jsonify({"error": "請提供業務員姓名"}), 400
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT s."傳票編號", s."處理日" AS "交易日期", p."商品名稱", p."販賣單價", s."數量",
                           (p."販賣單價" * s."數量") AS "銷售小計",
                           ((p."販賣單價" - p."進貨單價") * s."數量") AS "創造毛利小計",
                           c."顧客名稱"
                    FROM "販賣資料" s
                    JOIN "商品清單" p ON s."商品ID" = p."商品ID"
                    JOIN "顧客清單" c ON s."顧客ID" = c."顧客ID"
                    JOIN "負責人清單" e ON s."負責人ID" = e."負責人ID"
                    WHERE e."負責人姓名" = %s
                    ORDER BY s."處理日" DESC;
                """
                cur.execute(query, (staff_name,))
                sales_detail = cur.fetchall()
                
                total_sales = sum(float(row['銷售小計']) for row in sales_detail)
                total_profit = sum(float(row['創造毛利小計']) for row in sales_detail)
                
        return jsonify({
            "summary": {"total_sales": total_sales, "total_profit": total_profit},
            "sales_detail": sales_detail
        })
    except Exception as e:
        return jsonify({"error": f"讀取業務考核失敗：{str(e)}"}), 500

# --- 🎖️ 業務考核模組 API 2：特定業務的客戶採購偏好與預算地圖 ---
@app.route('/api/customer-preference-by-staff')
def get_customer_preference_by_staff():
    staff_name = request.args.get('staff_name')
    if not staff_name:
        return jsonify({"error": "請提供業務員姓名"}), 400
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT c."顧客名稱", p."群組名稱", SUM(s."數量") AS "累積購買數量",
                           SUM(p."販賣單價" * s."數量") AS "貢獻預算總額"
                    FROM "販賣資料" s
                    JOIN "商品清單" p ON s."商品ID" = p."商品ID"
                    JOIN "顧客清單" c ON s."顧客ID" = c."顧客ID"
                    JOIN "負責人清單" e ON s."負責人ID" = e."負責人ID"
                    WHERE e."負責人姓名" = %s
                    GROUP BY c."顧客名稱", p."群組名稱"
                    ORDER BY "貢獻預算總額" DESC;
                """
                cur.execute(query, (staff_name,))
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"讀取客戶預算地圖失敗：{str(e)}"}), 500

# --- 🎯 CRM 精準行銷模組 API ---
@app.route('/api/customer-footprint')
def get_customer_footprint():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT c."顧客ID" AS "顧客id", c."顧客名稱", c."聯絡電話",
                           s."傳票編號", s."處理日" AS "處理日期", s."數量" AS "購買數量"
                    FROM "顧客清單" c
                    LEFT JOIN "販賣資料" s ON c."顧客ID" = s."顧客ID"
                    ORDER BY c."顧客ID" ASC, s."處理日" DESC;
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"消費足跡失敗：{str(e)}"}), 500

@app.route('/api/sleeping-members')
def get_sleeping_members():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT c."顧客ID" AS "顧客id", c."顧客名稱", c."聯絡電話"
                    FROM "顧客清單" c
                    LEFT JOIN "販賣資料" s ON c."顧客ID" = s."顧客ID"
                    WHERE s."傳票編號" IS NULL
                    ORDER BY c."顧客ID";
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"沉睡會員失敗：{str(e)}"}), 500

@app.route('/api/dead-products')
def get_dead_products():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT p."商品ID" AS "商品id", p."商品名稱", p."群組名稱"
                    FROM "商品清單" p
                    LEFT JOIN "販賣資料" s ON p."商品ID" = s."商品ID"
                    WHERE s."傳票編號" IS NULL
                    ORDER BY p."商品ID";
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"滯銷商品失敗：{str(e)}"}), 500

# --- 🏆 業務英雄榜名次表 API ---
@app.route('/api/sales-ranking')
def get_sales_ranking():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT 
                        e."負責人姓名" AS "業務員",
                        COUNT(DISTINCT s."傳票編號") AS "經手訂單數",
                        SUM(p."販賣單價" * s."數量") AS "總銷售業績",
                        SUM((p."販賣單價" - p."進貨單價") * s."數量") AS "創造總毛利"
                    FROM "販賣資料" AS s
                    INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID"
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    GROUP BY e."負責人ID", e."負責人姓名"
                    ORDER BY "總銷售業績" DESC;
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"業務排行失敗：{str(e)}"}), 500

@app.route('/api/customer-ranking')
def get_customer_ranking():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT c."顧客名稱", SUM(p."販賣單價" * s."數量") AS "總金額"
                    FROM "販賣資料" AS s
                    INNER JOIN "顧客清單" AS c ON s."顧客ID" = c."顧客ID"
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    GROUP BY c."顧客ID", c."顧客名稱" ORDER BY "總金額" DESC LIMIT 5;
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"顧客排行失敗：{str(e)}"}), 500

@app.route('/api/sales-by-date')
def get_sales_by_date():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT s."處理日" AS "日期", SUM(p."販賣單價" * s."數量") AS "銷售額"
                    FROM "販賣資料" AS s
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    GROUP BY s."處理日" ORDER BY s."處理日" ASC;
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"日期銷售失敗：{str(e)}"}), 500

# --- 📊 儀表板綜合統計數據 API ---
@app.route('/api/dashboard-stats')
def get_dashboard_stats():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                kpi_query = """
                    SELECT 
                        COALESCE(SUM(p."販賣單價" * s."數量"), 0) AS total_sales, 
                        COALESCE(SUM((p."販賣單價" - p."進貨單價") * s."數量"), 0) AS total_profit,
                        CASE WHEN SUM(p."販賣單價" * s."數量") > 0 THEN ROUND((SUM((p."販賣單價" - p."進貨單價") * s."數量") * 100.0 / SUM(p."販賣單價" * s."數量")), 1) ELSE 0 END AS margin_rate,
                        COALESCE(SUM(s."數量"), 0) AS total_qty, 
                        COUNT(DISTINCT s."顧客ID") AS total_customers,
                        CASE WHEN COUNT(DISTINCT s."傳票編號") > 0 THEN COALESCE(SUM(p."販賣單價" * s."數量"), 0) / COUNT(DISTINCT s."傳票編號") ELSE 0 END AS avg_order_value
                    FROM "販賣資料" s LEFT JOIN "商品清單" p ON s."商品ID" = p."商品ID";
                """
                cur.execute(kpi_query)
                kpi_result = cur.fetchone()

                top_products_query = """
                    SELECT p."商品名稱", SUM(s."數量") AS "總銷售數量", 
                           SUM(p."販賣單價" * s."數量") AS "總銷售額", 
                           SUM((p."販賣單價" - p."進貨單價") * s."數量") AS "總創造毛利"
                    FROM "販賣資料" s
                    JOIN "商品清單" p ON s."商品ID" = p."商品ID"
                    GROUP BY p."商品ID", p."商品名稱"
                    ORDER BY "總創造毛利" DESC LIMIT 5;
                """
                cur.execute(top_products_query)
                top_products = cur.fetchall()

                top_customers_query = """
                    SELECT c."顧客名稱", SUM(p."販賣單價" * s."數量") AS "總金額"
                    FROM "販賣資料" s
                    JOIN "顧客清單" c ON s."顧客ID" = c."顧客ID"
                    JOIN "商品清單" p ON s."商品ID" = p."商品ID"
                    GROUP BY c."顧客ID", c."顧客名稱"
                    ORDER BY "總金額" DESC LIMIT 5;
                """
                cur.execute(top_customers_query)
                top_customers = cur.fetchall()

        return jsonify({
            "kpi": kpi_result,
            "top_products": top_products,
            "top_customers": top_customers
        })
    except Exception as e:
        return jsonify({"error": f"讀取儀表板綜合數據失敗：{str(e)}"}), 500

@app.route('/api/customer-stats')
def get_customer_stats():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT c."顧客名稱", COUNT(DISTINCT s."傳票編號") AS "購買次數", SUM(p."販賣單價" * s."數量") AS "總金額"
                    FROM "販賣資料" AS s
                    INNER JOIN "顧客清單" AS c ON s."顧客ID" = c."顧客ID"
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    GROUP BY c."顧客ID", c."顧客名稱" ORDER BY "總金額" DESC;
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"顧客數據失敗：{str(e)}"}), 500

# --- 💾 系統核心原始資料分頁檢視 API ---
@app.route('/api/sales')
def get_raw_sales():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT s."傳票編號", s."列編號", s."處理日", p."商品名稱", p."販賣單價", s."數量", 
                           (p."販賣單價" * s."數量") AS "流水小計", e."負責人姓名", c."顧客名稱" 
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
                cur.execute('SELECT \"商品ID\" AS \"商品id\", \"商品名稱\", \"群組名稱\", \"進貨單價\", \"販賣單價\" FROM \"商品清單\" ORDER BY \"商品ID\";')
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"商品資料失敗：{str(e)}"}), 500

@app.route('/api/customers')
def get_customers():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT \"顧客ID\" AS \"顧客id\", \"顧客名稱\", \"聯絡電話\" FROM \"顧客清單\" ORDER BY \"顧客ID\";')
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"客戶資料失敗：{str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)