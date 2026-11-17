// CivicFix AI - Citizen Application Client (LLM + RAG)

let lastGuidanceData = null;
let currentComplaintsList = [];

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  // Set default date for letter
  const today = new Date().toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric"
  });
  const dateInput = document.getElementById("letterDate");
  if (dateInput) dateInput.value = today;

  // Load LLM status
  fetchLlmStatus();

  // Load initial citizen complaints
  loadCitizenComplaints();
});

// ==========================================
// LLM CONFIGURATION
// ==========================================

async function fetchLlmStatus() {
  try {
    const res = await fetch("/api/llm/status");
    if (!res.ok) return;
    const data = await res.json();
    const active = data.active_provider || "RAG guidance fallback";
    
    const navText = document.getElementById("navLlmText");
    const sidebarIndicator = document.getElementById("sidebarLlmIndicator");
    if (navText) navText.textContent = `LLM: ${active}`;
    if (sidebarIndicator) sidebarIndicator.textContent = `⚡ Active LLM: ${active}`;

    const select = document.getElementById("llmProviderSelect");
    const keyInput = document.getElementById("llmApiKeyInput");
    if (select && data.config) {
      select.value = data.config.provider || "auto";
      toggleApiKeyInput();
      if (keyInput) {
        if (data.config.provider === "gemini" && data.config.gemini_api_key) {
          keyInput.value = data.config.gemini_api_key;
        } else if (data.config.provider === "groq" && data.config.groq_api_key) {
          keyInput.value = data.config.groq_api_key;
        } else if (data.config.provider === "openai" && data.config.openai_api_key) {
          keyInput.value = data.config.openai_api_key;
        }
      }
    }
  } catch (err) {
    console.error("Could not fetch LLM status:", err);
  }
}

function toggleApiKeyInput() {
  const select = document.getElementById("llmProviderSelect");
  const container = document.getElementById("apiKeyContainer");
  const keyInput = document.getElementById("llmApiKeyInput");
  if (!select || !container) return;

  if (select.value === "auto") {
    container.style.display = "none";
  } else {
    container.style.display = "block";
    if (select.value === "gemini") {
      keyInput.placeholder = "Enter your Google Gemini API key (AI Studio)...";
    } else if (select.value === "groq") {
      keyInput.placeholder = "Enter your Groq API key (gsk_...)...";
    } else if (select.value === "openai") {
      keyInput.placeholder = "Enter your OpenAI API key (sk-...)...";
    }
  }
}

async function saveLlmSettings() {
  const select = document.getElementById("llmProviderSelect");
  const keyInput = document.getElementById("llmApiKeyInput");
  const saveBtn = document.querySelector("#llmSettingsModal .btn-primary");
  const provider = select.value;
  const apiKey = keyInput.value.trim();

  if (provider !== "auto" && !apiKey) {
    alert("Please enter a valid API key for " + provider.toUpperCase() + ", or choose the RAG guidance fallback.");
    return;
  }

  const originalBtnText = saveBtn ? saveBtn.innerHTML : "Save & Activate";
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status"></span> Saving...`;
  }

  try {
    const res = await fetch("/api/llm/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider: provider, api_key: apiKey })
    });

    if (!res.ok) {
      let detailMsg = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        if (errJson && errJson.detail) {
          detailMsg = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
        }
      } catch (parseErr) {
        // ignore json parse error
      }
      throw new Error(detailMsg);
    }

    const data = await res.json();
    alert(`Success: ${data.message || 'LLM Settings updated successfully.'}`);
    await fetchLlmStatus();

    const modalEl = document.getElementById("llmSettingsModal");
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
  } catch (err) {
    alert(`Failed to save LLM settings: ${err.message}\n\nPlease verify that the server is running on http://127.0.0.1:8000.`);
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerHTML = originalBtnText;
    }
  }
}

// ==========================================
// SECTION SWITCHING
// ==========================================

function showCitizenSection(sectionName) {
  const sections = ["guidance", "report", "my-complaints", "letter"];
  sections.forEach(s => {
    let id = "sectionGuidance";
    if (s === "report") id = "sectionReport";
    else if (s === "my-complaints") id = "sectionMyComplaints";
    else if (s === "letter") id = "sectionLetter";

    const secEl = document.getElementById(id);
    if (secEl) secEl.classList.add("d-none");
  });

  let targetId = "sectionGuidance";
  if (sectionName === "report") targetId = "sectionReport";
  else if (sectionName === "my-complaints") targetId = "sectionMyComplaints";
  else if (sectionName === "letter") targetId = "sectionLetter";

  const targetEl = document.getElementById(targetId);
  if (targetEl) targetEl.classList.remove("d-none");

  const links = document.querySelectorAll("#citizenSidebarMenu .nav-pill-link");
  links.forEach(l => {
    l.classList.remove("active");
    if (l.getAttribute("href") === `#${sectionName}`) {
      l.classList.add("active");
    }
  });

  if (sectionName === "my-complaints") {
    loadCitizenComplaints();
  } else if (sectionName === "letter") {
    populateLetterSelectOptions();
  }
}

