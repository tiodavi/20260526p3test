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
    # Flask 會自動去與 app.py 同層的 templates/ 資料夾尋找 index.html
    return render_template('index.html')

# --- 🚀 修正版：熱門組合商品交叉銷售分析 API ---
@app.route('/api/cross-selling-analysis')
def get_cross_selling_analysis():
    """API: 輸入基準商品ID，找出買過該商品的客群，還買了哪些「其他商品」的排名累計"""
    target_product_id = request.args.get('target_product_id')
    if not target_product_id:
        return jsonify({"error": "缺少基準商品 ID"}), 400
        
    try:
        # 強制在 Python 端將傳入的參數轉為整數型態，避免與資料庫 INT 格式衝突
        target_id_int = int(target_product_id)
    except ValueError:
        return jsonify({"error": "商品 ID 格式必須為數字"}), 400
        
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT 
                        p."商品名稱",
                        p."群組名稱",
                        COUNT(DISTINCT s."顧客ID") AS "購買客戶數",
                        SUM(s."數量") AS "累積購買總數量",
                        SUM(s."數量" * p."販賣單價") AS "交叉貢獻總金額"
                    FROM "販賣資料" AS s
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    WHERE s."顧客ID" IN (
                        -- 子查詢：揪出買過基準商品的所有顧客
                        SELECT DISTINCT "顧客ID"
                        FROM "販賣資料"
                        WHERE "商品ID" = %s
                    )
                    AND s."商品ID" <> %s  -- 排除基準商品自身
                    GROUP BY p."商品ID", p."商品名稱", p."群組名稱"
                    ORDER BY "累積購買總數量" DESC, "交叉貢獻總金額" DESC;
                """
                cur.execute(query, (target_id_int, target_id_int))
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"交叉銷售分析失敗：{str(e)}"}), 500

# --- 🚀 升級版：特定商品群組/產品線營運表現分析 API ---
@app.route('/api/sales-by-group')
def get_sales_by_group():
    """API: 根據商品群組變數（如網路設備、手機），調閱其獨立流水帳，並聚焦大宗掃貨與營業表現"""
    group_name = request.args.get('group_name', '電腦主機')
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                base_query = """
                    SELECT 
                        s."傳票編號",
                        s."處理日" AS "處理日期",
                        p."群組名稱",
                        p."商品名稱",
                        p."販賣單價",
                        s."數量" AS "購買數量",
                        (p."販賣單價" * s."數量") AS "銷售小計金額",
                        c."顧客名稱",
                        e."負責人姓名" AS "經手業務"
                    FROM "販賣資料" AS s
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    INNER JOIN "顧客清單" AS c ON s."顧客ID" = c."顧客ID"
                    INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID"
                """
                
                if group_name == 'ALL':
                    query = base_query + ' ORDER BY s."數量" DESC, s."處理日" DESC;'
                    cur.execute(query)
                else:
                    query = base_query + ' WHERE p."群組名稱" = %s ORDER BY s."數量" DESC, s."處理日" DESC;'
                    cur.execute(query, (group_name,))
                    
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"商品群組/產品線銷貨表現分析失敗：{str(e)}"}), 500

# --- 🚀 既有業務績效考核模組後端 API 路由 ---
@app.route('/api/sales-detail-by-staff')
def get_sales_detail_by_staff():
    staff_name = request.args.get('staff_name')
    if not staff_name:
        return jsonify({"error": "缺少業務負責人姓名"}), 400
        
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query_detail = """
                    SELECT
                        s."傳票編號",
                        s."列編號",
                        s."處理日" AS "交易日期",
                        p."商品名稱",
                        p."販賣單價",
                        s."數量",
                        (p."販賣單價" * s."數量") AS "銷售小計",
                        ((p."販賣單價" - p."進貨單價") * s."數量") AS "創造毛利小計",
                        c."顧客名稱"
                    FROM "販賣資料" AS s
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID"
                    INNER JOIN "顧客清單" AS c ON s."顧客ID" = c."顧客ID"
                    WHERE e."負責人姓名" = %s
                    ORDER BY s."傳票編號" ASC, s."列編號" ASC;
                """
                cur.execute(query_detail, (staff_name,))
                sales_detail = cur.fetchall()
                
                query_summary = """
                    SELECT 
                        COALESCE(SUM(p."販賣單價" * s."數量"), 0) AS total_sales,
                        COALESCE(SUM((p."販賣單價" - p."進貨單價") * s."數量"), 0) AS total_profit
                    FROM "販賣資料" AS s
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID"
                    WHERE e."負責人姓名" = %s;
                """
                cur.execute(query_summary, (staff_name,))
                summary = cur.fetchone()
                
        return jsonify({"sales_detail": sales_detail, "summary": summary})
    except Exception as e:
        return jsonify({"error": f"業務績效明細抓取失敗：{str(e)}"}), 500

@app.route('/api/customer-preference-by-staff')
def get_customer_preference_by_staff():
    staff_name = request.args.get('staff_name')
    if not staff_name:
        return jsonify({"error": "缺少業務負責人姓名"}), 400
        
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT
                        c."顧客名稱",
                        p."群組名稱",
                        p."商品名稱",
                        SUM(s."數量") AS "累積購買數量",
                        SUM(p."販賣單價" * s."數量") AS "貢獻預算總額"
                    FROM "販賣資料" AS s
                    INNER JOIN "顧客清單" AS c ON s."顧客ID" = c."顧客ID"
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID"
                    WHERE e."負責人姓名" = %s
                    GROUP BY c."顧客ID", c."顧客名稱", p."商品ID", p."商品名稱", p."群組名稱"
                    ORDER BY c."顧客名稱" ASC, "累積購買數量" DESC;
                """
                cur.execute(query, (staff_name,))
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"客戶購買偏好追蹤失敗：{str(e)}"}), 500

