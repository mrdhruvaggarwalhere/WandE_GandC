/**
 * Deal Chain & Resale Linking Controller
 * Visualizes multi-leg transaction timelines and manages partial & full resales.
 */

const dealChain = {
  populateDropdowns() {
    const sellerSelect = document.getElementById('resell-seller');
    const buyerSelect = document.getElementById('resell-buyer');

    if (!sellerSelect || !buyerSelect) return;

    sellerSelect.innerHTML = '<option value="">-- Instructing Party --</option>';
    buyerSelect.innerHTML = '<option value="">-- Select New Buyer --</option>';

    app.parties.forEach(p => {
      sellerSelect.innerHTML += `<option value="${p.id}" data-brok="${p.default_seller_brokerage_per_tonne}">${p.legal_name}</option>`;
      buyerSelect.innerHTML += `<option value="${p.id}" data-brok="${p.default_buyer_brokerage_per_tonne}">${p.legal_name}</option>`;
    });

    this.setupResellLiveMath();
    this.setupResellFormSubmit();
  },

  setupResellLiveMath() {
    const authRateInput = document.getElementById('resell-auth-rate');
    const actualRateInput = document.getElementById('resell-actual-rate');
    const qtyInput = document.getElementById('resell-qty-qtl');
    const diffText = document.getElementById('resell-calc-diff-text');
    const profitText = document.getElementById('resell-calc-profit-text');

    const compute = () => {
      const authRate = parseFloat(authRateInput.value) || 0;
      const actualRate = parseFloat(actualRateInput.value) || 0;
      const qty = parseFloat(qtyInput.value) || 0;

      const diff = actualRate - authRate;
      const profit = diff * qty;

      diffText.textContent = `Rate Diff: ${diff >= 0 ? '+' : ''}₹${diff.toFixed(2)} / Qtl`;
      if (profit >= 0) {
        profitText.className = 'text-profit';
        profitText.textContent = `Profit: +₹${profit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
      } else {
        profitText.className = 'text-loss';
        profitText.textContent = `Loss: -₹${Math.abs(profit).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
      }
    };

    authRateInput.addEventListener('input', compute);
    actualRateInput.addEventListener('input', compute);
    qtyInput.addEventListener('input', compute);
  },

  async openResellModal(chainId, dealId) {
    const modal = document.getElementById('modal-resell');
    if (!modal) return;

    try {
      const chainData = await app.api(`/api/deal-chains/${chainId}`);
      const chain = chainData.chain;
      const lastDeal = chainData.deals[chainData.deals.length - 1];

      document.getElementById('resell-chain-id').value = chainId;
      document.getElementById('resell-parent-deal-id').value = dealId || lastDeal.id;
      document.getElementById('resell-chain-id-display').value = chainId;
      document.getElementById('resell-product-display').value = chain.product_name;

      // Auto select previous buyer as instructing seller
      const sellerSelect = document.getElementById('resell-seller');
      sellerSelect.value = lastDeal.buyer_id;

      // Auto populate dates and quantity
      const today = new Date().toISOString().split('T')[0];
      document.getElementById('resell-inst-date').value = today;
      document.getElementById('resell-delivery-date').value = today;
      document.getElementById('resell-qty-qtl').value = chain.initial_quantity_qtl;
      document.getElementById('resell-qty-hint').textContent = `Full Lot Size: ${chain.initial_quantity_qtl} Qtl (${chain.initial_quantity_qtl/10} MT)`;

      // Default authorized rate to last purchase rate
      document.getElementById('resell-auth-rate').value = lastDeal.rate_per_qtl;
      document.getElementById('resell-actual-rate').value = lastDeal.rate_per_qtl + 25; // Suggest small increment

      // Trigger math computation
      document.getElementById('resell-auth-rate').dispatchEvent(new Event('input'));

      modal.classList.add('open');
    } catch (e) {
      console.error(e);
    }
  },

  setupResellFormSubmit() {
    const form = document.getElementById('form-resell');
    if (!form) return;

    form.onsubmit = async (e) => {
      e.preventDefault();

      const payload = {
        chain_id: document.getElementById('resell-chain-id').value,
        parent_deal_id: document.getElementById('resell-parent-deal-id').value,
        seller_id: document.getElementById('resell-seller').value,
        buyer_id: document.getElementById('resell-buyer').value,
        instruction_date: document.getElementById('resell-inst-date').value,
        deal_date: document.getElementById('resell-inst-date').value,
        authorized_selling_rate_qtl: parseFloat(document.getElementById('resell-auth-rate').value),
        actual_sale_rate_qtl: parseFloat(document.getElementById('resell-actual-rate').value),
        quantity_qtl: parseFloat(document.getElementById('resell-qty-qtl').value),
        delivery_date: document.getElementById('resell-delivery-date').value,
        buyer_brokerage_rate_per_tonne: parseFloat(document.getElementById('resell-buyer-brok').value) || 0,
        seller_brokerage_rate_per_tonne: parseFloat(document.getElementById('resell-seller-brok').value) || 0
      };

      try {
        const result = await app.api('/api/deals/resell', {
          method: 'POST',
          body: JSON.stringify(payload)
        });

        app.showToast(`Resale deal #${result.link_sequence} linked! Profit: ₹${result.price_diff_profit.toLocaleString('en-IN')}`, 'success');
        app.closeModals();
        form.reset();

        app.loadDashboard();
        app.loadDeals();
        app.loadChains();
        app.loadBilling();
      } catch (err) {
        console.error(err);
      }
    };
  },

  renderChains(chains) {
    const container = document.getElementById('chains-container');
    if (!container) return;
    container.innerHTML = '';

    if (!chains || chains.length === 0) {
      container.innerHTML = '<div class="text-muted p-4">No deal chains found. Create a deal to begin a chain.</div>';
      return;
    }

    chains.forEach(async (c) => {
      const node = document.createElement('div');
      node.className = `timeline-node ${c.status === 'READY_FOR_BILLING' ? 'final' : ''}`;

      const totalProfit = Number(c.total_diff_profit || 0);
      const totalBrok = Number(c.total_brokerage || 0);
      const totalEarning = totalProfit + totalBrok;

      node.innerHTML = `
        <div class="timeline-bullet"></div>
        <div class="timeline-header">
          <div class="timeline-title">
            <span class="badge badge-neutral">${c.id}</span>
            <span>${c.product_name} • ${c.initial_quantity_qtl} Qtl (${c.initial_quantity_qtl / 10} MT)</span>
            <span class="badge badge-status-${c.status.toLowerCase()}">${c.status}</span>
          </div>
          <div class="flex-between gap-8">
            <button class="btn btn-primary btn-sm" onclick="dealChain.openResellModal('${c.id}')">
              <i data-lucide="plus"></i>
              <span>Resell / Link Next Deal</span>
            </button>
          </div>
        </div>

        <div style="background: rgba(15, 118, 110, 0.15); border: 1px dashed rgba(20, 184, 166, 0.4); border-radius: 8px; padding: 12px; margin-top: 8px;">
          <div style="font-size: 11px; color: #5EEAD4; font-weight: 700; text-transform: uppercase;">Direct Billing Resolution</div>
          <div style="font-size: 13.5px; font-weight: 600; color: #fff; margin-top: 2px;">
            ${c.original_seller_name} ➔ ${c.final_buyer_name || 'Awaiting Final Resale Buyer'} 
            @ ₹${app.formatNumber(c.final_billing_rate_qtl || 0)} + GST / Qtl
          </div>
        </div>

        <div class="timeline-grid">
          <div class="timeline-stat">
            <span class="timeline-stat-label">Total Resale Profit</span>
            <span class="timeline-stat-val text-profit">₹${app.formatNumber(totalProfit)}</span>
          </div>
          <div class="timeline-stat">
            <span class="timeline-stat-label">Total Brokerage</span>
            <span class="timeline-stat-val">₹${app.formatNumber(totalBrok)}</span>
          </div>
          <div class="timeline-stat">
            <span class="timeline-stat-label">Total Net Earning</span>
            <span class="timeline-stat-val text-profit">₹${app.formatNumber(totalEarning)}</span>
          </div>
          <div class="timeline-stat">
            <span class="timeline-stat-label">Chain Links</span>
            <span class="timeline-stat-val">${c.deal_count} Transactions</span>
          </div>
        </div>
      `;

      container.appendChild(node);
    });

    if (window.lucide) lucide.createIcons();
  }
};
