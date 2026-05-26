import os
from flask import Flask, jsonify, render_template_string
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# 從環境變數讀取 Neon PostgreSQL 連線字串
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """建立 Neon 資料庫連線"""
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# --- 前端 HTML 範本 (內嵌在單一檔案中，優化防錯與 UI 顯示) ---
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
        .sidebar a { color: rgba(255,255,255,0.75); text-decoration: none; display: block; padding: 15px; transition: 0.2s; }
        .sidebar a:hover { background: #343a40; color: white; padding-left: 20px; }
        .sidebar a.active { background: #0d6efd; color: white; font-weight: bold; }
        .card { border: none; box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,0.075); border-radius: 10px; }
        .table th { font-weight: 600; background-color: #343a40 !important; color: white !important; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-2 sidebar p-0 shadow">
                <div class="p-3 text-center border-bottom border-secondary">
                    <h4 class="m-0">🏪 3C 零售系統</h4>
                </div>
                <div class="mt-3">
                    <a href="#sales" id="menu-sales" onclick="loadData('sales')">📊 銷售流水帳</a>
                    <a href="#products" id="menu-products" onclick="loadData('products')">💻 商品母體資料</a>
                    <a href="#customers" id="menu-customers" onclick="loadData('customers')">👥 顧客客戶清單</a>
                </div>
            </div>
            
            <div class="col-md-10 p-4">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2 id="page-title" class="m-0">📊 銷售流水帳 (關聯查詢)</h2>
                    <span class="badge bg-success p-2">Neon 雲端連線正常</span>
                </div>
                <div class="card p-4 bg-white">
                    <div class="table-responsive">
                        <table class="table table-striped table-hover align-middle m-0" id="data-table">
                            <thead id="table-head">
                                </thead>
                            <tbody id="table-body">
                                <tr><td class="text-center" colspan="10">系統初始化中...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // 網頁載入完成後，自動讀取第一頁「銷售流水帳」
        document.addEventListener("DOMContentLoaded", function() {
            loadData('sales');
        });

        function loadData(type) {
            const body = document.getElementById('table-body');
            const head = document.getElementById('table-head');
            const title = document.getElementById('page-title');
            
            // 切換側邊欄高亮狀態
            document.querySelectorAll('.sidebar a').forEach(a => a.classList.remove('active'));
            document.getElementById(`menu-${type}`).classList.add('active');
            
            // 顯示載入中
            body.innerHTML = '<tr><td class="text-center py-4" colspan="10"><div class="spinner-border spinner-border-sm text-primary me-2"></div>讀取資料中，請稍候...</td></tr>';

            fetch(`/api/${type}`)
                .then(res => res.json())
                .then(data => {
                    // 🛡️ 安全攔截：檢查後端是否報錯或資料為空
                    if (!data || data.error || data.length === 0) {
                        head.innerHTML = '';
                        body.innerHTML = `<tr><td class="text-center py-4 text-muted" colspan="10">⚠️ ${data.error || '目前資料庫內無任何資料'}</td></tr>`;
                        return;
                    }

                    // 1. 動態建立表頭 (讀取 JSON 物件的第一筆資料的所有鍵值)
                    let headHtml = '<tr>';
                    const keys = Object.keys(data[0]);
                    keys.forEach(key => headHtml += `<th class="p-3">${key}</th>`);
                    headHtml += '</tr>';
                    head.innerHTML = headHtml;

                    // 2. 動態建立表身資料
                    let bodyHtml = '';
                    data.forEach(row => {
                        bodyHtml += '<tr>';
                        keys.forEach(key => {
                            let value = row[key];
                            // 格式化數值或日期（如果是數字則加上千分位，如果是空值則顯示橫線）
                            if (typeof value === 'number' && key.includes('單價') || key.includes('金額')) {
                                value = '$' + value.toLocaleString();
                            } else if (value === null || value === undefined) {
                                value = '-';
                            }
                            bodyHtml += `<td class="p-3">${value}</td>`;
                        });
                        bodyHtml += '</tr>';
                    });
                    body.innerHTML = bodyHtml;

                    // 3. 根據點擊切換網頁大標題
                    if (type === 'sales') title.innerText = '📊 銷售流水帳 (關聯查詢)';
                    if (type === 'products') title.innerText = '💻 商品母體資料';
                    if (type === 'customers') title.innerText = '👥 顧客客戶清單';
                })
                .catch(err => {
                    head.innerHTML = '';
                    body.innerHTML = `<tr><td class="text-center py-4 text-danger" colspan="10">❌ 遠端連線異常: ${err}</td></tr>`;
                });
        }
    </script>
</body>
</html>
"""

# --- 路由與 API 設定 (完全對齊 Neon 雙引號 Schema) ---

@app.route('/')
def index():
    """首頁：直接渲染前端 HTML 儀表板"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/sales')
def get_sales():
    """API: 取得銷售流水帳 (自動關聯商品、負責員工與顧客名稱)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # 精確對齊資料庫中帶有雙引號的中文欄位名稱
        query = """
            SELECT 
                s."傳票編號", s."分錄編號", s."處理日期",
                p."商品名稱", p."銷售單價", s."數量",
                (p."銷售單價" * s."數量") AS "總金額",
                e."負責人姓名" AS "經辦員工",
                c."顧客名稱" AS "客戶名稱"
            FROM "銷售資料" s
            LEFT JOIN "商品清單" p ON s."商品ID" = p."商品ID"
            LEFT JOIN "負責人清單" e ON s."負責人ID" = e."負責人ID"
            LEFT JOIN "顧客清單" c ON s."顧客ID" = c."顧客ID"
            ORDER BY s."處理日期" DESC, s."傳票編號" ASC;
        """
        cur.execute(query)
        results = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"資料庫查詢失敗，錯誤訊息：{str(e)}"}), 500

@app.route('/api/products')
def get_products():
    """API: 取得所有商品母體資料"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT "商品ID", "商品名稱", "群組名稱", "進貨單價", "銷售單價" FROM "商品清單" ORDER BY "商品ID";')
        results = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"商品資料讀取失敗：{str(e)}"}), 500

@app.route('/api/customers')
def get_customers():
    """API: 取得所有顧客客戶清單"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SELECT "顧客ID", "顧客名稱", "連絡電話" FROM "顧客清單" ORDER BY "顧客ID";')
        results = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"顧客資料讀取失敗：{str(e)}"}), 500

if __name__ == '__main__':
    # 本地測試環境執行 (Port 5000)
    app.run(debug=True)