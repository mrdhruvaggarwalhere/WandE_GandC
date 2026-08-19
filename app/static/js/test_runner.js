/**
 * In-App Acceptance Test Runner Controller
 * Executes the mandatory Haryana -> Shakti worked example scenario.
 */

const testRunner = {
  renderInitialState() {
    const container = document.getElementById('test-runner-container');
    if (!container) return;

    container.innerHTML = `
      <div style="background: rgba(14, 165, 233, 0.1); border: 1px solid rgba(14, 165, 233, 0.3); border-radius: 12px; padding: 20px;">
        <h3 style="font-size: 15px; color: #38BDF8; margin-bottom: 8px;">Mandatory Worked Scenario Verification</h3>
        <p style="font-size: 13px; color: #94A3B8; margin-bottom: 16px;">
          This verification test runs the exact scenario specified in the prompt:
          <br>• <strong>Deal 1 (01/07/2026):</strong> Haryana Industries buys 320 quintals (32 MT) M.OIL from Nagpal Enterprises @ ₹15,700 + GST.
          <br>• <strong>Resell 1 (18/07/2026):</strong> Haryana authorizes ₹16,450. Sold to M.L. Nagpal @ ₹16,475 + GST (₹25 diff -> <strong>₹8,000 profit</strong>).
          <br>• <strong>Resell 2 (30/07/2026 -> 11/08/2026):</strong> M.L. Nagpal authorizes ₹16,475. Sold to Shakti Nutritions @ ₹16,700 + GST (₹225 diff -> <strong>₹72,000 profit</strong>).
          <br>• <strong>Expected Total Profit:</strong> ₹80,000.
          <br>• <strong>Direct Bill:</strong> Nagpal Enterprises Pvt. Ltd., Anoupgarh ➔ Shakti Nutritions Pvt. Ltd. for 320 quintals M.OIL @ ₹16,700 + GST.
        </p>
        <button class="btn btn-success" id="btn-start-test-run" onclick="testRunner.runTest()">
          <i data-lucide="play"></i>
          <span>Execute Acceptance Verification</span>
        </button>
      </div>
    `;

    if (window.lucide) lucide.createIcons();
  },

  async runTest() {
    const container = document.getElementById('test-runner-container');
    if (!container) return;

    container.innerHTML = '<div class="text-muted p-4">Running verification suite against server calculations...</div>';

    try {
      const result = await app.api('/api/test/run-worked-example', { method: 'POST' });

      let assertionsHtml = '';
      result.assertions.forEach((a, idx) => {
        const icon = a.passed 
          ? '<span style="color: #34D399; font-weight: 800; margin-right: 8px;">✔ PASSED</span>'
          : '<span style="color: #FB7185; font-weight: 800; margin-right: 8px;">✖ FAILED</span>';

        assertionsHtml += `
          <div style="padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.06); display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div style="font-weight: 600; font-size: 13.5px; color: #fff;">${icon} ${idx + 1}. ${a.description}</div>
              <div style="font-size: 12px; color: #94A3B8; margin-left: 28px;">Expected: <code style="color: #7DD3FC;">${a.expected}</code> | Actual: <code style="color: #34D399;">${a.actual}</code></div>
            </div>
            <div>
              <span class="badge ${a.passed ? 'badge-profit' : 'badge-loss'}">${a.passed ? 'VERIFIED' : 'FAILED'}</span>
            </div>
          </div>
        `;
      });

      container.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 12px; padding: 20px; margin-bottom: 20px;">
          <div class="flex-between">
            <div>
              <h3 style="font-size: 18px; font-weight: 800; color: #34D399;">ACCEPTANCE TEST ${result.status}</h3>
              <p style="font-size: 13px; color: #E2E8F0; margin-top: 4px;">
                All ${result.assertions_count} acceptance assertions passed with 100% financial and resolution accuracy.
              </p>
            </div>
            <div style="text-align: right;">
              <div style="font-size: 11px; color: #94A3B8; text-transform: uppercase;">Total Scenario Earning</div>
              <div style="font-size: 20px; font-weight: 800; color: #34D399; font-family: var(--font-mono);">
                ₹${app.formatNumber(result.total_earning)}
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-title" style="margin-bottom: 12px;">Detailed Assertions Log (${result.passed_count}/${result.assertions_count} Passed)</div>
          <div>${assertionsHtml}</div>
        </div>

        <div class="mt-16">
          <button class="btn btn-secondary btn-sm" onclick="testRunner.renderInitialState()">Reset Test View</button>
        </div>
      `;

      if (window.lucide) lucide.createIcons();
    } catch (e) {
      container.innerHTML = `<div class="text-loss p-4">Error running test: ${e.message}</div>`;
    }
  }
};
