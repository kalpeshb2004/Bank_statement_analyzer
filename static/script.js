const fileInput = document.getElementById("fileInput");
const dropzone = document.getElementById("dropzone");
const dropzoneText = document.getElementById("dropzoneText");
const analyzeBtn = document.getElementById("analyzeBtn");
const uploadCard = document.getElementById("uploadCard");
const loadingState = document.getElementById("loadingState");
const errorState = document.getElementById("errorState");
const errorMessage = document.getElementById("errorMessage");
const retryBtn = document.getElementById("retryBtn");
const resultsSection = document.getElementById("results");
const newUploadBtn = document.getElementById("newUploadBtn");

let selectedFile = null;

fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) {
    const file = fileInput.files[0];
    
    if (file.type !== "application/pdf") {
      dropzoneText.textContent = "Please select a PDF file only";
      analyzeBtn.disabled = true;
      selectedFile = null;
      return;
    }
    
    if (file.size > 10 * 1024 * 1024) {  // 10MB limit
      dropzoneText.textContent = "File too large (max 10MB)";
      analyzeBtn.disabled = true;
      selectedFile = null;
      return;
    }
    
    selectedFile = file;
    dropzoneText.textContent = selectedFile.name;
    analyzeBtn.disabled = false;
  }
});

// Drag and drop support
["dragover", "dragenter"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
  }),
);


dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  if (e.dataTransfer.files.length > 0) {
    const file = e.dataTransfer.files[0];
    
    if (file.type !== "application/pdf") {
      dropzoneText.textContent = "Please select a PDF file only";
      analyzeBtn.disabled = true;
      return;
    }
    
    fileInput.files = e.dataTransfer.files;
    selectedFile = file;
    dropzoneText.textContent = selectedFile.name;
    analyzeBtn.disabled = false;
  }
});

analyzeBtn.addEventListener("click", async () => {
  if (!selectedFile) return;

  uploadCard.hidden = true;
  errorState.hidden = true;
  loadingState.hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });   // <- naya (loading state dikhane se pehle upar)

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    const response = await fetch("/upload", { method: "POST", body: formData });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(
        errData.detail || "The server could not process this file.",
      );
    }
    const data = await response.json();
    renderResults(data);
    loadingState.hidden = true;
    resultsSection.hidden = false;
  } catch (err) {
    loadingState.hidden = true;
    errorMessage.textContent = err.message;
    errorState.hidden = false;
  }
});

retryBtn.addEventListener("click", resetToUpload);
newUploadBtn.addEventListener("click", resetToUpload);

function resetToUpload() {
  resultsSection.hidden = true;
  errorState.hidden = true;
  uploadCard.hidden = false;
  selectedFile = null;
  fileInput.value = "";
  dropzoneText.textContent = "Choose a PDF, or drag it here";
  analyzeBtn.disabled = true;
}

function formatRupees(amount) {
  return (
    "Rs. " +
    Number(amount).toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

function renderResults(data) {
  const acc = data.account_details;
  document.getElementById("accName").textContent = acc.Name || "Unknown";
  document.getElementById("accDetails").textContent =
    `${acc.BankName || ""} · ${acc.Branch || ""} · A/C ${acc.AccountNo || ""}`;

  const s = data.summary;
  document.getElementById("statSpend").textContent = formatRupees(
    s.total_spend,
  );
  document.getElementById("statTxns").textContent = s.total_transactions;
  document.getElementById("statSent").textContent = formatRupees(
    s.person_transfer_sent,
  );
  document.getElementById("statReceived").textContent = formatRupees(
    s.person_transfer_received,
  );

  const tbody = document.querySelector("#categoryTable tbody");
  tbody.innerHTML = "";
  const sorted = Object.entries(data.category_breakdown).sort(
    (a, b) => b[1] - a[1],
  );
  for (const [category, amount] of sorted) {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${category}</td><td>${formatRupees(amount)}</td>`;
    tbody.appendChild(row);
  }

  // Cache-bust so a re-uploaded statement shows fresh charts, not the browser's cached image
  const ts = Date.now();
  document.getElementById("pieChart").src = `/reports/category_pie.png?t=${ts}`;
  document.getElementById("barChart").src = `/reports/category_bar.png?t=${ts}`;
}

// Auto-scroll add karo
function resetToUpload() {
  resultsSection.hidden = true;
  errorState.hidden = true;
  uploadCard.hidden = false;
  selectedFile = null;
  fileInput.value = "";
  dropzoneText.textContent = "Choose a PDF, or drag it here";
  analyzeBtn.disabled = true;
  window.scrollTo({ top: 0, behavior: "smooth" });   // <- naya
}

async function loadSidebarHistory() {
  const container = document.getElementById("sidebarHistory");
  try {
    const response = await fetch("/history");
    const data = await response.json();
    
    if (!data.history || data.history.length === 0) {
      container.innerHTML = '<p class="sidebar__empty">No statements yet</p>';
      return;
    }
    
    container.innerHTML = "";
    for (const item of data.history) {
      const div = document.createElement("div");
      div.className = "sidebar__item";
      div.innerHTML = `
        <span class="sidebar__item-name">${item.user_name || "Unknown"}</span>
        <span class="sidebar__item-meta">${item.uploaded_at} · ${formatRupees(item.total_spend)}</span>
      `;
      container.appendChild(div);
    }
      
    div.addEventListener("click", () => loadStatement(item.statement_id));
      container.appendChild(div);
      
  } catch (err) {
    container.innerHTML = '<p class="sidebar__empty">Could not load history</p>';
  }
}

document.getElementById("newAnalysisBtn").addEventListener("click", resetToUpload);

loadSidebarHistory();

async function loadStatement(id) {
  uploadCard.hidden = true;
  errorState.hidden = true;
  resultsSection.hidden = true;
  loadingState.hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });

  try {
    const response = await fetch(`/statement/${id}`);
    if (!response.ok) throw new Error("Could not load this statement.");
    const data = await response.json();
    renderResults(data);
    loadingState.hidden = true;
    resultsSection.hidden = false;
  } catch (err) {
    loadingState.hidden = true;
    errorMessage.textContent = err.message;
    errorState.hidden = false;
  }
}