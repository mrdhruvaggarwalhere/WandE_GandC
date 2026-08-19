/**
 * Deal Entry Controller
 * Handles Fast Deal Entry, keyboard navigation, and live calculations.
 */

const dealEntry = {
  openModal() {
    const modal = document.getElementById('modal-new-deal');
    if (!modal) return;
    
    // Set default dates
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('deal-date').value = today;
    document.getElementById('deal-delivery-date').value = today;
    
    this.setupLiveCalculators();
    modal.classList.add('open');
  },

  populateDropdowns() {
    const sellerSelect = document.getElementById('deal-seller');
    const buyerSelect = document.getElementById('deal-buyer');
    const productSelect = document.getElementById('deal-product');

    if (!sellerSelect || !buyerSelect || !productSelect) return;

    sellerSelect.innerHTML = '<option value="">-- Select Selling Party --</option>';
    buyerSelect.innerHTML = '<option value="">-- Select Buying Party --</option>';
    productSelect.innerHTML = '<option value="">-- Select Commodity --</option>';

    app.parties.forEach(p => {
      if (p.party_type === 'SELLER' || p.party_type === 'BOTH') {
        sellerSelect.innerHTML += `<option value="${p.id}" data-brok="${p.default_seller_brokerage_per_tonne}">${p.legal_name} (${p.city || ''})</option>`;
      }
      if (p.party_type === 'BUYER' || p.party_type === 'BOTH') {
        buyerSelect.innerHTML += `<option value="${p.id}" data-brok="${p.default_buyer_brokerage_per_tonne}">${p.legal_name} (${p.city || ''})</option>`;
      }
    });

    app.products.forEach(pr => {
      productSelect.innerHTML += `<option value="${pr.id}">${pr.name} (GST ${pr.default_gst_rate}%)</option>`;
    });

    // Auto update default brokerage when party is chosen
    buyerSelect.addEventListener('change', (e) => {
      const opt = buyerSelect.options[buyerSelect.selectedIndex];
      if (opt && opt.dataset.brok) {
        document.getElementById('deal-buyer-brok').value = opt.dataset.brok;
      }
    });

    sellerSelect.addEventListener('change', (e) => {
      const opt = sellerSelect.options[sellerSelect.selectedIndex];
      if (opt && opt.dataset.brok) {
        document.getElementById('deal-seller-brok').value = opt.dataset.brok;
      }
    });

    this.setupFormSubmit();
  },

  setupLiveCalculators() {
    const qtyInput = document.getElementById('deal-qty-qtl');
    const hint = document.getElementById('deal-qty-tonnes-hint');

    qtyInput.addEventListener('input', () => {
      const qtl = parseFloat(qtyInput.value) || 0;
      const mt = (qtl / 10).toFixed(2);
      hint.textContent = `Equal to: ${mt} Metric Tonnes (MT)`;
    });
  },

  setupFormSubmit() {
    const form = document.getElementById('form-new-deal');
    if (!form) return;

    form.onsubmit = async (e) => {
      e.preventDefault();

      const payload = {
        deal_date: document.getElementById('deal-date').value,
        seller_id: document.getElementById('deal-seller').value,
        buyer_id: document.getElementById('deal-buyer').value,
        product_id: document.getElementById('deal-product').value,
        quantity_qtl: parseFloat(document.getElementById('deal-qty-qtl').value),
        rate_per_qtl: parseFloat(document.getElementById('deal-rate-qtl').value),
        delivery_date: document.getElementById('deal-delivery-date').value,
        gst_applicable: parseInt(document.getElementById('deal-gst-applicable').value),
        buyer_brokerage_rate_per_tonne: parseFloat(document.getElementById('deal-buyer-brok').value) || 0,
        seller_brokerage_rate_per_tonne: parseFloat(document.getElementById('deal-seller-brok').value) || 0,
        notes: document.getElementById('deal-notes').value
      };

      try {
        const result = await app.api('/api/deals', {
          method: 'POST',
          body: JSON.stringify(payload)
        });

        app.showToast(`Deal ${result.deal_id} created in Lot ${result.chain_id}!`, 'success');
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
  }
};
