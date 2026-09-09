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
  marketRates: [],
  dashboardMetrics: null,
  activePartyFilter: 'ALL',
  activeStatusFilter: 'ALL',
  searchQuery: '',
  partySearchQuery: '',
  sortBy: 'date-desc',
  selectedDealForDispatch: null,

  // Initialization
  async init() {
    this.setupSidebar();
    this.setupNavigation();
    this.setupKeyboardShortcuts();
    this.setupCommandPalette();
    this.setupNewBargainModal();
    this.setupPartyModal();
    this.setupModals();
    this.setupFilters();

    // Initial Data Fetch
    await this.refreshAllData();

    // Auto Refresh Polling every 45 seconds for live Mandi Ticker
    setInterval(() => {
      this.fetchMarketRates();
      this.fetchDashboardMetrics(false);
    }, 45000);

    if (window.lucide) {
      lucide.createIcons();
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
        this.fetchMarketRates(),
        this.fetchDispatchLogs(),
        this.fetchDashboardMetrics()
      ]);

      this.renderCurrentView();
      this.updateCounters();
      this.renderMandiTicker();
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

  async fetchMarketRates() {
    try {
      this.marketRates = await this.api('/api/market-rates');
    } catch (_) {
      this.marketRates = [];
    }
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
      'dispatches': 'WhatsApp & Email Logs',
      'market-rates': 'Market Rates & Mandis',
      'reports': 'Trade Reports & Analytics',
      'trash': 'Trash / Recycle Bin'
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
      case 'market-rates':
        this.renderMarketRates();
        break;
      case 'reports':
        this.renderReports();
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
    const bargainsCount = document.getElementById('badge-bargains-count');
    if (bargainsCount) bargainsCount.textContent = this.deals.length;

    const partiesCount = document.getElementById('badge-parties-count');
    if (partiesCount) partiesCount.textContent = this.parties.length;

    const dispatchesCount = document.getElementById('badge-dispatches-count');
    if (dispatchesCount) dispatchesCount.textContent = this.dispatchLogs.length;

    const trashCount = document.getElementById('badge-trash-count');
    if (trashCount) trashCount.textContent = this.trashDeals.length;
  },

  // Live Mandi Ticker Marquee
  renderMandiTicker() {
    const track = document.getElementById('mandi-ticker-track');
    if (!track) return;

    if (!this.deals.length) return;

    const items = this.deals.slice(0, 8).map(d => {
      const bgn = d.bgn_code || d.id;
      const comm = d.product_name || 'Edible Oil';
      const qty = `${Math.round(d.quantity_tonnes || (d.quantity_qtl * 0.1))} MT`;
      const seller = (d.seller_trade_name || d.seller_name.split(',')[0]).toUpperCase();
      const buyer = (d.buyer_trade_name || d.buyer_name.split(',')[0]).toUpperCase();
      const rate = `₹${Math.round(d.rate_per_qtl).toLocaleString('en-IN')}/Qtl`;

      return `
        <div class="ticker-item">
          <span>[${bgn}] ${comm} ${qty}</span>
          <span>•</span>
          <strong>${seller} ➔ ${buyer}</strong>
          <span>•</span>
          <span class="rate">${rate}</span>
        </div>
      `;
    }).join('');

    // Duplicate string for seamless infinite marquee loop
    track.innerHTML = items + items;
  },

  // ==========================================================================
  // SCREEN 1: EXECUTIVE DASHBOARD
  // ==========================================================================
  renderDashboard() {
    const metrics = this.dashboardMetrics;
    if (!metrics) return;

    // 1. KPI Cards
    const elToday = document.getElementById('kpi-today-deals');
    if (elToday) elToday.textContent = metrics.todays_deals_count ?? this.deals.length;

    const elTrend = document.getElementById('kpi-deals-trend');
    if (elTrend) {
      const pct = metrics.deals_vs_yesterday_pct ?? 14;
      elTrend.textContent = `${pct >= 0 ? '+' : ''}${pct}% vs yesterday`;
    }

    const elVol = document.getElementById('kpi-traded-volume');
    if (elVol) {
      const totalMT = Math.round(metrics.active_traded_volume_mt || this.deals.reduce((acc, d) => acc + (d.quantity_tonnes || 0), 0));
      elVol.textContent = `${totalMT} MT`;
    }

    const elParties = document.getElementById('kpi-active-parties');
    if (elParties) elParties.textContent = metrics.active_parties_count ?? this.parties.length;

    const elPending = document.getElementById('kpi-pending-confirmations');
    if (elPending) {
      const pendingCount = this.deals.filter(d => d.status === 'PENDING' || d.is_buyer_confirmed === 0 || d.is_seller_confirmed === 0).length;
      elPending.textContent = pendingCount;
    }

    // 2. Commodity Volume Distribution
    const distContainer = document.getElementById('commodity-dist-container');
    if (distContainer && metrics.commodity_distribution) {
      const colors = ['fill-emerald', 'fill-gold', 'fill-cyan', 'fill-purple', 'fill-rose'];
      distContainer.innerHTML = metrics.commodity_distribution.map((item, idx) => {
        const colorClass = colors[idx % colors.length];
        return `
          <div class="commodity-dist-item">
            <div class="commodity-info-row">
              <span class="commodity-name">${this.escapeHtml(item.product_name)}</span>
              <span class="commodity-stats">
                <strong>${Math.round(item.total_tonnes)} MT</strong> (${item.deal_count} deals &bull; ${item.percentage}%)
              </span>
            </div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill ${colorClass}" style="width: ${item.percentage}%;"></div>
            </div>
          </div>
        `;
      }).join('');
    }

    // 3. Today's Bargains (In-Line Data Table)
    const tbody = document.getElementById('tbody-todays-bargains');
    if (tbody) {
      const activeDeals = this.deals.filter(d => !d.is_deleted);
      const todayDeals = activeDeals.length > 0 ? activeDeals : (metrics.recent_deals || []);

      if (todayDeals.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="9" style="text-align: center; color: var(--text-dim); padding: 40px;">
              No bargains recorded for today's session yet. Click <strong>+ New Bargain</strong> to add one.
            </td>
          </tr>
        `;
      } else {
        tbody.innerHTML = todayDeals.map(d => {
          const bgn = d.bgn_code || d.id;
          const sName = d.seller_name ? d.seller_name.split(',')[0] : 'Seller';
          const bName = d.buyer_name ? d.buyer_name.split(',')[0] : 'Buyer';
          const sStation = d.seller_station ? `<span class="station-tag">📍 ${this.escapeHtml(d.seller_station)}</span>` : '';
          const bStation = d.buyer_station ? `<span class="station-tag">📍 ${this.escapeHtml(d.buyer_station)}</span>` : '';
          const qty = `${Math.round(d.quantity_tonnes || (d.quantity_qtl * 0.1))} MT`;
          const rate = `₹${Math.round(d.rate_per_qtl).toLocaleString('en-IN')}`;
          const badgeClass = d.status === 'CONFIRMED' ? 'badge-confirmed' : d.status === 'CANCELLED' ? 'badge-cancelled' : 'badge-pending';

          return `
            <tr>
              <td>
                <a class="bgn-tag" onclick="app.openLetterheadModal('${d.id}')" title="Open Official A4 Bargain Confirmation">${bgn}</a>
              </td>
              <td class="mono" style="font-size: 12px; color: var(--text-muted);">${d.deal_date}</td>
              <td>
                <div style="display: flex; flex-direction: column; gap: 2px;">
                  <span style="font-weight: 600; color: #FFFFFF;">${this.escapeHtml(sName)}</span>
                  ${sStation}
                </div>
              </td>
              <td>
                <div style="display: flex; flex-direction: column; gap: 2px;">
                  <span style="font-weight: 600; color: #FFFFFF;">${this.escapeHtml(bName)}</span>
                  ${bStation}
                </div>
              </td>
              <td>
                <span style="font-weight: 500;">${this.escapeHtml(d.product_name)}</span>
              </td>
              <td class="mono" style="font-weight: 600;">${qty}</td>
              <td class="rate-figure">${rate}</td>
              <td>
                <span class="badge ${badgeClass}">${d.status}</span>
              </td>
              <td style="text-align: right;">
                <div style="display: flex; justify-content: flex-end; gap: 6px;">
                  <button class="btn btn-secondary btn-xs" onclick="app.openDispatchModal('${d.id}', 'both')" title="Send PDF to WhatsApp & Email">
                    <i data-lucide="send" style="width: 12px; height: 12px; color: #10B981;"></i>
                    <span>WhatsApp &amp; Email</span>
                  </button>
                  <button class="btn btn-secondary btn-xs" onclick="app.openLetterheadModal('${d.id}')" title="Official A4 Confirmation PDF">
                    <i data-lucide="file-text" style="width: 12px; height: 12px; color: var(--gold);"></i>
                    <span>A4 PDF</span>
                  </button>
                  <button class="btn btn-ghost btn-xs text-danger" onclick="app.trashDeal('${d.id}')" title="Delete Deal">
                    <i data-lucide="trash-2" style="width: 13px; height: 13px; color: var(--status-cancelled);"></i>
                  </button>
                </div>
              </td>
            </tr>
          `;
        }).join('');
      }
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
      if (this.sortBy === 'rate-desc') return b.rate_per_qtl - a.rate_per_qtl;
      if (this.sortBy === 'rate-asc') return a.rate_per_qtl - b.rate_per_qtl;
      if (this.sortBy === 'qty-desc') return b.quantity_tonnes - a.quantity_tonnes;
      return 0;
    });

    if (filtered.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="11" style="text-align: center; padding: 40px; color: var(--text-dim);">
            <i data-lucide="search-x" style="width: 32px; height: 32px; margin-bottom: 8px; opacity: 0.5;"></i>
            <p>No bargains match your filter criteria.</p>
            <button class="btn btn-secondary btn-sm" onclick="app.resetFilters()" style="margin-top: 10px;">Reset Filters</button>
          </td>
        </tr>
      `;
    } else {
      tbody.innerHTML = this.buildDealsTableRows(filtered, true);
    }
  },

  buildDealsTableRows(dealsList, showFullActions = false) {
    return dealsList.map(d => {
      const bgn = d.bgn_code || d.id;
      const sName = d.seller_name || 'Seller';
      const bName = d.buyer_name || 'Buyer';
      const sStation = d.seller_station ? `<span class="station-tag">📍 ${this.escapeHtml(d.seller_station)}</span>` : '';
      const bStation = d.buyer_station ? `<span class="station-tag">📍 ${this.escapeHtml(d.buyer_station)}</span>` : '';
      const rateStr = `₹${Math.round(d.rate_per_qtl).toLocaleString('en-IN')}`;
      const qtyStr = `${d.quantity_tonnes ? d.quantity_tonnes.toFixed(1) : (d.quantity_qtl * 0.1).toFixed(1)} MT`;

      let badgeClass = 'badge-confirmed';
      if (d.status === 'PENDING') badgeClass = 'badge-pending';
      if (d.status === 'CANCELLED') badgeClass = 'badge-cancelled';
      if (d.status === 'DRAFT') badgeClass = 'badge-revised';

      const buyerCheck = d.is_buyer_confirmed ? `<span class="check-pill check-yes">✓</span>` : `<span class="check-pill check-no">✕</span>`;
      const sellerCheck = d.is_seller_confirmed ? `<span class="check-pill check-yes">✓</span>` : `<span class="check-pill check-no">✕</span>`;

      return `
        <tr>
          <td>
            <a class="bgn-tag" onclick="app.openLetterheadModal('${d.id}')" title="Open Print-Ready A4 Confirmation">${bgn}</a>
          </td>
          <td class="mono" style="font-size: 12px; color: var(--text-muted);">${d.deal_date}</td>
          <td>
            <div style="display: flex; flex-direction: column; gap: 2px;">
              <span style="font-weight: 600; color: #FFFFFF;">${this.escapeHtml(sName)}</span>
              ${sStation}
            </div>
          </td>
          <td>
            <div style="display: flex; flex-direction: column; gap: 2px;">
              <span style="font-weight: 600; color: #FFFFFF;">${this.escapeHtml(bName)}</span>
              ${bStation}
            </div>
          </td>
          <td>
            <span style="font-weight: 500;">${this.escapeHtml(d.product_name)}</span>
          </td>
          <td class="mono" style="font-weight: 600;">${qtyStr}</td>
          <td class="rate-figure">${rateStr}</td>
          <td>
            <span class="badge ${badgeClass}">${d.status}</span>
          </td>
          <td style="text-align: center;">${buyerCheck}</td>
          <td style="text-align: center;">${sellerCheck}</td>
          <td style="text-align: right;">
            <div style="display: flex; justify-content: flex-end; gap: 6px;">
              <button class="btn btn-secondary btn-xs" onclick="app.openLetterheadModal('${d.id}')" title="Official A4 Confirmation">
                <i data-lucide="printer" style="width: 12px; height: 12px;"></i>
                <span>Letterhead</span>
              </button>
              <button class="btn btn-secondary btn-xs" onclick="app.openDispatchModal('${d.id}')" title="Dispatch via WhatsApp">
                <i data-lucide="message-circle" style="width: 12px; height: 12px; color: #25D366;"></i>
                <span>WhatsApp</span>
              </button>
              <button class="btn btn-ghost btn-xs" onclick="app.trashDeal('${d.id}')" title="Move to Trash">
                <i data-lucide="trash-2" style="width: 12px; height: 12px; color: var(--status-cancelled);"></i>
              </button>
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
          (p.bank_name && p.bank_name.toLowerCase().includes(q)) ||
          (p.bank_account_no && p.bank_account_no.toLowerCase().includes(q)) ||
          (p.bank_ifsc && p.bank_ifsc.toLowerCase().includes(q)) ||
          (p.contact_person && p.contact_person.toLowerCase().includes(q))
        );
      });
    }

    if (filtered.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-dim);">
          <i data-lucide="users-round" style="width: 32px; height: 32px; margin-bottom: 8px; opacity: 0.5;"></i>
          <p>No parties match your search.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = filtered.map(p => {
      const station = p.mandi_station || p.city || 'Mandi Yard';
      const pan = p.pan || (p.gstin ? p.gstin.substring(2, 12) : 'PAN PENDING');
      const gstin = p.gstin || 'UNREGISTERED';
      const bankInfo = p.bank_name ? 
        `🏦 ${this.escapeHtml(p.bank_name)} • A/c ${this.escapeHtml(p.bank_account_no || 'Pending')} • ${this.escapeHtml(p.bank_ifsc || '')}` : 
        '🏦 Bank Settlement Details Pending';

      // Parse contacts hierarchy
      let contacts = [];
      if (p.contacts_json) {
        try { contacts = JSON.parse(p.contacts_json); } catch (_) {}
      }
      if (!contacts.length) {
        contacts = [{ name: p.contact_person || 'Signatory', role: 'Owner', phone: p.phone || '', email: p.email || '' }];
      }

      const contactsHtml = contacts.map(c => {
        let roleClass = 'role-owner';
        if (c.role && c.role.toLowerCase().includes('dispatch')) roleClass = 'role-dispatch';
        if (c.role && (c.role.toLowerCase().includes('account') || c.role.toLowerCase().includes('broker'))) roleClass = 'role-accounts';

        const cleanPhone = (c.phone || '').replace(/[^0-9]/g, '');
        const waLink = cleanPhone ? `https://wa.me/${cleanPhone}?text=${encodeURIComponent(`Namaste ${c.name} Ji, Greetings from Ganesh & Company, Sri Ganganagar.`)}` : '#';

        return `
          <div class="contact-row">
            <div class="contact-left">
              <span class="contact-role-badge ${roleClass}">${this.escapeHtml(c.role || 'Contact')}</span>
              <span class="contact-person-name" title="${this.escapeHtml(c.name)}">${this.escapeHtml(c.name)}</span>
            </div>
            <div class="contact-actions">
              ${c.phone ? `
                <a href="${waLink}" target="_blank" rel="noopener noreferrer" class="btn-whatsapp-chat" title="Chat on WhatsApp">
                  <i data-lucide="message-circle" style="width: 11px; height: 11px;"></i>
                  <span>Chat</span>
                </a>
                <a href="tel:${c.phone}" class="btn btn-ghost btn-xs" title="Call ${c.phone}">
                  <i data-lucide="phone" style="width: 11px; height: 11px;"></i>
                </a>
              ` : ''}
            </div>
          </div>
        `;
      }).join('');

      return `
        <div class="party-card">
          <div class="party-card-top">
            <div class="party-name-group">
              <span class="party-legal-name">${this.escapeHtml(p.legal_name)}</span>
              <span class="party-station-badge">📍 ${this.escapeHtml(station)}</span>
            </div>
            <span class="badge ${p.party_type === 'SELLER' ? 'badge-cancelled' : p.party_type === 'BUYER' ? 'badge-confirmed' : 'badge-revised'}">
              ${p.party_type}
            </span>
          </div>

          <div class="gstin-pan-strip">
            <span>GST: <strong>${this.escapeHtml(gstin)}</strong></span>
            <span>&bull;</span>
            <span>PAN: <strong>${this.escapeHtml(pan)}</strong></span>
          </div>

          <div class="bank-details-strip" style="font-size: 11px; color: var(--emerald); background: rgba(16, 185, 129, 0.05); padding: 5px 8px; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.15); display: flex; align-items: center; justify-content: space-between; margin: 4px 0 6px 0;" title="${this.escapeHtml(bankInfo)}">
            <span style="font-family: var(--font-mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${bankInfo}</span>
          </div>

          <div class="contact-hierarchy-list">
            ${contactsHtml}
          </div>

          <div style="display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--border-subtle); padding-top: 10px; margin-top: 4px; gap: 6px;">
            <button class="btn btn-secondary btn-xs" onclick="app.openPartyProfileModal('${p.id}')">
              <i data-lucide="eye" style="width: 12px; height: 12px;"></i>
              <span>Profile</span>
            </button>
            <button class="btn btn-ghost btn-xs" onclick="app.openEditPartyModal('${p.id}')" style="border: 1px solid var(--border-subtle);" title="Edit Party Details & Bank Account">
              <i data-lucide="pencil" style="width: 12px; height: 12px;"></i>
              <span>Edit</span>
            </button>
            <button class="btn btn-primary btn-xs" onclick="app.openNewBargainForParty('${p.id}')">
              <i data-lucide="plus" style="width: 12px; height: 12px;"></i>
              <span>+ Deal</span>
            </button>
          </div>
        </div>
      `;
    }).join('');
  },

  // ==========================================================================
  // SCREEN 3: AUTHENTIC A4 CONFIRMATION PRINT VIEW
  // ==========================================================================
  openLetterheadModal(dealId) {
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

    document.getElementById('doc-rate').textContent = `₹${Math.round(deal.rate_per_qtl).toLocaleString('en-IN')} + GST Per Qt.`;
    document.getElementById('doc-advance-date').textContent = deal.advance_payment_date || deal.deal_date;
    document.getElementById('doc-delivery-condition').textContent = deal.delivery_condition || `Ex-Mill Delivery Lifting: ${deal.deal_date} to ${deal.delivery_date}`;

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

  // Official PDF Generator / Downloader
  downloadContractPdf(dealId) {
    const deal = dealId 
      ? (this.deals.find(d => d.id === dealId) || this.trashDeals.find(d => d.id === dealId))
      : (this.selectedDealForLetterhead || this.selectedDealForDispatch || this.deals[0]);
    
    const bgn = deal ? (deal.bgn_code || deal.id) : 'Bargain_Confirmation';
    const filename = `Bargain_Confirmation_${bgn}.pdf`;
    const element = document.getElementById('printable-contract-area');

    if (!element) {
      window.print();
      return;
    }

    this.showToast(`Generating official system PDF: ${filename}...`, 'info');

    if (window.html2pdf) {
      const opt = {
        margin: [8, 10, 8, 10],
        filename: filename,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, logging: false },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
      };
      html2pdf().set(opt).from(element).save().then(() => {
        this.showToast(`Downloaded ${filename} successfully!`, 'success');
      }).catch(err => {
        console.warn('html2pdf fallback to print:', err);
        window.print();
      });
    } else {
      window.print();
    }
  },

  // Print Trigger
  triggerPrint() {
    window.print();
  },

  // ==========================================================================
  // SCREEN 5: PARTY PROFILE MODAL
  // ==========================================================================
  async openPartyProfileModal(partyId) {
    try {
      this.currentProfilePartyId = partyId;
      const data = await this.api(`/api/parties/${partyId}/profile`);
      const party = data.party;
      const kpis = data.kpis;

      document.getElementById('profile-party-name').textContent = party.legal_name;
      document.getElementById('prof-kpi-deals').textContent = kpis.total_deals;
      document.getElementById('prof-kpi-volume').textContent = `${Math.round(kpis.confirmed_volume_mt)} MT`;
      document.getElementById('prof-kpi-pending').textContent = kpis.pending_deals;
      const stationEl = document.getElementById('prof-kpi-station');
      if (stationEl) stationEl.textContent = party.mandi_station || party.city || 'Mandi Yard';

      const bankHtml = party.bank_name ? `
        <div style="background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 8px; padding: 12px; margin-top: 12px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
            <span style="font-size: 11px; font-weight: 700; color: var(--emerald); text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; gap: 6px;">
              <i data-lucide="landmark" style="width: 14px; height: 14px;"></i> Bank Settlement Details
            </span>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-ghost btn-xs" onclick="app.copyToClipboard('${party.bank_account_no}', 'Account Number copied!')" title="Copy Account Number">
                <i data-lucide="copy" style="width: 11px; height: 11px;"></i> Copy A/C
              </button>
              <button class="btn btn-ghost btn-xs" onclick="app.copyToClipboard('${party.bank_ifsc}', 'IFSC Code copied!')" title="Copy IFSC">
                <i data-lucide="copy" style="width: 11px; height: 11px;"></i> Copy IFSC
              </button>
            </div>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px;">
            <div><span style="color: var(--text-dim);">Bank:</span> <strong style="color: #fff;">${this.escapeHtml(party.bank_name)}</strong></div>
            <div><span style="color: var(--text-dim);">Account No:</span> <strong class="mono" style="color: var(--emerald);">${this.escapeHtml(party.bank_account_no || 'N/A')}</strong></div>
            <div><span style="color: var(--text-dim);">IFSC Code:</span> <strong class="mono" style="color: var(--gold);">${this.escapeHtml(party.bank_ifsc || 'N/A')}</strong></div>
            <div><span style="color: var(--text-dim);">Branch:</span> <span>${this.escapeHtml(party.bank_branch || 'Mandi Branch')}</span></div>
          </div>
        </div>
      ` : `
        <div style="background: rgba(255, 255, 255, 0.02); border: 1px dashed var(--border-subtle); border-radius: 8px; padding: 12px; margin-top: 12px; display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: var(--text-dim);">
          <span>No bank settlement account registered.</span>
          <button class="btn btn-secondary btn-xs" onclick="document.getElementById('modal-party-profile').classList.remove('active'); app.openEditPartyModal('${party.id}');">
            <i data-lucide="plus" style="width: 11px; height: 11px;"></i> Add Bank Info
          </button>
        </div>
      `;

      // Overview details
      const metaEl = document.getElementById('prof-meta-details');
      metaEl.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
          <div><strong>Station:</strong> ${party.mandi_station || party.city || 'Mandi Yard'}</div>
          <div><strong>Party Type:</strong> ${party.party_type}</div>
          <div><strong>GSTIN:</strong> ${party.gstin || 'Unregistered'}</div>
          <div><strong>PAN:</strong> ${party.pan || (party.gstin ? party.gstin.substring(2, 12) : 'N/A')}</div>
          <div><strong>Address:</strong> ${party.address || 'Mandi Yard'}</div>
          <div><strong>Credit Limit:</strong> ₹${(party.credit_limit || 0).toLocaleString('en-IN')}</div>
        </div>
        ${bankHtml}
      `;

      // Contacts list
      const contactsEl = document.getElementById('prof-contacts-list');
      contactsEl.innerHTML = data.contacts.map(c => `
        <div class="contact-row">
          <div class="contact-left">
            <span class="contact-role-badge ${c.role === 'Owner' ? 'role-owner' : c.role.includes('Dispatch') ? 'role-dispatch' : 'role-accounts'}">${c.role}</span>
            <span class="contact-person-name">${c.name} &bull; ${c.phone || ''} &bull; ${c.email || ''}</span>
          </div>
        </div>
      `).join('');

      // Deals list
      const dealsTbody = document.getElementById('tbody-prof-deals');
      if (data.deals.length === 0) {
        dealsTbody.innerHTML = `<tr><td colspan="9" style="text-align: center; padding: 20px; color: var(--text-dim);">No transactions on record.</td></tr>`;
      } else {
        dealsTbody.innerHTML = data.deals.map(d => `
          <tr>
            <td><a class="bgn-tag" onclick="app.openLetterheadModal('${d.id}')">${d.bgn_code || d.id}</a></td>
            <td class="mono">${d.deal_date}</td>
            <td>${d.buyer_id === partyId ? 'BUYER' : 'SELLER'}</td>
            <td>${d.buyer_id === partyId ? d.seller_name : d.buyer_name}</td>
            <td>${d.product_name}</td>
            <td class="mono">${(d.quantity_tonnes || d.quantity_qtl * 0.1).toFixed(1)} MT</td>
            <td class="rate-figure">₹${Math.round(d.rate_per_qtl).toLocaleString('en-IN')}</td>
            <td><span class="badge ${d.status === 'CONFIRMED' ? 'badge-confirmed' : 'badge-pending'}">${d.status}</span></td>
            <td>
              <button class="btn btn-secondary btn-xs" onclick="app.openLetterheadModal('${d.id}')">Letterhead</button>
            </td>
          </tr>
        `).join('');
      }

      // Commodity bars
      const commBars = document.getElementById('prof-commodity-bars');
      if (data.commodity_history.length === 0) {
        commBars.innerHTML = `<div style="color: var(--text-dim); text-align: center; padding: 20px;">No commodity trade history.</div>`;
      } else {
        commBars.innerHTML = data.commodity_history.map(item => `
          <div class="commodity-dist-item">
            <div class="commodity-info-row">
              <span class="commodity-name">${item.product_name}</span>
              <span class="commodity-stats"><strong>${Math.round(item.total_tonnes)} MT</strong> (${item.percentage}%)</span>
            </div>
            <div class="progress-bar-bg">
              <div class="progress-bar-fill fill-gold" style="width: ${item.percentage}%;"></div>
            </div>
          </div>
        `).join('');
      }

      const modal = document.getElementById('modal-party-profile');
      if (modal) modal.classList.add('active');

      if (window.lucide) lucide.createIcons();
    } catch (err) {
      this.showToast('Failed to load party profile', 'error');
    }
  },

  // ==========================================================================
  // SCREEN 6: INSTANT COMMUNICATION DISPATCH MODAL
  // ==========================================================================
  openDispatchModal(dealId, initialTab = 'both') {
    const deal = this.deals.find(d => d.id === dealId) || this.trashDeals.find(d => d.id === dealId);
    if (!deal) return;

    this.selectedDealForDispatch = deal;
    this.selectedDealForLetterhead = deal;
    const bgn = deal.bgn_code || deal.id;
    const sName = deal.seller_name || 'Seller';
    const bName = deal.buyer_name || 'Buyer';
    const sStation = deal.seller_station || 'Sangaria';
    const bStation = deal.buyer_station || 'Siliguri';
    const tonnes = deal.quantity_tonnes ? deal.quantity_tonnes.toFixed(0) : (deal.quantity_qtl * 0.1).toFixed(0);
    const rate = Math.round(deal.rate_per_qtl).toLocaleString('en-IN');
    const advance = deal.advance_payment_date || deal.deal_date;
    const delivery = deal.delivery_condition || 'Ex-Mill Lifting as per contract';
    const pdfName = `Bargain_Confirmation_${bgn}.pdf`;

    // Populate filename in all badges
    ['both-pdf-filename', 'wa-pdf-filename', 'email-pdf-filename'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = pdfName;
    });

    // Clean Phone number
    const rawPhone = deal.buyer_phone || deal.seller_phone || '+91 94140 51234';
    const phoneDigits = rawPhone.replace(/[^0-9]/g, '');
    const formattedPhone = phoneDigits.startsWith('91') ? `+${phoneDigits}` : `+91 ${phoneDigits}`;
    const emailTo = deal.buyer_email || deal.seller_email || 'recipient@mandi.in';

    // Populate inputs
    if (document.getElementById('dispatch-both-phone')) document.getElementById('dispatch-both-phone').value = formattedPhone;
    if (document.getElementById('dispatch-both-email')) document.getElementById('dispatch-both-email').value = emailTo;
    if (document.getElementById('dispatch-phone')) document.getElementById('dispatch-phone').value = formattedPhone;
    if (document.getElementById('dispatch-email-to')) document.getElementById('dispatch-email-to').value = emailTo;

    // WhatsApp Formatted Text with System-Generated Notice and Direct Online Link
    const baseUrl = this.publicUrl || window.location.origin;
    const contractUrl = `${baseUrl}/contract/${deal.id}`;
    const directPdfUrl = `${baseUrl}/api/deals/${deal.id}/pdf`;
    const waText = 
`*BARGAIN CONFIRMATION — GANESH & COMPANY*
*Sri Ganganagar, Rajasthan*
━━━━━━━━━━━━━━━━━━━━━━━━
*Bargain No:* ${bgn}
*Date:* ${deal.deal_date}
*Seller:* ${sName.toUpperCase()} (${sStation})
*Buyer:* ${bName.toUpperCase()} (${bStation})
*Commodity:* ${deal.product_name}
*Quantity:* ${tonnes} Tons (${deal.quantity_qtl} Quintals)
*Rate:* ₹${rate} + GST Per Quintal
*Advance Payment Date:* ${advance}
*Delivery Condition:* ${delivery}
━━━━━━━━━━━━━━━━━━━━━━━━
📄 *Official Document:* ${pdfName}
🔗 *View & Download PDF:* ${contractUrl}
📥 *Direct PDF Link:* ${directPdfUrl}
⚠️ *Note:* This PDF is a system-generated document and does not require a physical signature.
_All deals subject to Sri Ganganagar Jurisdiction._
_For inquiries contact: Sanjay Kumar Aggarwal (94619-40113)_`;

    this.currentWaText = waText;

    // Previews
    if (document.getElementById('whatsapp-preview-box')) document.getElementById('whatsapp-preview-box').textContent = waText;
    if (document.getElementById('both-preview-box')) document.getElementById('both-preview-box').textContent = waText;

    // Direct Web Link with proper CRLF line breaks
    const waUrl = `https://web.whatsapp.com/send?phone=${phoneDigits}&text=${encodeURIComponent(waText.replace(/\r?\n/g, '\r\n'))}`;
    const openBtn = document.getElementById('btn-open-whatsapp-web');
    if (openBtn) openBtn.href = waUrl;

    // Email Subject and Body with System-Generated Notice
    const emailSubject = `Official Bargain Confirmation [${bgn}] (System Generated PDF) - Ganesh & Company`;
    if (document.getElementById('dispatch-email-subject')) document.getElementById('dispatch-email-subject').value = emailSubject;
    if (document.getElementById('email-preview-box')) {
      document.getElementById('email-preview-box').innerHTML = `
Dear Sir,<br><br>
We have confirmed the following bargain as Canvassing Agents:<br><br>
<strong>Bargain ID:</strong> ${bgn}<br>
<strong>Commodity:</strong> ${deal.product_name}<br>
<strong>Quantity:</strong> ${tonnes} MT (${deal.quantity_qtl} Quintals)<br>
<strong>Rate:</strong> ₹${rate} + GST per quintal<br>
<strong>Seller:</strong> ${sName} (${sStation})<br>
<strong>Buyer:</strong> ${bName} (${bStation})<br>
<strong>Advance Date:</strong> ${advance}<br>
<strong>Delivery Condition:</strong> ${delivery}<br><br>
<strong>Document:</strong> ${pdfName}<br>
<em>*** NOTE: This is a system-generated PDF document and does not require a physical signature. All transactions subject to Sri Ganganagar Jurisdiction. ***</em><br><br>
Yours faithfully,<br>
<strong>Ganesh & Company, Sri Ganganagar</strong><br>
House No.2 Friends Colony, Opp. Bahal Petrol Pump<br>
Mob. 94619-40113 / 94619-40114 / 94619-40115
      `;
    }

    // Switch to initial tab
    this.switchDispatchTab(initialTab);

    const modal = document.getElementById('modal-dispatch');
    if (modal) modal.classList.add('active');

    if (window.lucide) lucide.createIcons();
    this.checkWhatsAppBotStatus();
  },

  switchDispatchTab(tab) {
    document.querySelectorAll('#dispatch-tabs .profile-tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    const bothPane = document.getElementById('tab-pane-both');
    const waPane = document.getElementById('tab-pane-whatsapp');
    const emailPane = document.getElementById('tab-pane-email');

    if (bothPane) bothPane.style.display = tab === 'both' ? 'flex' : 'none';
    if (waPane) waPane.style.display = tab === 'whatsapp' ? 'flex' : 'none';
    if (emailPane) emailPane.style.display = tab === 'email' ? 'flex' : 'none';
  },

  async sendPdfToBoth() {
    if (!this.selectedDealForDispatch) return;
    const deal = this.selectedDealForDispatch;
    const bgn = deal.bgn_code || deal.id;
    const phoneInput = document.getElementById('dispatch-both-phone')?.value || '';
    const phoneDigits = phoneInput.replace(/[^0-9]/g, '');
    const emailTo = document.getElementById('dispatch-both-email')?.value || '';
    const pdfName = `Bargain_Confirmation_${bgn}.pdf`;

    // 1. Download official PDF to local computer
    this.downloadContractPdf(deal.id);

    // 2. Launch WhatsApp Web with pre-filled message
    const waText = document.getElementById('both-preview-box')?.textContent || '';
    if (phoneDigits) {
      const waUrl = `https://web.whatsapp.com/send?phone=${phoneDigits}&text=${encodeURIComponent(waText)}`;
      window.open(waUrl, '_blank');
    }

    // 3. Launch Email Client (mailto:)
    if (emailTo) {
      const subject = encodeURIComponent(`Official Bargain Confirmation [${bgn}] (System Generated PDF) - Ganesh & Company`);
      const body = encodeURIComponent(
`Dear Sir,

Please find confirmed the following bargain contract canvassed by Ganesh & Company:

Bargain ID: ${bgn}
Commodity: ${deal.product_name}
Quantity: ${deal.quantity_tonnes || (deal.quantity_qtl * 0.1)} MT (${deal.quantity_qtl} Quintals)
Rate: ₹${Math.round(deal.rate_per_qtl)} + GST per quintal
Seller: ${deal.seller_name}
Buyer: ${deal.buyer_name}
Delivery Condition: ${deal.delivery_condition || 'Ex-Mill Lifting'}

Attached Document: ${pdfName}
*** NOTE: This is a system-generated PDF document and does not require a physical signature. All transactions subject to Sri Ganganagar Jurisdiction. ***

Yours faithfully,
Ganesh & Company, Sri Ganganagar
Phone: 94619-40113 / 94619-40114`
      );
      const mailtoLink = document.createElement('a');
      mailtoLink.href = `mailto:${emailTo}?subject=${subject}&body=${body}`;
      mailtoLink.target = '_blank';
      mailtoLink.click();
    }

    // 4. Log both channels in backend database
    await this.logDispatchEvent('WHATSAPP', phoneInput);
    await this.logDispatchEvent('EMAIL', emailTo);

    this.showToast(`✓ Official PDF downloaded & dispatched to WhatsApp and Email`, 'success', 5000);
    document.getElementById('modal-dispatch')?.classList.remove('active');
  },

  async sharePdfDirectly() {
    if (!this.selectedDealForDispatch) return;
    const deal = this.selectedDealForDispatch;
    const bgn = deal.bgn_code || deal.id;
    const filename = `Bargain_Confirmation_${bgn}.pdf`;
    const waText = document.getElementById('both-preview-box')?.textContent || document.getElementById('whatsapp-preview-box')?.textContent || '';

    // Fast instant download from backend PDF generator
    const link = document.createElement('a');
    link.href = `/api/deals/${deal.id}/pdf`;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    // If Web Share API is available (e.g. mobile or Mac Safari), share file directly
    if (navigator.canShare) {
      try {
        const resp = await fetch(`/api/deals/${deal.id}/pdf`);
        const blob = await resp.blob();
        const file = new File([blob], filename, { type: 'application/pdf' });

        if (navigator.canShare({ files: [file] })) {
          await navigator.share({
            files: [file],
            title: `Bargain Confirmation [${bgn}]`,
            text: waText
          });
          this.showToast('✓ PDF shared via WhatsApp successfully', 'success');
          this.logDispatchEvent('WHATSAPP');
          return;
        }
      } catch (err) {
        if (err.name === 'AbortError') return;
        console.warn('Share error:', err);
      }
    }

    // Default desktop browser: Open WhatsApp with formatted deal message and direct online contract link
    const phoneInput = document.getElementById('dispatch-both-phone')?.value || document.getElementById('dispatch-phone')?.value || deal.buyer_phone || '';
    const phoneDigits = phoneInput.replace(/[^0-9]/g, '');
    if (phoneDigits) {
      const waUrl = `https://web.whatsapp.com/send?phone=${phoneDigits}&text=${encodeURIComponent(waText)}`;
      window.open(waUrl, '_blank');
      this.showToast(`✓ PDF downloaded & WhatsApp opened for +${phoneDigits}`, 'success');
      this.logDispatchEvent('WHATSAPP');
    }
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
  // SCREEN 7: MARKET RATES & MANDI BENCHMARKS
  // ==========================================================================
  renderMarketRates() {
    const grid = document.getElementById('market-rates-grid');
    if (!grid) return;

    if (!this.marketRates.length) {
      grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: var(--text-dim); padding: 30px;">No benchmark rates available.</div>`;
      return;
    }

    grid.innerHTML = this.marketRates.map(r => {
      const changeVal = r.change_today || 0;
      const isPositive = changeVal >= 0;
      return `
        <div class="kpi-card">
          <div class="kpi-card-header">
            <span class="kpi-title">${this.escapeHtml(r.commodity_name)}</span>
            <span class="station-tag">📍 ${this.escapeHtml(r.mandi_station)}</span>
          </div>
          <div class="kpi-value-row">
            <span class="kpi-value">₹${Math.round(r.benchmark_rate_qtl).toLocaleString('en-IN')}</span>
            <span class="kpi-badge ${isPositive ? 'kpi-badge-positive' : 'kpi-badge-warning'}">
              ${isPositive ? '▲ +' : '▼ '}${changeVal}
            </span>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-dim); margin-top: 4px;">
            <span>High: ₹${Math.round(r.high_rate || r.benchmark_rate_qtl).toLocaleString('en-IN')}</span>
            <span>Low: ₹${Math.round(r.low_rate || r.benchmark_rate_qtl).toLocaleString('en-IN')}</span>
          </div>
        </div>
      `;
    }).join('');
  },

  // ==========================================================================
  // SCREEN 8: DISPATCH AUDIT LOGS
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
          <td><a class="bgn-tag" onclick="app.openLetterheadModal('${l.deal_id}')">${l.bgn_code || l.deal_id}</a></td>
          <td><strong>${this.escapeHtml(l.recipient_name)}</strong></td>
          <td><span class="badge badge-revised">${l.recipient_type}</span></td>
          <td>
            <span style="display: inline-flex; align-items: center; gap: 4px; font-weight: 600; color: ${isWA ? '#25D366' : '#38BDF8'};">
              <i data-lucide="${isWA ? 'message-circle' : 'mail'}" style="width: 13px; height: 13px;"></i>
              ${l.channel}
            </span>
          </td>
          <td class="mono">${this.escapeHtml(l.phone_or_email || '')}</td>
          <td style="max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-muted);">${this.escapeHtml(l.message_preview)}</td>
          <td><span class="badge badge-confirmed">${l.status}</span></td>
          <td class="mono" style="font-size: 11px; color: var(--text-dim);">${l.created_at.replace('T', ' ').substring(0, 16)}</td>
        </tr>
      `;
    }).join('');
  },

  // ==========================================================================
  // SCREEN 9: REPORTS & ANALYTICS
  renderReports() {
    const m = this.dashboardMetrics;
    if (!m) return;

    const totalDealsEl = document.getElementById('rep-total-deals');
    if (totalDealsEl) totalDealsEl.textContent = m.total_active_deals || this.deals.length;

    const volEl = document.getElementById('rep-traded-volume');
    if (volEl) volEl.textContent = `${Math.round(m.active_traded_volume_mt || 0)} MT`;

    const diffProfitEl = document.getElementById('rep-diff-profit');
    if (diffProfitEl) diffProfitEl.textContent = `₹${Math.round(m.total_price_diff_profit || 0).toLocaleString('en-IN')}`;

    const partiesCountEl = document.getElementById('rep-active-parties');
    if (partiesCountEl) partiesCountEl.textContent = m.active_parties_count || this.parties.length;

    const tbody = document.getElementById('tbody-party-receivables');
    if (tbody) {
      tbody.innerHTML = this.parties.map(p => {
        const partyDeals = this.deals.filter(d => d.buyer_id === p.id || d.seller_id === p.id);
        const totalTonnes = partyDeals.reduce((sum, d) => sum + (d.quantity_tonnes || (d.quantity_qtl * 0.1) || 0), 0);
        return `
          <tr>
            <td><strong>${this.escapeHtml(p.legal_name)}</strong></td>
            <td><span class="station-tag">📍 ${this.escapeHtml(p.mandi_station || p.city || 'Mandi Yard')}</span></td>
            <td><span class="badge ${p.party_type === 'SELLER' ? 'badge-cancelled' : p.party_type === 'BUYER' ? 'badge-confirmed' : 'badge-revised'}">${p.party_type}</span></td>
            <td class="mono">${partyDeals.length} Contracts</td>
            <td class="rate-figure" style="color: var(--emerald); font-weight: 700;">${totalTonnes.toFixed(1)} MT</td>
            <td>
              <button class="btn btn-secondary btn-xs" onclick="app.openPartyProfileModal('${p.id}')">View Profile</button>
            </td>
          </tr>
        `;
      }).join('');
    }
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
        <td><span class="bgn-tag" style="opacity: 0.7;">${d.bgn_code || d.id}</span></td>
        <td class="mono">${d.deal_date}</td>
        <td>${d.seller_name}</td>
        <td>${d.buyer_name}</td>
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
      this.renderMandiTicker();
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
      this.renderMandiTicker();
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
      if (equivLabel) equivLabel.textContent = `= ${mt.toFixed(1)} MT (Tonnes)`;
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
      const rateQtl = parseFloat(document.getElementById('input-rate-qtl').value);
      const advanceDate = document.getElementById('input-advance-date').value;
      const deliveryCondition = document.getElementById('input-delivery-condition').value;
      const notes = document.getElementById('input-deal-notes').value;

      if (!sellerId || !buyerId) {
        this.showToast('Please select valid Seller and Buyer from suggestions', 'error');
        return;
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
            rate_per_qtl: rateQtl,
            advance_payment_date: advanceDate,
            delivery_condition: deliveryCondition,
            notes: notes
          })
        });

        this.showToast(`Bargain contract ${result.deal_id} created successfully!`, 'success');
        closeModal();

        await this.fetchDeals();
        await this.fetchDashboardMetrics();
        this.updateCounters();
        this.renderCurrentView();
        this.renderMandiTicker();

        // Prompt to open A4 letterhead confirmation
        this.openLetterheadModal(result.deal_id);
      } catch (_) {}
    });
  },

  // Helper for copying text with feedback
  copyToClipboard(text, successMsg = 'Copied to clipboard!') {
    if (!text) {
      this.showToast('Nothing to copy', 'warning');
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        this.showToast(successMsg, 'success');
      }).catch(() => {
        this.fallbackCopyText(text, successMsg);
      });
    } else {
      this.fallbackCopyText(text, successMsg);
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
    } catch (err) {
      this.showToast(`Error saving party: ${err.message}`, 'error');
    }
  },

  setupAutocomplete(inputId, hiddenId, dropdownId, roleType) {
    const input = document.getElementById(inputId);
    const hidden = document.getElementById(hiddenId);
    const dropdown = document.getElementById(dropdownId);
    if (!input || !dropdown) return;

    let selectedIndex = -1;

    const renderOptions = (matches) => {
      if (!matches.length) {
        dropdown.innerHTML = `<div style="padding: 10px; color: var(--text-dim); font-size: 12px;">No matching parties</div>`;
        dropdown.classList.add('active');
        return;
      }

      dropdown.innerHTML = matches.map((p, idx) => `
        <div class="autocomplete-option" data-id="${p.id}" data-name="${p.legal_name}" data-idx="${idx}">
          <div>
            <strong>${p.legal_name}</strong>
            <span style="font-size: 11px; color: var(--text-dim); display: block;">📍 ${p.mandi_station || p.city || 'Mandi'}</span>
          </div>
          <span class="badge ${p.party_type === 'SELLER' ? 'badge-cancelled' : 'badge-confirmed'}">${p.party_type}</span>
        </div>
      `).join('');

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
        return (
          p.legal_name.toLowerCase().includes(q) ||
          (p.trade_name && p.trade_name.toLowerCase().includes(q)) ||
          (p.mandi_station && p.mandi_station.toLowerCase().includes(q)) ||
          (p.city && p.city.toLowerCase().includes(q))
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
        options.forEach((opt, idx) => opt.classList.toggle('selected', idx === selectedIndex));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = (selectedIndex - 1 + options.length) % options.length;
        options.forEach((opt, idx) => opt.classList.toggle('selected', idx === selectedIndex));
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
        { label: 'Go to Market Rates & Mandis', view: 'market-rates' },
        { label: 'Go to Reports & Brokerage', view: 'reports' },
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
      <div style="font-size: 11px; font-weight: 700; color: var(--text-dim); padding: 4px 8px; text-transform: uppercase;">Quick Actions</div>
      <div class="command-item" onclick="app.closeCommandPalette(); document.getElementById('btn-open-new-bargain')?.click();">
        <div class="command-item-left">
          <i data-lucide="plus-circle" style="width: 14px; height: 14px; color: var(--emerald);"></i>
          <span>+ Create New Bargain Contract</span>
        </div>
        <kbd>Ctrl+B</kbd>
      </div>
      <div class="command-item" onclick="app.closeCommandPalette(); app.openNewPartyModal();">
        <div class="command-item-left">
          <i data-lucide="user-plus" style="width: 14px; height: 14px; color: var(--emerald);"></i>
          <span>+ Add New Party Master</span>
        </div>
      </div>
      <div class="command-item" onclick="app.closeCommandPalette(); app.exportToCsv();">
        <div class="command-item-left">
          <i data-lucide="download" style="width: 14px; height: 14px; color: var(--gold);"></i>
          <span>Export All Bargains to CSV</span>
        </div>
      </div>
      <div class="command-item" onclick="app.closeCommandPalette(); app.navigate('bargains');">
        <div class="command-item-left">
          <i data-lucide="receipt" style="width: 14px; height: 14px;"></i>
          <span>View All Bargain Contracts</span>
        </div>
      </div>
      <div class="command-item" onclick="app.closeCommandPalette(); app.navigate('parties');">
        <div class="command-item-left">
          <i data-lucide="building-2" style="width: 14px; height: 14px;"></i>
          <span>View Party Directory (Mills & Buyers)</span>
        </div>
      </div>
      <div class="command-item" onclick="app.closeCommandPalette(); app.navigate('market-rates');">
        <div class="command-item-left">
          <i data-lucide="trending-up" style="width: 14px; height: 14px;"></i>
          <span>View Live Mandi Benchmark Rates</span>
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
    document.getElementById('btn-download-pdf')?.addEventListener('click', () => {
      this.downloadContractPdf(this.selectedDealForLetterhead?.id);
    });
    document.getElementById('btn-letterhead-dispatch')?.addEventListener('click', () => {
      const dealId = this.selectedDealForLetterhead?.id;
      if (dealId) {
        document.getElementById('modal-letterhead')?.classList.remove('active');
        this.openDispatchModal(dealId, 'both');
      }
    });

    // Dispatch modal actions
    document.getElementById('btn-close-dispatch')?.addEventListener('click', () => {
      document.getElementById('modal-dispatch')?.classList.remove('active');
    });

    document.querySelectorAll('#dispatch-tabs .profile-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this.switchDispatchTab(btn.dataset.tab);
      });
    });

    // PDF Download triggers in dispatch tabs
    document.getElementById('btn-both-download-pdf')?.addEventListener('click', () => {
      this.downloadContractPdf(this.selectedDealForDispatch?.id);
    });
    document.getElementById('btn-wa-download-pdf')?.addEventListener('click', () => {
      this.downloadContractPdf(this.selectedDealForDispatch?.id);
    });
    document.getElementById('btn-email-download-pdf')?.addEventListener('click', () => {
      this.downloadContractPdf(this.selectedDealForDispatch?.id);
    });

    // Send PDF to Both (WhatsApp + Email) Action
    document.getElementById('btn-dispatch-both-action')?.addEventListener('click', () => {
      this.sendPdfToBoth();
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
    if (!this.deals.length) {
      this.showToast('No deals to export', 'info');
      return;
    }

    const headers = ["Bargain ID", "Date", "Seller", "Seller Station", "Buyer", "Buyer Station", "Commodity", "Quantity (MT)", "Rate (Rs/Qtl)", "Status"];
    const rows = this.deals.map(d => [
      d.bgn_code || d.id,
      d.deal_date,
      `"${(d.seller_name || '').replace(/"/g, '""')}"`,
      `"${(d.seller_station || '').replace(/"/g, '""')}"`,
      `"${(d.buyer_name || '').replace(/"/g, '""')}"`,
      `"${(d.buyer_station || '').replace(/"/g, '""')}"`,
      `"${(d.product_name || '').replace(/"/g, '""')}"`,
      d.quantity_tonnes || (d.quantity_qtl * 0.1),
      d.rate_per_qtl,
      d.status
    ]);

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `GaneshAndCo_Bargains_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    this.showToast('Exported bargains register to CSV', 'success');
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
