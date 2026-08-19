/**
 * Reports & Analytics Controller
 */

const reports = {
  async loadReport() {
    const reportType = document.getElementById('report-type-select').value;
    const thead = document.getElementById('report-table-thead');
    const tbody = document.getElementById('report-table-tbody');

    if (!thead || !tbody) return;

    thead.innerHTML = '';
    tbody.innerHTML = '<tr><td colspan="10" class="text-muted text-center p-4">Loading report...</td></tr>';

    try {
      const data = await app.api(`/api/reports/${reportType}`);
      
      // Render Table Headers
      const trHead = document.createElement('tr');
      data.columns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col;
        trHead.appendChild(th);
      });
      thead.appendChild(trHead);

      // Render Rows
      tbody.innerHTML = '';
      if (!data.rows || data.rows.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${data.columns.length}" class="text-muted text-center p-4">No records found for this report.</td></tr>`;
        return;
      }

      data.rows.forEach(r => {
        const tr = document.createElement('tr');
        if (reportType === 'deal-register') {
          tr.innerHTML = `
            <td class="text-mono">${app.formatDate(r.deal_date)}</td>
            <td class="text-mono">${r.deal_id}</td>
            <td class="text-mono">${r.chain_id}</td>
            <td><strong>${r.buyer_name}</strong></td>
            <td>${r.seller_name}</td>
            <td><span class="badge badge-neutral">${r.product_name}</span></td>
            <td class="text-mono">${r.quantity_qtl}</td>
            <td class="text-mono">${r.quantity_tonnes}</td>
            <td class="text-mono">₹${app.formatNumber(r.rate_per_qtl)}</td>
            <td class="text-mono text-profit">₹${app.formatNumber(r.price_diff_profit)}</td>
            <td class="text-mono">₹${app.formatNumber(r.total_brokerage_amount)}</td>
            <td class="text-mono">${app.formatDate(r.delivery_date)}</td>
            <td><span class="badge badge-status-${r.status.toLowerCase()}">${r.status}</span></td>
          `;
        } else if (reportType === 'profit-report') {
          tr.innerHTML = `
            <td class="text-mono">${r.chain_id}</td>
            <td class="text-mono">${r.deal_id}</td>
            <td class="text-mono">${app.formatDate(r.deal_date)}</td>
            <td><strong>${r.instructing_party}</strong></td>
            <td>${r.actual_buyer}</td>
            <td class="text-mono">${r.quantity_qtl} Qtl</td>
            <td class="text-mono">₹${app.formatNumber(r.authorized_selling_rate_qtl)}</td>
            <td class="text-mono">₹${app.formatNumber(r.actual_rate)}</td>
            <td class="text-mono text-profit">+₹${app.formatNumber(r.price_diff_per_qtl)}</td>
            <td class="text-mono text-profit" style="font-weight: 800;">₹${app.formatNumber(r.price_diff_profit)}</td>
          `;
        } else if (reportType === 'brokerage-outstanding') {
          tr.innerHTML = `
            <td class="text-mono">${r.id}</td>
            <td><strong>${r.legal_name}</strong></td>
            <td><span class="badge badge-neutral">${r.party_type}</span></td>
            <td class="text-mono">${r.phone || '-'}</td>
            <td>${r.city || '-'}</td>
            <td class="text-mono text-profit" style="font-weight: 700;">₹${app.formatNumber(r.total_due)}</td>
          `;
        }
        tbody.appendChild(tr);
      });
    } catch (e) {
      console.error(e);
    }
  }
};
