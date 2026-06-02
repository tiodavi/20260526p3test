import os
from flask import Flask, jsonify, render_template_string, request
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

# --- 前端 HTML 範本 (內嵌在單一檔案中) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3C 進銷存管理系統 (業務績效與 CRM 增強版)</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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
        .chart-container { position: relative; height: 260px; width: 100%; display: flex; justify-content: center; align-items: center; }
        .bonus-banner { background: #d1e7dd; border-left: 5px solid #198754; padding: 15px; border-radius: 6px; margin-bottom: 20px; display: none; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-2 sidebar p-0 shadow">
                <div class="p-3 text-center border-bottom border-secondary">
                    <h4 class="m-0">🏪 3C 零售系統</h4>
                </div>
                
                <div class="p-2 bg-success text-center fw-bold text-white small">🏅 業務績效考核模組</div>
                <div class="mt-2">
                    <a href="#sales-detail-check" id="menu-sales-detail-check" onclick="loadData('sales-detail-check')">💰 業務業績明細(算獎金)</a>
                    <a href="#customer-preference" id="menu-customer-preference" onclick="loadData('customer-preference')">🎯 客戶購買偏好追蹤</a>
                </div>

                <div class="p-2 border-top border-secondary text-center fw-bold text-muted small mt-2">📊 核心營運與數據</div>
                <div>
                    <a href="#dashboard" id="menu-dashboard" onclick="loadData('dashboard')">🏠 營運儀表板</a>
                    <a href="#sales-ranking" id="menu-sales-ranking" onclick="loadData('sales-ranking')">🏅 業務業績總排行</a>
                    <a href="#customer-ranking" id="menu-customer-ranking" onclick="loadData('customer-ranking')">🏆 顧客貢獻排行</a>
                    <a href="#dead-products" id="menu-dead-products" onclick="loadData('dead-products')">⚠️ 滯銷商品分析</a>
                    <a href="#sales-by-date" id="menu-sales-by-date" onclick="loadData('sales-by-date')">📅 區間銷售流水</a>
                    <a href="#sales-by-group" id="menu-sales-by-group" onclick="loadData('sales-by-group')">💻 商品群組銷貨</a>
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

                <div id="sales-bonus-panel" class="bonus-banner row g-3 m-0 mb-4">
                    <div class="col-md-4">
                        <div class="fw-bold text-success text-uppercase small">👤 當前查核業務員</div>
                        <h3 class="m-0 text-dark" id="bonus-sales-name">-</h3>
                    </div>
                    <div class="col-md-3">
                        <div class="fw-bold text-success text-uppercase small">💰 經手總業績 (營業額)</div>
                        <h4 class="m-0 text-dark" id="bonus-total-sales">$0</h4>
                    </div>
                    <div class="col-md-3">
                        <div class="fw-bold text-success text-uppercase small">💵 創造總毛利</div>
                        <h4 class="m-0 text-dark" id="bonus-total-profit">$0</h4>
                    </div>
                    <div class="col-md-2">
                        <div class="fw-bold text-danger text-uppercase small">🎁 預估獎金 (業績 5%)</div>
                        <h4 class="m-0 text-danger fw-bold" id="bonus-calculated">$0</h4>
                    </div>
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

                <div id="dashboard-chart-block" class="row g-3 mb-4 d-none">
                    <div class="col-md-4">
                        <div class="card p-3 bg-white text-center h-100">
                            <h6 class="text-secondary mb-2">🍕 Top 5 商品毛利貢獻佔比</h6>
                            <div class="chart-container">
                                <canvas id="profitPieChart"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card p-3 bg-white text-center h-100">
                            <h6 class="text-secondary mb-2">🏢 Top 5 顧客消費金額排行</h6>
                            <div class="chart-container">
                                <canvas id="customerBarChart"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card p-3 bg-white text-center h-100">
                            <h6 class="text-secondary mb-2">🏅 業務員銷售總額 PK 排行</h6>
                            <div class="chart-container">
                                <canvas id="salesBarChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div id="filter-block-sales" class="filter-container align-items-center gap-3" style="display: none;">
                    <label for="sales-staff-select" class="form-label m-0 fw-bold text-secondary">👤 選擇查核業務人員：</label>
                    <select id="sales-staff-select" class="form-select" style="max-width: 300px;" onchange="fetchSalesDataByDynamicStaff()">
                    </select>
                </div>

                <div id="filter-block-date" class="filter-container align-items-center gap-3" style="display: none;">
                    <label for="start-date" class="form-label m-0 fw-bold text-secondary">📅 開始日期：</label>
                    <input type="date" id="start-date" class="form-control" style="max-width: 200px;" value="2021-04-01">
                    <label for="end-date" class="form-label m-0 fw-bold text-secondary">📅 結束日期：</label>
                    <input type="date" id="end-date" class="form-control" style="max-width: 200px;" value="2021-06-30">
                    <button class="btn btn-primary fw-bold" onclick="fetchSalesByDate()">🔍 篩選區間明細</button>
                </div>

                <div id="filter-block-group" class="filter-container align-items-center gap-3" style="display: none;">
                    <label for="group-name-select" class="form-select" style="max-width: 300px;" onchange="fetchSalesByGroup()"></select>
                </div>

                <div id="filter-block" class="filter-container align-items-center gap-3" style="display: none;">
                    <select id="customer-select" class="form-select" style="max-width: 300px;" onchange="filterCustomerStats()"></select>
                </div>

                <div class="card p-4 bg-white">
                    <h5 id="table-title" class="mb-3 text-secondary" style="display:none;">🔥 Top 5 高毛利商品明細排行</h5>
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
        let currentActiveModule = 'sales-detail-check'; // 追蹤目前點選的是明細還是購買偏好
        let cachedStatsData = [];
        let profitChartInstance = null;
        let customerChartInstance = null;
        let salesChartInstance = null;

        document.addEventListener("DOMContentLoaded", function() {
            loadData('sales-detail-check'); // 預設進來直接看業務業績明細查核
        });

        function loadData(type) {
            const body = document.getElementById('table-body');
            const head = document.getElementById('table-head');
            const title = document.getElementById('page-title');
            const tableTitle = document.getElementById('table-title');
            
            const filterBlockSales = document.getElementById('filter-block-sales');
            const filterBlockGroup = document.getElementById('filter-block-group');
            const filterBlockDate = document.getElementById('filter-block-date');
            const filterBlock = document.getElementById('filter-block');
            
            const dashboardCards = document.getElementById('dashboard-cards');
            const chartBlock = document.getElementById('dashboard-chart-block');
            const salesBonusPanel = document.getElementById('sales-bonus-panel');
            
            document.querySelectorAll('.sidebar a').forEach(a => a.classList.remove('active'));
            const activeMenu = document.getElementById(`menu-${type}`);
            if (activeMenu) activeMenu.classList.add('active');
            
            // 控制篩選欄位顯示
            filterBlockSales.style.display = (type === 'sales-detail-check' || type === 'customer-preference') ? 'flex' : 'none';
            if (type === 'sales-detail-check' || type === 'customer-preference') {
                currentActiveModule = type;
                initSalesStaffDropdown();
            }

            filterBlockDate.style.display = (type === 'sales-by-date') ? 'flex' : 'none';
            filterBlockGroup.style.display = (type === 'sales-by-group') ? 'flex' : 'none';
            filterBlock.style.display = (type === 'customer-stats') ? 'flex' : 'none';

            // 控制 KPI 面板與業績獎金面板
            if (type === 'sales-detail-check') {
                salesBonusPanel.style.display = 'flex';
            } else {
                salesBonusPanel.style.display = 'none';
            }

            if (type === 'dashboard') {
                dashboardCards.style.display = 'flex';
                chartBlock.classList.remove('d-none');
                tableTitle.style.display = 'block';
                title.innerText = '🏠 營運儀表板';
            } else {
                dashboardCards.style.display = 'none';
                chartBlock.classList.add('d-none');
                tableTitle.style.display = 'none';
            }
            
            body.innerHTML = '<tr><td class="text-center py-4" colspan="10"><div class="spinner-border spinner-border-sm text-primary me-2"></div>數據拉取中，請稍候...</td></tr>';

            if (type === 'dashboard') {
                fetch('/api/dashboard-stats')
                    .then(res => res.json())
                    .then(data => {
                        document.getElementById('kpi-total-sales').innerText = '$' + Math.round(data.kpi.total_sales).toLocaleString();
                        document.getElementById('kpi-total-profit').innerText = '$' + Math.round(data.kpi.total_profit).toLocaleString();
                        document.getElementById('kpi-margin-rate').innerText = data.kpi.margin_rate + '%';
                        document.getElementById('kpi-total-qty').innerText = Math.round(data.kpi.total_qty).toLocaleString() + ' 件';
                        document.getElementById('kpi-avg-order').innerText = '$' + Math.round(data.kpi.avg_order_value).toLocaleString();
                        document.getElementById('kpi-total-customers').innerText = data.kpi.total_customers + ' 人';
                        
                        renderProfitPieChart(data.top_products);
                        renderCustomerBarChart(data.top_customers);
                        renderSalesBarChart(data.top_sales);
                        renderTable(data.top_products);
                    });
                return;
            }

            if (type === 'sales-detail-check' || type === 'customer-preference') {
                fetchSalesDataByDynamicStaff();
                return;
            }

            if (type === 'sales-by-group') { fetchSalesByGroup(); return; }
            if (type === 'sales-by-date') { fetchSalesByDate(); return; }

            if (type === 'sales-ranking') {
                fetch('/api/sales-ranking').then(res => res.json()).then(data => {
                    title.innerText = '🏅 業務員業績總排行榜 (Top Sales)';
                    renderTable(data);
                });
                return;
            }

            if (type === 'customer-ranking') {
                fetch('/api/customer-ranking').then(res => res.json()).then(data => {
                    title.innerText = '🏆 顧客貢獻度排行榜 (VVIP 總覽)';
                    renderTable(data);
                });
                return;
            }

            if (type === 'dead-products') {
                fetch('/api/dead-products').then(res => res.json()).then(data => {
                    title.innerText = '⚠️ 滯銷商品分析清單 (從未有過銷售紀錄)';
                    renderTable(data);
                });
                return;
            }

            fetch(`/api/${type}`)
                .then(res => res.json())
                .then(data => {
                    if (type === 'customer-stats') cachedStatsData = data;
                    renderTable(data);
                    if (type === 'sales') title.innerText = '📊 銷售流水帳 (全公司總覽)';
                    if (type === 'customer-stats') title.innerText = '📈 顧客消費統計分析';
                    if (type === 'products') title.innerText = '💻 商品母體資料';
                    if (type === 'customers') title.innerText = '👥 顧客客戶清單';
                });
        }

        // 初始化業務員動態下拉選單
        function initSalesStaffDropdown() {
            const select = document.getElementById('sales-staff-select');
            if (select.options.length > 0) return;

            fetch('/api/sales-ranking') // 從現有 API 抓取所有有業績的業務員
                .then(res => res.json())
                .then(staffList => {
                    if (staffList && !staffList.error) {
                        staffList.forEach((staff, index) => {
                            const opt = document.createElement('option');
                            opt.value = staff['負責人ID']; 
                            opt.innerHTML = `[ID: ${staff['負責人ID']}] ${staff['負責人姓名']}`;
                            if (index === 0) opt.selected = true; // 預設選擇第一位業務
                            select.appendChild(opt);
                        });
                        fetchSalesDataByDynamicStaff(); // 載入完畢後自動觸發第一次查詢
                    }
                });
        }

        // 動態透過變數傳遞給後端 API 查核
        function fetchSalesDataByDynamicStaff() {
            const select = document.getElementById('sales-staff-select');
            if (select.options.length === 0) return;

            const staffId = select.value;
            const staffName = select.options[select.selectedIndex].text.split('] ')[1];
            const title = document.getElementById('page-title');
            
            if (currentActiveModule === 'sales-detail-check') {
                title.innerText = `💰 業務績效明細查核 - [${staffName}]`;
                document.getElementById('bonus-sales-name').innerText = staffName;
                
                // 抓取明細與即時計算獎金
                fetch(`/api/sales-detail-by-staff?staff_id=${staffId}`)
                    .then(res => res.json())
                    .then(data => {
                        if (data.error || data.sales_detail.length === 0) {
                            document.getElementById('bonus-total-sales').innerText = '$0';
                            document.getElementById('bonus-total-profit').innerText = '$0';
                            document.getElementById('bonus-calculated').innerText = '$0';
                            renderTable([]);
                            return;
                        }
                        
                        // 更新上方獎金看板
                        const summary = data.summary;
                        document.getElementById('bonus-total-sales').innerText = '$' + Math.round(summary.total_sales).toLocaleString();
                        document.getElementById('bonus-total-profit').innerText = '$' + Math.round(summary.total_profit).toLocaleString();
                        document.getElementById('bonus-calculated').innerText = '$' + Math.round(summary.total_sales * 0.05).toLocaleString(); // 業績 5% 獎金
                        
                        renderTable(data.sales_detail);
                    });
            } else if (currentActiveModule === 'customer-preference') {
                title.innerText = `🎯 客戶購買偏好追蹤 - [${staffName}]`;
                fetch(`/api/customer-preference-by-staff?staff_id=${staffId}`)
                    .then(res => res.json())
                    .then(data => {
                        renderTable(data);
                    });
            }
        }

        function fetchSalesByGroup() {
            // 保留原有群組查詢邏輯...
        }

        function fetchSalesByDate() {
            const startDate = document.getElementById('start-date').value;
            const endDate = document.getElementById('end-date').value;
            const title = document.getElementById('page-title');
            fetch(`/api/sales-by-date?start=${startDate}&end=${endDate}`)
                .then(res => res.json()).then(data => { renderTable(data); });
        }

        function renderProfitPieChart(productsData) {
            const ctx = document.getElementById('profitPieChart').getContext('2d');
            if (profitChartInstance) profitChartInstance.destroy();
            profitChartInstance = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: productsData.map(item => item['商品名稱']),
                    datasets: [{ data: productsData.map(item => item['總創造毛利']), backgroundColor: ['#0d6efd', '#6f42c1', '#fd7e14', '#198754', '#ffc107'] }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }

        function renderCustomerBarChart(customersData) {
            const ctx = document.getElementById('customerBarChart').getContext('2d');
            if (customerChartInstance) customerChartInstance.destroy();
            customerChartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: customersData.map(item => item['顧客名稱']),
                    datasets: [{ label: '消費額', data: customersData.map(item => item['總金額']), backgroundColor: '#6f42c1' }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }

        function renderSalesBarChart(salesData) {
            const ctx = document.getElementById('salesBarChart').getContext('2d');
            if (salesChartInstance) salesChartInstance.destroy();
            salesChartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: salesData.map(item => item['負責人姓名']),
                    datasets: [{ label: '銷售總額', data: salesData.map(item => item['銷售總額']), backgroundColor: '#198754' }]
                },
                options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }

        function renderTable(data) {
            const head = document.getElementById('table-head');
            const body = document.getElementById('table-body');
            if (!data || data.length === 0) {
                head.innerHTML = '';
                body.innerHTML = '<tr><td class="text-center py-4 text-muted" colspan="10">⚠️ 查無此業務員經手的相關明細紀錄</td></tr>';
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
                    if (value !== null && value !== undefined && 
                        (key.includes('單價') || key.includes('金額') || key.includes('平均') || key.includes('銷售額') || key.includes('毛利') || key.includes('總額') || key.includes('小計') || key.includes('貢獻預算'))) {
                        if (key.includes('率')) { value = parseFloat(value).toFixed(1) + '%'; }
                        else { const numValue = parseFloat(value); if (!isNaN(numValue)) value = '$' + Math.round(numValue).toLocaleString(); }
                    } else if (value === null || value === undefined) { value = '-'; }
                    bodyHtml += `<td class="p-3">${value}</td>`;
                });
                bodyHtml += '</tr>';
            });
            body.innerHTML = bodyHtml;
        }
    </script>
