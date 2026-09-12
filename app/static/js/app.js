/**
 * ==========================================================================
 * GANESH & COMPANY — ENTERPRISE COMMODITY BROKERAGE PLATFORM
 * Core Frontend Controller & Information Architecture Manager
 * Sri Ganganagar, Rajasthan
 * ==========================================================================
 */

const app = {
  // Application State
  currentView: 'dashboard',
  parties: [],
  products: [],
  deals: [],
  trashDeals: [],
  dispatchLogs: [],
  dashboardMetrics: null,
  activePartyFilter: 'ALL',
  activeStatusFilter: 'ALL',
  searchQuery: '',
  partySearchQuery: '',
  sortBy: 'date-desc',
  selectedDealForDispatch: null,
  selectedDealForLetterhead: null,
  currentLetterheadRole: 'SELLER',
  selectedDealIds: new Set(),

  // Initialization
  async init() {
    this.setupSidebar();
    this.setupNavigation();
    this.setupKeyboardShortcuts();
    this.setupCommandPalette();
    this.setupNewBargainModal();
    this.setupEditBargainModal();
    this.setupPartyModal();
    this.setupModals();
    this.setupFilters();

    // Initial Data Fetch
    await this.refreshAllData();

    // Periodic Dashboard Refresh every 60s
    setInterval(() => {
      this.fetchDashboardMetrics(false);
    }, 60000);

    // Close action dropdowns on outside click
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.action-dropdown-container')) {
        document.querySelectorAll('.action-dropdown-menu.active').forEach(el => el.classList.remove('active'));
      }
    });

    if (window.lucide) {
      lucide.createIcons();
    }
  },

  formatDateCompact(dateStr) {
    if (!dateStr) return '—';
    try {
      const parts = dateStr.split('-');
      if (parts.length === 3) {
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const day = parseInt(parts[2], 10);
        const month = months[parseInt(parts[1], 10) - 1];
        const year = parts[0];
        if (month) return `${day} ${month} ${year}`;
      }
      return dateStr;
    } catch (_) {
      return dateStr;
    }
  },

  formatCompanyName(name) {
    if (!name) return '—';
    let clean = name.trim();
    if (clean === clean.toUpperCase() && clean.length > 3) {
      clean = clean.toLowerCase().replace(/\b([a-z])/g, (m, c) => c.toUpperCase());
    }
    return clean;
  },

  toggleActionDropdown(id, e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    const dropdown = document.getElementById(`dropdown-${id}`);
    if (!dropdown) return;
    const isCurrentlyActive = dropdown.classList.contains('active');
    document.querySelectorAll('.action-dropdown-menu.active').forEach(el => el.classList.remove('active'));
    if (!isCurrentlyActive) {
      dropdown.classList.add('active');
    }
  },

  // API Client with error handling and toast feedback
  async api(endpoint, options = {}) {
    const defaultHeaders = {
      'Content-Type': 'application/json',
      'X-User-Name': 'Sanjay Kumar Aggarwal',
      'X-User-Role': 'ADMIN'
    };

    try {
      const response = await fetch(endpoint, {
        ...options,
        headers: { ...defaultHeaders, ...(options.headers || {}) }
      });

      if (!response.ok) {
        let errMsg = 'Network request failed';
        try {
          const errData = await response.json();
          errMsg = errData.error || errMsg;
        } catch (_) {}
        throw new Error(errMsg);
      }

      return await response.json();
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      this.showToast(err.message || 'API request failed', 'error');
      throw err;
    }
  },

  // Toast Notifications
  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let iconName = 'info';
    if (type === 'success') iconName = 'check-circle';
    if (type === 'error') iconName = 'alert-circle';

    toast.innerHTML = `
      <i data-lucide="${iconName}" style="width: 16px; height: 16px; flex-shrink: 0;"></i>
      <span>${this.escapeHtml(message)}</span>
    `;
    container.appendChild(toast);

    if (window.lucide) {
      lucide.createIcons({ root: toast });
    }

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.2s ease';
      setTimeout(() => toast.remove(), 200);
    }, 3500);
  },

  publicUrl: null,

  // Global Data Refresh
  async refreshAllData() {
    try {
      await Promise.all([
        this.fetchPublicUrl(),
        this.fetchParties(),
        this.fetchProducts(),
        this.fetchDeals(),
        this.fetchTrashDeals(),
        this.fetchDispatchLogs(),
        this.fetchDashboardMetrics()
      ]);

      this.renderCurrentView();
      this.updateCounters();
    } catch (e) {
      console.error("Initialization data fetch error:", e);
    }
  },

  async fetchPublicUrl() {
    try {
      const res = await this.api('/api/public-url');
      if (res && res.public_url) {
        this.publicUrl = res.public_url;
      }
    } catch (e) {
      console.warn('Public URL not loaded:', e);
    }
  },

  // Data Fetchers
  async fetchParties() {
    this.parties = await this.api('/api/parties');
  },

  async fetchProducts() {
    this.products = await this.api('/api/products');
  },

  async fetchDeals() {
    this.deals = await this.api('/api/deals');
  },

  async fetchTrashDeals() {
    this.trashDeals = await this.api('/api/deals?only_deleted=1');
  },

  async fetchDispatchLogs() {
    try {
      this.dispatchLogs = await this.api('/api/dispatch-logs');
    } catch (_) {
      this.dispatchLogs = [];
    }
  },

  async fetchDashboardMetrics(updateUI = true) {
    try {
      this.dashboardMetrics = await this.api('/api/dashboard');
      if (updateUI && this.currentView === 'dashboard') {
        this.renderDashboard();
      }
    } catch (_) {}
  },

  // Sidebar Layout & Collapse
  setupSidebar() {
    const sidebar = document.getElementById('app-sidebar');
    const toggleBtn = document.getElementById('btn-toggle-sidebar');
    const toggleIcon = document.getElementById('sidebar-toggle-icon');

    const toggle = () => {
      sidebar.classList.toggle('collapsed');
      if (toggleIcon) {
        toggleIcon.setAttribute('data-lucide', sidebar.classList.contains('collapsed') ? 'chevron-right' : 'chevron-left');
        if (window.lucide) lucide.createIcons();
      }
    };

    if (toggleBtn) {
      toggleBtn.addEventListener('click', toggle);
    }

    document.getElementById('brand-home-link')?.addEventListener('click', () => {
      this.navigate('dashboard');
    });
  },

  // Navigation Routing
  setupNavigation() {
    document.querySelectorAll('.nav-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const view = link.dataset.view;
        if (view) this.navigate(view);
      });
    });

    document.getElementById('btn-goto-bargains')?.addEventListener('click', () => {
      this.navigate('bargains');
    });

    document.getElementById('kpi-card-today-deals')?.addEventListener('click', () => {
      this.navigate('bargains');
    });

    document.getElementById('kpi-card-parties')?.addEventListener('click', () => {
      this.navigate('parties');
    });

    document.getElementById('kpi-card-pending')?.addEventListener('click', () => {
      const panel = document.getElementById('panel-needs-attention');
      if (panel) {
        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });

    document.getElementById('btn-dash-new-bargain')?.addEventListener('click', () => {
      this.openNewBargainModal();
    });

    document.getElementById('btn-refresh-dashboard')?.addEventListener('click', async () => {
      await this.refreshAllData();
      this.showToast('Dashboard metrics updated to live mandi feeds', 'success');
    });
  },

  navigate(viewName) {
    this.currentView = viewName;

    // Update active nav link
    document.querySelectorAll('.nav-link').forEach(link => {
      link.classList.toggle('active', link.dataset.view === viewName);
    });

    // Update breadcrumb
    const breadcrumb = document.getElementById('breadcrumb-current');
    const titles = {
      'dashboard': 'Executive Dashboard',
      'bargains': 'Bargains Hub',
      'parties': 'Party Directory',
      'dispatches': 'Communications',
      'trash': 'Recycle Bin'
    };
    if (breadcrumb) {
      breadcrumb.textContent = titles[viewName] || 'Dashboard';
    }

    // Toggle view panes
    document.querySelectorAll('.view-pane').forEach(pane => {
      pane.classList.toggle('active', pane.id === `view-${viewName}`);
    });

    this.renderCurrentView();
  },

  renderCurrentView() {
    switch (this.currentView) {
      case 'dashboard':
        this.renderDashboard();
        break;
      case 'bargains':
        this.renderBargainsHub();
        break;
      case 'parties':
        this.renderPartyDirectory();
        break;
      case 'dispatches':
        this.renderDispatchLogs();
        break;
      case 'trash':
        this.renderTrash();
        break;
    }

    if (window.lucide) {
      lucide.createIcons();
    }
  },

  updateCounters() {
    const updateBadge = (id, count) => {
      const el = document.getElementById(id);
      if (!el) return;
      const num = Number(count) || 0;
      if (num > 0) {
        el.textContent = num;
        el.style.display = 'inline-flex';
      } else {
        el.textContent = '';
        el.style.display = 'none';
      }
    };

    const activeDealsCount = (this.deals || []).filter(d => !d.is_deleted).length;
    const activePartiesCount = (this.parties || []).filter(p => !p.is_deleted).length;
    const dispatchesCount = (this.dispatchLogs || []).length;
    const trashCount = (this.trashDeals || []).length;

    updateBadge('badge-bargains-count', activeDealsCount);
    updateBadge('badge-parties-count', activePartiesCount);
    updateBadge('badge-dispatches-count', dispatchesCount);
    updateBadge('badge-trash-count', trashCount);
  },

  // ==========================================================================
  // SCREEN 1: EXECUTIVE DASHBOARD
  // ==========================================================================
  renderDashboard() {
    const metrics = this.dashboardMetrics;
    if (!metrics) return;

    // 1. KPI Cards (authoritative DB values with explicit periods)
    const elToday = document.getElementById('kpi-today-deals');
    if (elToday) elToday.textContent = metrics.todays_deals_count ?? 0;

    const elVol = document.getElementById('kpi-traded-volume');
    if (elVol) {
      const totalMT = Math.round(metrics.todays_traded_volume_mt || 0);
      elVol.textContent = `${totalMT} MT`;
    }

    const elParties = document.getElementById('kpi-active-parties');
    if (elParties) elParties.textContent = metrics.active_parties_count ?? (this.parties?.length || 0);

    const elPending = document.getElementById('kpi-pending-confirmations');
    if (elPending) {
      elPending.textContent = metrics.pending_confirmations_count ?? (this.deals?.filter(d => d.status === 'PENDING' || d.reconfirmation_required || !d.is_buyer_confirmed || !d.is_seller_confirmed).length || 0);
    }

    // 2. Today's Bargains (Table vs Empty State)
    const theadTodays = document.getElementById('thead-todays-bargains');
    const tbodyTodays = document.getElementById('tbody-todays-bargains');
    const emptyStateTodays = document.getElementById('empty-state-todays-bargains');

    const now = new Date();
    const localToday = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const utcToday = now.toISOString().split('T')[0];
    const todayDeals = (this.deals || []).filter(d => !d.is_deleted && (d.deal_date === localToday || d.deal_date === utcToday));

    if (todayDeals.length === 0) {
      if (theadTodays) theadTodays.style.display = 'none';
      if (tbodyTodays) tbodyTodays.innerHTML = '';
      if (emptyStateTodays) emptyStateTodays.style.display = 'block';
    } else {
      if (theadTodays) theadTodays.style.display = '';
      if (emptyStateTodays) emptyStateTodays.style.display = 'none';
      if (tbodyTodays) {
        tbodyTodays.innerHTML = todayDeals.map(d => {
          const bgn = d.bgn_code || d.id;
          const sName = d.seller_name ? d.seller_name.split(',')[0] : 'Seller';
          const bName = d.buyer_name ? d.buyer_name.split(',')[0] : 'Buyer';
          const sStation = d.seller_station || '';
          const bStation = d.buyer_station || '';
          const tonnes = d.quantity_tonnes ? Number(d.quantity_tonnes.toFixed(1)) : Number(((d.quantity_qtl || 0) * 0.1).toFixed(1));
          const qty = `${tonnes} MT`;
          const sRate = d.seller_rate || d.rate_per_qtl || 0;
          const bRate = d.buyer_rate || d.rate_per_qtl || sRate;
          let rateHtml = `<span class="cell-rate-single">₹${Math.round(sRate).toLocaleString('en-IN')}</span>`;
          if (Math.round(sRate) !== Math.round(bRate)) {
            rateHtml = `
              <div class="cell-rate-dual">
                <span class="cell-rate-seller"><span class="cell-rate-label">Seller</span>₹${Math.round(sRate).toLocaleString('en-IN')}</span>
                <span class="cell-rate-buyer"><span class="cell-rate-label">Buyer</span>₹${Math.round(bRate).toLocaleString('en-IN')}</span>
              </div>
            `;
          }

          let statusClass = 'confirmed';
          let statusText = d.status || 'CONFIRMED';
          if (d.status === 'PENDING') statusClass = 'pending';
          else if (d.status === 'CANCELLED') statusClass = 'cancelled';
          else if (d.status === 'DRAFT') statusClass = 'draft';

          const reconfirmBadge = d.reconfirmation_required ? 
            `<span class="status-tag status-tag-reconfirm" title="Commercial terms updated - reconfirmation required">Reconfirm Req.</span>` : '';
          const confStatus = `Buyer ${d.is_buyer_confirmed ? '✓' : '—'} · Seller ${d.is_seller_confirmed ? '✓' : '—'}`;
          const formattedDate = this.formatDateCompact(d.deal_date);

          return `
            <tr>
              <td>
                <a class="cell-bgn-id" onclick="app.openLetterheadModal('${d.id}')" title="View Official Confirmation">${bgn}</a>
              </td>
              <td class="mono" style="font-size: 12px; color: var(--text-muted); white-space: nowrap;">${formattedDate}</td>
              <td>
                <div class="cell-party-block">
                  <span class="cell-party-name">${this.escapeHtml(this.formatCompanyName(sName))}</span>
                  ${sStation ? `<span class="cell-party-sub">${this.escapeHtml(sStation)}</span>` : ''}
                </div>
              </td>
              <td>
                <div class="cell-party-block">
                  <span class="cell-party-name">${this.escapeHtml(this.formatCompanyName(bName))}</span>
                  ${bStation ? `<span class="cell-party-sub">${this.escapeHtml(bStation)}</span>` : ''}
                </div>
              </td>
              <td>
                <span style="font-weight: 500;">${this.escapeHtml(d.product_name || '—')}</span>
              </td>
              <td class="mono" style="font-weight: 500; white-space: nowrap;">${qty}</td>
              <td>${rateHtml}</td>
              <td>
                <div class="cell-status-block">
                  <div style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap;">
                    <span class="status-tag status-tag-${statusClass}">${statusText}</span>
                    ${reconfirmBadge}
                  </div>
                  <span class="cell-confirmation-sub">${confStatus}</span>
                </div>
              </td>
              <td style="text-align: right; white-space: nowrap;">
                <div class="table-actions-group">
                  <button class="btn btn-secondary btn-xs" onclick="app.openEditBargainModal('${d.id}')" title="Edit Bargain">
                    <i data-lucide="edit-3" style="width: 12px; height: 12px;"></i>
                    <span>Edit</span>
                  </button>
                  <button class="btn btn-secondary btn-xs" onclick="app.openDispatchModal('${d.id}')" title="Dispatch via WhatsApp / Email">
                    <i data-lucide="send" style="width: 12px; height: 12px;"></i>
                    <span>Send</span>
                  </button>
                  <div class="action-dropdown-container">
                    <button class="btn btn-ghost btn-xs" onclick="app.toggleActionDropdown('dash-${d.id}', event)" title="More Actions">
                      <i data-lucide="more-horizontal" style="width: 13px; height: 13px;"></i>
                    </button>
                    <div class="action-dropdown-menu" id="dropdown-dash-${d.id}">
                      <button type="button" class="dropdown-item" onclick="app.downloadContractPdf('${d.id}', 'SELLER')">
                        <i data-lucide="file-text" style="width: 12px; height: 12px;"></i>
                        <span>Seller PDF</span>
                      </button>
                      <button type="button" class="dropdown-item" onclick="app.downloadContractPdf('${d.id}', 'BUYER')">
                        <i data-lucide="file-text" style="width: 12px; height: 12px;"></i>
                        <span>Buyer PDF</span>
                      </button>
                      <button type="button" class="dropdown-item" onclick="app.openLetterheadModal('${d.id}')">
                        <i data-lucide="printer" style="width: 12px; height: 12px;"></i>
                        <span>Letterhead</span>
                      </button>
                      <div class="dropdown-divider"></div>
                      <button type="button" class="dropdown-item text-danger" onclick="app.trashDeal('${d.id}')">
                        <i data-lucide="trash-2" style="width: 12px; height: 12px;"></i>
                        <span>Move to Trash</span>
                      </button>
                    </div>
                  </div>
                </div>
              </td>
            </tr>
          `;
        }).join('');
      }
    }

    // 3. Needs Attention Operational Section
    const theadAttention = document.getElementById('thead-needs-attention');
    const tbodyAttention = document.getElementById('tbody-needs-attention');
    const emptyStateAttention = document.getElementById('empty-state-needs-attention');
    const badgeAttention = document.getElementById('badge-needs-attention-count');

    const needsAttentionDeals = (this.deals || []).filter(d => {
      if (d.is_deleted) return false;
      if (d.status === 'PENDING') return true;
      if (d.reconfirmation_required === 1 || d.reconfirmation_required === true) return true;
      if (!d.is_buyer_confirmed || !d.is_seller_confirmed) return true;
      return false;
    });

    if (badgeAttention) {
      if (needsAttentionDeals.length > 0) {
        badgeAttention.textContent = needsAttentionDeals.length;
        badgeAttention.style.display = 'inline-block';
      } else {
        badgeAttention.textContent = '';
        badgeAttention.style.display = 'none';
      }
    }

    if (needsAttentionDeals.length === 0) {
      if (theadAttention) theadAttention.style.display = 'none';
      if (tbodyAttention) tbodyAttention.innerHTML = '';
      if (emptyStateAttention) emptyStateAttention.style.display = 'block';
    } else {
      if (theadAttention) theadAttention.style.display = '';
      if (emptyStateAttention) emptyStateAttention.style.display = 'none';
      if (tbodyAttention) {
        tbodyAttention.innerHTML = needsAttentionDeals.map(d => {
          const bgn = d.bgn_code || d.id;
          const sName = d.seller_name ? d.seller_name.split(',')[0] : 'Seller';
          const bName = d.buyer_name ? d.buyer_name.split(',')[0] : 'Buyer';
          const tonnes = d.quantity_tonnes ? Number(d.quantity_tonnes.toFixed(1)) : Number(((d.quantity_qtl || 0) * 0.1).toFixed(1));
          const formattedDate = this.formatDateCompact(d.deal_date);

          let issueBadge = '';
          let issueDesc = '';
          if (d.reconfirmation_required) {
            issueBadge = '<span class="status-tag status-tag-reconfirm">Reconfirm Req.</span>';
            issueDesc = 'Commercial terms modified';
          } else if (d.status === 'PENDING') {
            issueBadge = '<span class="status-tag status-tag-pending">Pending</span>';
            issueDesc = 'Awaiting initial confirmation';
          } else if (!d.is_buyer_confirmed && !d.is_seller_confirmed) {
            issueBadge = '<span class="status-tag status-tag-pending">Pending Both</span>';
            issueDesc = 'Awaiting buyer & seller';
          } else if (!d.is_buyer_confirmed) {
            issueBadge = '<span class="status-tag status-tag-pending">Pending Buyer</span>';
            issueDesc = 'Awaiting buyer confirmation';
          } else if (!d.is_seller_confirmed) {
            issueBadge = '<span class="status-tag status-tag-pending">Pending Seller</span>';
            issueDesc = 'Awaiting seller confirmation';
          }

          return `
            <tr>
              <td>
                <a class="cell-bgn-id" onclick="app.openLetterheadModal('${d.id}')" title="View Official Confirmation">${bgn}</a>
              </td>
              <td class="mono" style="font-size: 12px; color: var(--text-muted); white-space: nowrap;">${formattedDate}</td>
              <td>
                <div class="cell-party-block">
                  <span class="cell-party-name">${this.escapeHtml(this.formatCompanyName(sName))} &rarr; ${this.escapeHtml(this.formatCompanyName(bName))}</span>
                </div>
              </td>
              <td style="font-size: 13px;">
                <span style="font-weight: 500;">${this.escapeHtml(d.product_name || '—')}</span>
                <span class="mono" style="color: var(--text-muted); margin-left: 6px;">${tonnes} MT</span>
              </td>
              <td>
                <div style="display: flex; align-items: center; gap: 6px;">
                  ${issueBadge}
                  <span style="font-size: 12px; color: var(--text-secondary);">${issueDesc}</span>
                </div>
              </td>
              <td style="text-align: right; white-space: nowrap;">
                <div class="table-actions-group" style="justify-content: flex-end;">
                  <button class="btn btn-secondary btn-xs" onclick="app.openDispatchModal('${d.id}')" title="Dispatch Confirmation">
                    <i data-lucide="send" style="width: 12px; height: 12px;"></i>
                    <span>Send</span>
                  </button>
                  <button class="btn btn-secondary btn-xs" onclick="app.openEditBargainModal('${d.id}')" title="Edit Bargain">
                    <i data-lucide="edit-3" style="width: 12px; height: 12px;"></i>
                    <span>Edit</span>
                  </button>
                </div>
              </td>
            </tr>
          `;
        }).join('');
      }
    }

    if (window.lucide) {
      lucide.createIcons();
    }
  },

  // ==========================================================================
  // SCREEN 2: BARGAINS HUB
  // ==========================================================================
  renderBargainsHub() {
    const tbody = document.getElementById('tbody-all-bargains');
    if (!tbody) return;

    let filtered = [...this.deals];

    // Status filter
    if (this.activeStatusFilter !== 'ALL') {
      filtered = filtered.filter(d => d.status === this.activeStatusFilter);
    }

    // Text search filter
    if (this.searchQuery) {
      const q = this.searchQuery.toLowerCase();
      filtered = filtered.filter(d => {
        return (
          (d.bgn_code && d.bgn_code.toLowerCase().includes(q)) ||
          (d.seller_name && d.seller_name.toLowerCase().includes(q)) ||
          (d.buyer_name && d.buyer_name.toLowerCase().includes(q)) ||
          (d.seller_station && d.seller_station.toLowerCase().includes(q)) ||
          (d.buyer_station && d.buyer_station.toLowerCase().includes(q)) ||
          (d.product_name && d.product_name.toLowerCase().includes(q))
        );
      });
    }

    // Sorting
    filtered.sort((a, b) => {
      if (this.sortBy === 'date-desc') return new Date(b.deal_date) - new Date(a.deal_date);
      if (this.sortBy === 'date-asc') return new Date(a.deal_date) - new Date(b.deal_date);
      if (this.sortBy === 'rate-desc') return (b.seller_rate || b.rate_per_qtl) - (a.seller_rate || a.rate_per_qtl);
      if (this.sortBy === 'rate-asc') return (a.seller_rate || a.rate_per_qtl) - (b.seller_rate || b.rate_per_qtl);
      if (this.sortBy === 'qty-desc') return b.quantity_tonnes - a.quantity_tonnes;
      return 0;
    });

    this.visibleBargains = filtered;

    if (filtered.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="10">
            <div class="table-empty-state">
              <i data-lucide="search-x" style="width: 28px; height: 28px; color: var(--text-dim); margin-bottom: 8px;"></i>
              <div style="font-size: 14px; font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">No matching bargains</div>
              <div style="font-size: 12.5px; color: var(--text-muted); margin-bottom: 14px;">Try clearing search keywords or active filters.</div>
              <button class="btn btn-secondary btn-sm" onclick="app.resetFilters()">
                <span>Reset Filters</span>
              </button>
            </div>
          </td>
        </tr>
      `;
    } else {
      tbody.innerHTML = this.buildDealsTableRows(filtered, true);
    }

    // Sync master checkbox & bulk action bar
    this.updateBulkActionBar();

    const masterChk = document.getElementById('check-all-bargains');
    if (masterChk) {
      masterChk.checked = filtered.length > 0 && filtered.every(d => this.selectedDealIds.has(d.id));
      masterChk.indeterminate = filtered.some(d => this.selectedDealIds.has(d.id)) && !masterChk.checked;
      masterChk.onclick = (e) => this.toggleSelectAllBargains(e.target.checked);
    }

    // Wire bulk bar buttons if not already wired
    document.getElementById('btn-bulk-clear')?.addEventListener('click', () => {
      this.selectedDealIds.clear();
      this.renderBargainsHub();
    });

    document.getElementById('btn-bulk-delete')?.addEventListener('click', () => {
      this.bulkDeleteSelected();
    });

    if (window.lucide) {
      lucide.createIcons();
    }
  },

  toggleSelectAllBargains(checked) {
    if (!this.visibleBargains) return;
    if (checked) {
      this.visibleBargains.forEach(d => this.selectedDealIds.add(d.id));
    } else {
      this.visibleBargains.forEach(d => this.selectedDealIds.delete(d.id));
    }
    this.renderBargainsHub();
  },

  toggleSelectDeal(dealId, checked) {
    if (checked) {
      this.selectedDealIds.add(dealId);
    } else {
      this.selectedDealIds.delete(dealId);
    }
    this.updateBulkActionBar();
    const masterChk = document.getElementById('check-all-bargains');
    if (masterChk && this.visibleBargains) {
      masterChk.checked = this.visibleBargains.length > 0 && this.visibleBargains.every(d => this.selectedDealIds.has(d.id));
      masterChk.indeterminate = this.visibleBargains.some(d => this.selectedDealIds.has(d.id)) && !masterChk.checked;
    }
  },

  updateBulkActionBar() {
    const bulkBar = document.getElementById('bulk-action-bar');
    const countEl = document.getElementById('bulk-selected-count');
    const count = this.selectedDealIds.size;

    if (!bulkBar) return;

    if (count > 0) {
      bulkBar.style.display = 'flex';
      if (countEl) countEl.textContent = `${count} selected`;
    } else {
      bulkBar.style.display = 'none';
    }
  },

  async bulkDeleteSelected() {
    const count = this.selectedDealIds.size;
    if (count === 0) return;

    if (!confirm(`Move ${count} bargains to Recycle Bin?\n\nThe selected bargains can be restored later.`)) return;

    try {
      const dealIds = Array.from(this.selectedDealIds);
      const res = await this.api('/api/deals/bulk-delete', {
        method: 'POST',
        body: JSON.stringify({ deal_ids: dealIds })
      });

      this.showToast(`✓ Moved ${res.deleted_count || count} bargains to Recycle Bin`, 'success');
      this.selectedDealIds.clear();
      await this.fetchDeals();
      await this.fetchTrashDeals();
      await this.fetchDashboardMetrics();
      this.updateCounters();
      this.renderCurrentView();
    } catch (err) {
      this.showToast('Bulk move to Recycle Bin failed: ' + err.message, 'error');
    }
  },

  buildDealsTableRows(dealsList, showFullActions = false) {
    return dealsList.map(d => {
      const bgn = d.bgn_code || d.id;
      const sName = d.seller_name || 'Seller';
      const bName = d.buyer_name || 'Buyer';
      const sStation = d.seller_station || '';
      const bStation = d.buyer_station || '';

      const sRate = d.seller_rate || d.rate_per_qtl || 0;
      const bRate = d.buyer_rate || d.rate_per_qtl || sRate;
      let rateHtml = `<span class="cell-rate-single">₹${Math.round(sRate).toLocaleString('en-IN')}</span>`;
      if (Math.round(sRate) !== Math.round(bRate)) {
        rateHtml = `
          <div class="cell-rate-dual">
            <span class="cell-rate-seller"><span class="cell-rate-label">Seller</span>₹${Math.round(sRate).toLocaleString('en-IN')}</span>
            <span class="cell-rate-buyer"><span class="cell-rate-label">Buyer</span>₹${Math.round(bRate).toLocaleString('en-IN')}</span>
          </div>
        `;
      }

      const tonnes = d.quantity_tonnes ? Number(d.quantity_tonnes.toFixed(1)) : Number((d.quantity_qtl * 0.1).toFixed(1));
      const qtyStr = `${tonnes} MT`;

      let statusClass = 'confirmed';
      let statusText = d.status || 'CONFIRMED';
      if (d.status === 'PENDING') statusClass = 'pending';
      else if (d.status === 'CANCELLED') statusClass = 'cancelled';
      else if (d.status === 'DRAFT') statusClass = 'draft';

      const reconfirmBadge = d.reconfirmation_required ? 
        `<span class="status-tag status-tag-reconfirm" title="Commercial terms updated - reconfirmation required">Reconfirm Req.</span>` : '';
      
      const confStatus = `Buyer ${d.is_buyer_confirmed ? '✓' : '—'} · Seller ${d.is_seller_confirmed ? '✓' : '—'}`;
      const isChecked = this.selectedDealIds.has(d.id);
      const formattedDate = this.formatDateCompact(d.deal_date);

      return `
        <tr>
          <td style="text-align: center; width: 38px;">
            <input type="checkbox" class="deal-chk" data-deal-id="${d.id}" ${isChecked ? 'checked' : ''} onchange="app.toggleSelectDeal('${d.id}', this.checked)">
          </td>
          <td>
            <a class="cell-bgn-id" onclick="app.openLetterheadModal('${d.id}')" title="View Official Confirmation">${bgn}</a>
          </td>
          <td class="mono" style="font-size: 12px; color: var(--text-muted); white-space: nowrap;">${formattedDate}</td>
          <td>
            <div class="cell-party-block">
              <span class="cell-party-name">${this.escapeHtml(this.formatCompanyName(sName))}</span>
              ${sStation ? `<span class="cell-party-sub">${this.escapeHtml(sStation)}</span>` : ''}
            </div>
          </td>
          <td>
            <div class="cell-party-block">
              <span class="cell-party-name">${this.escapeHtml(this.formatCompanyName(bName))}</span>
              ${bStation ? `<span class="cell-party-sub">${this.escapeHtml(bStation)}</span>` : ''}
            </div>
          </td>
          <td>
            <span style="font-weight: 500;">${this.escapeHtml(d.product_name || '—')}</span>
          </td>
          <td class="mono" style="font-weight: 500; white-space: nowrap;">${qtyStr}</td>
          <td>${rateHtml}</td>
          <td>
            <div class="cell-status-block">
              <div style="display: flex; align-items: center; gap: 4px; flex-wrap: wrap;">
                <span class="status-tag status-tag-${statusClass}">${statusText}</span>
                ${reconfirmBadge}
              </div>
              <span class="cell-confirmation-sub">${confStatus}</span>
            </div>
          </td>
          <td style="text-align: right; white-space: nowrap;">
            <div class="table-actions-group">
              <button class="btn btn-secondary btn-xs" onclick="app.openEditBargainModal('${d.id}')" title="Edit Bargain">
                <i data-lucide="edit-3" style="width: 12px; height: 12px;"></i>
                <span>Edit</span>
              </button>
              <button class="btn btn-secondary btn-xs" onclick="app.openDispatchModal('${d.id}')" title="Dispatch via WhatsApp / Email">
                <i data-lucide="send" style="width: 12px; height: 12px;"></i>
                <span>Send</span>
              </button>
              <div class="action-dropdown-container">
                <button class="btn btn-ghost btn-xs" onclick="app.toggleActionDropdown('${d.id}', event)" title="More Actions">
                  <i data-lucide="more-horizontal" style="width: 13px; height: 13px;"></i>
                </button>
                <div class="action-dropdown-menu" id="dropdown-${d.id}">
                  <button type="button" class="dropdown-item" onclick="app.downloadContractPdf('${d.id}', 'SELLER')">
                    <i data-lucide="file-text" style="width: 12px; height: 12px;"></i>
                    <span>Seller PDF</span>
                  </button>
                  <button type="button" class="dropdown-item" onclick="app.downloadContractPdf('${d.id}', 'BUYER')">
                    <i data-lucide="file-text" style="width: 12px; height: 12px;"></i>
                    <span>Buyer PDF</span>
                  </button>
                  <button type="button" class="dropdown-item" onclick="app.openLetterheadModal('${d.id}')">
                    <i data-lucide="printer" style="width: 12px; height: 12px;"></i>
                    <span>Letterhead</span>
                  </button>
                  <div class="dropdown-divider"></div>
                  <button type="button" class="dropdown-item text-danger" onclick="app.trashDeal('${d.id}')">
                    <i data-lucide="trash-2" style="width: 12px; height: 12px;"></i>
                    <span>Move to Trash</span>
                  </button>
                </div>
              </div>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  },

  // ==========================================================================
  // SCREEN 4: PARTY DIRECTORY
  // ==========================================================================
  renderPartyDirectory() {
    const container = document.getElementById('party-cards-container');
    if (!container) return;

    let filtered = [...this.parties];

    // Segmented party type filter
    if (this.activePartyFilter !== 'ALL') {
      filtered = filtered.filter(p => p.party_type === this.activePartyFilter || p.party_type === 'BOTH');
    }

    // Party search input
    if (this.partySearchQuery) {
      const q = this.partySearchQuery.toLowerCase();
      filtered = filtered.filter(p => {
        return (
          (p.legal_name && p.legal_name.toLowerCase().includes(q)) ||
          (p.trade_name && p.trade_name.toLowerCase().includes(q)) ||
          (p.mandi_station && p.mandi_station.toLowerCase().includes(q)) ||
          (p.city && p.city.toLowerCase().includes(q)) ||
          (p.gstin && p.gstin.toLowerCase().includes(q)) ||
          (p.pan && p.pan.toLowerCase().includes(q)) ||
          (p.contact_person && p.contact_person.toLowerCase().includes(q))
        );
      });
    }

    if (filtered.length === 0) {
      container.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 40px; color: var(--text-dim);">
            No parties match your search criteria.
          </td>
        </tr>
      `;
      return;
    }

    container.innerHTML = filtered.map(p => {
      const station = p.mandi_station || p.city || '—';
      const pan = p.pan || (p.gstin ? p.gstin.substring(2, 12) : '—');
      const gstin = p.gstin || '—';

      // Parse contacts hierarchy
      let contacts = [];
      if (p.contacts_json) {
        try { contacts = JSON.parse(p.contacts_json); } catch (_) {}
      }
      if (!contacts.length) {
        contacts = [{ name: p.contact_person || 'Signatory', role: 'Owner', phone: p.phone || '', email: p.email || '' }];
      }

      const primaryContact = contacts[0] || {};
      const cleanPhone = (primaryContact.phone || p.phone || '').replace(/[^0-9]/g, '');
      const waLink = cleanPhone ? `https://wa.me/${cleanPhone}?text=${encodeURIComponent(`Namaste ${primaryContact.name || p.legal_name} Ji, Greetings from Ganesh & Company.`)}` : '';
      const dealCount = (this.deals || []).filter(d => d.seller_id === p.id || d.buyer_id === p.id).length;

      let typeBadgeClass = 'status-tag-draft';
      if (p.party_type === 'SELLER') typeBadgeClass = 'status-tag-pending';
      else if (p.party_type === 'BUYER') typeBadgeClass = 'status-tag-confirmed';
      else if (p.party_type === 'BOTH') typeBadgeClass = 'status-tag-revised';

      return `
        <tr>
          <td>
            <div class="cell-party-block">
              <a class="cell-party-name" style="cursor: pointer;" onclick="app.openPartyProfileModal('${p.id}')">${this.escapeHtml(this.formatCompanyName(p.legal_name))}</a>
              <span class="cell-party-sub">GSTIN: ${this.escapeHtml(gstin)} · PAN: ${this.escapeHtml(pan)}</span>
            </div>
          </td>
          <td>
            <span style="color: var(--text-main); font-weight: 500;">${this.escapeHtml(station)}</span>
          </td>
          <td>
            <span class="status-tag ${typeBadgeClass}">${this.escapeHtml(p.party_type || 'DUAL')}</span>
          </td>
          <td>
            <span style="font-weight: 500;">${this.escapeHtml(primaryContact.name || p.contact_person || '—')}</span>
            ${primaryContact.role ? `<span style="font-size: 11px; color: var(--text-dim); display: block;">${this.escapeHtml(primaryContact.role)}</span>` : ''}
          </td>
          <td>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span class="mono" style="font-size: 12px;">${this.escapeHtml(primaryContact.phone || p.phone || '—')}</span>
              ${waLink ? `
                <a href="${waLink}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost btn-xs" title="Chat on WhatsApp" style="padding: 2px 5px; color: #2EA043;">
                  <i data-lucide="message-circle" style="width: 12px; height: 12px;"></i>
                </a>
              ` : ''}
            </div>
          </td>
          <td style="color: var(--text-muted); font-size: 12px;">
            ${this.escapeHtml(primaryContact.email || p.email || '—')}
          </td>
          <td class="mono" style="font-weight: 600; color: var(--text-primary);">
            ${dealCount}
          </td>
          <td style="text-align: right; white-space: nowrap;">
            <div class="table-actions-group">
              <button class="btn btn-secondary btn-xs" onclick="app.openNewBargainForParty('${p.id}')" title="Create Deal">
                <i data-lucide="plus" style="width: 11px; height: 11px;"></i>
                <span>Deal</span>
              </button>
              <button class="btn btn-ghost btn-xs" onclick="app.openPartyProfileModal('${p.id}')" title="View Profile">
                <i data-lucide="eye" style="width: 12px; height: 12px;"></i>
              </button>
              <button class="btn btn-ghost btn-xs" onclick="app.openEditPartyModal('${p.id}')" title="Edit Party">
                <i data-lucide="pencil" style="width: 12px; height: 12px;"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    if (window.lucide) {
      lucide.createIcons();
    }
  },

  // ==========================================================================
  // SCREEN 3: AUTHENTIC A4 CONFIRMATION PRINT VIEW
  // ==========================================================================
  openLetterheadModal(dealId, role = 'SELLER') {
    const deal = this.deals.find(d => d.id === dealId) || this.trashDeals.find(d => d.id === dealId);
    if (!deal) {
      this.showToast('Contract not found', 'error');
      return;
    }

    this.selectedDealForLetterhead = deal;
    const bgn = deal.bgn_code || deal.id;

    // Populate official document
    document.getElementById('doc-bgn-code').textContent = bgn;
    document.getElementById('doc-date').textContent = deal.deal_date;
    document.getElementById('doc-seller').textContent = (deal.seller_name || 'Seller Firm').toUpperCase();
    document.getElementById('doc-buyer').textContent = (deal.buyer_name || 'Buyer Firm').toUpperCase();
    document.getElementById('doc-commodity').textContent = deal.product_name;

    const tonnes = deal.quantity_tonnes ? deal.quantity_tonnes : (deal.quantity_qtl * 0.1);
    const qtl = deal.quantity_qtl ? deal.quantity_qtl : (tonnes * 10);
    document.getElementById('doc-quantity').textContent = `${tonnes.toFixed(1)} Tons (${qtl.toFixed(0)} Quintals)`;

    document.getElementById('doc-advance-date').textContent = deal.advance_payment_date || deal.deal_date;
    document.getElementById('doc-delivery-condition').textContent = deal.delivery_condition || `Ex-Mill Delivery Lifting: ${deal.deal_date} to ${deal.delivery_date}`;

    // Apply role-specific rate & labels
    this.setLetterheadRole(role);

    // System-generated timestamp at bottom of PDF
    const nowStr = new Date().toLocaleString('en-IN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    const metaEl = document.getElementById('doc-system-meta');
    if (metaEl) {
      metaEl.textContent = `Computer Generated on ${nowStr} via Ganesh & Company Central Platform • Sri Ganganagar (Raj.) • Valid across all Mandis without signature`;
    }

    const modal = document.getElementById('modal-letterhead');
    if (modal) modal.classList.add('active');

    if (window.lucide) lucide.createIcons();
  },

  setLetterheadRole(role) {
    this.currentLetterheadRole = role;
    const deal = this.selectedDealForLetterhead;
    if (!deal) return;

    const sellerBtn = document.getElementById('btn-copy-seller');
    const buyerBtn = document.getElementById('btn-copy-buyer');
    const roleBadge = document.getElementById('doc-role-badge');
    const rateEl = document.getElementById('doc-rate');

    if (sellerBtn) sellerBtn.classList.toggle('active', role === 'SELLER');
    if (buyerBtn) buyerBtn.classList.toggle('active', role === 'BUYER');

    if (roleBadge) {
      roleBadge.textContent = role === 'SELLER' ? '(SELLER COPY)' : '(BUYER COPY)';
    }

    if (rateEl) {
      const targetRate = role === 'SELLER' 
        ? (deal.seller_rate || deal.rate_per_qtl || 0)
        : (deal.buyer_rate || deal.seller_rate || deal.rate_per_qtl || 0);
      rateEl.textContent = `₹${Math.round(targetRate).toLocaleString('en-IN')} + GST Per Qt.`;
    }
  },

  // Official PDF Generator / Downloader
  downloadContractPdf(dealId, forcedRole = null) {
    const deal = dealId 
      ? (this.deals.find(d => d.id === dealId) || this.trashDeals.find(d => d.id === dealId))
      : (this.selectedDealForLetterhead || this.selectedDealForDispatch || this.deals[0]);
    
    if (!deal) return;
    const role = forcedRole || this.currentLetterheadRole || 'SELLER';
    const bgn = deal.bgn_code || deal.id;
    const filename = `Bargain_Confirmation_${bgn}_${role}.pdf`;

    this.showToast(`Downloading official ${role} system PDF: ${filename}...`, 'info');

    // Instant download from backend server generating strict role-confidential PDF
    const link = document.createElement('a');
    link.href = `/api/deals/${deal.id}/pdf?role=${role}`;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  },

  // Print Trigger
  triggerPrint() {
    window.print();
  },

  // ==========================================================================
  // SCREEN 5: PARTY PROFILE MODAL
  // ==========================================================================
  // SCREEN 4: PARTY PROFILE / DETAILS MODAL
  // ==========================================================================
  async openPartyProfileModal(partyId) {
    try {
      this.currentProfilePartyId = partyId;
      const data = await this.api(`/api/parties/${partyId}/profile`);
      const party = data.party;
      const kpis = data.kpis;

      const nameEl = document.getElementById('profile-party-name');
      if (nameEl) nameEl.textContent = this.formatCompanyName(party.legal_name);

      const stationEl = document.getElementById('prof-kpi-station');
      if (stationEl) stationEl.textContent = party.mandi_station || party.city || 'Mandi Yard';

      const typeEl = document.getElementById('prof-party-type');
      if (typeEl) typeEl.textContent = (party.party_type || 'BOTH').toUpperCase();

      // Compact useful statistics
      const dealsEl = document.getElementById('prof-kpi-deals');
      if (dealsEl) dealsEl.textContent = kpis.total_deals || 0;
      const volEl = document.getElementById('prof-kpi-volume');
      if (volEl) volEl.textContent = `${Math.round(kpis.confirmed_volume_mt || 0)} MT`;
      const pendEl = document.getElementById('prof-kpi-pending');
      if (pendEl) pendEl.textContent = kpis.pending_deals || 0;

      // Masked Bank Account Number
      const rawAcc = party.bank_account_no || '';
      const maskedAcc = rawAcc.length > 5 ? '•••• ' + rawAcc.slice(-5) : (rawAcc || 'N/A');

      const bankHtml = party.bank_name ? `
        <div class="bank-details-card" style="margin-top: 10px;">
          <div class="bank-details-header">
            <span style="display: flex; align-items: center; gap: 6px; font-size: 11.5px; font-weight: 600; color: var(--text-primary);">
              <i data-lucide="landmark" style="width: 14px; height: 14px; color: var(--brand);"></i>
              <span>Bank Settlement Details</span>
            </span>
            <span style="font-size: 11px; color: var(--text-dim);">${this.escapeHtml(party.bank_branch || 'Mandi Branch')}</span>
          </div>
          <div class="bank-grid">
            <div class="bank-data-cell">
              <span>Bank: <strong style="color: var(--text-primary);">${this.escapeHtml(party.bank_name)}</strong></span>
            </div>
            <div class="bank-data-cell">
              <span>A/C: <strong class="mono" style="color: var(--text-primary);">${maskedAcc}</strong></span>
              <button type="button" class="btn btn-secondary btn-xs" onclick="app.copyToClipboard('${rawAcc}', 'Account Number copied!', this)" title="Copy Account Number">
                <i data-lucide="copy" style="width: 11px; height: 11px;"></i>
                <span>Copy A/C</span>
              </button>
            </div>
            <div class="bank-data-cell">
              <span>IFSC: <strong class="mono" style="color: var(--brand);">${this.escapeHtml(party.bank_ifsc || 'N/A')}</strong></span>
              <button type="button" class="btn btn-secondary btn-xs" onclick="app.copyToClipboard('${party.bank_ifsc || ''}', 'IFSC Code copied!', this)" title="Copy IFSC Code">
                <i data-lucide="copy" style="width: 11px; height: 11px;"></i>
                <span>Copy IFSC</span>
              </button>
            </div>
            <div class="bank-data-cell">
              <span>Branch: <span style="color: var(--text-primary);">${this.escapeHtml(party.bank_branch || 'Mandi Branch')}</span></span>
            </div>
          </div>
        </div>
      ` : `
        <div style="background: var(--bg-subtle); border: 1px dashed var(--border-subtle); border-radius: var(--radius-sm); padding: 12px; margin-top: 10px; display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: var(--text-secondary);">
          <span>No bank settlement account registered.</span>
          <button type="button" class="btn btn-secondary btn-xs" onclick="document.getElementById('modal-party-profile').classList.remove('active'); app.openEditPartyModal('${party.id}');">
            <i data-lucide="plus" style="width: 11px; height: 11px;"></i>
            <span>Add Bank Info</span>
          </button>
        </div>
      `;

      // Business details overview
      const metaEl = document.getElementById('prof-meta-details');
      if (metaEl) {
        metaEl.innerHTML = `
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; padding: 12px; background: var(--bg-subtle); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); font-size: 12px;">
            <div><span style="color: var(--text-dim);">Party Type:</span> <strong style="color: var(--text-primary);">${party.party_type}</strong></div>
            <div><span style="color: var(--text-dim);">Station:</span> <strong style="color: var(--text-primary);">${party.mandi_station || party.city || 'Mandi Yard'}</strong></div>
            <div><span style="color: var(--text-dim);">GSTIN:</span> <strong class="mono" style="color: var(--text-primary);">${party.gstin || 'Unregistered'}</strong></div>
            <div><span style="color: var(--text-dim);">PAN:</span> <strong class="mono" style="color: var(--text-primary);">${party.pan || (party.gstin ? party.gstin.substring(2, 12) : 'N/A')}</strong></div>
            <div style="grid-column: 1 / -1;"><span style="color: var(--text-dim);">Address:</span> <span style="color: var(--text-primary);">${party.address || 'Mandi Yard'}</span></div>
            <div><span style="color: var(--text-dim);">Credit Limit:</span> <strong class="mono" style="color: var(--text-primary);">₹${(party.credit_limit || 0).toLocaleString('en-IN')}</strong></div>
          </div>
          ${bankHtml}
        `;
      }

      // Contacts list
      const contactsEl = document.getElementById('prof-contacts-list');
      if (contactsEl) {
        if (!data.contacts.length) {
          contactsEl.innerHTML = `<div style="font-size: 12px; color: var(--text-dim); padding: 8px 0;">No contacts registered.</div>`;
        } else {
          contactsEl.innerHTML = data.contacts.map(c => `
            <div class="contact-row-item">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="contact-role-pill">${c.role || 'Contact'}</span>
                <strong style="color: var(--text-primary); font-size: 12.5px;">${c.name}</strong>
              </div>
              <div style="display: flex; align-items: center; gap: 12px; font-size: 12px; color: var(--text-secondary);">
                ${c.phone ? `<span class="mono">${c.phone}</span>` : ''}
                ${c.email ? `<span>${c.email}</span>` : ''}
                <div style="display: flex; gap: 4px;">
                  ${c.phone ? `<a href="tel:${c.phone.replace(/[^0-9]/g, '')}" class="btn btn-ghost btn-xs" title="Call"><i data-lucide="phone" style="width: 11px; height: 11px;"></i> <span>Call</span></a>` : ''}
                  ${c.phone ? `<a href="https://wa.me/${c.phone.replace(/[^0-9]/g, '')}" target="_blank" rel="noopener noreferrer" class="btn btn-ghost btn-xs" title="WhatsApp"><i data-lucide="message-circle" style="width: 11px; height: 11px;"></i> <span>WhatsApp</span></a>` : ''}
                  ${c.email ? `<a href="mailto:${c.email}" class="btn btn-ghost btn-xs" title="Email"><i data-lucide="mail" style="width: 11px; height: 11px;"></i> <span>Email</span></a>` : ''}
                </div>
              </div>
            </div>
          `).join('');
        }
      }

      // Deals list
      const dealsTbody = document.getElementById('tbody-prof-deals');
      if (dealsTbody) {
        if (!data.deals.length) {
          dealsTbody.innerHTML = `<tr><td colspan="9" style="text-align: center; padding: 24px; color: var(--text-dim);">No transactions on record.</td></tr>`;
        } else {
          dealsTbody.innerHTML = data.deals.map(d => `
            <tr>
              <td><a class="cell-bgn-id" onclick="app.openLetterheadModal('${d.id}')">${d.bgn_code || d.id}</a></td>
              <td class="mono">${this.formatDateCompact(d.deal_date)}</td>
              <td><span class="status-tag status-pending">${d.buyer_id === partyId ? 'BUYER' : 'SELLER'}</span></td>
              <td style="color: var(--text-primary);">${this.formatCompanyName(d.buyer_id === partyId ? d.seller_name : d.buyer_name)}</td>
              <td>${d.product_name}</td>
              <td class="mono">${(d.quantity_tonnes || d.quantity_qtl * 0.1).toFixed(1)} MT</td>
              <td class="rate-figure">₹${Math.round(d.rate_per_qtl).toLocaleString('en-IN')}</td>
              <td><span class="status-tag ${d.status === 'CONFIRMED' ? 'status-confirmed' : 'status-pending'}">${d.status}</span></td>
              <td>
                <button type="button" class="btn btn-secondary btn-xs" onclick="app.openLetterheadModal('${d.id}')">Letterhead</button>
              </td>
            </tr>
          `).join('');
        }
      }

      // Commodity bars
      const commBars = document.getElementById('prof-commodity-bars');
      if (commBars) {
        if (!data.commodity_history.length) {
          commBars.innerHTML = `<div style="color: var(--text-dim); text-align: center; padding: 24px;">No commodity trade history.</div>`;
        } else {
          commBars.innerHTML = data.commodity_history.map(item => `
            <div class="commodity-dist-item">
              <div class="commodity-info-row">
                <span class="commodity-name" style="font-weight: 500; color: var(--text-primary);">${item.product_name}</span>
                <span class="commodity-stats"><strong>${Math.round(item.total_tonnes)} MT</strong> (${item.percentage}%)</span>
              </div>
              <div class="progress-bar-bg" style="background: var(--border-subtle); height: 6px; border-radius: 3px; overflow: hidden; margin-top: 4px;">
                <div class="progress-bar-fill" style="width: ${item.percentage}%; background: var(--brand); height: 100%;"></div>
              </div>
            </div>
          `).join('');
        }
      }

      const modal = document.getElementById('modal-party-profile');
      if (modal) modal.classList.add('active');

      if (window.lucide) lucide.createIcons();
    } catch (err) {
      this.showToast('Failed to load party profile', 'error');
    }
  },

  // ==========================================================================
  // SCREEN 6: SEND BARGAIN CONFIRMATION (PARTY DIRECTORY AS SOURCE OF TRUTH)
  // ==========================================================================
  async openDispatchModal(dealId) {
    let deal = this.deals.find(d => d.id === dealId) || this.trashDeals.find(d => d.id === dealId);
    let details = null;

    try {
      details = await this.api(`/api/deals/${dealId}/confirmation-details`);
    } catch (e) {
      console.warn('Could not fetch confirmation details freshly:', e);
    }

    if (!deal && !details) return;

    const dData = details ? details.deal : deal;
    const seller = details ? details.seller : {
      id: deal.seller_id,
      name: deal.seller_name,
      station: deal.seller_station,
      email: (deal.seller_email || '').trim(),
      phone: (deal.seller_phone || '').trim(),
      has_email: Boolean((deal.seller_email || '').trim()),
      has_phone: Boolean((deal.seller_phone || '').trim()),
      rate: deal.seller_rate != null ? deal.seller_rate : deal.rate_per_qtl
    };
    const buyer = details ? details.buyer : {
      id: deal.buyer_id,
      name: deal.buyer_name,
      station: deal.buyer_station,
      email: (deal.buyer_email || '').trim(),
      phone: (deal.buyer_phone || '').trim(),
      has_email: Boolean((deal.buyer_email || '').trim()),
      has_phone: Boolean((deal.buyer_phone || '').trim()),
      rate: deal.buyer_rate != null ? deal.buyer_rate : deal.rate_per_qtl
    };

    this.selectedDealForDispatch = {
      ...(deal || {}),
      ...dData,
      seller_id: seller.id,
      seller_name: seller.name,
      seller_station: seller.station,
      seller_email: seller.email,
      seller_phone: seller.phone,
      seller_rate: seller.rate,
      buyer_id: buyer.id,
      buyer_name: buyer.name,
      buyer_station: buyer.station,
      buyer_email: buyer.email,
      buyer_phone: buyer.phone,
      buyer_rate: buyer.rate
    };
    this.selectedDealForLetterhead = this.selectedDealForDispatch;

    const bgn = dData.bgn_code || dData.id;
    const tonnes = dData.quantity_tonnes ? Number(dData.quantity_tonnes.toFixed(1)) : Number((dData.quantity_qtl * 0.1).toFixed(1));

    // Populate compact metadata header
    const bgnEl = document.getElementById('send-meta-bgn');
    if (bgnEl) bgnEl.textContent = bgn;
    const prodEl = document.getElementById('send-meta-product');
    if (prodEl) prodEl.textContent = dData.product_name;
    const qtyEl = document.getElementById('send-meta-quantity');
    if (qtyEl) qtyEl.textContent = `${tonnes} MT (${dData.quantity_qtl} Qtl)`;
    const dateEl = document.getElementById('send-meta-date');
    if (dateEl) dateEl.textContent = `Date: ${this.formatDateCompact(dData.deal_date)}`;

    // Seller Card
    const sNameEl = document.getElementById('send-seller-name');
    if (sNameEl) sNameEl.textContent = this.formatCompanyName(seller.name);
    const sStationEl = document.getElementById('send-seller-station');
    if (sStationEl) sStationEl.textContent = seller.station || 'Station unlisted';
    const sRateEl = document.getElementById('send-seller-rate');
    if (sRateEl) sRateEl.textContent = `₹${Math.round(seller.rate).toLocaleString('en-IN')} / Qtl`;
    
    const sEmailInput = document.getElementById('dispatch-seller-email');
    const sEmailChk = document.getElementById('chk-seller-email');
    const sEmailMissingNote = document.getElementById('seller-email-missing-note');
    const sBtnAddEmail = document.getElementById('btn-seller-add-email');
    
    if (sEmailInput) sEmailInput.value = seller.email || '';
    if (seller.has_email) {
      if (sEmailChk) { sEmailChk.checked = true; sEmailChk.disabled = false; }
      if (sEmailMissingNote) sEmailMissingNote.style.display = 'none';
      if (sEmailInput) sEmailInput.style.display = 'block';
    } else {
      if (sEmailChk) { sEmailChk.checked = false; sEmailChk.disabled = true; }
      if (sEmailMissingNote) sEmailMissingNote.style.display = 'inline';
      if (sBtnAddEmail) {
        sBtnAddEmail.onclick = () => {
          document.getElementById('modal-dispatch')?.classList.remove('active');
          this.openEditPartyModal(seller.id);
        };
      }
    }

    const sPhoneInput = document.getElementById('dispatch-seller-phone');
    const sPhoneChk = document.getElementById('chk-seller-wa');
    const sPhoneMissingNote = document.getElementById('seller-phone-missing-note');
    const sBtnAddPhone = document.getElementById('btn-seller-add-phone');

    if (sPhoneInput) sPhoneInput.value = seller.phone || '';
    if (seller.has_phone) {
      if (sPhoneChk) { sPhoneChk.checked = true; sPhoneChk.disabled = false; }
      if (sPhoneMissingNote) sPhoneMissingNote.style.display = 'none';
      if (sPhoneInput) sPhoneInput.style.display = 'block';
    } else {
      if (sPhoneChk) { sPhoneChk.checked = false; sPhoneChk.disabled = true; }
      if (sPhoneMissingNote) sPhoneMissingNote.style.display = 'inline';
      if (sBtnAddPhone) {
        sBtnAddPhone.onclick = () => {
          document.getElementById('modal-dispatch')?.classList.remove('active');
          this.openEditPartyModal(seller.id);
        };
      }
    }

    // Buyer Card
    const bNameEl = document.getElementById('send-buyer-name');
    if (bNameEl) bNameEl.textContent = this.formatCompanyName(buyer.name);
    const bStationEl = document.getElementById('send-buyer-station');
    if (bStationEl) bStationEl.textContent = buyer.station || 'Station unlisted';
    const bRateEl = document.getElementById('send-buyer-rate');
    if (bRateEl) bRateEl.textContent = `₹${Math.round(buyer.rate).toLocaleString('en-IN')} / Qtl`;

    const bEmailInput = document.getElementById('dispatch-buyer-email');
    const bEmailChk = document.getElementById('chk-buyer-email');
    const bEmailMissingNote = document.getElementById('buyer-email-missing-note');
    const bBtnAddEmail = document.getElementById('btn-buyer-add-email');

    if (bEmailInput) bEmailInput.value = buyer.email || '';
    if (buyer.has_email) {
      if (bEmailChk) { bEmailChk.checked = true; bEmailChk.disabled = false; }
      if (bEmailMissingNote) bEmailMissingNote.style.display = 'none';
      if (bEmailInput) bEmailInput.style.display = 'block';
    } else {
      if (bEmailChk) { bEmailChk.checked = false; bEmailChk.disabled = true; }
      if (bEmailMissingNote) bEmailMissingNote.style.display = 'inline';
      if (bBtnAddEmail) {
        bBtnAddEmail.onclick = () => {
          document.getElementById('modal-dispatch')?.classList.remove('active');
          this.openEditPartyModal(buyer.id);
        };
      }
    }

    const bPhoneInput = document.getElementById('dispatch-buyer-phone');
    const bPhoneChk = document.getElementById('chk-buyer-wa');
    const bPhoneMissingNote = document.getElementById('buyer-phone-missing-note');
    const bBtnAddPhone = document.getElementById('btn-buyer-add-phone');

    if (bPhoneInput) bPhoneInput.value = buyer.phone || '';
    if (buyer.has_phone) {
      if (bPhoneChk) { bPhoneChk.checked = true; bPhoneChk.disabled = false; }
      if (bPhoneMissingNote) bPhoneMissingNote.style.display = 'none';
      if (bPhoneInput) bPhoneInput.style.display = 'block';
    } else {
      if (bPhoneChk) { bPhoneChk.checked = false; bPhoneChk.disabled = true; }
      if (bPhoneMissingNote) bPhoneMissingNote.style.display = 'inline';
      if (bBtnAddPhone) {
        bBtnAddPhone.onclick = () => {
          document.getElementById('modal-dispatch')?.classList.remove('active');
          this.openEditPartyModal(buyer.id);
        };
      }
    }

    // Status Badges from fresh server query
    const dStatus = details?.dispatch_status || {};
    const sEmailSent = dStatus.seller_email === 'SENT';
    const bEmailSent = dStatus.buyer_email === 'SENT';
    const sWaSent = dStatus.seller_wa === 'SENT';
    const bWaSent = dStatus.buyer_wa === 'SENT';

    const sLabel = document.getElementById('label-seller-email-status');
    if (sLabel) sLabel.textContent = sEmailSent ? '✓ Email sent' : 'Email not sent';
    const sBadge = document.getElementById('status-badge-seller-email');
    if (sBadge) sBadge.className = `channel-status-badge ${sEmailSent ? 'sent' : ''}`;

    const bLabel = document.getElementById('label-buyer-email-status');
    if (bLabel) bLabel.textContent = bEmailSent ? '✓ Email sent' : 'Email not sent';
    const bBadge = document.getElementById('status-badge-buyer-email');
    if (bBadge) bBadge.className = `channel-status-badge ${bEmailSent ? 'sent' : ''}`;

    const sWaLabel = document.getElementById('label-seller-wa-status');
    if (sWaLabel) sWaLabel.textContent = sWaSent ? '✓ WhatsApp prepared' : 'WhatsApp not prepared';
    const sWaBadge = document.getElementById('status-badge-seller-wa');
    if (sWaBadge) sWaBadge.className = `channel-status-badge ${sWaSent ? 'sent' : ''}`;

    const bWaLabel = document.getElementById('label-buyer-wa-status');
    if (bWaLabel) bWaLabel.textContent = bWaSent ? '✓ WhatsApp prepared' : 'WhatsApp not prepared';
    const bWaBadge = document.getElementById('status-badge-buyer-wa');
    if (bWaBadge) bWaBadge.className = `channel-status-badge ${bWaSent ? 'sent' : ''}`;

    // Clean Human-Readable Preview (Confidential Rates strictly isolated per copy)
    const cleanPreview = 
`BARGAIN CONFIRMATION — GANESH & COMPANY
Bargain No: ${bgn} | Date: ${dData.deal_date}
Commodity: ${dData.product_name} | Quantity: ${tonnes} MT (${dData.quantity_qtl} Quintals)

Seller: ${this.formatCompanyName(seller.name)} (${seller.station || 'Station'})
Seller Rate: ₹${Math.round(seller.rate).toLocaleString('en-IN')}/Qtl + GST (Seller Copy)

Buyer: ${this.formatCompanyName(buyer.name)} (${buyer.station || 'Station'})
Buyer Rate: ₹${Math.round(buyer.rate).toLocaleString('en-IN')}/Qtl + GST (Buyer Copy)

Advance Date: ${dData.advance_payment_date || dData.deal_date}
Delivery Condition: ${dData.delivery_condition || 'Ex-Mill Lifting as per contract'}

Note: System-generated confirmation as Canvassing Agents. Subject to Sri Ganganagar Jurisdiction.
Contact: Sanjay Kumar Aggarwal (94619-40113)`;

    const previewBox = document.getElementById('send-preview-content');
    if (previewBox) {
      previewBox.textContent = cleanPreview;
      previewBox.classList.remove('active');
    }
    const chevron = document.getElementById('preview-chevron');
    if (chevron) chevron.style.transform = 'rotate(0deg)';

    // Show modal
    const modal = document.getElementById('modal-dispatch');
    if (modal) modal.classList.add('active');

    if (window.lucide) lucide.createIcons();
  },

  async sendPdfToBoth() {
    if (!this.selectedDealForDispatch) return;
    const deal = this.selectedDealForDispatch;
    const btn = document.getElementById('btn-dispatch-send-both');
    const label = document.getElementById('label-send-both');

    const sEmailChk = document.getElementById('chk-seller-email');
    const bEmailChk = document.getElementById('chk-buyer-email');

    const sEmail = (sEmailChk && !sEmailChk.checked) ? '' : (document.getElementById('dispatch-seller-email')?.value.trim() || '');
    const bEmail = (bEmailChk && !bEmailChk.checked) ? '' : (document.getElementById('dispatch-buyer-email')?.value.trim() || '');

    if (!sEmail && !bEmail) {
      this.showToast('Please enable and enter an email for at least one party', 'warning');
      return;
    }

    if (btn) btn.disabled = true;
    if (label) label.textContent = 'Sending...';

    try {
      let sentCount = 0;
      let errors = [];

      // Send to Seller if email present
      if (sEmail) {
        const sRes = await fetch('/api/dispatch/send-both', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            deal_id: deal.id,
            email: sEmail,
            role: 'SELLER'
          })
        });
        const sData = await sRes.json();
        if (sData.email?.success || sData.success) {
          sentCount++;
          document.getElementById('label-seller-email-status').textContent = '✓ Email sent';
          document.getElementById('status-badge-seller-email').className = 'channel-status-badge sent';
        } else if (sData.email?.error) {
          errors.push(`Seller: ${sData.email.error}`);
        }
      }

      // Send to Buyer if email present
      if (bEmail) {
        const bRes = await fetch('/api/dispatch/send-both', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            deal_id: deal.id,
            email: bEmail,
            role: 'BUYER'
          })
        });
        const bData = await bRes.json();
        if (bData.email?.success || bData.success) {
          sentCount++;
          document.getElementById('label-buyer-email-status').textContent = '✓ Email sent';
          document.getElementById('status-badge-buyer-email').className = 'channel-status-badge sent';
        } else if (bData.email?.error) {
          errors.push(`Buyer: ${bData.email.error}`);
        }
      }

      if (sentCount > 0) {
        this.showToast(`${sentCount} email${sentCount > 1 ? 's' : ''} dispatched successfully!`, 'success');
        if (typeof this.loadDeals === 'function') await this.loadDeals();
      } else if (errors.length) {
        this.showToast(`Dispatch note: ${errors.join(', ')}`, 'warning');
      }
    } catch (err) {
      console.error('Send to both error:', err);
      this.showToast(`Failed to send confirmation: ${err.message}`, 'error');
    } finally {
      if (btn) btn.disabled = false;
      if (label) label.textContent = 'Send to Both';
    }
  },

  async sendToSingleRole(role) {
    if (!this.selectedDealForDispatch) return;
    const deal = this.selectedDealForDispatch;
    const isSeller = role === 'SELLER';
    const email = document.getElementById(isSeller ? 'dispatch-seller-email' : 'dispatch-buyer-email')?.value.trim();
    const btn = document.getElementById(isSeller ? 'btn-seller-only' : 'btn-buyer-only');

    if (!email) {
      this.showToast(`Please specify ${isSeller ? 'Seller' : 'Buyer'} email address`, 'warning');
      return;
    }

    if (btn) btn.disabled = true;

    try {
      const resp = await fetch('/api/dispatch/send-both', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          deal_id: deal.id,
          email: email,
          role: role
        })
      });
      const data = await resp.json();

      if (data.email?.success || data.success) {
        const labelEl = document.getElementById(isSeller ? 'label-seller-email-status' : 'label-buyer-email-status');
        const badgeEl = document.getElementById(isSeller ? 'status-badge-seller-email' : 'status-badge-buyer-email');
        if (labelEl) labelEl.textContent = '✓ Email sent';
        if (badgeEl) badgeEl.className = 'channel-status-badge sent';
        this.showToast(`${isSeller ? 'Seller' : 'Buyer'} confirmation email sent!`, 'success');
        if (typeof this.loadDeals === 'function') await this.loadDeals();
      } else {
        this.showToast(`Delivery note: ${data.email?.error || 'Email queued'}`, 'info');
      }
    } catch (err) {
      this.showToast(`Could not send: ${err.message}`, 'error');
    } finally {
      if (btn) btn.disabled = false;
    }
  },

  prepareWhatsAppForRole(role) {
    const deal = this.selectedDealForDispatch;
    if (!deal) return;

    const isSeller = role === 'SELLER';
    const phone = document.getElementById(isSeller ? 'dispatch-seller-phone' : 'dispatch-buyer-phone')?.value.trim() || '';
    const phoneDigits = phone.replace(/[^0-9]/g, '');

    const bgn = deal.bgn_code || deal.id;
    const rateVal = isSeller 
      ? (deal.seller_rate != null ? deal.seller_rate : deal.rate_per_qtl)
      : (deal.buyer_rate != null ? deal.buyer_rate : deal.rate_per_qtl);
    const tonnes = deal.quantity_tonnes ? deal.quantity_tonnes.toFixed(0) : (deal.quantity_qtl * 0.1).toFixed(0);

    const waText = 
`*BARGAIN CONFIRMATION — GANESH & COMPANY* (${isSeller ? 'SELLER COPY' : 'BUYER COPY'})
*Sri Ganganagar, Rajasthan*
━━━━━━━━━━━━━━━━━━━━━━━━
*Bargain No:* ${bgn}
*Date:* ${deal.deal_date}
*Seller:* ${deal.seller_name.toUpperCase()}${deal.seller_station ? ` (${deal.seller_station})` : ''}
*Buyer:* ${deal.buyer_name.toUpperCase()}${deal.buyer_station ? ` (${deal.buyer_station})` : ''}
*Commodity:* ${deal.product_name}
*Quantity:* ${tonnes} Tons (${deal.quantity_qtl} Quintals)
*Rate:* Rs. ${Math.round(rateVal).toLocaleString('en-IN')} + GST Per Quintal
*Advance Date:* ${deal.advance_payment_date || deal.deal_date}
*Delivery Condition:* ${deal.delivery_condition || 'Ex-Mill Lifting as per contract'}
━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *Note:* This is a system-generated document. No physical signature required.
_Subject to Sri Ganganagar Jurisdiction._
_For inquiries contact: Sanjay Kumar Aggarwal (94619-40113)_`;

    const waUrl = `https://web.whatsapp.com/send?phone=${phoneDigits}&text=${encodeURIComponent(waText.replace(/\r?\n/g, '\r\n'))}`;
    window.open(waUrl, '_blank', 'noopener,noreferrer');

    // Update status indicator
    const labelEl = document.getElementById(isSeller ? 'label-seller-wa-status' : 'label-buyer-wa-status');
    const badgeEl = document.getElementById(isSeller ? 'status-badge-seller-wa' : 'status-badge-buyer-wa');
    if (labelEl) labelEl.textContent = '✓ WhatsApp prepared';
    if (badgeEl) badgeEl.className = 'channel-status-badge sent';

    this.showToast(`Prepared WhatsApp message for ${isSeller ? 'Seller' : 'Buyer'}`, 'success');
  },

  waBotPollInterval: null,

  async checkWhatsAppBotStatus() {
    try {
      const res = await fetch('/api/whatsapp/status');
      const data = await res.json();
      const dot = document.getElementById('wa-bot-status-dot');
      const text = document.getElementById('wa-bot-status-text');
      const linkBtn = document.getElementById('btn-wa-link-device');
      const sendBtn = document.getElementById('btn-direct-send-wa');

      if (data.is_ready) {
        if (dot) { dot.style.background = '#10B981'; dot.style.boxShadow = '0 0 8px rgba(16,185,129,0.7)'; }
        if (text) { text.textContent = '✓ WhatsApp Connected (Auto-Send Ready)'; text.style.color = '#10B981'; }
        if (linkBtn) { linkBtn.textContent = 'Linked ✓'; linkBtn.style.opacity = '0.7'; }
        if (sendBtn) {
          sendBtn.style.opacity = '1';
          sendBtn.disabled = false;
        }
      } else {
        if (dot) { dot.style.background = '#F59E0B'; dot.style.boxShadow = 'none'; }
        if (text) { text.textContent = 'WhatsApp Not Linked (Click to link)'; text.style.color = 'var(--text-muted)'; }
        if (linkBtn) { linkBtn.textContent = 'Link WhatsApp'; linkBtn.style.opacity = '1'; }
      }
      return data;
    } catch (e) {
      console.warn('Failed to fetch WhatsApp bot status:', e);
    }
  },

  async openWhatsAppQrModal() {
    const modal = document.getElementById('modal-whatsapp-qr');
    if (modal) modal.classList.add('active');

    const spinner = document.getElementById('wa-qr-spinner');
    const img = document.getElementById('wa-qr-img');
    const label = document.getElementById('wa-qr-status-label');

    if (spinner) { spinner.style.display = 'block'; spinner.textContent = 'Starting WhatsApp Session...'; }
    if (img) img.style.display = 'none';
    if (label) label.textContent = 'Initializing WhatsApp...';

    // Start bot background session
    fetch('/api/whatsapp/start', { method: 'POST' }).catch(() => {});

    // Poll status every 1.5s
    if (this.waBotPollInterval) clearInterval(this.waBotPollInterval);
    this.waBotPollInterval = setInterval(async () => {
      try {
        const res = await fetch('/api/whatsapp/status');
        const data = await res.json();

        if (data.is_ready) {
          clearInterval(this.waBotPollInterval);
          this.waBotPollInterval = null;
          this.closeWhatsAppQrModal();
          this.showToast('✓ WhatsApp Linked Successfully! Ready for direct PDF dispatch.', 'success', 5000);
          this.checkWhatsAppBotStatus();
          return;
        }

        if (data.qr_code) {
          if (spinner) spinner.style.display = 'none';
          if (img) {
            img.src = data.qr_code;
            img.style.display = 'block';
          }
          if (label) label.textContent = 'Scan QR code with WhatsApp on your phone';
        } else if (data.status === 'STARTING') {
          if (label) label.textContent = 'Starting browser session...';
        } else if (data.status === 'CONNECTING') {
          if (label) label.textContent = 'Connecting to WhatsApp...';
        }
      } catch (err) {
        console.warn('Poll error:', err);
      }
    }, 1500);
  },

  closeWhatsAppQrModal() {
    if (this.waBotPollInterval) {
      clearInterval(this.waBotPollInterval);
      this.waBotPollInterval = null;
    }
    const modal = document.getElementById('modal-whatsapp-qr');
    if (modal) modal.classList.remove('active');
  },

  async sendPdfDirectlyToWhatsApp() {
    const deal = this.selectedDealForDispatch;
    if (!deal) return;

    const phoneInput = document.getElementById('dispatch-phone')?.value || deal.buyer_phone || '';
    const phoneDigits = phoneInput.replace(/[^0-9]/g, '');
    const waText = this.currentWaText || document.getElementById('whatsapp-preview-box')?.innerText || '';

    if (!phoneDigits) {
      this.showToast('Please enter a valid phone number', 'warning');
      return;
    }

    // Check status
    const status = await this.checkWhatsAppBotStatus();
    if (!status || !status.is_ready) {
      this.openWhatsAppQrModal();
      return;
    }

    // Immediate non-blocking feedback: User never waits
    this.showToast(`🤖 Automated bot uploading PDF in background to +${phoneDigits}. You can continue working!`, 'info', 6000);
    document.getElementById('modal-dispatch')?.classList.remove('active');

    fetch('/api/whatsapp/send-document', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        deal_id: deal.id,
        phone: phoneDigits,
        caption: waText
      })
    }).then(async (resp) => {
      const result = await resp.json();
      if (resp.ok && result.success) {
        this.showToast(`✓ Official PDF Contract delivered directly to +${phoneDigits} on WhatsApp!`, 'success', 7000);
        this.logDispatchEvent('WHATSAPP', phoneDigits, true);
      } else {
        if (result.status === 'GATEWAY_NOT_CONFIGURED' || result.status === 'NEEDS_QR') {
          this.openWhatsAppQrModal();
        } else {
          this.showToast(`WhatsApp Bot: ${result.error || result.message || 'Check bot connection'}`, 'warning', 7000);
        }
      }
    }).catch(err => {
      this.showToast(`WhatsApp Send: ${err.message}`, 'danger', 6000);
    });
  },



  openEmailClient() {
    if (!this.selectedDealForDispatch) return;
    const deal = this.selectedDealForDispatch;
    const bgn = deal.bgn_code || deal.id;
    const emailTo = document.getElementById('dispatch-email-to')?.value || '';
    const subject = encodeURIComponent(document.getElementById('dispatch-email-subject')?.value || `Bargain Confirmation [${bgn}]`);
    const body = encodeURIComponent(document.getElementById('email-preview-box')?.innerText || '');

    // Download PDF first
    this.downloadContractPdf(deal.id);

    const mailtoLink = document.createElement('a');
    mailtoLink.href = `mailto:${emailTo}?subject=${subject}&body=${body}`;
    mailtoLink.target = '_blank';
    mailtoLink.click();

    this.logDispatchEvent('EMAIL', emailTo);
    this.showToast(`Opened email client with system-generated PDF notice`, 'info');
  },

  // ==========================================================================
  // REDIFFMAIL SMTP CONFIGURATION & DIRECT EMAIL DISPATCH
  // ==========================================================================
  async openRediffmailModal() {
    const modal = document.getElementById('modal-rediffmail-config');
    if (!modal) return;

    // Reset feedback
    const feedback = document.getElementById('email-test-feedback');
    if (feedback) {
      feedback.style.display = 'none';
      feedback.textContent = '';
    }

    try {
      const cfg = await this.api('/api/email/config');
      if (cfg) {
        const userInput = document.getElementById('cfg-email-user');
        const passInput = document.getElementById('cfg-email-pass');
        const fromInput = document.getElementById('cfg-email-from-name');
        const hostInput = document.getElementById('cfg-email-host');
        const portInput = document.getElementById('cfg-email-port');
        const enabledInput = document.getElementById('cfg-email-enabled');
        const presetSelect = document.getElementById('cfg-email-preset');

        if (userInput) userInput.value = cfg.smtp_user || 'ganeshsgnr@rediffmail.com';
        if (passInput) {
          passInput.value = cfg.has_password ? cfg.smtp_pass : '';
          passInput.placeholder = cfg.has_password ? '•••••••• (Saved - leave empty to keep)' : 'Enter your Rediffmail password';
          passInput.required = !cfg.has_password;
        }
        if (fromInput) fromInput.value = cfg.from_name || 'Ganesh & Company';
        if (hostInput) hostInput.value = cfg.smtp_host || 'smtp.rediffmail.com';
        if (portInput) portInput.value = cfg.smtp_port || 587;
        if (enabledInput) enabledInput.checked = !!cfg.is_enabled;

        // Sync preset
        if (presetSelect) {
          if (cfg.smtp_host === 'smtp-relay.brevo.com' || cfg.smtp_host === 'smtp-relay.sendinblue.com') {
            presetSelect.value = 'brevo';
          } else if (cfg.smtp_host === 'smtp.rediffmail.com' && Number(cfg.smtp_port) === 587) {
            presetSelect.value = 'standard';
          } else if (cfg.smtp_host === 'mail.rediffmailpro.com' && (Number(cfg.smtp_port) === 465 || Number(cfg.smtp_port) === 587)) {
            presetSelect.value = 'pro';
          } else if (cfg.smtp_host === 'smtp.gmail.com') {
            presetSelect.value = 'gmail';
          } else {
            presetSelect.value = 'custom';
          }
        }
      }
    } catch (err) {
      console.warn('Could not load email config:', err);
    }

    modal.classList.add('active');
    if (window.lucide) lucide.createIcons();
  },

  closeRediffmailModal() {
    const modal = document.getElementById('modal-rediffmail-config');
    if (modal) modal.classList.remove('active');
  },

  async saveRediffmailConfig(e) {
    if (e) e.preventDefault();
    const userInput = document.getElementById('cfg-email-user')?.value?.trim();
    const passInput = document.getElementById('cfg-email-pass')?.value;
    const fromInput = document.getElementById('cfg-email-from-name')?.value?.trim();
    const hostInput = document.getElementById('cfg-email-host')?.value?.trim();
    const portInput = document.getElementById('cfg-email-port')?.value;
    const enabledInput = document.getElementById('cfg-email-enabled')?.checked;
    const presetSelect = document.getElementById('cfg-email-preset')?.value;

    const useSsl = presetSelect === 'pro' || Number(portInput) === 465;

    try {
      const payload = {
        smtp_user: userInput,
        from_email: userInput,
        from_name: fromInput || 'Ganesh & Company',
        smtp_host: hostInput,
        smtp_port: parseInt(portInput || '587', 10),
        use_ssl: useSsl,
        is_enabled: enabledInput ? 1 : 0
      };
      if (passInput && passInput !== '••••••••') {
        payload.smtp_pass = passInput;
      }

      await this.api('/api/email/config', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      this.showToast('✓ Email Gateway configuration saved successfully!', 'success', 5000);
      this.closeRediffmailModal();
    } catch (err) {
      this.showToast(`Failed to save settings: ${err.message}`, 'danger');
    }
  },

  async testRediffmailConnection() {
    const testBtn = document.getElementById('btn-test-rediffmail-connection');
    const feedback = document.getElementById('email-test-feedback');
    const user = document.getElementById('cfg-email-user')?.value?.trim() || 'ganeshsgnr@rediffmail.com';

    if (testBtn) {
      testBtn.disabled = true;
      testBtn.innerHTML = `<span class="spinner-sm" style="display:inline-block; width:12px; height:12px; border:2px solid currentColor; border-right-color:transparent; border-radius:50%; animation:spin 0.6s linear infinite; vertical-align:middle; margin-right:6px;"></span> Connecting...`;
    }

    if (feedback) {
      feedback.style.display = 'block';
      feedback.style.background = 'rgba(59, 130, 246, 0.1)';
      feedback.style.color = '#3b82f6';
      feedback.style.border = '1px solid rgba(59, 130, 246, 0.3)';
      feedback.textContent = `Connecting to Rediffmail SMTP and sending test email to ${user}...`;
    }

    try {
      // If password field has new value, save config first
      const passVal = document.getElementById('cfg-email-pass')?.value;
      if (passVal && passVal !== '••••••••') {
        await this.saveRediffmailConfig();
      }

      const resp = await fetch('/api/email/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recipient: user })
      });
      const data = await resp.json();

      if (resp.ok && data.success) {
        if (feedback) {
          feedback.style.background = 'rgba(16, 185, 129, 0.15)';
          feedback.style.color = '#10b981';
          feedback.style.border = '1px solid rgba(16, 185, 129, 0.3)';
          feedback.textContent = `✓ Rediffmail SMTP Connected! Verification email delivered to ${user}.`;
        }
        this.showToast(`✓ Rediffmail test email sent successfully to ${user}!`, 'success', 6000);
      } else {
        const errorMsg = data.error || data.message || 'SMTP Authentication failed';
        if (feedback) {
          feedback.style.background = 'rgba(239, 68, 68, 0.15)';
          feedback.style.color = '#ef4444';
          feedback.style.border = '1px solid rgba(239, 68, 68, 0.3)';
          feedback.textContent = `✗ Connection failed: ${errorMsg}`;
        }
        this.showToast(`Rediffmail Test Failed: ${errorMsg}`, 'danger', 7000);
      }
    } catch (err) {
      if (feedback) {
        feedback.style.background = 'rgba(239, 68, 68, 0.15)';
        feedback.style.color = '#ef4444';
        feedback.style.border = '1px solid rgba(239, 68, 68, 0.3)';
        feedback.textContent = `✗ Network error: ${err.message}`;
      }
      this.showToast(`Error: ${err.message}`, 'danger');
    } finally {
      if (testBtn) {
        testBtn.disabled = false;
        testBtn.innerHTML = `<i data-lucide="send" style="width: 14px; height: 14px;"></i> <span>Test Connection</span>`;
        if (window.lucide) lucide.createIcons();
      }
    }
  },

  async sendContractViaRediffmail() {
    const deal = this.selectedDealForDispatch;
    if (!deal) return;

    const emailTo = document.getElementById('dispatch-email-to')?.value?.trim() || deal.buyer_email || deal.seller_email || '';
    const subject = document.getElementById('dispatch-email-subject')?.value || `Bargain Confirmation [${deal.bgn_code || deal.id}]`;
    const emailBodyText = document.getElementById('email-preview-box')?.innerText || '';

    if (!emailTo || !emailTo.includes('@')) {
      this.showToast('Please specify a valid recipient email address', 'warning');
      return;
    }

    // Immediate non-blocking notification: user does not wait
    this.showToast(`📨 Sending official PDF contract to ${emailTo}...`, 'info', 4000);
    document.getElementById('modal-dispatch')?.classList.remove('active');

    try {
      const resp = await fetch('/api/email/send-document', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          deal_id: deal.id,
          recipient_email: emailTo,
          recipient_name: deal.buyer_name || 'Client',
          subject: subject,
          body: emailBodyText
        })
      });

      const data = await resp.json();
      if (resp.ok && data.success) {
        this.showToast(`✓ Official PDF Contract successfully delivered to ${emailTo}!`, 'success', 6000);
        await this.logDispatchEvent('EMAIL', emailTo, true);
      } else {
        const err = data.error || 'Failed to send email';
        this.showToast(`Email Dispatch Failed: ${err}`, 'danger', 8000);
        if (err.toLowerCase().includes('password') || err.toLowerCase().includes('auth') || err.toLowerCase().includes('not configured')) {
          this.openRediffmailModal();
        }
      }
    } catch (err) {
      this.showToast(`Email Error: ${err.message}`, 'danger', 6000);
    }
  },

  async logDispatchEvent(channel, recipientVal = null, silent = false) {
    if (!this.selectedDealForDispatch) return;
    const deal = this.selectedDealForDispatch;
    const targetVal = recipientVal || (channel === 'WHATSAPP' 
      ? (document.getElementById('dispatch-both-phone')?.value || document.getElementById('dispatch-phone')?.value || deal.buyer_phone)
      : (document.getElementById('dispatch-both-email')?.value || document.getElementById('dispatch-email-to')?.value || deal.buyer_email));

    try {
      await this.api('/api/dispatch-logs', {
        method: 'POST',
        body: JSON.stringify({
          deal_id: deal.id,
          recipient_type: 'BUYER',
          recipient_name: deal.buyer_name,
          channel: channel,
          phone_or_email: targetVal || 'Client',
          message_preview: `Bargain Confirmation PDF [${deal.bgn_code || deal.id}]`,
          status: 'SENT'
        })
      });
      if (!silent) this.showToast(`Logged confirmation dispatch via ${channel}`, 'success');
      await this.fetchDispatchLogs();
      this.updateCounters();
    } catch (_) {}
  },

  // ==========================================================================
  // SCREEN 5: DISPATCH AUDIT LOGS
  // ==========================================================================
  renderDispatchLogs() {
    const tbody = document.getElementById('tbody-dispatch-logs');
    if (!tbody) return;

    if (!this.dispatchLogs.length) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; padding: 30px; color: var(--text-dim);">No dispatch logs recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = this.dispatchLogs.map(l => {
      const isWA = l.channel === 'WHATSAPP';
      return `
        <tr>
          <td class="mono" style="color: var(--text-dim);">${l.id}</td>
          <td><a class="cell-bgn-id" onclick="app.openLetterheadModal('${l.deal_id}')">${l.bgn_code || l.deal_id}</a></td>
          <td><strong style="color: var(--text-primary); font-weight: 500;">${this.escapeHtml(this.formatCompanyName(l.recipient_name))}</strong></td>
          <td><span class="status-tag status-pending">${l.recipient_type}</span></td>
          <td>
            <span style="display: inline-flex; align-items: center; gap: 5px; font-weight: 500; font-size: 12px; color: ${isWA ? '#25D366' : '#79C0FF'};">
              <i data-lucide="${isWA ? 'message-circle' : 'mail'}" style="width: 13px; height: 13px;"></i>
              ${l.channel}
            </span>
          </td>
          <td class="mono">${this.escapeHtml(l.phone_or_email || '')}</td>
          <td style="max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-muted); font-size: 12px;">${this.escapeHtml(l.message_preview)}</td>
          <td><span class="status-tag status-confirmed">${l.status}</span></td>
          <td class="mono" style="font-size: 11px; color: var(--text-dim);">${l.created_at.replace('T', ' ').substring(0, 16)}</td>
        </tr>
      `;
    }).join('');
    if (window.lucide) lucide.createIcons();
  },

  // ==========================================================================
  // SCREEN 10: TRASH / RECYCLE BIN
  // ==========================================================================
  renderTrash() {
    const tbody = document.getElementById('tbody-trash-deals');
    if (!tbody) return;

    if (!this.trashDeals.length) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; padding: 40px; color: var(--text-dim);">Trash bin is clean. No soft-deleted bargains.</td></tr>`;
      return;
    }

    tbody.innerHTML = this.trashDeals.map(d => `
      <tr>
        <td><span class="cell-bgn-id" style="opacity: 0.7;">${d.bgn_code || d.id}</span></td>
        <td class="mono">${d.deal_date}</td>
        <td style="color: var(--text-primary);">${this.formatCompanyName(d.seller_name)}</td>
        <td style="color: var(--text-primary);">${this.formatCompanyName(d.buyer_name)}</td>
        <td>${d.product_name}</td>
        <td class="mono">${(d.quantity_tonnes || d.quantity_qtl * 0.1).toFixed(1)} MT</td>
        <td class="rate-figure">₹${Math.round(d.rate_per_qtl).toLocaleString('en-IN')}</td>
        <td class="mono" style="color: var(--text-dim); font-size: 11px;">${(d.deleted_at || '').substring(0, 16).replace('T', ' ')}</td>
        <td style="text-align: right;">
          <button class="btn btn-secondary btn-xs" onclick="app.restoreDeal('${d.id}')" title="Restore Bargain">
            <i data-lucide="rotate-ccw" style="width: 12px; height: 12px; color: var(--emerald);"></i>
            <span>Restore</span>
          </button>
          <button class="btn btn-danger btn-xs" onclick="app.permanentDeleteDeal('${d.id}')" title="Permanently Delete">
            <i data-lucide="x" style="width: 12px; height: 12px;"></i>
            <span>Purge</span>
          </button>
        </td>
      </tr>
    `).join('');
    if (window.lucide) lucide.createIcons();
  },

  deleteDeal(dealId) {
    return this.trashDeal(dealId);
  },

  async trashDeal(dealId) {
    const deal = this.deals.find(d => d.id === dealId) || this.trashDeals.find(d => d.id === dealId);
    const bgn = deal ? (deal.bgn_code || deal.id) : dealId;
    if (!confirm(`Are you sure you want to move bargain [${bgn}] to the Trash bin?`)) return;
    try {
      await this.api(`/api/deals/${dealId}/trash`, { method: 'POST' });
      this.showToast(`Bargain [${bgn}] moved to Trash bin`, 'info');
      await this.fetchDeals();
      await this.fetchTrashDeals();
      await this.fetchDashboardMetrics();
      this.updateCounters();
      this.renderCurrentView();
    } catch (err) {
      console.error('Failed to trash deal:', err);
      this.showToast('Failed to delete bargain: ' + (err.message || err), 'error');
    }
  },

  async restoreDeal(dealId) {
    try {
      await this.api(`/api/deals/${dealId}/restore`, { method: 'POST' });
      this.showToast('Deal restored to active Bargains register', 'success');
      await this.fetchDeals();
      await this.fetchTrashDeals();
      await this.fetchDashboardMetrics();
      this.updateCounters();
      this.renderCurrentView();
    } catch (_) {}
  },

  async permanentDeleteDeal(dealId) {
    if (!confirm("WARNING: This will permanently wipe this bargain from the database. This action CANNOT be undone! Proceed?")) return;
    try {
      await this.api(`/api/deals/${dealId}/permanent`, { method: 'DELETE' });
      this.showToast('Bargain permanently deleted', 'success');
      await this.fetchTrashDeals();
      this.updateCounters();
      this.renderTrash();
    } catch (_) {}
  },

  // ==========================================================================
  // NEW BARGAIN DEAL ENTRY MODAL (Keyboard-First Ctrl+B)
  // ==========================================================================
  setupNewBargainModal() {
    const modal = document.getElementById('modal-new-bargain');
    const form = document.getElementById('form-new-bargain');
    const openBtn = document.getElementById('btn-open-new-bargain');
    const hubNewBtn = document.getElementById('btn-hub-new-bargain');
    const closeBtn = document.getElementById('btn-close-new-bargain');
    const cancelBtn = document.getElementById('btn-cancel-new-bargain');

    const openModal = () => {
      // Pre-fill today's date
      const today = new Date().toISOString().split('T')[0];
      const dateInput = document.getElementById('input-deal-date');
      if (dateInput && !dateInput.value) dateInput.value = today;

      const advanceInput = document.getElementById('input-advance-date');
      if (advanceInput && !advanceInput.value) {
        const nextDate = new Date();
        nextDate.setDate(nextDate.getDate() + 2);
        advanceInput.value = nextDate.toISOString().split('T')[0];
      }

      // Populate commodities dropdown
      const prodSelect = document.getElementById('input-product-id');
      if (prodSelect) {
        prodSelect.innerHTML = this.products.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
      }

      modal.classList.add('active');
      document.getElementById('input-seller-name')?.focus();
      if (window.lucide) lucide.createIcons();
    };

    const closeModal = () => {
      modal.classList.remove('active');
      form.reset();
    };

    openBtn?.addEventListener('click', openModal);
    hubNewBtn?.addEventListener('click', openModal);
    closeBtn?.addEventListener('click', closeModal);
    cancelBtn?.addEventListener('click', closeModal);

    // Quantity conversion helper
    const qtyInput = document.getElementById('input-quantity-qtl');
    const equivLabel = document.getElementById('equiv-tonnes-label');
    qtyInput?.addEventListener('input', (e) => {
      const qtl = parseFloat(e.target.value) || 0;
      const mt = qtl * 0.1;
      if (equivLabel) equivLabel.textContent = `= ${mt.toFixed(1)} MT`;
    });

    // Rate sync helper (Same as Seller)
    const sellerRateInput = document.getElementById('input-seller-rate-qtl');
    const buyerRateInput = document.getElementById('input-buyer-rate-qtl');
    const sameRateChk = document.getElementById('chk-same-rate');

    sellerRateInput?.addEventListener('input', (e) => {
      if (sameRateChk?.checked && buyerRateInput) {
        buyerRateInput.value = e.target.value;
      }
    });

    sameRateChk?.addEventListener('change', (e) => {
      if (e.target.checked && buyerRateInput && sellerRateInput) {
        buyerRateInput.readOnly = true;
        buyerRateInput.value = sellerRateInput.value;
      } else if (buyerRateInput) {
        buyerRateInput.readOnly = false;
        buyerRateInput.focus();
      }
    });

    // Setup Autocomplete for Seller and Buyer
    this.setupAutocomplete('input-seller-name', 'input-seller-id', 'seller-autocomplete-dropdown', 'SELLER');
    this.setupAutocomplete('input-buyer-name', 'input-buyer-id', 'buyer-autocomplete-dropdown', 'BUYER');

    // Submit Form
    form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const bgnCode = document.getElementById('input-bgn-code').value.trim();
      const dealDate = document.getElementById('input-deal-date').value;
      const sellerId = document.getElementById('input-seller-id').value;
      const buyerId = document.getElementById('input-buyer-id').value;
      const productId = document.getElementById('input-product-id').value;
      const qtyQtl = parseFloat(document.getElementById('input-quantity-qtl').value);
      const sellerRate = parseFloat(document.getElementById('input-seller-rate-qtl').value);
      const buyerRate = parseFloat(document.getElementById('input-buyer-rate-qtl').value) || sellerRate;
      const advanceDate = document.getElementById('input-advance-date').value;
      const deliveryCondition = document.getElementById('input-delivery-condition').value;
      const notes = document.getElementById('input-deal-notes').value;

      if (!sellerId || !buyerId) {
        this.showToast('Please select valid Seller and Buyer from suggestions', 'error');
        return;
      }

      const submitBtn = document.getElementById('btn-submit-new-bargain') || form.querySelector('button[type="submit"]');
      const origBtnHtml = submitBtn ? submitBtn.innerHTML : '';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span>Saving Bargain...</span>';
      }

      try {
        const result = await this.api('/api/deals', {
          method: 'POST',
          body: JSON.stringify({
            bgn_code: bgnCode || undefined,
            deal_date: dealDate,
            seller_id: sellerId,
            buyer_id: buyerId,
            product_id: productId,
            quantity_qtl: qtyQtl,
            rate_per_qtl: sellerRate,
            seller_rate: sellerRate,
            buyer_rate: buyerRate,
            advance_payment_date: advanceDate,
            delivery_condition: deliveryCondition,
            notes: notes
          })
        });

        this.showToast(`Bargain ${result.bgn_code || ''} confirmed and issued successfully!`, 'success');
        closeModal();

        await this.fetchDeals();
        await this.fetchDashboardMetrics();
        this.updateCounters();
        this.renderCurrentView();

        // Prompt to dispatch confirmation modal immediately
        if (result.deal_id) {
          setTimeout(() => {
            this.openDispatchModal(result.deal_id);
          }, 300);
        }
      } catch (err) {
        this.showToast(err.message, 'error');
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = origBtnHtml;
        }
      }
    });
  },

  // ==========================================================================
  // EDIT BARGAIN DEAL MODAL (In-Place Edit Preserving Bargain ID)
  // ==========================================================================
  setupEditBargainModal() {
    const modal = document.getElementById('modal-edit-bargain');
    const form = document.getElementById('form-edit-bargain');
    const closeBtn = document.getElementById('btn-close-edit-bargain');
    const cancelBtn = document.getElementById('btn-cancel-edit-bargain');

    const closeModal = () => {
      modal.classList.remove('active');
      form.reset();
    };

    closeBtn?.addEventListener('click', closeModal);
    cancelBtn?.addEventListener('click', closeModal);

    // Quantity conversion helper
    const qtyInput = document.getElementById('edit-quantity-qtl');
    const equivLabel = document.getElementById('edit-equiv-tonnes-label');
    qtyInput?.addEventListener('input', (e) => {
      const qtl = parseFloat(e.target.value) || 0;
      const mt = qtl * 0.1;
      if (equivLabel) equivLabel.textContent = `= ${mt.toFixed(1)} MT`;
    });

    // Rate sync helper
    const sellerRateInput = document.getElementById('edit-seller-rate-qtl');
    const buyerRateInput = document.getElementById('edit-buyer-rate-qtl');
    const sameRateChk = document.getElementById('edit-chk-same-rate');

    sellerRateInput?.addEventListener('input', (e) => {
      if (sameRateChk?.checked && buyerRateInput) {
        buyerRateInput.value = e.target.value;
      }
    });

    sameRateChk?.addEventListener('change', (e) => {
      if (e.target.checked && buyerRateInput && sellerRateInput) {
        buyerRateInput.readOnly = true;
        buyerRateInput.value = sellerRateInput.value;
      } else if (buyerRateInput) {
        buyerRateInput.readOnly = false;
        buyerRateInput.focus();
      }
    });

    // Setup Autocompletes for Edit form
    this.setupAutocomplete('edit-seller-name', 'edit-seller-id', 'edit-seller-autocomplete-dropdown', 'SELLER');
    this.setupAutocomplete('edit-buyer-name', 'edit-buyer-id', 'edit-buyer-autocomplete-dropdown', 'BUYER');

    // Submit Edit Form
    form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const dealId = document.getElementById('edit-deal-id').value;
      if (!dealId) return;

      const dealDate = document.getElementById('edit-deal-date').value;
      const status = document.getElementById('edit-deal-status').value;
      const sellerId = document.getElementById('edit-seller-id').value;
      const buyerId = document.getElementById('edit-buyer-id').value;
      const productId = document.getElementById('edit-product-id').value;
      const qtyQtl = parseFloat(document.getElementById('edit-quantity-qtl').value);
      const sellerRate = parseFloat(document.getElementById('edit-seller-rate-qtl').value);
      const buyerRate = parseFloat(document.getElementById('edit-buyer-rate-qtl').value) || sellerRate;
      const advanceDate = document.getElementById('edit-advance-date').value;
      const deliveryCondition = document.getElementById('edit-delivery-condition').value;
      const notes = document.getElementById('edit-deal-notes').value;

      if (!sellerId || !buyerId) {
        this.showToast('Please select valid Seller and Buyer from suggestions', 'error');
        return;
      }

      const submitBtn = document.getElementById('btn-submit-edit-bargain') || form.querySelector('button[type="submit"]');
      const origBtnHtml = submitBtn ? submitBtn.innerHTML : '';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span>Saving Changes...</span>';
      }

      try {
        const result = await this.api(`/api/deals/${dealId}/edit`, {
          method: 'POST',
          body: JSON.stringify({
            deal_date: dealDate,
            status: status,
            seller_id: sellerId,
            buyer_id: buyerId,
            product_id: productId,
            quantity_qtl: qtyQtl,
            rate_per_qtl: sellerRate,
            seller_rate: sellerRate,
            buyer_rate: buyerRate,
            advance_payment_date: advanceDate,
            delivery_condition: deliveryCondition,
            notes: notes
          })
        });

        if (result.reconfirmation_required) {
          this.showToast(`Bargain ${result.bgn_code || dealId} updated! Commercial terms changed: flagged as Reconfirmation Required.`, 'warning', 6000);
        } else {
          this.showToast(`Bargain ${result.bgn_code || dealId} updated successfully!`, 'success');
        }

        closeModal();
        await this.fetchDeals();
        await this.fetchDashboardMetrics();
        this.updateCounters();
        this.renderCurrentView();
      } catch (err) {
        this.showToast('Failed to update bargain: ' + err.message, 'error');
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = origBtnHtml;
        }
      }
    });
  },

  openEditBargainModal(dealId) {
    const deal = this.deals.find(d => d.id === dealId);
    if (!deal) {
      this.showToast('Bargain not found', 'error');
      return;
    }

    const modal = document.getElementById('modal-edit-bargain');
    if (!modal) return;

    // Populate commodity dropdown
    const prodSelect = document.getElementById('edit-product-id');
    if (prodSelect) {
      prodSelect.innerHTML = this.products.map(p => `<option value="${p.id}" ${p.id === deal.product_id ? 'selected' : ''}>${p.name}</option>`).join('');
    }

    document.getElementById('edit-deal-id').value = deal.id;
    document.getElementById('edit-bgn-code-badge').textContent = deal.bgn_code || deal.id;
    document.getElementById('edit-deal-date').value = deal.deal_date;
    document.getElementById('edit-deal-status').value = deal.status || 'CONFIRMED';
    document.getElementById('edit-seller-name').value = deal.seller_name || '';
    document.getElementById('edit-seller-id').value = deal.seller_id || '';
    document.getElementById('edit-buyer-name').value = deal.buyer_name || '';
    document.getElementById('edit-buyer-id').value = deal.buyer_id || '';

    const qty = deal.quantity_qtl || ((deal.quantity_tonnes || 0) * 10);
    document.getElementById('edit-quantity-qtl').value = qty;
    document.getElementById('edit-equiv-tonnes-label').textContent = `= ${(qty * 0.1).toFixed(1)} MT`;

    const sRate = deal.seller_rate || deal.rate_per_qtl || 0;
    const bRate = deal.buyer_rate || deal.rate_per_qtl || sRate;
    document.getElementById('edit-seller-rate-qtl').value = sRate;
    document.getElementById('edit-buyer-rate-qtl').value = bRate;
    const isSame = Math.round(sRate) === Math.round(bRate);
    document.getElementById('edit-chk-same-rate').checked = isSame;
    document.getElementById('edit-buyer-rate-qtl').readOnly = isSame;

    document.getElementById('edit-advance-date').value = deal.advance_payment_date || '';
    document.getElementById('edit-delivery-condition').value = deal.delivery_condition || '';
    document.getElementById('edit-deal-notes').value = deal.notes || '';

    modal.classList.add('active');
    if (window.lucide) lucide.createIcons();
  },

  // Helper for copying text with inline button feedback
  copyToClipboard(text, successMsg = 'Copied to clipboard!', btnEl = null) {
    if (!text) {
      this.showToast('Nothing to copy', 'warning');
      return;
    }

    const applyBtnFeedback = () => {
      if (btnEl) {
        const origHtml = btnEl.innerHTML;
        btnEl.innerHTML = `<i data-lucide="check" style="width: 11px; height: 11px; color: var(--status-confirmed);"></i> <span>Copied</span>`;
        if (window.lucide) lucide.createIcons();
        setTimeout(() => {
          btnEl.innerHTML = origHtml;
          if (window.lucide) lucide.createIcons();
        }, 1800);
      }
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        applyBtnFeedback();
        this.showToast(successMsg, 'success');
      }).catch(() => {
        this.fallbackCopyText(text, successMsg, btnEl);
      });
    } else {
      this.fallbackCopyText(text, successMsg, btnEl);
    }
  },

  fallbackCopyText(text, successMsg) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.position = "fixed";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand('copy');
      this.showToast(successMsg, 'success');
    } catch (err) {
      this.showToast('Could not copy text', 'error');
    }
    document.body.removeChild(textArea);
  },

  // ==========================================================================
  // PARTY MASTER MODAL (Add & Edit with Authentic Mandi Bank Settlement)
  // ==========================================================================
  setupPartyModal() {
    const modal = document.getElementById('modal-party-form');
    const form = document.getElementById('form-party');
    const addBtn = document.getElementById('btn-add-party');
    const closeBtn = document.getElementById('btn-close-party-form');
    const cancelBtn = document.getElementById('btn-cancel-party-form');
    const editFromProfileBtn = document.getElementById('btn-edit-party-from-profile');

    addBtn?.addEventListener('click', () => {
      this.openNewPartyModal();
    });

    closeBtn?.addEventListener('click', () => {
      modal?.classList.remove('active');
    });

    cancelBtn?.addEventListener('click', () => {
      modal?.classList.remove('active');
    });

    editFromProfileBtn?.addEventListener('click', () => {
      if (this.currentProfilePartyId) {
        document.getElementById('modal-party-profile')?.classList.remove('active');
        this.openEditPartyModal(this.currentProfilePartyId);
      }
    });

    form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      await this.savePartyForm();
    });
  },

  openNewPartyModal() {
    const modal = document.getElementById('modal-party-form');
    const form = document.getElementById('form-party');
    if (!modal || !form) return;

    form.reset();
    document.getElementById('party-form-id').value = '';
    document.getElementById('party-form-modal-title').textContent = 'Add New Party Master';
    document.getElementById('btn-party-form-label').textContent = 'Create Party Master';
    document.getElementById('party-form-type').value = 'BOTH';

    modal.classList.add('active');
    document.getElementById('party-form-legal-name')?.focus();
    if (window.lucide) lucide.createIcons();
  },

  openEditPartyModal(partyId) {
    const party = this.parties.find(p => p.id === partyId);
    if (!party) {
      this.showToast('Party not found in local cache', 'error');
      return;
    }

    const modal = document.getElementById('modal-party-form');
    const form = document.getElementById('form-party');
    if (!modal || !form) return;

    form.reset();
    document.getElementById('party-form-id').value = party.id;
    document.getElementById('party-form-modal-title').textContent = `Edit Party: ${party.trade_name || party.legal_name}`;
    document.getElementById('btn-party-form-label').textContent = 'Update Party Master';

    document.getElementById('party-form-legal-name').value = party.legal_name || '';
    document.getElementById('party-form-trade-name').value = party.trade_name || '';
    document.getElementById('party-form-type').value = party.party_type || 'BOTH';
    document.getElementById('party-form-station').value = party.mandi_station || party.city || '';

    // Bank Details
    document.getElementById('party-form-bank-name').value = party.bank_name || '';
    document.getElementById('party-form-bank-account-no').value = party.bank_account_no || '';
    document.getElementById('party-form-bank-ifsc').value = party.bank_ifsc || '';
    document.getElementById('party-form-bank-branch').value = party.bank_branch || '';

    // Tax & Credit
    document.getElementById('party-form-gstin').value = party.gstin || '';
    document.getElementById('party-form-pan').value = party.pan || '';
    document.getElementById('party-form-credit-limit').value = party.credit_limit || 0;

    // Contact Details
    document.getElementById('party-form-contact-person').value = party.contact_person || '';
    document.getElementById('party-form-phone').value = party.phone || '';
    document.getElementById('party-form-email').value = party.email || '';
    document.getElementById('party-form-address').value = party.address || '';

    modal.classList.add('active');
    document.getElementById('party-form-legal-name')?.focus();
    if (window.lucide) lucide.createIcons();
  },

  async savePartyForm() {
    const partyId = document.getElementById('party-form-id').value.trim();
    const legalName = document.getElementById('party-form-legal-name').value.trim();
    if (!legalName) {
      this.showToast('Please enter Party Legal Name', 'error');
      return;
    }

    const payload = {
      id: partyId || undefined,
      legal_name: legalName,
      trade_name: document.getElementById('party-form-trade-name').value.trim() || legalName,
      party_type: document.getElementById('party-form-type').value,
      mandi_station: document.getElementById('party-form-station').value.trim(),
      city: document.getElementById('party-form-station').value.trim(),
      bank_name: document.getElementById('party-form-bank-name').value.trim(),
      bank_account_no: document.getElementById('party-form-bank-account-no').value.trim(),
      bank_ifsc: document.getElementById('party-form-bank-ifsc').value.trim().toUpperCase(),
      bank_branch: document.getElementById('party-form-bank-branch').value.trim(),
      gstin: document.getElementById('party-form-gstin').value.trim().toUpperCase(),
      pan: document.getElementById('party-form-pan').value.trim().toUpperCase(),
      credit_limit: parseFloat(document.getElementById('party-form-credit-limit').value) || 0,
      contact_person: document.getElementById('party-form-contact-person').value.trim(),
      phone: document.getElementById('party-form-phone').value.trim(),
      email: document.getElementById('party-form-email').value.trim(),
      address: document.getElementById('party-form-address').value.trim(),
      default_buyer_brokerage_per_tonne: 0.0,
      default_seller_brokerage_per_tonne: 0.0
    };

    const submitBtn = document.getElementById('btn-submit-party-form');
    const labelSpan = document.getElementById('btn-party-form-label');
    const origLabel = labelSpan ? labelSpan.textContent : 'Save Party Master';
    if (submitBtn) {
      submitBtn.disabled = true;
      if (labelSpan) labelSpan.textContent = 'Saving...';
    }

    try {
      const endpoint = partyId ? `/api/parties/${partyId}` : '/api/parties';
      const result = await this.api(endpoint, {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      this.showToast(partyId ? `Party "${legalName}" updated successfully!` : `Party "${legalName}" created successfully!`, 'success');
      document.getElementById('modal-party-form')?.classList.remove('active');

      // Refresh parties list
      const parties = await this.api('/api/parties');
      this.parties = parties;
      this.renderPartyDirectory();
      this.updateCounters();

      // If this party's profile is currently open, refresh it immediately
      if (partyId && this.currentProfilePartyId === partyId) {
        await this.openPartyProfileModal(partyId);
      }
    } catch (err) {
      this.showToast(`Error saving party: ${err.message}`, 'error');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        if (labelSpan) labelSpan.textContent = origLabel;
      }
    }
  },

  setupAutocomplete(inputId, hiddenId, dropdownId, roleType) {
    const input = document.getElementById(inputId);
    const hidden = document.getElementById(hiddenId);
    const dropdown = document.getElementById(dropdownId);
    if (!input || !dropdown) return;

    let selectedIndex = -1;

    const formatRoleLabel = (type) => {
      if (type === 'BOTH') return 'Buyer & Seller';
      if (type === 'SELLER') return 'Seller';
      if (type === 'BUYER') return 'Buyer';
      return 'Counterparty';
    };

    const renderOptions = (matches) => {
      if (!matches.length) {
        dropdown.innerHTML = `<div style="padding: 12px 14px; color: var(--text-dim); font-size: 12.5px;">No matching parties found</div>`;
        dropdown.classList.add('active');
        return;
      }

      dropdown.innerHTML = matches.map((p, idx) => {
        const station = p.mandi_station || p.city || '';
        const state = p.state || '';
        const locParts = [station, state].filter(Boolean);
        const locStr = locParts.length ? locParts.join(', ') : 'Station unlisted';
        const roleStr = formatRoleLabel(p.party_type);
        const subline = `${locStr} · ${roleStr}`;

        return `
          <div class="autocomplete-option" data-id="${p.id}" data-name="${p.legal_name}" data-idx="${idx}">
            <div class="party-opt-name">${p.legal_name}</div>
            <div class="party-opt-sub">${subline}</div>
          </div>
        `;
      }).join('');

      selectedIndex = -1;

      dropdown.querySelectorAll('.autocomplete-option').forEach(opt => {
        opt.addEventListener('click', () => {
          input.value = opt.dataset.name;
          hidden.value = opt.dataset.id;
          dropdown.classList.remove('active');
        });
      });

      dropdown.classList.add('active');
    };

    input.addEventListener('input', () => {
      const q = input.value.toLowerCase().trim();
      if (!q) {
        dropdown.classList.remove('active');
        hidden.value = '';
        return;
      }

      const matches = this.parties.filter(p => {
        // Enforce role compatibility: Seller allows SELLER and BOTH; Buyer allows BUYER and BOTH
        if (roleType === 'SELLER' && p.party_type !== 'SELLER' && p.party_type !== 'BOTH') {
          return false;
        }
        if (roleType === 'BUYER' && p.party_type !== 'BUYER' && p.party_type !== 'BOTH') {
          return false;
        }

        const leg = (p.legal_name || '').toLowerCase();
        const trd = (p.trade_name || '').toLowerCase();
        const mnd = (p.mandi_station || '').toLowerCase();
        const cty = (p.city || '').toLowerCase();
        const stt = (p.state || '').toLowerCase();

        return (
          leg.includes(q) ||
          trd.includes(q) ||
          mnd.includes(q) ||
          cty.includes(q) ||
          stt.includes(q)
        );
      });

      renderOptions(matches);
    });

    input.addEventListener('keydown', (e) => {
      const options = dropdown.querySelectorAll('.autocomplete-option');
      if (!dropdown.classList.contains('active') || !options.length) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIndex = (selectedIndex + 1) % options.length;
        options.forEach((opt, idx) => {
          const isSel = idx === selectedIndex;
          opt.classList.toggle('selected', isSel);
          if (isSel) opt.scrollIntoView({ block: 'nearest' });
        });
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = (selectedIndex - 1 + options.length) % options.length;
        options.forEach((opt, idx) => {
          const isSel = idx === selectedIndex;
          opt.classList.toggle('selected', isSel);
          if (isSel) opt.scrollIntoView({ block: 'nearest' });
        });
      } else if (e.key === 'Enter') {
        if (selectedIndex >= 0 && options[selectedIndex]) {
          e.preventDefault();
          options[selectedIndex].click();
        }
      } else if (e.key === 'Escape') {
        dropdown.classList.remove('active');
      }
    });

    document.addEventListener('click', (e) => {
      if (!input.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.remove('active');
      }
    });
  },

  openNewBargainForParty(partyId) {
    const party = this.parties.find(p => p.id === partyId);
    if (!party) return;

    document.getElementById('btn-open-new-bargain')?.click();

    if (party.party_type === 'SELLER') {
      document.getElementById('input-seller-name').value = party.legal_name;
      document.getElementById('input-seller-id').value = party.id;
      document.getElementById('input-buyer-name')?.focus();
    } else {
      document.getElementById('input-buyer-name').value = party.legal_name;
      document.getElementById('input-buyer-id').value = party.id;
      document.getElementById('input-seller-name')?.focus();
    }
  },

  // ==========================================================================
  // GLOBAL SHORTCUTS & COMMAND PALETTE (⌘K)
  // ==========================================================================
  setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      // ⌘K or Ctrl+K -> Open Command Palette
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        this.openCommandPalette();
      }

      // ⌘B or Ctrl+B -> Open New Bargain Modal
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        document.getElementById('btn-open-new-bargain')?.click();
      }

      // Escape -> Close any modal
      if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
      }
    });
  },

  setupCommandPalette() {
    const modal = document.getElementById('modal-command-palette');
    const input = document.getElementById('command-palette-input');
    const results = document.getElementById('command-palette-results');
    const openBtn = document.getElementById('btn-open-command-palette');

    openBtn?.addEventListener('click', () => this.openCommandPalette());

    input?.addEventListener('input', () => {
      const q = input.value.toLowerCase().trim();
      if (!q) {
        this.renderDefaultCommands();
        return;
      }

      let matchesHtml = '';

      // Match Deals
      const dealMatches = this.deals.filter(d => 
        (d.bgn_code && d.bgn_code.toLowerCase().includes(q)) ||
        d.seller_name.toLowerCase().includes(q) ||
        d.buyer_name.toLowerCase().includes(q) ||
        d.product_name.toLowerCase().includes(q)
      ).slice(0, 5);

      if (dealMatches.length) {
        matchesHtml += `<div style="font-size: 11px; font-weight: 700; color: var(--gold); padding: 4px 8px; text-transform: uppercase;">Bargain Contracts</div>`;
        matchesHtml += dealMatches.map(d => `
          <div class="command-item" onclick="app.closeCommandPalette(); app.openLetterheadModal('${d.id}');">
            <div class="command-item-left">
              <span class="bgn-tag">${d.bgn_code || d.id}</span>
              <span>${d.product_name} &bull; ${d.seller_name.split(',')[0]} ➔ ${d.buyer_name.split(',')[0]}</span>
            </div>
            <span class="rate-figure">₹${Math.round(d.rate_per_qtl).toLocaleString('en-IN')}</span>
          </div>
        `).join('');
      }

      // Match Parties
      const partyMatches = this.parties.filter(p =>
        p.legal_name.toLowerCase().includes(q) ||
        (p.mandi_station && p.mandi_station.toLowerCase().includes(q))
      ).slice(0, 5);

      if (partyMatches.length) {
        matchesHtml += `<div style="font-size: 11px; font-weight: 700; color: var(--emerald); padding: 6px 8px 4px; text-transform: uppercase;">Parties</div>`;
        matchesHtml += partyMatches.map(p => `
          <div class="command-item" onclick="app.closeCommandPalette(); app.openPartyProfileModal('${p.id}');">
            <div class="command-item-left">
              <i data-lucide="building-2" style="width: 14px; height: 14px; color: var(--emerald);"></i>
              <span>${p.legal_name}</span>
            </div>
            <span class="station-tag">📍 ${p.mandi_station || p.city}</span>
          </div>
        `).join('');
      }

      // Navigation shortcuts
      const navMatches = [
        { label: 'Go to Executive Dashboard', view: 'dashboard' },
        { label: 'Go to Bargains Hub', view: 'bargains' },
        { label: 'Go to Party Directory', view: 'parties' },
        { label: 'Go to WhatsApp & Email Logs', view: 'dispatches' },
        { label: 'Go to Trash / Recycle Bin', view: 'trash' }
      ].filter(n => n.label.toLowerCase().includes(q));

      if (navMatches.length) {
        matchesHtml += `<div style="font-size: 11px; font-weight: 700; color: var(--text-dim); padding: 6px 8px 4px; text-transform: uppercase;">Navigation</div>`;
        matchesHtml += navMatches.map(n => `
          <div class="command-item" onclick="app.closeCommandPalette(); app.navigate('${n.view}');">
            <div class="command-item-left">
              <i data-lucide="arrow-right" style="width: 14px; height: 14px;"></i>
              <span>${n.label}</span>
            </div>
          </div>
        `).join('');
      }

      results.innerHTML = matchesHtml || `<div style="padding: 16px; text-align: center; color: var(--text-dim);">No results found</div>`;
      if (window.lucide) lucide.createIcons();
    });
  },

  openCommandPalette() {
    const modal = document.getElementById('modal-command-palette');
    const input = document.getElementById('command-palette-input');
    if (!modal) return;

    modal.classList.add('active');
    this.renderDefaultCommands();
    if (input) {
      input.value = '';
      input.focus();
    }
  },

  closeCommandPalette() {
    document.getElementById('modal-command-palette')?.classList.remove('active');
  },

  renderDefaultCommands() {
    const results = document.getElementById('command-palette-results');
    if (!results) return;

    results.innerHTML = `
      <div class="command-category-title">QUICK ACTIONS</div>
      <div class="command-item" onclick="app.closeCommandPalette(); document.getElementById('btn-open-new-bargain')?.click();">
        <div class="command-item-left">
          <i data-lucide="plus" style="width: 14px; height: 14px; color: var(--brand);"></i>
          <span>New Bargain</span>
        </div>
        <kbd>Ctrl+B</kbd>
      </div>
      <div class="command-item" onclick="app.closeCommandPalette(); app.openNewPartyModal();">
        <div class="command-item-left">
          <i data-lucide="user-plus" style="width: 14px; height: 14px; color: var(--text-secondary);"></i>
          <span>Add Party</span>
        </div>
      </div>
      <div class="command-item" onclick="app.closeCommandPalette(); app.exportToCsv();">
        <div class="command-item-left">
          <i data-lucide="download" style="width: 14px; height: 14px; color: var(--text-secondary);"></i>
          <span>Export Bargains</span>
        </div>
      </div>

      <div class="command-category-title" style="margin-top: 10px;">NAVIGATION</div>
      <div class="command-item" onclick="app.closeCommandPalette(); app.navigate('dashboard');">
        <div class="command-item-left">
          <i data-lucide="layout-dashboard" style="width: 14px; height: 14px; color: var(--text-secondary);"></i>
          <span>Dashboard</span>
        </div>
      </div>
      <div class="command-item" onclick="app.closeCommandPalette(); app.navigate('bargains');">
        <div class="command-item-left">
          <i data-lucide="receipt" style="width: 14px; height: 14px; color: var(--text-secondary);"></i>
          <span>Bargains Hub</span>
        </div>
      </div>
      <div class="command-item" onclick="app.closeCommandPalette(); app.navigate('parties');">
        <div class="command-item-left">
          <i data-lucide="building-2" style="width: 14px; height: 14px; color: var(--text-secondary);"></i>
          <span>Party Directory</span>
        </div>
      </div>
      <div class="command-item" onclick="app.closeCommandPalette(); app.navigate('dispatches');">
        <div class="command-item-left">
          <i data-lucide="message-square-share" style="width: 14px; height: 14px; color: var(--text-secondary);"></i>
          <span>Communications</span>
        </div>
      </div>
      <div class="command-item" onclick="app.closeCommandPalette(); app.navigate('trash');">
        <div class="command-item-left">
          <i data-lucide="trash-2" style="width: 14px; height: 14px; color: var(--text-secondary);"></i>
          <span>Recycle Bin</span>
        </div>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
  },

  // Modals & Tabs Listeners
  setupModals() {
    // Letterhead modal actions
    document.getElementById('btn-close-letterhead')?.addEventListener('click', () => {
      document.getElementById('modal-letterhead')?.classList.remove('active');
    });
    document.getElementById('btn-print-contract')?.addEventListener('click', () => {
      this.triggerPrint();
    });
    document.getElementById('btn-copy-seller')?.addEventListener('click', () => {
      this.setLetterheadRole('SELLER');
    });
    document.getElementById('btn-copy-buyer')?.addEventListener('click', () => {
      this.setLetterheadRole('BUYER');
    });
    document.getElementById('btn-download-pdf')?.addEventListener('click', () => {
      this.downloadContractPdf(this.selectedDealForLetterhead?.id);
    });
    document.getElementById('btn-letterhead-dispatch')?.addEventListener('click', () => {
      const dealId = this.selectedDealForLetterhead?.id;
      if (dealId) {
        document.getElementById('modal-letterhead')?.classList.remove('active');
        this.openDispatchModal(dealId);
      }
    });

    // Send Bargain Confirmation Modal Actions
    document.getElementById('btn-close-dispatch')?.addEventListener('click', () => {
      document.getElementById('modal-dispatch')?.classList.remove('active');
    });
    document.getElementById('btn-cancel-dispatch')?.addEventListener('click', () => {
      document.getElementById('modal-dispatch')?.classList.remove('active');
    });

    // Primary Dispatch Action: Send to Both
    document.getElementById('btn-dispatch-send-both')?.addEventListener('click', () => {
      this.sendPdfToBoth();
    });

    // Role-specific actions
    document.getElementById('btn-seller-only')?.addEventListener('click', () => {
      this.sendToSingleRole('SELLER');
    });
    document.getElementById('btn-buyer-only')?.addEventListener('click', () => {
      this.sendToSingleRole('BUYER');
    });

    document.getElementById('btn-seller-wa-web')?.addEventListener('click', () => {
      this.prepareWhatsAppForRole('SELLER');
    });
    document.getElementById('btn-buyer-wa-web')?.addEventListener('click', () => {
      this.prepareWhatsAppForRole('BUYER');
    });

    document.getElementById('btn-seller-download-pdf')?.addEventListener('click', () => {
      if (this.selectedDealForDispatch) {
        window.open(`/api/deals/${this.selectedDealForDispatch.id}/pdf?role=SELLER`, '_blank');
      }
    });
    document.getElementById('btn-buyer-download-pdf')?.addEventListener('click', () => {
      if (this.selectedDealForDispatch) {
        window.open(`/api/deals/${this.selectedDealForDispatch.id}/pdf?role=BUYER`, '_blank');
      }
    });

    // Collapsible Confirmation Preview
    document.getElementById('btn-toggle-preview')?.addEventListener('click', () => {
      const box = document.getElementById('send-preview-content');
      const chevron = document.getElementById('preview-chevron');
      if (box) {
        const isOpen = box.classList.toggle('active');
        if (chevron) chevron.style.transform = isOpen ? 'rotate(180deg)' : 'rotate(0deg)';
      }
    });

    // Party Profile Edit Details trigger
    document.getElementById('btn-edit-party-from-profile')?.addEventListener('click', () => {
      if (this.currentProfilePartyId) {
        document.getElementById('modal-party-profile')?.classList.remove('active');
        this.openEditPartyModal(this.currentProfilePartyId);
      }
    });

    // Party Profile Tabs
    document.querySelectorAll('#party-profile-tabs .profile-tab-btn, #party-profile-tabs .profile-tab-btn-clean').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#party-profile-tabs .profile-tab-btn, #party-profile-tabs .profile-tab-btn-clean').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.dataset.tab;
        const cPane = document.getElementById('tab-pane-prof-contacts');
        const dPane = document.getElementById('tab-pane-prof-deals');
        const mPane = document.getElementById('tab-pane-prof-commodities');
        if (cPane) cPane.style.display = tab === 'contacts' ? 'flex' : 'none';
        if (dPane) dPane.style.display = tab === 'deals' ? 'block' : 'none';
        if (mPane) mPane.style.display = tab === 'commodities' ? 'flex' : 'none';
      });
    });

    document.getElementById('btn-native-share-both')?.addEventListener('click', () => {
      this.sharePdfDirectly();
    });

    document.getElementById('btn-native-share-wa')?.addEventListener('click', () => {
      this.sharePdfDirectly();
    });



    // WhatsApp tab actions
    document.getElementById('btn-copy-whatsapp')?.addEventListener('click', () => {
      const text = document.getElementById('whatsapp-preview-box')?.textContent || '';
      navigator.clipboard.writeText(text);
      this.showToast('Copied WhatsApp message text to clipboard', 'success');
      this.logDispatchEvent('WHATSAPP');
    });

    // WhatsApp direct bot send and linking
    document.getElementById('btn-direct-send-wa')?.addEventListener('click', () => {
      this.sendPdfDirectlyToWhatsApp();
    });

    document.getElementById('btn-wa-link-device')?.addEventListener('click', () => {
      this.openWhatsAppQrModal();
    });

    document.getElementById('btn-close-wa-qr')?.addEventListener('click', () => {
      this.closeWhatsAppQrModal();
    });

    document.getElementById('btn-cancel-wa-qr')?.addEventListener('click', () => {
      this.closeWhatsAppQrModal();
    });

    document.getElementById('btn-open-whatsapp-web')?.addEventListener('click', (e) => {
      e.preventDefault();
      const deal = this.selectedDealForDispatch;
      if (!deal) return;
      const phoneInput = document.getElementById('dispatch-phone')?.value || deal.buyer_phone || '';
      const phoneDigits = phoneInput.replace(/[^0-9]/g, '');
      const waText = this.currentWaText || document.getElementById('whatsapp-preview-box')?.textContent || '';

      if (phoneDigits) {
        if (navigator.clipboard) {
          navigator.clipboard.writeText(waText).catch(() => {});
        }
        const waUrl = `https://web.whatsapp.com/send?phone=${phoneDigits}&text=${encodeURIComponent(waText.replace(/\r?\n/g, '\r\n'))}`;
        window.open(waUrl, '_blank');
        this.showToast(`✓ Opened WhatsApp for +${phoneDigits} (Formatted text copied to clipboard)`, 'success', 5000);
        this.logDispatchEvent('WHATSAPP', phoneInput);
        document.getElementById('modal-dispatch')?.classList.remove('active');
      } else {
        this.showToast('Please enter a valid phone number', 'warning');
      }
    });

    // Email tab actions
    document.getElementById('btn-copy-email')?.addEventListener('click', () => {
      const text = document.getElementById('email-preview-box')?.innerText || '';
      navigator.clipboard.writeText(text);
      this.showToast('Copied email text to clipboard', 'success');
    });

    document.getElementById('btn-open-email-client')?.addEventListener('click', () => {
      this.openEmailClient();
    });

    document.getElementById('btn-log-email-sent')?.addEventListener('click', () => {
      this.logDispatchEvent('EMAIL');
      document.getElementById('modal-dispatch')?.classList.remove('active');
    });

    // 1-Click Direct Send via Rediffmail (PDF attached)
    document.getElementById('btn-send-rediffmail-direct')?.addEventListener('click', () => {
      this.sendContractViaRediffmail();
    });

    // Rediffmail configuration modal triggers
    document.getElementById('btn-topbar-rediffmail')?.addEventListener('click', () => {
      this.openRediffmailModal();
    });
    document.getElementById('btn-open-rediffmail-config')?.addEventListener('click', () => {
      this.openRediffmailModal();
    });
    document.getElementById('btn-close-rediffmail-modal')?.addEventListener('click', () => {
      this.closeRediffmailModal();
    });
    document.getElementById('btn-cancel-rediffmail-config')?.addEventListener('click', () => {
      this.closeRediffmailModal();
    });

    // Rediffmail configuration form submit
    document.getElementById('form-rediffmail-config')?.addEventListener('submit', (e) => {
      this.saveRediffmailConfig(e);
    });

    // Test connection button
    document.getElementById('btn-test-rediffmail-connection')?.addEventListener('click', () => {
      this.testRediffmailConnection();
    });

    // Toggle password visibility in setup modal
    document.getElementById('btn-toggle-email-pass')?.addEventListener('click', () => {
      const passInput = document.getElementById('cfg-email-pass');
      if (passInput) {
        passInput.type = passInput.type === 'password' ? 'text' : 'password';
      }
    });

    // Preset selection change (Standard vs Pro vs Custom)
    document.getElementById('cfg-email-preset')?.addEventListener('change', (e) => {
      const preset = e.target.value;
      const hostInput = document.getElementById('cfg-email-host');
      const portInput = document.getElementById('cfg-email-port');
      if (preset === 'brevo') {
        if (hostInput) hostInput.value = 'smtp-relay.brevo.com';
        if (portInput) portInput.value = '587';
      } else if (preset === 'standard') {
        if (hostInput) hostInput.value = 'smtp.rediffmail.com';
        if (portInput) portInput.value = '587';
      } else if (preset === 'pro') {
        if (hostInput) hostInput.value = 'mail.rediffmailpro.com';
        if (portInput) portInput.value = '465';
      } else if (preset === 'gmail') {
        if (hostInput) hostInput.value = 'smtp.gmail.com';
        if (portInput) portInput.value = '587';
      }
    });

    // Party Profile modal
    document.getElementById('btn-close-party-profile')?.addEventListener('click', () => {
      document.getElementById('modal-party-profile')?.classList.remove('active');
    });

    document.querySelectorAll('#party-profile-tabs .profile-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#party-profile-tabs .profile-tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.dataset.tab;
        document.getElementById('tab-pane-prof-contacts').style.display = tab === 'contacts' ? 'flex' : 'none';
        document.getElementById('tab-pane-prof-deals').style.display = tab === 'deals' ? 'block' : 'none';
        document.getElementById('tab-pane-prof-commodities').style.display = tab === 'commodities' ? 'flex' : 'none';
      });
    });

    // Close on overlay backdrop click
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
      overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.classList.remove('active');
      });
    });
  },

  // Filters & Search Setup
  setupFilters() {
    // Debounced search on Bargains Hub
    const searchInput = document.getElementById('filter-search-input');
    let debounceTimer;
    searchInput?.addEventListener('input', (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        this.searchQuery = e.target.value.trim();
        this.renderBargainsHub();
      }, 300);
    });

    // Status filter pills
    document.querySelectorAll('#status-filter-group .filter-pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#status-filter-group .filter-pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.activeStatusFilter = btn.dataset.status;
        this.renderBargainsHub();
      });
    });

    // Sort select
    document.getElementById('sort-select')?.addEventListener('change', (e) => {
      this.sortBy = e.target.value;
      this.renderBargainsHub();
    });

    // Party type filter pills
    document.querySelectorAll('#party-type-filter-group .filter-pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#party-type-filter-group .filter-pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.activePartyFilter = btn.dataset.type;
        this.renderPartyDirectory();
      });
    });

    // Party search input
    const partySearch = document.getElementById('party-search-input');
    partySearch?.addEventListener('input', (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        this.partySearchQuery = e.target.value.trim();
        this.renderPartyDirectory();
      }, 300);
    });

    // CSV Export
    document.getElementById('btn-export-csv')?.addEventListener('click', () => {
      this.exportToCsv();
    });

    document.getElementById('btn-export-excel-report')?.addEventListener('click', () => {
      window.location.href = '/api/export/excel';
    });
  },

  resetFilters() {
    this.searchQuery = '';
    this.activeStatusFilter = 'ALL';
    const input = document.getElementById('filter-search-input');
    if (input) input.value = '';
    document.querySelectorAll('#status-filter-group .filter-pill-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.status === 'ALL');
    });
    this.renderBargainsHub();
  },

  exportToCsv() {
    const dealsToExport = (this.visibleBargains && this.visibleBargains.length > 0) ? this.visibleBargains : this.deals;
    if (!dealsToExport.length) {
      this.showToast('No deals to export', 'info');
      return;
    }

    const headers = [
      "Bargain ID",
      "Date",
      "Seller",
      "Seller Station",
      "Buyer",
      "Buyer Station",
      "Commodity",
      "Quantity (MT)",
      "Seller Rate (Rs/Qtl)",
      "Buyer Rate (Rs/Qtl)",
      "Status",
      "Reconfirm Required"
    ];

    const rows = dealsToExport.map(d => [
      d.bgn_code || d.id,
      d.deal_date,
      `"${(d.seller_name || '').replace(/"/g, '""')}"`,
      `"${(d.seller_station || '').replace(/"/g, '""')}"`,
      `"${(d.buyer_name || '').replace(/"/g, '""')}"`,
      `"${(d.buyer_station || '').replace(/"/g, '""')}"`,
      `"${(d.product_name || '').replace(/"/g, '""')}"`,
      (d.quantity_tonnes || (d.quantity_qtl * 0.1)).toFixed(1),
      d.seller_rate || d.rate_per_qtl,
      d.buyer_rate || d.rate_per_qtl,
      d.status,
      d.reconfirmation_required ? "YES" : "NO"
    ]);

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `GaneshAndCo_Bargains_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    this.showToast(`Exported ${dealsToExport.length} bargains to CSV`, 'success');
  },

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
};

// Boot on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  app.init();
});
