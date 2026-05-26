import os
from flask import Flask, jsonify, render_template_string
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# 從環境變數讀取 Neon PostgreSQL 連線字串 (部署在 Vercel 時在後台設定)
# 本地測試時可以直接貼上字串，例如: "postgresql://user:password@ep-xxx.neon.tech/neondb?sslmode=require"
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """建立 Neon 資料庫連線"""
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# --- 前端 HTML 範本 (內嵌在單一檔案中) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3C 進銷存管理系統</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .sidebar { background: #212529; color: white; min-height: 100vh; }
        .sidebar a { color: #rgba(255,255,255,0.75); text-decoration: none; display: block; padding: 15px; }
        .sidebar a:hover { background: #343a40; color: white; }
        .card { border: none; box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,0.075); }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-2 sidebar p-0">
                <div class="p-3 text-center border-bottom border-secondary">
                    <h4>🏪 零售系統</h4>
                </div>
                <a href="#sales" onclick="loadData('sales')">📊 銷售流水帳</a>
                <a href="#products" onclick="loadData('products')">💻 商品母體資料</a>
                <a href="#customers" onclick="loadData('customers')">👥 顧客清單</a>
            </div>
            
            <div class="col-md-10 p-4">
                <h2 id="page-title" class="mb-4">銷售流水帳資料</h2>
                <div class="card p-3">
                    <div class="table-responsive">
                        <table class="table table-hover align-middle" id="data-table">
                            <thead class="table-dark" id="table-head">
                                </thead>
                            <tbody id="table-body">
                                <tr><td class="text-center" colspan="10">資料載入中...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // 頁面載入時預設讀取銷售資料
        window.onload = function() { loadData('sales'); };

        function loadData(type) {
            const body = document.getElementById('table-body');
            const head = document.getElementById('table-head');
            const title = document.getElementById('page-title');
            
            body.innerHTML = '<tr><td class="text-center" colspan="10">資料載入中...</td></tr>';

            fetch(`/api/${type}`)
                .then(res => res.json())
                .then(data => {
                    if (data.length === 0) {
                        body.innerHTML = '<tr><td class="text-center" colspan="10">目前無任何資料</td></tr>';
                        return;
                    }

                    // 動態建立表頭與表身
                    let headHtml = '<tr>';
                    const keys = Object.keys(data[0]);
                    keys.forEach(key => headHtml += `<th>${key}</th>`);
                    headHtml += '</tr>';
                    head.innerHTML = headHtml;

                    let bodyHtml = '';
                    data.forEach(row => {
                        bodyHtml += '<tr>';
                        keys.forEach(key => {
                            bodyHtml += `<td>${row[key] || ''}</td>`;
                        });
                        bodyHtml += '</tr>';
                    });
                    body.innerHTML = bodyHtml;

                    // 更新標題
                    if(type === 'sales') title.innerText = '📊 銷售流水帳 (關聯查詢)';
                    if(type === 'products') title.innerText = '💻 商品母體資料';
                    if(type === 'customers') title.innerText = '👥 顧客客戶清單';
                })
                .catch(err => {
                    body.innerHTML = `<tr><td class="text-center text-danger" colspan="10">資料讀取失敗: ${err}</td></tr>`;
                });
        }
    </script>
</body>
</html>
"""

# --- 路由設定 ---

@app.route('/')
def index():
    """首頁：直接渲染前端 HTML"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/sales')
def get_sales():
    """API: 取得銷售資料 (自動關聯商品、員工與顧客名稱)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # 使用 JOIN 把 ID 轉化為易讀的名稱
        query = """
            SELECT 
                s.傳票編號, s.分錄編號, s.處理日期,
                p.商品名稱, p.銷售單價, s.數量,
                (p.銷售單價 * s.數量) AS 總金額,
                e.負責人姓名 AS 經辦員工,
                c.顧客名稱 AS 客戶名稱
            FROM 銷售資料 s
            LEFT JOIN 商品清單 p ON s.商品ID = p.商品ID
            LEFT JOIN 負責人清單 e ON s.負責人ID = e.負責人ID
            LEFT JOIN 顧客清單 c ON s.顧客ID = c.顧客ID
            ORDER BY s.處理日期 DESC;
        """
        cur.execute(query)
        results = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/products')
def get_products():
    """API: 取得所有商品"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT 商品ID, 商品名稱, 群組名稱, 進貨單價, 銷售單價 FROM 商品清單 ORDER BY 商品ID;")
        results = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/customers')
def get_customers():
    """API: 取得所有顧客"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT 顧客ID, 顧客名稱, 連絡電話 FROM 顧客清單 ORDER BY 顧客ID;")
        results = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # 本地測試執行
    app.run(debug=True)