// ==========================================
// 1. AI GUIDANCE (LLM + RAG)
// ==========================================

function fillGuidanceExample(text) {
  document.getElementById("guidanceDescription").value = text;
}

async function handleGetGuidance(e) {
  e.preventDefault();
  const desc = document.getElementById("guidanceDescription").value.trim();
  const cat = document.getElementById("guidanceCategory").value;

  if (!desc) {
    alert("Please enter a problem description.");
    return;
  }

  // Show loading
  document.getElementById("guidancePlaceholder").classList.add("d-none");
  document.getElementById("guidanceResults").classList.add("d-none");
  document.getElementById("guidanceLoading").classList.remove("d-none");

  try {
    const res = await fetch("/api/guidance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: desc, category: cat || null })
    });

    if (!res.ok) {
      throw new Error(`Failed to retrieve guidance: ${res.statusText}`);
    }

    const data = await res.json();
    lastGuidanceData = data;
    renderGuidanceResults(data);
  } catch (err) {
    console.error(err);
    alert(`Error retrieving guidance: ${err.message}`);
    document.getElementById("guidancePlaceholder").classList.remove("d-none");
  } finally {
    document.getElementById("guidanceLoading").classList.add("d-none");
  }
}

function renderGuidanceResults(data) {
  const resultsContainer = document.getElementById("guidanceResults");
  const unclearAlert = document.getElementById("guidanceUnclearAlert");
  const contentCard = document.getElementById("guidanceContentCard");

  resultsContainer.classList.remove("d-none");

  // Check if unclear
  if (!data.is_clear) {
    unclearAlert.classList.remove("d-none");
    document.getElementById("guidanceUnclearMsg").textContent = data.clarity_message;
    contentCard.classList.add("d-none");
    return;
  }

  unclearAlert.classList.add("d-none");
  contentCard.classList.remove("d-none");

  // Category & LLM Badges
  document.getElementById("guidanceCategoryBadge").textContent = data.identified_category || "Unclassified";
  const llmBadge = document.getElementById("guidanceLlmBadge");
  if (llmBadge) {
    llmBadge.textContent = `⚡ ${data.llm_provider || "LLM Engine"}`;
  }

  // LLM Diagnostic Assessment Summary
  const aiAnalysisEl = document.getElementById("guidanceAiAnalysis");
  if (aiAnalysisEl) {
    aiAnalysisEl.textContent = data.ai_analysis || "The LLM analyzed this grievance against official guidelines and confirmed jurisdiction under the designated authority.";
  }

  // Verified Badge & Alert
  const verifiedBadge = document.getElementById("guidanceVerifiedBadge");
  const verifiedAlert = document.getElementById("guidanceVerifiedAlert");
  const verifiedText = document.getElementById("guidanceVerifiedText");

  if (data.has_verified_guidance) {
    verifiedBadge.className = "badge bg-success";
    verifiedBadge.innerHTML = '<i class="bi bi-shield-check me-1"></i>Verified Guidance (RAG)';
    verifiedAlert.className = "alert alert-success py-2 px-3 small mb-3";
    verifiedText.textContent = data.verified_guidance_message || "Guidelines verified from official government document.";
  } else {
    verifiedBadge.className = "badge bg-warning text-dark";
    verifiedBadge.innerHTML = '<i class="bi bi-exclamation-circle me-1"></i>Standard Guidance';
    verifiedAlert.className = "alert alert-warning py-2 px-3 small mb-3";
    verifiedText.textContent = data.verified_guidance_message || "No verified government guidelines found for this issue. General civic grievance submission steps apply.";
  }

  // Department Info
  document.getElementById("guidanceDeptName").textContent = data.recommended_department || "Municipal Authority";
  document.getElementById("guidanceDeptJurisdiction").textContent = data.jurisdiction_notes || "";
  document.getElementById("guidanceJurisdictionDisclaimer").textContent = data.jurisdiction_disclaimer;

  // Procedure Steps (LLM Synthesized)
  const procedureList = document.getElementById("guidanceProcedureList");
  procedureList.innerHTML = "";
  if (data.procedure_steps && data.procedure_steps.length > 0) {
    data.procedure_steps.forEach(step => {
      const li = document.createElement("li");
      li.className = "list-group-item d-flex align-items-start gap-2 py-2";
      li.innerHTML = `<i class="bi bi-check2-circle text-primary mt-1"></i><span>${step}</span>`;
      procedureList.appendChild(li);
    });
  }

  // Required Evidence Checklist
  const evidenceList = document.getElementById("guidanceEvidenceList");
  evidenceList.innerHTML = "";
  if (data.required_evidence && data.required_evidence.length > 0) {
    data.required_evidence.forEach(item => {
      const li = document.createElement("li");
      li.className = "list-group-item d-flex align-items-start gap-2 py-2";
      li.innerHTML = `<i class="bi bi-dot fs-5 text-secondary"></i><span>${item}</span>`;
      evidenceList.appendChild(li);
    });
  }

  // RAG Sources & Page Numbers
  const sourcesContainer = document.getElementById("guidanceSourcesContainer");
  sourcesContainer.innerHTML = "";

  if (data.sources && data.sources.length > 0) {
    data.sources.forEach(src => {
      const box = document.createElement("div");
      box.className = "rag-source-box";
      box.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-1">
          <span class="fw-bold small text-primary"><i class="bi bi-file-earmark-pdf me-1"></i>${src.document_title}</span>
          <span class="rag-score-pill">Relevance: ${(src.score * 100).toFixed(0)}%</span>
        </div>
        <div class="text-muted small mb-1">Source File: <b>${src.filename}</b> | <b>Page ${src.page_number}</b></div>
        <div class="small fst-italic text-dark border-start ps-2 my-1" style="background: #ffffff; padding: 4px 8px; border-radius: 4px;">
          "${src.excerpt}"
        </div>
      `;
      sourcesContainer.appendChild(box);
    });
  } else {
    sourcesContainer.innerHTML = `
      <div class="alert alert-light border small text-muted mb-0">
        <i class="bi bi-info-circle me-1"></i> No matching official PDF chunks met the similarity threshold.
      </div>
    `;
  }
}

function proceedToReportWithGuidance() {
  if (!lastGuidanceData) return;
  showCitizenSection("report");

  if (lastGuidanceData.identified_category) {
    document.getElementById("reportCategory").value = lastGuidanceData.identified_category;
  }
  const originalDesc = document.getElementById("guidanceDescription").value;
  if (originalDesc) {
    document.getElementById("reportDescription").value = originalDesc;
  }
}

// ==========================================
// 2. REPORT PROBLEM
// ==========================================

function previewComplaintImage(e) {
  const file = e.target.files[0];
  const preview = document.getElementById("imagePreview");
  const container = document.getElementById("imagePreviewContainer");
  if (file) {
    const reader = new FileReader();
    reader.onload = (event) => {
      preview.src = event.target.result;
      container.classList.remove("d-none");
    };
    reader.readAsDataURL(file);
  } else {
    container.classList.add("d-none");
  }
}

async function handleComplaintSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById("btnSubmitComplaint");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Submitting...`;

  const category = document.getElementById("reportCategory").value;
  const description = document.getElementById("reportDescription").value;
  const location = document.getElementById("reportLocation").value;
  const citizenName = document.getElementById("reportCitizenName").value;
  const citizenEmail = document.getElementById("reportCitizenEmail").value;
  const citizenPhone = document.getElementById("reportCitizenPhone").value;
  const imageInput = document.getElementById("reportImage");

  const formData = new FormData();
  formData.append("category", category);
  formData.append("description", description);
  formData.append("location", location);
  formData.append("citizen_name", citizenName);
  formData.append("citizen_email", citizenEmail);
  if (citizenPhone) formData.append("citizen_phone", citizenPhone);
  if (imageInput.files[0]) formData.append("image", imageInput.files[0]);

  try {
    const res = await fetch("/api/complaints", {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Server Error (${res.status})`);
    }

    const data = await res.json();

    // Show success card
    const successCard = document.getElementById("submissionSuccessCard");
    successCard.classList.remove("d-none");
    document.getElementById("successComplaintNo").textContent = data.complaint_no;
    document.getElementById("successCategory").textContent = data.category;
    document.getElementById("successDept").textContent = data.department_name;
    successCard.setAttribute("data-complaint-id", data.complaint_id);

    // Reset form
    document.getElementById("reportComplaintForm").reset();
    document.getElementById("imagePreviewContainer").classList.add("d-none");

    // Refresh complaints list
    loadCitizenComplaints();
  } catch (err) {
    console.error(err);
    alert(`Error registering complaint: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-check2-circle"></i><span>Submit Grievance</span>`;
  }
}

function openLetterForComplaintFromSuccess() {
  const successCard = document.getElementById("submissionSuccessCard");
  const cid = successCard.getAttribute("data-complaint-id");
  showCitizenSection("letter");
  if (cid) {
    document.getElementById("letterComplaintSelect").value = cid;
    loadLetterForSelectedComplaint();
  }
}

// ==========================================
// 3. MY COMPLAINTS
// ==========================================

async function loadCitizenComplaints() {
  const tbody = document.getElementById("citizenComplaintsTableBody");
  tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted"><div class="spinner-border spinner-border-sm text-primary me-2"></div>Loading complaints...</td></tr>`;

  try {
    const res = await fetch("/api/complaints");
    if (!res.ok) throw new Error("Failed to load complaints");
    const data = await res.json();
    currentComplaintsList = data;

    if (data.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">No complaints submitted yet. Click <b>Report Problem</b> to submit one.</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    data.forEach(c => {
      const tr = document.createElement("tr");
      const statusClass = getStatusBadgeClass(c.status);

      tr.innerHTML = `
        <td class="ps-3"><b class="text-primary">${c.complaint_no}</b></td>
        <td><span class="badge bg-light text-dark border">${c.category}</span></td>
        <td class="small text-truncate" style="max-width: 180px;" title="${c.location}">${c.location}</td>
        <td class="small">${c.department_name || "Municipal Authority"}</td>
        <td class="small text-muted">${c.created_at}</td>
        <td><span class="badge ${statusClass}">${c.status}</span></td>
        <td class="text-end pe-3">
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-primary" title="View Details" onclick="viewComplaintDetails(${c.id})">
              <i class="bi bi-eye"></i>
            </button>
            <button class="btn btn-outline-success" title="Draft Complaint Letter (LLM)" onclick="openLetterForComplaint(${c.id})">
              <i class="bi bi-file-earmark-pdf"></i>
            </button>
            <button class="btn btn-outline-danger" title="Delete Complaint" onclick="deleteComplaint(${c.id})">
              <i class="bi bi-trash"></i>
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });

    populateLetterSelectOptions();
  } catch (err) {
    console.error(err);
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Failed to load complaints: ${err.message}</td></tr>`;
  }
}

async function viewComplaintDetails(id) {
  try {
    const res = await fetch(`/api/complaints/${id}`);
    if (!res.ok) throw new Error("Failed to fetch complaint details");
    const c = await res.json();

    document.getElementById("modalComplaintTitle").textContent = `Complaint Details — ${c.complaint_no}`;
    const modalBody = document.getElementById("modalComplaintBody");

    const statusBadge = getStatusBadgeClass(c.status);
    let imageHtml = "";
    if (c.image_path) {
      imageHtml = `
        <div class="mt-3">
          <label class="fw-bold small text-muted text-uppercase mb-1 d-block">Photographic Proof</label>
          <img src="${c.image_path}" alt="Complaint Proof" class="img-fluid rounded border" style="max-height: 250px;">
        </div>
      `;
    }

    modalBody.innerHTML = `
      <div class="row g-3">
        <div class="col-md-6">
          <div class="small text-muted">Category</div>
          <div class="fw-bold text-dark">${c.category}</div>
        </div>
        <div class="col-md-6">
          <div class="small text-muted">Status</div>
          <div><span class="badge ${statusBadge}">${c.status}</span></div>
        </div>
        <div class="col-md-6">
          <div class="small text-muted">Assigned Department</div>
          <div class="fw-semibold text-primary">${c.department_name || "Municipal Authority"}</div>
        </div>
        <div class="col-md-6">
          <div class="small text-muted">Reported Date</div>
          <div>${c.created_at}</div>
        </div>
        <div class="col-12">
          <div class="small text-muted">Location</div>
          <div class="bg-light p-2 rounded small">${c.location}</div>
        </div>
        <div class="col-12">
          <div class="small text-muted">Description</div>
          <div class="p-2 border rounded small">${c.description}</div>
        </div>
        <div class="col-12">
          <div class="small text-muted">Citizen Contact</div>
          <div class="small">${c.citizen_name} | ${c.citizen_email} | ${c.citizen_phone || "No phone provided"}</div>
        </div>
      </div>
      ${imageHtml}
    `;

    const modal = new bootstrap.Modal(document.getElementById("complaintDetailsModal"));
    modal.show();
  } catch (err) {
    alert(`Could not load details: ${err.message}`);
  }
}

async function deleteComplaint(id) {
  if (!confirm("Are you sure you want to delete this complaint record?")) return;
  try {
    const res = await fetch(`/api/complaints/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Delete failed");
    loadCitizenComplaints();
  } catch (err) {
    alert(`Error deleting complaint: ${err.message}`);
  }
}

function openLetterForComplaint(id) {
  showCitizenSection("letter");
  document.getElementById("letterComplaintSelect").value = id;
  loadLetterForSelectedComplaint();
}

// ==========================================
// 4. COMPLAINT LETTER (LLM DRAFTED)
// ==========================================

function populateLetterSelectOptions() {
  const select = document.getElementById("letterComplaintSelect");
  if (!select) return;
  const currentVal = select.value;
  select.innerHTML = `<option value="">Choose a complaint...</option>`;

  currentComplaintsList.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.complaint_no} — ${c.category} (${c.location.slice(0, 30)})`;
    select.appendChild(opt);
  });

  if (currentVal && Array.from(select.options).some(o => o.value === currentVal)) {
    select.value = currentVal;
  } else if (currentComplaintsList.length > 0) {
    select.value = currentComplaintsList[0].id;
    loadLetterForSelectedComplaint();
  }
}

async function loadLetterForSelectedComplaint() {
  const select = document.getElementById("letterComplaintSelect");
  const id = select.value;
  if (!id) return;

  try {
    const res = await fetch(`/api/complaints/${id}/letter-preview`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to load letter preview");
    }
    const data = await res.json();

    document.getElementById("letterDate").value = data.date;
    document.getElementById("letterRecipient").value = data.recipient;
    document.getElementById("letterSubject").value = data.subject;
    document.getElementById("letterBody").value = data.body;
    document.getElementById("letterCitizenName").value = data.citizen_name;
    document.getElementById("letterCitizenPhone").value = data.citizen_phone;
    document.getElementById("letterCitizenEmail").value = data.citizen_email;
  } catch (err) {
    console.error(err);
    alert(err.message);
  }
}

function updateLetterSignature() {
  const name = document.getElementById("letterCitizenName").value;
  const phone = document.getElementById("letterCitizenPhone").value;
  const email = document.getElementById("letterCitizenEmail").value;
  let body = document.getElementById("letterBody").value;

  const sigMatch = body.lastIndexOf("Yours sincerely,");
  if (sigMatch !== -1) {
    const mainBody = body.substring(0, sigMatch).trim();
    const newSig = `Yours sincerely,\n${name}\nContact: ${phone || "Not provided"} | Email: ${email || "Not provided"}`;
    document.getElementById("letterBody").value = `${mainBody}\n\n${newSig}`;
  }
}

function resetLetterDefault() {
  loadLetterForSelectedComplaint();
}

async function handleDownloadLetterPDF() {
  const select = document.getElementById("letterComplaintSelect");
  const complaintId = select.value;
  const subject = document.getElementById("letterSubject").value.trim();
  const recipient = document.getElementById("letterRecipient").value.trim();
  const body = document.getElementById("letterBody").value.trim();
  const date = document.getElementById("letterDate").value.trim();

  if (!body) {
    alert("Please generate or enter letter content first.");
    return;
  }

  const selectedComplaint = currentComplaintsList.find(c => String(c.id) === String(complaintId));
  const complaintNo = selectedComplaint ? selectedComplaint.complaint_no : "CF-NOTICE";

  const btn = document.getElementById("btnDownloadPDF");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Building PDF...`;

  const formData = new FormData();
  formData.append("complaint_no", complaintNo);
  formData.append("subject", subject);
  formData.append("recipient", recipient);
  formData.append("body", body);
  formData.append("date", date);

  try {
    const res = await fetch("/api/complaints/download-letter-pdf", {
      method: "POST",
      body: formData
    });

    if (!res.ok) throw new Error("Failed to build PDF");

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Grievance_Letter_${complaintNo}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    console.error(err);
    alert(`Could not download PDF: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-file-earmark-arrow-down-fill"></i><span>Download as PDF</span>`;
  }
}

function getStatusBadgeClass(status) {
  switch (status) {
    case "Pending": return "status-pending";
    case "In Progress": return "status-in-progress";
    case "Resolved": return "status-resolved";
    case "Rejected": return "status-rejected";
    default: return "bg-secondary text-white";
  }
}
