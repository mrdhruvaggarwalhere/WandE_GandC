/**
 * Direct Billing Instructions Controller
 * Review, approval, and export staging for direct commercial invoices.
 */

const billing = {
  renderBillingInstructions(instructions) {
    const tbody = document.getElementById('billing-table-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!instructions || instructions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="text-muted text-center p-4">No billing instructions ready yet.</td></tr>';
      return;
    }

    instructions.forEach(b => {
      const tr = document.createElement('tr');
      const isApproved = b.approval_status === 'APPROVED';

      const approveBtn = !isApproved
        ? `<button class="btn btn-success btn-sm" onclick="billing.approveInstruction('${b.id}')">Approve</button>`
        : `<span class="badge badge-profit"><i data-lucide="check"></i> Approved</span>`;

      tr.innerHTML = `
        <td class="text-mono"><strong>${b.id}</strong></td>
        <td class="text-mono">${b.chain_id}</td>
        <td><strong>${b.seller_name}</strong></td>
        <td><strong>${b.buyer_name}</strong></td>
        <td>${b.quantity_qtl} Qtl ${b.product_name}</td>
        <td class="text-mono">₹${app.formatNumber(b.rate_per_qtl)}</td>
        <td class="text-mono text-profit">₹${app.formatNumber(b.total_value)}</td>
        <td><span class="badge badge-status-${b.approval_status.toLowerCase()}">${b.approval_status}</span></td>
        <td>
          <div class="flex-between gap-8">
            ${approveBtn}
            <button class="btn btn-secondary btn-sm" onclick="busyAdapter.previewVoucher('${b.id}')" title="Preview BUSY XML Voucher">
              BUSY XML
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });

    if (window.lucide) lucide.createIcons();
  },

  async approveInstruction(instructionId) {
    if (app.currentRole !== 'ADMIN' && app.currentRole !== 'ACCOUNTS') {
      app.showToast('Only Accounts or Administrator roles can approve official billing instructions.', 'warning');
      return;
    }

    try {
      const result = await app.api(`/api/billing-instructions/${instructionId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ remarks: 'Reviewed and confirmed by Accounts' })
      });

      app.showToast(`Billing Instruction ${instructionId} APPROVED!`, 'success');
      app.loadBilling();
      app.loadDashboard();
      app.loadChains();
    } catch (e) {
      console.error(e);
    }
  }
};
