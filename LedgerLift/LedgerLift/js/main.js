// Basic main.js for LedgerLift

document.addEventListener('DOMContentLoaded', () => {
  // Step navigation
  const steps = ['step-1', 'step-2', 'step-3', 'step-4'];
  let currentStep = 0;

  function showStep(idx) {
    steps.forEach((id, i) => {
      const panel = document.getElementById(id);
      if (panel) {
        panel.classList.toggle('hidden', i !== idx);
        panel.classList.toggle('opacity-0', i !== idx);
        panel.classList.toggle('opacity-100', i === idx);
        panel.classList.toggle('block', i === idx);
      }
    });
  }

  // File upload logic
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const fileName = document.getElementById('file-name');
  const nextBtn = document.getElementById('to-step-2');
  const analyzing = document.getElementById('analyzing');
  const aiSummary = document.getElementById('ai-summary');
  const aiError = document.getElementById('ai-error');

  let uploadedFile = null;

  if (dropZone && fileInput && nextBtn) {
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', e => {
      e.preventDefault();
      dropZone.classList.add('bg-blue-100');
    });
    dropZone.addEventListener('dragleave', e => {
      e.preventDefault();
      dropZone.classList.remove('bg-blue-100');
    });
    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('bg-blue-100');
      if (e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        fileName.textContent = fileInput.files[0].name;
        nextBtn.disabled = false;
        uploadedFile = fileInput.files[0];
      }
    });
    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) {
        fileName.textContent = fileInput.files[0].name;
        nextBtn.disabled = false;
        uploadedFile = fileInput.files[0];
      }
    });
    nextBtn.addEventListener('click', async () => {
      if (!uploadedFile) return;
      showStep(1); // Show analyzing step
      if (aiError) aiError.classList.add('hidden');
      if (aiSummary) aiSummary.classList.add('hidden');
      if (analyzing) analyzing.classList.remove('hidden');
      // Upload file to backend
      const formData = new FormData();
      formData.append('file', uploadedFile);
      try {
        const res = await fetch('/upload', {
          method: 'POST',
          body: formData
        });
        let data;
        try {
          data = await res.json();
        } catch (e) {
          throw new Error('Upload failed: Invalid JSON response');
        }
        if (!res.ok) {
          throw new Error(data.error || ('Upload failed: ' + res.statusText));
        }
        // Show AI summary (simulate for now)
        if (analyzing) analyzing.classList.add('hidden');
        if (aiSummary) aiSummary.classList.remove('hidden');
        // Populate errors table for all sheets
        const errorTable = document.getElementById('error-table');
        if (errorTable && data.errors) {
          const tbody = errorTable.querySelector('tbody');
          tbody.innerHTML = '';
          const sheetNames = Object.keys(data.errors);
          let anyErrors = false;
          sheetNames.forEach(sheet => {
            const errors = data.errors[sheet];
            if (errors.length > 0) {
              anyErrors = true;
              // Add a row for the sheet name
              const sheetRow = document.createElement('tr');
              sheetRow.innerHTML = `<td colspan="2" class="font-bold bg-blue-50">${sheet}</td>`;
              tbody.appendChild(sheetRow);
              errors.forEach(err => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td class="py-2 px-4">${err.row ?? ''}</td><td class="py-2 px-4">${err.issue ?? ''}</td>`;
                tbody.appendChild(tr);
              });
            }
          });
          if (!anyErrors) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="2" class="text-center text-gray-500 py-2">No errors found!</td>';
            tbody.appendChild(tr);
          }
        }
      } catch (err) {
        if (analyzing) analyzing.classList.add('hidden');
        if (aiError) {
          aiError.textContent = 'Error: ' + err.message;
          aiError.classList.remove('hidden');
        }
      }
    });
  }

  // Step 2: Analyze (real upload now)
  const toStep3Btn = document.getElementById('to-step-3');
  if (toStep3Btn) {
    toStep3Btn.addEventListener('click', () => showStep(2));
  }

  // Step 3: Review Errors (simulate)
  const toStep4Btn = document.getElementById('to-step-4');
  if (toStep4Btn) {
    toStep4Btn.addEventListener('click', () => showStep(3));
  }

  // Bulk Fixes logic
  const bulkFixBtn = document.getElementById('bulk-fix-btn');
  if (bulkFixBtn) {
    bulkFixBtn.addEventListener('click', async () => {
      // Collect selected fixes
      const fixes = [];
      if (document.getElementById('fix-balance')?.checked) fixes.push('auto-balance');
      if (document.getElementById('fix-missing')?.checked) fixes.push('fill-missing');
      if (document.getElementById('fix-duplicates')?.checked) fixes.push('remove-duplicates');
      // Get the current sheet (use the first sheet for now)
      const errorTable = document.getElementById('error-table');
      let sheet = null;
      if (errorTable && errorTable.querySelector('tbody')) {
        const firstSheetRow = errorTable.querySelector('tbody tr');
        if (firstSheetRow && firstSheetRow.textContent) {
          sheet = firstSheetRow.textContent.trim();
        }
      }
      // Send to backend
      try {
        const formData = new FormData();
        formData.append('fixes', fixes.join(','));
        if (sheet) formData.append('sheet', sheet);
        const res = await fetch('/bulk-fix', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        // Show summary
        const summaryDiv = document.getElementById('bulk-fix-summary');
        if (summaryDiv) {
          summaryDiv.textContent = '';
          Object.keys(data).forEach(sheetName => {
            const summary = data[sheetName].summary || [];
            summary.forEach(line => {
              const p = document.createElement('p');
              p.textContent = `${sheetName}: ${line}`;
              summaryDiv.appendChild(p);
            });
          });
        }
        // Re-fetch errors and update table
        const errorsRes = await fetch('/upload', { method: 'POST', body: window.lastUploadedFormData });
        const errorsData = await errorsRes.json();
        const errorTable = document.getElementById('error-table');
        if (errorTable && errorsData.errors) {
          const tbody = errorTable.querySelector('tbody');
          tbody.innerHTML = '';
          const sheetNames = Object.keys(errorsData.errors);
          let anyErrors = false;
          sheetNames.forEach(sheet => {
            const errors = errorsData.errors[sheet];
            if (errors.length > 0) {
              anyErrors = true;
              const sheetRow = document.createElement('tr');
              sheetRow.innerHTML = `<td colspan="2" class="font-bold bg-blue-50">${sheet}</td>`;
              tbody.appendChild(sheetRow);
              errors.forEach(err => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td class="py-2 px-4">${err.row ?? ''}</td><td class="py-2 px-4">${err.issue ?? ''}</td>`;
                tbody.appendChild(tr);
              });
            }
          });
          if (!anyErrors) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="2" class="text-center text-gray-500 py-2">No errors found!</td>';
            tbody.appendChild(tr);
            // Optionally, enable the Next button
            const nextBtn = document.getElementById('to-step-4');
            if (nextBtn) nextBtn.disabled = false;
          }
        }
      } catch (err) {
        alert('Bulk fix failed: ' + (err.message || err));
      }
    });
  }

  // Export Now and Download Report
  const exportBtn = document.getElementById('export-btn');
  const downloadReportBtn = document.getElementById('download-report-btn');
  function downloadReport() {
    fetch('/financial-report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sheet: null, errors: [], fixes: [], summary: [] })
    })
      .then(res => res.blob())
      .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'financial_report.html';
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      });
  }
  if (exportBtn) exportBtn.addEventListener('click', downloadReport);
  if (downloadReportBtn) downloadReportBtn.addEventListener('click', downloadReport);

  // Download CSV
  const downloadCsvBtn = document.getElementById('download-csv-btn');
  if (downloadCsvBtn) {
    downloadCsvBtn.addEventListener('click', () => {
      fetch('/download-csv')
        .then(res => res.blob())
        .then(blob => {
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'ledgerlift_export.zip';
          document.body.appendChild(a);
          a.click();
          a.remove();
          window.URL.revokeObjectURL(url);
        });
    });
  }

  // Send Email
  const sendEmailBtn = document.getElementById('send-email-btn');
  if (sendEmailBtn) {
    sendEmailBtn.addEventListener('click', async () => {
      const emailInput = document.getElementById('email-input');
      const email = emailInput?.value;
      if (!email) {
        alert('Please enter an email address.');
        return;
      }
      const res = await fetch('/send-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recipient: email, subject: 'LedgerLift Report', body: 'Your report is ready.' })
      });
      const data = await res.json();
      const status = document.getElementById('email-status');
      if (data.success) {
        if (status) {
          status.textContent = 'Email sent!';
          status.classList.remove('hidden');
        }
      } else {
        alert('Failed to send email: ' + (data.error || 'Unknown error'));
      }
    });
  }

  // Scroll to workflow
  window.scrollToWorkflow = function() {
    const workflow = document.getElementById('workflow');
    if (workflow) workflow.scrollIntoView({ behavior: 'smooth' });
  };

  // --- Rule Toggles and Feedback UI ---
  // 1. Rule Toggles
  const ruleToggleSection = document.createElement('div');
  ruleToggleSection.className = 'mt-6 mb-4 p-4 bg-blue-50 rounded-lg';
  ruleToggleSection.innerHTML = `
    <h3 class="text-lg font-bold mb-2 text-blue-700">Error Detection Rules</h3>
    <div id="rule-toggles" class="flex flex-wrap gap-4"></div>
  `;
  const step3Panel = document.getElementById('step-3');
  if (step3Panel) {
    step3Panel.insertBefore(ruleToggleSection, step3Panel.querySelector('.overflow-x-auto'));
  }
  // Fetch rules (hardcoded for now, could be fetched from backend)
  const availableRules = [
    { id: 'double-entry', label: 'Double-entry (Debits = Credits)', default: true },
    { id: 'missing-values', label: 'Missing Values', default: true },
    { id: 'duplicates', label: 'Duplicate Rows', default: true },
    { id: 'invalid-dates', label: 'Invalid Dates', default: true },
    { id: 'account-codes', label: 'Account Codes (COA)', default: true },
    { id: 'gaap-ifrs', label: 'GAAP/IFRS Rules', default: true },
    { id: 'anomaly', label: 'Anomaly Detection (ML)', default: true },
    { id: 'cross-sheet', label: 'Cross-Sheet Reconciliation', default: true },
    { id: 'formula-audit', label: 'Formula Audit', default: true },
  ];
  const ruleTogglesDiv = document.getElementById('rule-toggles');
  if (ruleTogglesDiv) {
    availableRules.forEach(rule => {
      const wrapper = document.createElement('div');
      wrapper.className = 'flex items-center gap-2';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.id = `rule-toggle-${rule.id}`;
      checkbox.checked = rule.default;
      checkbox.className = 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-blue-500 rounded';
      const label = document.createElement('label');
      label.htmlFor = checkbox.id;
      label.textContent = rule.label;
      label.className = 'text-gray-700 text-base';
      wrapper.appendChild(checkbox);
      wrapper.appendChild(label);
      ruleTogglesDiv.appendChild(wrapper);
    });
  }
  // When toggles change, re-upload with selected rules
  if (ruleTogglesDiv) {
    ruleTogglesDiv.addEventListener('change', async () => {
      // Gather enabled rules
      const enabled = availableRules.filter(r => document.getElementById(`rule-toggle-${r.id}`)?.checked).map(r => r.id);
      // Re-upload file with ?rules= param
      if (!uploadedFile) return;
      showStep(1);
      if (aiError) aiError.classList.add('hidden');
      if (aiSummary) aiSummary.classList.add('hidden');
      if (analyzing) analyzing.classList.remove('hidden');
      const formData = new FormData();
      formData.append('file', uploadedFile);
      try {
        const res = await fetch(`/upload?rules=${encodeURIComponent(enabled.join(','))}`, {
          method: 'POST',
          body: formData
        });
        let data;
        try { data = await res.json(); } catch (e) { throw new Error('Upload failed: Invalid JSON response'); }
        if (!res.ok) throw new Error(data.error || ('Upload failed: ' + res.statusText));
        if (analyzing) analyzing.classList.add('hidden');
        if (aiSummary) aiSummary.classList.remove('hidden');
        // Repopulate errors table
        const errorTable = document.getElementById('error-table');
        if (errorTable && data.errors) {
          const tbody = errorTable.querySelector('tbody');
          tbody.innerHTML = '';
          const sheetNames = Object.keys(data.errors);
          let anyErrors = false;
          sheetNames.forEach(sheet => {
            const errors = data.errors[sheet];
            if (errors.length > 0) {
              anyErrors = true;
              const sheetRow = document.createElement('tr');
              sheetRow.innerHTML = `<td colspan="2" class="font-bold bg-blue-50">${sheet}</td>`;
              tbody.appendChild(sheetRow);
              errors.forEach(err => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td class="py-2 px-4">${err.row ?? ''}</td><td class="py-2 px-4">${err.issue ?? ''}</td>`;
                tbody.appendChild(tr);
              });
            }
          });
          if (!anyErrors) {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="2" class="text-center text-gray-500 py-2">No errors found!</td>';
            tbody.appendChild(tr);
          }
        }
      } catch (err) {
        if (analyzing) analyzing.classList.add('hidden');
        if (aiError) {
          aiError.textContent = 'Error: ' + err.message;
          aiError.classList.remove('hidden');
        }
      }
    });
  }

  // 2. Feedback UI
  const feedbackBtn = document.createElement('button');
  feedbackBtn.textContent = 'Give Feedback';
  feedbackBtn.className = 'ml-4 px-4 py-2 bg-blue-200 text-blue-800 rounded hover:bg-blue-300 font-semibold';
  feedbackBtn.type = 'button';
  let feedbackModal = document.getElementById('feedback-modal');
  if (!feedbackModal) {
    feedbackModal = document.createElement('div');
    feedbackModal.id = 'feedback-modal';
    feedbackModal.className = 'fixed inset-0 bg-black/40 flex items-center justify-center z-50 hidden';
    feedbackModal.innerHTML = `
      <div class="bg-white rounded-xl p-8 max-w-lg w-full shadow-xl relative">
        <button id="close-feedback-modal" class="absolute top-2 right-2 text-gray-400 hover:text-blue-600">&times;</button>
        <h3 class="text-2xl font-bold mb-4 text-blue-700">Feedback</h3>
        <textarea id="feedback-text" class="w-full h-32 border border-gray-300 rounded-lg p-2 mb-4" placeholder="Describe your feedback or suggest improvements..."></textarea>
        <button id="submit-feedback" class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-semibold">Submit Feedback</button>
        <div id="feedback-success" class="text-green-600 mt-4 hidden">Thank you for your feedback!</div>
      </div>
    `;
    document.body.appendChild(feedbackModal);
  }
  // Add feedback button to error review step
  if (step3Panel) {
    step3Panel.querySelector('h2')?.appendChild(feedbackBtn);
  }
  feedbackBtn.addEventListener('click', () => {
    feedbackModal.classList.remove('hidden');
  });
  feedbackModal.querySelector('#close-feedback-modal').addEventListener('click', () => {
    feedbackModal.classList.add('hidden');
    feedbackModal.querySelector('#feedback-success').classList.add('hidden');
    feedbackModal.querySelector('#feedback-text').value = '';
  });
  feedbackModal.querySelector('#submit-feedback').addEventListener('click', async () => {
    const text = feedbackModal.querySelector('#feedback-text').value;
    if (!text.trim()) return;
    // POST feedback to backend
    await fetch('/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ feedback: text })
    });
    feedbackModal.querySelector('#feedback-success').classList.remove('hidden');
    setTimeout(() => {
      feedbackModal.classList.add('hidden');
      feedbackModal.querySelector('#feedback-success').classList.add('hidden');
      feedbackModal.querySelector('#feedback-text').value = '';
    }, 2000);
  });

  // Initial step
  showStep(0);
}); 