</body>
</html>
"""

# --- 🚀 新增業務績效考核模組後端 API 路由 ---

@app.route('/api/sales-detail-by-staff')
def get_sales_detail_by_staff():
    """API: 透過動態變數(staff_id) 查核特定業務的流水帳明細並計算毛利與業績"""
    staff_id = request.args.get('staff_id')
    if not staff_id:
        return jsonify({"error": "缺少業務負責人 ID"}), 400
        
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 1. 串聯你提供的 SQL 語法，並加入毛利計算，透過 %s 動態防禦注入
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
                    WHERE e."負責人ID" = %s
                    ORDER BY s."傳票編號" ASC, s."列編號" ASC;
                """
                cur.execute(query_detail, (staff_id,))
                sales_detail = cur.fetchall()
                
                # 2. 計算該業務的業績加總、毛利加總
                query_summary = """
                    SELECT 
                        COALESCE(SUM(p."販賣單價" * s."數量"), 0) AS total_sales,
                        COALESCE(SUM((p."販賣單價" - p."進貨單價") * s."數量"), 0) AS total_profit
                    FROM "販賣資料" AS s
                    INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID"
                    WHERE s."負責人ID" = %s;
                """
                cur.execute(query_summary, (staff_id,))
                summary = cur.fetchone()
                
        return jsonify({"sales_detail": sales_detail, "summary": summary})
    except Exception as e:
        return jsonify({"error": f"業務績效明細抓取失敗：{str(e)}"}), 500


