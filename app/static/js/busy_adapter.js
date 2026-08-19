/**
 * BUSY Accounting Integration Adapter Controller
 */

const busyAdapter = {
  async loadBusyVouchers() {
    const tbody = document.getElementById('busy-table-tbody');
    if (!tbody) return;

    try {
      const instructions = await app.api('/api/billing-instructions');
      tbody.innerHTML = '';

      if (!instructions || instructions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-muted text-center p-4">No billing vouchers ready. Approve a billing instruction to stage for BUSY.</td></tr>';
        return;
      }

      instructions.forEach(b => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="text-mono"><strong>INV-${b.chain_id}</strong></td>
          <td class="text-mono">${b.chain_id}</td>
          <td>${b.seller_name}</td>
          <td>${b.buyer_name}</td>
          <td>${b.quantity_qtl} Qtl ${b.product_name}</td>
          <td class="text-mono text-profit">₹${app.formatNumber(b.total_value)}</td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="busyAdapter.previewVoucher('${b.id}')">
              View XML
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {
      console.error(e);
    }
  },

  async previewVoucher(instructionId) {
    const modal = document.getElementById('modal-busy-voucher');
    const codeBlock = document.getElementById('busy-voucher-code');
    const title = document.getElementById('busy-voucher-modal-title');
    const copyBtn = document.getElementById('btn-copy-busy-payload');

    if (!modal || !codeBlock) return;

    try {
      const payload = await app.api(`/api/busy/preview/${instructionId}`);
      title.textContent = `BUSY Voucher: ${payload.voucher_no}`;
      codeBlock.textContent = payload.xml_payload;

      copyBtn.onclick = () => {
        navigator.clipboard.writeText(payload.xml_payload);
        app.showToast('BUSY XML payload copied to clipboard!', 'success');
      };

      modal.classList.add('open');
    } catch (e) {
      console.error(e);
    }
  }
};
