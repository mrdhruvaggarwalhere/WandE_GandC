/**
 * G&C Deal & Brokerage Automation Platform
 * Core Application Router & State Manager
 */

const app = {
  currentRole: 'ADMIN',
  currentUserName: 'Dhruv Aggarwal (Admin)',
  parties: [],
  products: [],
  deals: [],
  chains: [],
  billingInstructions: [],

  init() {
    this.setupNavigation();
    this.setupRoleSwitcher();
    this.setupGlobalActions();
    this.fetchMasterData().then(() => {
      this.loadDashboard();
      this.loadDeals();
      this.loadChains();
      this.loadBilling();
    });

    if (window.lucide) {
      lucide.createIcons();
    }
  },

  // Role Management
  setupRoleSwitcher() {
    const select = document.getElementById('role-select');
    const badge = document.getElementById('role-badge');

    select.addEventListener('change', (e) => {
      this.currentRole = e.target.value;
      badge.textContent = this.currentRole;
      if (this.currentRole === 'ADMIN') {
        this.currentUserName = 'Dhruv Aggarwal (Admin)';
        badge.className = 'badge badge-profit';
      } else if (this.currentRole === 'BROKER') {
        this.currentUserName = 'Girish Chander (Broker)';
        badge.className = 'badge badge-status-confirmed';
      } else if (this.currentRole === 'ACCOUNTS') {
        this.currentUserName = 'Sunil Sharma (Accounts)';
        badge.className = 'badge badge-status-pending';
      } else {
        this.currentUserName = 'Audit Officer (Viewer)';
        badge.className = 'badge badge-neutral';
      }
      this.showToast(`Switched active role to ${this.currentRole}`, 'info');
    });
  },

  // API Request Helper with Role Attribution
  async api(endpoint, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      'X-User-Name': this.currentUserName,
      'X-User-Role': this.currentRole,
      ...(options.headers || {})
    };

    try {
      const res = await fetch(endpoint, { ...options, headers });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Server error occurred');
      }
      return await res.json();
    } catch (error) {
      this.showToast(error.message, 'error');
      throw error;
    }
  },

  // Global Navigation
  setupNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const view = item.dataset.view;
        this.navigate(view);
      });
    });
  },

  navigate(viewName) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    const activeNav = document.getElementById(`nav-${viewName}`);
    if (activeNav) activeNav.classList.add('active');

    // Hide all views
    const views = ['dashboard', 'deals', 'chains', 'billing', 'ledger', 'reports', 'masters', 'busy', 'tests'];
    views.forEach(v => {
      const el = document.getElementById(`view-${v}`);
      if (el) el.style.display = (v === viewName) ? 'block' : 'none';
    });

    const titleMap = {
      dashboard: ['Dashboard Overview', 'Central deal tracking and financial metrics'],
      deals: ['Primary Deals Register', 'Excel Columns A:G mapping compliant transaction log'],
      chains: ['Deal Chains & Lots', 'Interactive resale chain tracking, margins & final bill resolving'],
      billing: ['Direct Billing Instructions', 'Official commercial invoices from original seller to final buyer'],
      ledger: ['Party Ledgers & Statements', 'Brokerage charge dues and settlement tracking'],
      reports: ['Analytics & Reports Suite', 'Analytical breakdowns, profits, and delivery registers'],
      masters: ['Masters & Settings', 'Party directory, product registry, and rate configurations'],
      busy: ['BUSY Integration Hub', 'Staging and export adapter for BUSY accounting software'],
      tests: ['Acceptance Test Suite', 'Mandatory Haryana-to-Shakti worked example verification']
    };

    if (titleMap[viewName]) {
      document.getElementById('page-title').textContent = titleMap[viewName][0];
      document.getElementById('page-subtitle').textContent = titleMap[viewName][1];
    }

    // Refresh view data on navigation
    if (viewName === 'dashboard') this.loadDashboard();
    if (viewName === 'deals') this.loadDeals();
    if (viewName === 'chains') this.loadChains();
    if (viewName === 'billing') this.loadBilling();
    if (viewName === 'ledger') ledger.loadLedger();
    if (viewName === 'reports') reports.loadReport();
    if (viewName === 'masters') masters.loadMasters();
    if (viewName === 'busy') busyAdapter.loadBusyVouchers();
    if (viewName === 'tests') testRunner.renderInitialState();

    if (window.lucide) lucide.createIcons();
  },

  // Setup Global Actions (New deal button, export)
  setupGlobalActions() {
    document.getElementById('btn-open-new-deal').addEventListener('click', () => dealEntry.openModal());
    document.getElementById('btn-deals-new-deal').addEventListener('click', () => dealEntry.openModal());
    document.getElementById('btn-export-excel').addEventListener('click', () => this.exportExcel());
  },

  exportExcel() {
    this.showToast('Generating multi-sheet Excel workbook...', 'info');
    window.location.href = '/api/export/excel';
  },

  // Load Masters
  async fetchMasterData() {
    try {
      this.parties = await this.api('/api/parties');
      this.products = await this.api('/api/products');
      dealEntry.populateDropdowns();
      dealChain.populateDropdowns();
      ledger.populatePartySelect();
    } catch (e) {
      console.error('Failed loading masters', e);
    }
  },

  // Dashboard Loader
  async loadDashboard() {
    try {
      const data = await this.api('/api/dashboard');
      document.getElementById('kpi-active-deals').textContent = data.total_active_deals;
      document.getElementById('kpi-profit').textContent = this.formatCurrency(data.total_price_diff_profit);
      document.getElementById('kpi-brokerage').textContent = this.formatCurrency(data.total_brokerage);
      document.getElementById('kpi-net-earning').textContent = this.formatCurrency(data.net_earnings);

      document.getElementById('kpi-del-today').textContent = data.deliveries_today;
      document.getElementById('kpi-del-week').textContent = data.deliveries_this_week;
      document.getElementById('kpi-del-overdue').textContent = data.deliveries_overdue;
      document.getElementById('kpi-chains-billing').textContent = data.chains_ready_billing;

      document.getElementById('badge-deals-count').textContent = data.total_active_deals;
      document.getElementById('badge-billing-ready').textContent = data.chains_ready_billing;

      // Render Recent Deals in Dashboard
      const dealsTbody = document.getElementById('dashboard-deals-tbody');
      dealsTbody.innerHTML = '';
      data.recent_deals.forEach(d => {
        const tr = document.createElement('tr');
        const profitBadge = d.price_diff_profit > 0
          ? `<span class="badge badge-profit">+₹${this.formatNumber(d.price_diff_profit)}</span>`
          : (d.price_diff_profit < 0 ? `<span class="badge badge-loss">-₹${this.formatNumber(Math.abs(d.price_diff_profit))}</span>` : `<span class="badge badge-neutral">₹0</span>`);

        tr.innerHTML = `
          <td class="text-mono">${this.formatDate(d.deal_date)}</td>
          <td><strong>${d.buyer_name}</strong></td>
          <td>${d.seller_name}</td>
          <td><span class="badge badge-neutral">${d.product_name}</span></td>
          <td class="text-mono">${d.quantity_tonnes} MT</td>
          <td class="text-mono">₹${this.formatNumber(d.rate_per_qtl)}</td>
          <td>${profitBadge}</td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="dealChain.openResellModal('${d.chain_id}', '${d.id}')">Resell</button>
          </td>
        `;
        dealsTbody.appendChild(tr);
      });

      // Render Receivables in Dashboard
      const recvTbody = document.getElementById('dashboard-receivables-tbody');
      recvTbody.innerHTML = '';
      data.party_receivables.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${p.party_name}</strong></td>
          <td class="text-mono text-profit">₹${this.formatNumber(p.balance_due)}</td>
        `;
        recvTbody.appendChild(tr);
      });

      // Check for Latest Direct Billing Instruction to show in banner
      const billings = await this.api('/api/billing-instructions');
      if (billings && billings.length > 0) {
        const latest = billings[0];
        document.getElementById('dashboard-billing-banner').style.display = 'flex';
        document.getElementById('dashboard-banner-text').textContent = latest.instruction_text;
        document.getElementById('btn-banner-view-chain').onclick = () => {
          this.navigate('chains');
        };
      }

      if (window.lucide) lucide.createIcons();
    } catch (e) {
      console.error(e);
    }
  },

  // Load Primary Deals Table
  async loadDeals() {
    try {
      this.deals = await this.api('/api/deals');
      document.getElementById('badge-deals-count').textContent = this.deals.length;
      const tbody = document.getElementById('deals-table-tbody');
      tbody.innerHTML = '';

      this.deals.forEach(d => {
        const tr = document.createElement('tr');
        const profitBadge = d.price_diff_profit > 0
          ? `<span class="badge badge-profit">+₹${this.formatNumber(d.price_diff_profit)}</span>`
          : (d.price_diff_profit < 0 ? `<span class="badge badge-loss">-₹${this.formatNumber(Math.abs(d.price_diff_profit))}</span>` : `<span class="badge badge-neutral">₹0</span>`);

        const gstText = d.gst_applicable ? `+${d.gst_percentage}% GST` : '(No GST)';

        tr.innerHTML = `
          <td class="text-mono highlight-ag">${this.formatDate(d.deal_date)}</td>
          <td class="highlight-ag"><strong>${d.buyer_name}</strong></td>
          <td class="highlight-ag">${d.seller_name}</td>
          <td class="highlight-ag"><span class="badge badge-neutral">${d.product_name}</span></td>
          <td class="text-mono highlight-ag">${d.quantity_qtl} Qtl (${d.quantity_tonnes} MT)</td>
          <td class="text-mono highlight-ag">₹${this.formatNumber(d.rate_per_qtl)} ${gstText}</td>
          <td class="text-mono highlight-ag">${this.formatDate(d.delivery_date)}</td>
          <td class="text-mono">${d.chain_id}</td>
          <td class="text-mono">#${d.link_sequence}</td>
          <td>${profitBadge}</td>
          <td class="text-mono">₹${this.formatNumber(d.total_brokerage_amount)}</td>
          <td><span class="badge badge-status-${d.status.toLowerCase()}">${d.status}</span></td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="dealChain.openResellModal('${d.chain_id}', '${d.id}')" title="Resell / Link Next Deal">
              Resell
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {
      console.error(e);
    }
  },

  // Load Chains
  async loadChains() {
    try {
      this.chains = await this.api('/api/deal-chains');
      document.getElementById('badge-chains-count').textContent = this.chains.length;
      dealChain.renderChains(this.chains);
    } catch (e) {
      console.error(e);
    }
  },

  // Load Billing
  async loadBilling() {
    try {
      this.billingInstructions = await this.api('/api/billing-instructions');
      billing.renderBillingInstructions(this.billingInstructions);
    } catch (e) {
      console.error(e);
    }
  },

  // Modal Controllers
  closeModals() {
    document.querySelectorAll('.modal-backdrop').forEach(el => el.classList.remove('open'));
  },

  // Formatters
  formatCurrency(val) {
    const num = Number(val || 0);
    return '₹' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  },

  formatNumber(val) {
    const num = Number(val || 0);
    return num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  },

  formatDate(isoStr) {
    if (!isoStr) return '';
    const parts = String(isoStr).split('T')[0].split('-');
    if (parts.length === 3) {
      return `${parts[2]}/${parts[1]}/${parts[0]}`;
    }
    return isoStr;
  },

  // Toast Notification
  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
};

document.addEventListener('DOMContentLoaded', () => {
  app.init();
});