# --- 🚀 既有 CRM 精準行銷模組後端 API 路由 ---
@app.route('/api/customer-footprint')
def get_customer_footprint():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT
                        c."顧客ID" AS "顧客id",
                        c."顧客名稱",
                        c."聯絡電話",
                        s."傳票編號",
                        s."處理日" AS "處理日期",
                        s."數量" AS "購買數量"
                    FROM "顧客清單" AS c
                    LEFT JOIN "販賣資料" AS s ON c."顧客ID" = s."顧客ID"
                    ORDER BY c."顧客ID" ASC, s."傳票編號" ASC;
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"客戶消費足跡數據抓取失敗：{str(e)}"}), 500

@app.route('/api/sleeping-members')
def get_sleeping_members():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT
                        c."顧客ID" AS "顧客id",
                        c."顧客名稱",
                        c."聯絡電話",
                        s."傳票編號"
                    FROM "顧客清單" AS c
                    LEFT JOIN "販賣資料" AS s ON c."顧客ID" = s."顧客ID"
                    WHERE s."傳票編號" IS NULL
                    ORDER BY c."顧客ID" ASC;
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"零消費沉睡會員名單抓取失敗：{str(e)}"}), 500

@app.route('/api/dead-products')
def get_dead_products():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT p."商品ID" AS "商品id", p."商品名稱", p."群組名稱"
                    FROM "商品清單" AS p LEFT JOIN "販賣資料" AS s ON p."商品ID" = s."商品ID"
                    WHERE s."傳票編號" IS NULL ORDER BY p."商品ID";
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"滯銷商品數據失敗：{str(e)}"}), 500

@app.route('/api/sales-ranking')
def get_sales_ranking():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT e."負責人姓名", COUNT(*) AS "訂單筆數", SUM(p."販賣單價" * s."數量") AS "銷售總額"
                    FROM "販賣資料" AS s
                    INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID"
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    GROUP BY e."負責人ID", e."負責人姓名" ORDER BY "銷售總額" DESC;
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
                    SELECT c."顧客名稱", COUNT(*) AS "訂單筆數", SUM(p."販賣單價" * s."數量") AS "總金額"
                    FROM "販賣資料" AS s
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    INNER JOIN "顧客清單" AS c ON s."顧客ID" = c."顧客ID"
                    GROUP BY c."顧客ID", c."顧客名稱" ORDER BY "總金額" DESC;
                """
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"顧客貢獻排行失敗：{str(e)}"}), 500

@app.route('/api/sales-by-date')
def get_sales_by_date():
    start_date = request.args.get('start', '2021-04-01')
    end_date = request.args.get('end', '2021-06-30')
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT s."傳票編號", s."處理日", p."商品名稱", e."負責人姓名", c."顧客名稱", s."數量"
                    FROM "販賣資料" AS s INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID" INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID" INNER JOIN "顧客清單" AS c ON s."顧客ID" = c."顧客ID"
                    WHERE s."處理日" BETWEEN %s AND %s ORDER BY s."處理日" ASC;
                """
                cur.execute(query, (start_date, end_date))
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"日期區間查詢失敗：{str(e)}"}), 500

