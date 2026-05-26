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

# --- 前端 HTML 範本 (內嵌在單一檔案中，新增顧客統計頁面與下拉選單篩選) ---
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
        .filter-container { display: none; background: #e9ecef; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
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
                    <a href="#customer-stats" id="menu-customer-stats" onclick="loadData('customer-stats')">📈 顧客消費統計</a>
                    <a href="#products" id="menu-products" onclick="loadData('products')">💻 商品母體資料</a>
                    <a href="#customers" id="menu-customers" onclick="loadData('customers')">👥 顧客客戶清單</a>
                </div>
            </div>
            
            <div class="col-md-10 p-4">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2 id="page-title" class="m-0">📊 銷售流水帳 (關聯查詢)</h2>
                    <span class="badge bg-success p-2">Neon 雲端連線正常</span>
                </div>

                <div id="filter-block" class="filter-container align-items-center gap-3">
                    <label for="customer-select" class="form-label m-0 fw-bold text-secondary">🔍 篩選特定顧客：</label>
                    <select id="customer-select" class="form-select" style="max-width: 300px;" onchange="filterCustomerStats()">
                        <option value="ALL">-- 顯示所有顧客 --</option>
                    </select>
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
        // 全域變數，用來儲存統計資料以便前端抽樣篩選
        let cachedStatsData = [];

        // 網頁載入完成後，自動讀取第一頁「銷售流水帳」
        document.addEventListener("DOMContentLoaded", function() {
            loadData('sales');
        });

        function loadData(type) {
            const body = document.getElementById('table-body');
            const head = document.getElementById('table-head');
            const title = document.getElementById('page-title');
            const filterBlock = document.getElementById('filter-block');
            
            // 切換側邊欄高亮狀態
            document.querySelectorAll('.sidebar a').forEach(a => a.classList.remove('active'));
            document.getElementById(`menu-${type}`).classList.add('active');
            
            // 判斷是否顯示下拉選單控制列
            if (type === 'customer-stats') {
                filterBlock.style.display = 'flex';
                initCustomerDropdown(); // 初始化顧客下拉選單
            } else {
                filterBlock.style.display = 'none';
            }
            
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

                    // 如果是統計頁面，先緩存起來給下拉選單篩選用
                    if (type === 'customer-stats') {
                        cachedStatsData = data;
                    }

                    renderTable(data);

                    // 3. 根據點擊切換網頁大標題
                    if (type === 'sales') title.innerText = '📊 銷售流水帳 (關聯查詢)';
                    if (type === 'customer-stats') title.innerText = '📈 顧客消費統計分析';
                    if (type === 'products') title.innerText = '💻 商品母體資料';
                    if (type === 'customers') title.innerText = '👥 顧客客戶清單';
                })
                .catch(err => {
                    head.innerHTML = '';
                    body.innerHTML = `<tr><td class="text-center py-4 text-danger" colspan="10">❌ 遠端連線異常: ${err}</td></tr>`;
                });
        }

        // 渲染表格的共用邏輯
        function renderTable(data) {
            const head = document.getElementById('table-head');
            const body = document.getElementById('table-body');

            if (data.length === 0) {
                body.innerHTML = '<tr><td class="text-center py-4 text-muted" colspan="10">沒有符合篩選條件的資料</td></tr>';
                return;
            }

            // 1. 建立表頭
            let headHtml = '<tr>';
            const keys = Object.keys(data[0]);
            keys.forEach(key => headHtml += `<th class="p-3">${key}</th>`);
            headHtml += '</tr>';
            head.innerHTML = headHtml;

            // 2. 建立表身資料
            let bodyHtml = '';
            data.forEach(row => {
                bodyHtml += '<tr>';
                keys.forEach(key => {
                    let value = row[key];
                    // 格式化價格數值
                    if (typeof value === 'number' && (key.includes('單價') || key.includes('金額') || key.includes('平均'))) {
                        value = '$' + Math.round(value).toLocaleString(); // 四捨五入並加千分位
                    } else if (value === null || value === undefined) {
                        value = '-';
                    }
                    bodyHtml += `<td class="p-3">${value}</td>`;
                });
                bodyHtml += '</tr>';
            });
            body.innerHTML = bodyHtml;
        }

        // 初始化顧客下拉選單
        function initCustomerDropdown() {
            const select = document.getElementById('customer-select');
            // 如果已經加載過選單，就不重複撈取
            if (select.options.length > 1) return;

            fetch('/api/customers')
                .then(res => res.json())
                .then(customers => {
                    if (customers && !customers.error) {
                        customers.forEach(c => {
                            const opt = document.createElement('option');
                            opt.value = c['顧客ID'];
                            opt.innerHTML = `[ID: ${c['顧客ID']}] ${c['顧客名稱']}`;
                            select.appendChild(opt);
                        });
                    }
                });
        }

        // 下拉選單切換時的動態篩選
        function filterCustomerStats() {
            const selectedId = document.getElementById('customer-select').value;
            if (selectedId === 'ALL') {
                renderTable(cachedStatsData);
            } else {
                // 依據顧客ID進行前端動態過濾
                const filtered = cachedStatsData.filter(row => row['顧客ID'].toString() === selectedId);
                renderTable(filtered);
            }
        }
    </script>
</body>
</html>
"""

# --- 路由與 API 設定 ---

@app.route('/')
def index():
    """首頁：直接渲染前端 HTML 儀表板"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/customer-stats')
def get_customer_stats():
    """
    API: 核心分析功能
    以「銷售資料」為核心，串聯商品與顧客資訊，依「顧客ID」分組，
    統計出每位顧客購買商品的特定名稱（文字排序最大值 MAX）以及平均購買單價（AVG）
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 📊 關鍵 SQL：聚合函數搭配 GROUP BY
        query = """
            SELECT 
                s."顧客ID",
                c."顧客名稱",
                MAX(p."商品名稱") AS "購買特定商品(文字最大值)",
                AVG(p."銷售單價") AS "平均購買單價",
                SUM(s."數量") AS "累積購買總數量"
            FROM "銷售資料" s
            LEFT JOIN "顧客清單" c ON s."顧客ID" = c."顧客ID"
            LEFT JOIN "商品清單" p ON s."商品ID" = p."商品ID"
            GROUP BY s."顧客ID", c."顧客名稱"
            ORDER BY s."顧客ID" ASC;
        """
        cur.execute(query)
        results = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"統計資料分析失敗，錯誤訊息：{str(e)}"}), 500

@app.route('/api/sales')
def get_sales():
    """API: 取得銷售流水帳"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
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
    # 本地測試環境執行
    app.run(debug=True)