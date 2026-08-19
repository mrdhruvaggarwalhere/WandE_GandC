/**
 * Party Ledger & Brokerage Statement Controller
 */

const ledger = {
  populatePartySelect() {
    const select = document.getElementById('ledger-party-select');
    const paySelect = document.getElementById('pay-party-id');
    if (!select || !paySelect) return;

    select.innerHTML = '<option value="">-- All Parties --</option>';
    paySelect.innerHTML = '<option value="">-- Select Party --</option>';

    app.parties.forEach(p => {
      select.innerHTML += `<option value="${p.id}">${p.legal_name}</option>`;
      paySelect.innerHTML += `<option value="${p.id}">${p.legal_name}</option>`;
    });

    select.addEventListener('change', () => this.loadLedger());
    this.setupPaymentModal();
  },

  async loadLedger() {
    const partyId = document.getElementById('ledger-party-select').value;
    const url = partyId ? `/api/ledger?party_id=${partyId}` : '/api/ledger';

    try {
      const entries = await app.api(url);
      const tbody = document.getElementById('ledger-table-tbody');
      tbody.innerHTML = '';

      if (!entries || entries.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-muted text-center p-4">No ledger entries found.</td></tr>';
        return;
      }

      entries.forEach(e => {
        const tr = document.createElement('tr');
        const isPayment = e.entry_type === 'PAYMENT_RECEIVED' || e.amount < 0;
        const amountClass = isPayment ? 'text-profit' : 'text-mono';
        const typeBadge = isPayment 
          ? `<span class="badge badge-profit">Payment Receipt</span>` 
          : `<span class="badge badge-status-pending">Brokerage Due</span>`;

        tr.innerHTML = `
          <td class="text-mono">${app.formatDate(e.entry_date)}</td>
          <td><strong>${e.party_name}</strong></td>
          <td>${typeBadge}</td>
          <td class="text-mono">${e.reference_no || '-'}</td>
          <td class="${amountClass}">₹${app.formatNumber(Math.abs(e.amount))}</td>
          <td>${e.notes || '-'}</td>
          <td>${e.created_by}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error(err);
    }
  },

  setupPaymentModal() {
    const btn = document.getElementById('btn-open-payment-modal');
    const modal = document.getElementById('modal-payment');
    const form = document.getElementById('form-payment');

    if (!btn || !modal || !form) return;

    btn.addEventListener('click', () => {
      document.getElementById('pay-date').value = new Date().toISOString().split('T')[0];
      modal.classList.add('open');
    });

    form.onsubmit = async (e) => {
      e.preventDefault();

      const payload = {
        party_id: document.getElementById('pay-party-id').value,
        amount: parseFloat(document.getElementById('pay-amount').value),
        entry_date: document.getElementById('pay-date').value,
        reference_no: document.getElementById('pay-ref').value,
        notes: document.getElementById('pay-notes').value,
        entry_type: 'PAYMENT_RECEIVED'
      };

      try {
        await app.api('/api/ledger/payment', {
          method: 'POST',
          body: JSON.stringify(payload)
        });

        app.showToast('Brokerage receipt successfully recorded!', 'success');
        app.closeModals();
        form.reset();
        this.loadLedger();
        app.loadDashboard();
      } catch (err) {
        console.error(err);
      }
    };
  }
};
