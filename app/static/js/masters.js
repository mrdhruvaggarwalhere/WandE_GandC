/**
 * Masters & Settings Controller
 */

const masters = {
  loadMasters() {
    this.renderParties();
    this.renderProducts();
  },

  renderParties() {
    const tbody = document.getElementById('masters-parties-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    app.parties.forEach(p => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>
          <strong>${p.legal_name}</strong>
          <div style="font-size: 11px; color: #94A3B8;">${p.city || ''}, ${p.state || ''} • GSTIN: ${p.gstin || 'N/A'}</div>
        </td>
        <td><span class="badge badge-neutral">${p.party_type}</span></td>
        <td class="text-mono">B: ₹${p.default_buyer_brokerage_per_tonne} | S: ₹${p.default_seller_brokerage_per_tonne}</td>
        <td class="text-mono">${p.busy_ledger_id || 'Not Mapped'}</td>
      `;
      tbody.appendChild(tr);
    });
  },

  renderProducts() {
    const tbody = document.getElementById('masters-products-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    app.products.forEach(pr => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${pr.name}</strong></td>
        <td class="text-mono">${pr.short_code}</td>
        <td class="text-mono">${pr.default_gst_rate}%</td>
        <td class="text-mono">${pr.busy_item_id || 'Not Mapped'}</td>
      `;
      tbody.appendChild(tr);
    });
  }
};