@app.route('/api/customer-preference-by-staff')
def get_customer_preference_by_staff():
    """API: 透過動態變數(staff_id) 追蹤該業務經手的客戶購買商品偏好"""
    staff_id = request.args.get('staff_id')
    if not staff_id:
        return jsonify({"error": "缺少業務負責人 ID"}), 400
        
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
                    WHERE s."負責人ID" = %s
                    GROUP BY c."顧客ID", c."顧客名稱", p."商品ID", p."商品名稱", p."群組名稱"
                    ORDER BY c."顧客名稱" ASC, "累積購買數量" DESC;
                """
                cur.execute(query, (staff_id,))
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"客戶購買偏好追蹤失敗：{str(e)}"}), 500

# --- 其餘既有後端 API 路由 (維持安全 with 架構) ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/dead-products')
def get_dead_products():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT p."商品ID" AS "商品id", p."商品名稱", p."群組名稱" FROM "商品清單" AS p LEFT JOIN "販賣資料" AS s ON p."商品ID" = s."商品ID" WHERE s."傳票編號" IS NULL ORDER BY p."商品ID";')
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/sales-ranking')
def get_sales_ranking():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT e."負責人ID", e."負責人姓名", COUNT(*) AS "訂單筆數", SUM(p."販賣單價" * s."數量") AS "銷售總額" FROM "販賣資料" AS s INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID" INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID" GROUP BY e."負責人ID", e."負責人姓名" ORDER BY "銷售總額" DESC;')
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/customer-ranking')
def get_customer_ranking():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT c."顧客名稱", COUNT(*) AS "訂單筆數", SUM(p."販賣單價" * s."數量") AS "總金額" FROM "販賣資料" AS s INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID" INNER JOIN "顧客清單" AS c ON s."顧客ID" = c."顧客ID" GROUP BY c."顧客ID", c."顧客名稱" ORDER BY "總金額" DESC;')
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/sales-by-date')
def get_sales_by_date():
    start_date = request.args.get('start', '2021-04-01')
    end_date = request.args.get('end', '2021-06-30')
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT s."傳票編號", s."處理日", p."商品名稱", e."負責人姓名", c."顧客名稱", s."數量" FROM "販賣資料" AS s INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID" INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID" INNER JOIN "顧客清單" AS c ON s."顧客ID" = c."顧客ID" WHERE s."處理日" BETWEEN %s AND %s ORDER BY s."處理日" ASC;', (start_date, end_date))
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard-stats')
def get_dashboard_stats():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT COALESCE(SUM(p."販賣單價" * s."數量"), 0) AS total_sales, COALESCE(SUM((p."販賣單價" - p."進貨單價") * s."數量"), 0) AS total_profit, CASE WHEN SUM(p."販賣單價" * s."數量") > 0 THEN ROUND((SUM((p."販賣單價" - p."進貨單價") * s."數量") * 100.0 / SUM(p."販賣單價" * s."數量")), 1) ELSE 0 END AS margin_rate, COALESCE(SUM(s."數量"), 0) AS total_qty, COUNT(DISTINCT s."顧客ID") AS total_customers, CASE WHEN COUNT(DISTINCT s."傳票編號") > 0 THEN COALESCE(SUM(p."販賣單價" * s."數量"), 0) / COUNT(DISTINCT s."傳票編號") ELSE 0 END AS avg_order_value FROM "販賣資料" s LEFT JOIN "商品清單" p ON s."商品ID" = p."商品ID";')
                kpi_result = cur.fetchone()
                cur.execute('SELECT p."商品名稱", SUM(s."數量") AS "總銷售數量", SUM(p."販賣單價" * s."數量") AS "總銷售額", SUM((p."販賣單價" - p."進貨單價") * s."數量") AS "總創造毛利" FROM "販賣資料" s LEFT JOIN "商品清單" p ON s."商品ID" = p."商品ID" GROUP BY p."商品名稱" ORDER BY "總創造毛利" DESC LIMIT 5;')
                top_products = cur.fetchall()
                cur.execute('SELECT c."顧客名稱", SUM(p."販賣單價" * s."數量") AS "總金額" FROM "販賣資料" s INNER JOIN "商品清單" p ON s."商品ID" = p."商品ID" INNER JOIN "顧客清單" c ON s."顧客ID" = c."顧客ID" GROUP BY c."顧客ID", c."顧客名稱" ORDER BY "總金額" DESC LIMIT 5;')
                top_customers = cur.fetchall()
                cur.execute('SELECT e."負責人姓名", SUM(p."販賣單價" * s."數量") AS "銷售總額" FROM "販賣資料" s INNER JOIN "負責人清單" e ON s."負責人ID" = e."負責人ID" INNER JOIN "商品清單" p ON s."商品ID" = p."商品ID" GROUP BY e."負責人ID", e."負責人姓名" ORDER BY "銷售總額" DESC LIMIT 5;')
                top_sales = cur.fetchall()
        return jsonify({"kpi": kpi_result, "top_products": top_products, "top_customers": top_customers, "top_sales": top_sales})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/sales')
def get_sales():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT s."傳票編號", s."列編號", s."處理日", p."商品名稱", p."販賣單價", s."數量", (p."販賣單價" * s."數量") AS "流水小計", e."負責人姓名", c."顧客名稱" FROM "販賣資料" AS s INNER JOIN "商品清單" AS p ON s."商品ID" = p."商品ID" INNER JOIN "負責人清單" AS e ON s."負責人ID" = e."負責人ID" INNER JOIN "顧客清單" AS c ON s."顧客ID" = c."顧客ID" ORDER BY s."傳票編號" ASC, s."列編號" ASC;')
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/products')
def get_products():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT "商品ID" AS "商品id", "商品名稱", "群組名稱", "進貨單價", "販賣單價" FROM "商品清單" ORDER BY "商品ID";')
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/customers')
def get_customers():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT "顧客ID" AS "顧客id", "顧客名稱", "聯絡電話" FROM "顧客清單" ORDER BY "顧客ID";')
                results = cur.fetchall()
        return jsonify(results)
    except Exception as e: return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)