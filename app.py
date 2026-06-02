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
        .sidebar a { color: rgba(255,255,255,0.75); text-decoration: none; display: block; padding: 15px; transition: 0.2s; }
        .sidebar a:hover { background: #343a40; color: white; padding-left: 20px; }
        .sidebar a.active { background: #0d6efd; color: white; font-weight: bold; }
        .card { border: none; box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,0.075); border-radius: 10px; }
        .table th { font-weight: 600; background-color: #343a40 !important; color: white !important; }
        .filter-container { display: none; background: #e9ecef; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .kpi-card { border-left: 5px solid #0d6efd; }
        .kpi-title { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: bold; color: #6c757d; }
        .kpi-value { font-size: 1.6rem; font-weight: 700; color: #343a40; }
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
                    <a href="#dashboard" id="menu-dashboard" onclick="loadData('dashboard')">🏠 營運儀表板</a>
                    <a href="#sales" id="menu-sales" onclick="loadData('sales')">📊 銷售流水帳</a>
                    <a href="#customer-stats" id="menu-customer-stats" onclick="loadData('customer-stats')">📈 顧客消費統計</a>
                    <a href="#products" id="menu-products" onclick="loadData('products')">💻 商品母體資料</a>
                    <a href="#customers" id="menu-customers" onclick="loadData('customers')">👥 顧客客戶清單</a>
                </div>
            </div>
            
            <div class="col-md-10 p-4">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2 id="page-title" class="m-0">🏠 營運儀表板</h2>
                    <span class="badge bg-success p-2">Neon 雲端連線正常</span>
                </div>

                <div id="dashboard-cards" class="row g-3 mb-4">
                    <div class="col-md-2">
                        <div class="card p-3 bg-white h-100 kpi-card" style="border-left-color: #0d6efd;">
                            <div class="kpi-title">💰 累積銷售額</div>
                            <div class="kpi-value" id="kpi-total-sales">$0</div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card p-3 bg-white h-100 kpi-card" style="border-left-color: #6f42c1;">
                            <div class="kpi-title">💵 預估總毛利</div>
                            <div class="kpi-value" id="kpi-total-profit">$0</div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card p-3 bg-white h-100 kpi-card" style="border-left-color: #fd7e14;">
                            <div class="kpi-title">📊 平均毛利率</div>
                            <div class="kpi-value" id="kpi-margin-rate">0%</div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card p-3 bg-white h-100 kpi-card" style="border-left-color: #198754;">
                            <div class="kpi-title">📦 總銷售商品</div>
                            <div class="kpi-value" id="kpi-total-qty">0 件</div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card p-3 bg-white h-100 kpi-card" style="border-left-color: #ffc107;">
                            <div class="kpi-title">🤝 平均客單價</div>
                            <div class="kpi-value" id="kpi-avg-order">$0</div>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <div class="card p-3 bg-white h-100 kpi-card" style="border-left-color: #dc3545;">
                            <div class="kpi-title">👥 活躍客戶數</div>
                            <div class="kpi-value" id="kpi-total-customers">0 人</div>
                        </div>
                    </div>
                </div>

                <div id="filter-block" class="filter-container align-items-center gap-3">
                    <label for="customer-select" class="form-label m-0 fw-bold text-secondary">🔍 篩選特定顧客：</label>
                    <select id="customer-select" class="form-select" style="max-width: 300px;" onchange="filterCustomerStats()">
                        <option value="ALL">-- 顯示所有顧客 --</option>
                    </select>
                </div>

                <div class="card p-4 bg-white">
                    <h5 id="table-title" class="mb-3 text-secondary" style="display:none;">🔥 Top 5 高毛利商品排行</h5>
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
        let cachedStatsData = [];

        document.addEventListener("DOMContentLoaded", function() {
            // 系統預設首頁直接載入儀表板
            loadData('dashboard');
        });

        function loadData(type) {
            const body = document.getElementById('table-body');
            const head = document.getElementById('table-head');
            const title = document.getElementById('page-title');
            const tableTitle = document.getElementById('table-title');
            const filterBlock = document.getElementById('filter-block');
            const dashboardCards = document.getElementById('dashboard-cards');
            
            document.querySelectorAll('.sidebar a').forEach(a => a.classList.remove('active'));
            document.getElementById(`menu-${type}`).classList.add('active');
            
            if (type === 'customer-stats') {
                filterBlock.style.display = 'flex';
                initCustomerDropdown();
            } else {
                filterBlock.style.display = 'none';
            }

            if (type === 'dashboard') {
                dashboardCards.style.display = 'flex';
                tableTitle.style.display = 'block';
                title.innerText = '🏠 營運儀表板';
            } else {
                dashboardCards.style.display = 'none';
                tableTitle.style.display = 'none';
            }
            
            body.innerHTML = '<tr><td class="text-center py-4" colspan="10"><div class="spinner-border spinner-border-sm text-primary me-2"></div>讀取資料中，請稍候...</td></tr>';

            if (type === 'dashboard') {
                fetch('/api/dashboard-stats')
                    .then(res => res.json())
                    .then(data => {
                        if (data.error) {
                            body.innerHTML = `<tr><td class="text-center py-4 text-danger" colspan="10">❌ 數據載入失敗: ${data.error}</td></tr>`;
                            return;
                        }
                        // 渲染六大 KPI 卡片
                        document.getElementById('kpi-total-sales').innerText = '$' + Math.round(data.kpi.total_sales).toLocaleString();
                        document.getElementById('kpi-total-profit').innerText = '$' + Math.round(data.kpi.total_profit).toLocaleString();
                        document.getElementById('kpi-margin-rate').innerText = data.kpi.margin_rate + '%';
                        document.getElementById('kpi-total-qty').innerText = Math.round(data.kpi.total_qty).toLocaleString() + ' 件';
                        document.getElementById('kpi-avg-order').innerText = '$' + Math.round(data.kpi.avg_order_value).toLocaleString();
                        document.getElementById('kpi-total-customers').innerText = data.kpi.total_customers + ' 人';
                        
                        // 下方表格渲染高毛利排行
                        renderTable(data.top_products);
                    })
                    .catch(err => {
                        body.innerHTML = `<tr><td class="text-center py-4 text-danger" colspan="10">❌ 遠端連線異常: ${err}</td></tr>`;
                    });
                return;
            }

            fetch(`/api/${type}`)
                .then(res => res.json())
                .then(data => {
                    if (!data || data.error || data.length === 0) {
                        head.innerHTML = '';
                        body.innerHTML = `<tr><td class="text-center py-4 text-muted" colspan="10">⚠️ ${data.error || '目前資料庫內無任何資料'}</td></tr>`;
                        return;
                    }

                    if (type === 'customer-stats') {
                        cachedStatsData = data;
                    }

                    renderTable(data);

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

        function renderTable(data) {
            const head = document.getElementById('table-head');
            const body = document.getElementById('table-body');

            if (data.length === 0) {
                body.innerHTML = '<tr><td class="text-center py-4 text-muted" colspan="10">沒有符合篩選條件的資料</td></tr>';
                return;
            }

            let headHtml = '<tr>';
            const keys = Object.keys(data[0]);
            keys.forEach(key => headHtml += `<th class="p-3">${key}</th>`);
            headHtml += '</tr>';
            head.innerHTML = headHtml;

            let bodyHtml = '';
            data.forEach(row => {
                bodyHtml += '<tr>';
                keys.forEach(key => {
                    let value = row[key];
                    
                    // 您的千分位與金額優化邏輯，並延伸支援「毛利」關鍵字
                    if (value !== null && value !== undefined && 
                        (key.includes('單價') || key.includes('金額') || key.includes('平均') || key.includes('銷售額') || key.includes('毛利'))) {
                        
                        if (key.includes('率')) {
                            // 毛利率保持小數點與百分比
                            value = parseFloat(value).toFixed(1) + '%';
                        } else {
                            const numValue = parseFloat(value);
                            if (!isNaN(numValue)) {
                                value = '$' + Math.round(numValue).toLocaleString();
                            }
                        }
                    } else if (value === null || value === undefined) {
                        value = '-';
                    }
                    bodyHtml += `<td class="p-3">${value}</td>`;
                });
                bodyHtml += '</tr>';
            });
            body.innerHTML = bodyHtml;
        }

        function initCustomerDropdown() {
            const select = document.getElementById('customer-select');
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

        function filterCustomerStats() {
            const selectedId = document.getElementById('customer-select').value;
            if (selectedId === 'ALL') {
                renderTable(cachedStatsData);
            } else {
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
    """首頁"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/dashboard-stats')
def get_dashboard_stats():
    """API: 取得儀表板 KPI (修正整數除法漏洞) 與商品利潤排行"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. 查詢 KPI 核心指標 (調整 * 100.0 到除號前面，解決 0.0% 錯誤)
        kpi_query = """
            SELECT 
                COALESCE(SUM(p."銷售單價" * s."數量"), 0) AS total_sales,
                COALESCE(SUM((p."銷售單價" - p."進貨單價") * s."數量"), 0) AS total_profit,
                CASE 
                    WHEN SUM(p."銷售單價" * s."數量") > 0 
                    THEN ROUND((SUM((p."銷售單價" - p."進貨單價") * s."數量") * 100.0 / SUM(p."銷售單價" * s."數量")), 1)
                    ELSE 0 
                END AS margin_rate,
                COALESCE(SUM(s."數量"), 0) AS total_qty,
                COUNT(DISTINCT s."顧客ID") AS total_customers,
                CASE 
                    WHEN COUNT(DISTINCT s."傳票編號") > 0 
                    THEN COALESCE(SUM(p."銷售單價" * s."數量"), 0) / COUNT(DISTINCT s."傳票編號")
                    ELSE 0 
                END AS avg_order_value
            FROM "銷售資料" s
            LEFT JOIN "商品清單" p ON s."商品ID" = p."商品ID";
        """
        cur.execute(kpi_query)
        kpi_result = cur.fetchone()

        # 2. 查詢 Top 5 高毛利商品排行 (同樣修正單品毛利率整數除法)
        top_products_query = """
            SELECT 
                p."商品名稱",
                SUM(s."數量") AS "總銷售數量",
                SUM(p."銷售單價" * s."數量") AS "總銷售額",
                SUM((p."銷售單價" - p."進貨單價") * s."數量") AS "總創造毛利",
                ROUND((SUM((p."銷售單價" - p."進貨單價") * s."數量") * 100.0 / NULLIF(SUM(p."銷售單價" * s."數量"), 0)), 1) AS "單品毛利率"
            FROM "銷售資料" s
            LEFT JOIN "商品清單" p ON s."商品ID" = p."商品ID"
            GROUP BY p."商品名稱"
            ORDER BY "總創造毛利" DESC
            LIMIT 5;
        """
        cur.execute(top_products_query)
        top_products = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            "kpi": kpi_result,
            "top_products": top_products
        })
    except Exception as e:
        return jsonify({"error": f"儀表板數據統計失敗，錯誤訊息：{str(e)}"}), 500

@app.route('/api/customer-stats')
def get_customer_stats():
    """API: 取得顧客消費統計分析"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT 
                s."顧客ID",
                c."顧客名稱",
                MAX(p."商品名稱") AS "購買特定商品(文字最大值)",
                ROUND(AVG(p."銷售單價"), 0) AS "平均購買單價",
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
    app.run(debug=True)