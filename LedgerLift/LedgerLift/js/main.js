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
        // Show summary or update errors table
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
        // Optionally, update the errors table again (could re-fetch errors)
      } catch (err) {
        alert('Bulk fix failed: ' + (err.message || err));
      }
    });
  }

  // Scroll to workflow
  window.scrollToWorkflow = function() {
    const workflow = document.getElementById('workflow');
    if (workflow) workflow.scrollIntoView({ behavior: 'smooth' });
  };

  // Initial step
  showStep(0);
}); 