@app.route('/api/dashboard-stats')
def get_dashboard_stats():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                kpi_query = """
                    SELECT 
                        COALESCE(SUM(p."販賣單價" * s."數量"), 0) AS total_sales, COALESCE(SUM((p."販賣單價" - p."進貨單價") * s."數量"), 0) AS total_profit,
                        CASE WHEN SUM(p."販賣單價" * s."數量") > 0 THEN ROUND((SUM((p."販賣單價" - p."進貨單價") * s."數量") * 100.0 / SUM(p."販賣單價" * s."數量")), 1) ELSE 0 END AS margin_rate,
                        COALESCE(SUM(s."數量"), 0) AS total_qty, COUNT(DISTINCT s."顧客ID") AS total_customers,
                        CASE WHEN COUNT(DISTINCT s."傳票編號") > 0 THEN COALESCE(SUM(p."販賣單價" * s."數量"), 0) / COUNT(DISTINCT s."傳票編號") ELSE 0 END AS avg_order_value
                    FROM "販賣資料" s LEFT JOIN "商品清單" p ON s."商品ID" = p."商品ID";
                """
                cur.execute(kpi_query)
                kpi_result = cur.fetchone()

                top_products_query = 'SELECT p."商品名稱", SUM(s."數量") AS "總銷售數量", SUM(p."販賣單價" * s."數量") AS "總銷售額", SUM((p."販賣單價" - p."進貨單價") * s."數量") AS "總創造毛利", ROUND((SUM((p."販賣單價" - p."進貨單價") * s."數量") * 100.0 / NULLIF(SUM(p."販賣單價" * s."數量"), 0)), 1) AS "單品毛利率" FROM "販賣資料" s LEFT JOIN "商品清單" p ON s."商品ID" = p."商品ID" GROUP BY p."商品名稱" ORDER BY "總創造毛利" DESC LIMIT 5;'
                cur.execute(top_products_query)
                top_products = cur.fetchall()

                top_customers_query = 'SELECT c."顧客名稱", SUM(p."販賣單價" * s."數量") AS "總金額" FROM "販賣資料" s INNER JOIN "商品清單" p ON s."商品ID" = p."商品ID" INNER JOIN "顧客清單" c ON s."顧客ID" = c."顧客ID" GROUP BY c."顧客ID", c."顧客名稱" ORDER BY "總金額" DESC LIMIT 5;'
                cur.execute(top_customers_query)
                top_customers = cur.fetchall()

                top_sales_query = 'SELECT e."負責人姓名", SUM(p."販賣單價" * s."數量") AS "銷售總額" FROM "販賣資料" s INNER JOIN "負責人清單" e ON s."負責人ID" = e."負責人ID" INNER JOIN "商品清單" p ON s."商品ID" = p."商品ID" GROUP BY e."負責人ID", e."負責人姓名" ORDER BY "銷售總額" DESC LIMIT 5;'
                cur.execute(top_sales_query)
                top_sales = cur.fetchall()
        return jsonify({"kpi": kpi_result, "top_products": top_products, "top_customers": top_customers, "top_sales": top_sales})
    except Exception as e:
        return jsonify({"error": f"儀表板失敗：{str(e)}"}), 500

@app.route('/api/customer-stats')
def get_customer_stats():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = 'SELECT s."顧客ID" AS "顧客id", c."顧客名稱", MAX(p."商品名稱") AS "購買特定商品(文字最大值)", ROUND(AVG(p."販賣單價"), 0) AS "平均購買單價", SUM(s."數量") AS "累積購買總數量" FROM "販賣資料" s LEFT JOIN "顧客清單" c ON s."顧客ID" = c."顧客ID" LEFT JOIN "商品清單" p ON s."商品ID" = p."商品ID" GROUP BY s."顧客ID", c."顧客名稱" ORDER BY s."顧客ID" ASC;'
                cur.execute(query)
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"顧客消費統計失敗：{str(e)}"}), 500

@app.route('/api/sales')
def get_sales():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = 'SELECT s."傳票編號", s."列編號", s."處理日", p."商品名稱", p."販賣單價", s."數量", (p."販賣單價" * s."數量") AS "流水小計", e."負責人姓名", c."顧客名稱" FROM "販賣資料" AS s INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID" INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID" INNER JOIN "顧客清單" AS c ON s."顧客ID" = c."顧客ID" ORDER BY s."傳票編號" ASC, s."列編號" ASC;'
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
                cur.execute('SELECT "顧客ID" AS "顧客id", "顧客名稱", "聯絡電話" FROM "顧客清單" ORDER BY "顧客ID";')
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"顧客資料失敗：{str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)