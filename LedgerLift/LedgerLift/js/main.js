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
      }
    });
    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) {
        fileName.textContent = fileInput.files[0].name;
        nextBtn.disabled = false;
      }
    });
    nextBtn.addEventListener('click', () => {
      showStep(1);
    });
  }

  // Step 2: Analyze (simulate)
  const toStep3Btn = document.getElementById('to-step-3');
  if (toStep3Btn) {
    toStep3Btn.addEventListener('click', () => showStep(2));
  }

  // Step 3: Review Errors (simulate)
  const toStep4Btn = document.getElementById('to-step-4');
  if (toStep4Btn) {
    toStep4Btn.addEventListener('click', () => showStep(3));
  }

  // Scroll to workflow
  window.scrollToWorkflow = function() {
    const workflow = document.getElementById('workflow');
    if (workflow) workflow.scrollIntoView({ behavior: 'smooth' });
  };

  // Initial step
  showStep(0);
}); 