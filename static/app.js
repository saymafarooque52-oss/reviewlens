let allReviews = [];
let sentimentChartInstance = null;
let topicChartInstance = null;

const csvFileInput = document.getElementById("csvFile");
const analyzeBtn = document.getElementById("analyzeBtn");
const statusMsg = document.getElementById("statusMsg");
const dashboard = document.getElementById("dashboard");
const metaBadge = document.getElementById("metaBadge");

const searchInput = document.getElementById("searchInput");
const filterProduct = document.getElementById("filterProduct");
const filterSentiment = document.getElementById("filterSentiment");
const filterTopic = document.getElementById("filterTopic");
const resetFiltersBtn = document.getElementById("resetFiltersBtn");

analyzeBtn.addEventListener("click", async () => {
  const file = csvFileInput.files[0];
  if (!file) {
    statusMsg.textContent = "Please choose a .csv file first.";
    return;
  }

  const formData = new FormData();
  formData.append("file", file, file.name);

  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Analyzing...";
  statusMsg.textContent = `Cleaning "${file.name}" and analyzing reviews in batches...`;

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || "Failed to analyze CSV");
    }

    allReviews = data.reviews || [];
    renderDashboard(data);
    statusMsg.textContent = "Analysis complete!";
  } catch (err) {
    statusMsg.textContent = `Error: ${err.message}`;
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze Reviews";
  }
});

function renderDashboard(data) {
  const { summary, cleaning_stats, meta } = data;
  dashboard.classList.remove("hidden");

  metaBadge.classList.remove("hidden");
  metaBadge.textContent = `AI Calls: ${meta.ai_calls} | Cache Hits: ${meta.cache_hits} | Time: ${meta.processing_time_sec}s`;

  document.getElementById("statTotal").textContent = summary.total_analysed;
  document.getElementById("statCleaning").textContent =
    `${cleaning_stats.skipped_empty} empty skipped, ${cleaning_stats.duplicates} duplicate`;
  document.getElementById("statPos").textContent = `${summary.positive_pct}%`;
  document.getElementById("statNeu").textContent = `${summary.neutral_pct}%`;
  document.getElementById("statNeg").textContent = `${summary.negative_pct}%`;
  document.getElementById("statReply").textContent = summary.needs_reply_count;
  document.getElementById("statAgreement").textContent =
    `Rating agreement: ${summary.rating_agreement_pct}% (${summary.mismatch_count} mismatches)`;

  const complaintsList = document.getElementById("topComplaints");
  complaintsList.innerHTML = summary.top_complaints.length
    ? summary.top_complaints.map((c) => `<li>${escapeHtml(c)}</li>`).join("")
    : "<li>No major complaints detected.</li>";

  const praisesList = document.getElementById("topPraises");
  praisesList.innerHTML = summary.top_praises.length
    ? summary.top_praises.map((p) => `<li>${escapeHtml(p)}</li>`).join("")
    : "<li>No praises detected yet.</li>";

  const productCards = document.getElementById("productCards");
  productCards.innerHTML = (summary.product_breakdown || [])
    .map(
      (p) => `
      <div class="product-tile" onclick="selectProductFilter('${escapeHtml(p.product)}')">
        <h3>${escapeHtml(p.product)}</h3>
        <div class="product-metrics">
          <span><strong>${p.total}</strong> reviews (${p.positive} pos / ${p.neutral} neu / ${p.negative} neg)</span>
          <span>Top issue: <strong>${escapeHtml(p.top_issue)}</strong></span>
        </div>
      </div>`
    )
    .join("");

  const products = [...new Set(allReviews.map((r) => r.product))];
  filterProduct.innerHTML =
    `<option value="all">All Products</option>` +
    products.map((p) => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join("");

  renderCharts();
  renderTable();
}

function selectProductFilter(productName) {
  filterProduct.value = productName;
  renderTable();
  document.getElementById("reviewsBody").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderCharts() {
  if (typeof Chart === "undefined") return;

  const completed = allReviews.filter((r) => r.analysis_status === "completed");
  const posCount = completed.filter((r) => r.sentiment === "positive").length;
  const neuCount = completed.filter((r) => r.sentiment === "neutral").length;
  const negCount = completed.filter((r) => r.sentiment === "negative").length;

  const sentCtx = document.getElementById("sentimentChart").getContext("2d");
  if (sentimentChartInstance) sentimentChartInstance.destroy();
  sentimentChartInstance = new Chart(sentCtx, {
    type: "doughnut",
    data: {
      labels: ["Positive", "Neutral", "Negative"],
      datasets: [
        {
          data: [posCount, neuCount, negCount],
          backgroundColor: ["#22c55e", "#94a3b8", "#ef4444"],
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" } },
    },
  });

  const topicCounts = {};
  completed.forEach((r) => {
    (r.topics || []).forEach((t) => {
      topicCounts[t] = (topicCounts[t] || 0) + 1;
    });
  });

  const labels = Object.keys(topicCounts).map((t) => t.replace("_", " ").toUpperCase());
  const values = Object.values(topicCounts);

  const topicCtx = document.getElementById("topicChart").getContext("2d");
  if (topicChartInstance) topicChartInstance.destroy();
  topicChartInstance = new Chart(topicCtx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Mentions",
          data: values,
          backgroundColor: "#2563eb",
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
    },
  });
}

[filterProduct, filterSentiment, filterTopic].forEach((el) =>
  el.addEventListener("change", renderTable)
);
searchInput.addEventListener("input", renderTable);

resetFiltersBtn.addEventListener("click", () => {
  searchInput.value = "";
  filterProduct.value = "all";
  filterSentiment.value = "all";
  filterTopic.value = "all";
  renderTable();
});

function getFilteredReviews() {
  const prodVal = filterProduct.value;
  const sentVal = filterSentiment.value;
  const topicVal = filterTopic.value;
  const q = searchInput.value.trim().toLowerCase();

  return allReviews.filter((r) => {
    if (prodVal !== "all" && r.product !== prodVal) return false;
    if (sentVal !== "all" && r.sentiment !== sentVal) return false;
    if (topicVal !== "all" && !(r.topics || []).includes(topicVal)) return false;
    if (q) {
      const hay = `${r.review_id} ${r.product} ${r.review_text} ${r.summary || ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function renderTable() {
  const filtered = getFilteredReviews();
  document.getElementById("filteredCount").textContent = filtered.length;

  const tbody = document.getElementById("reviewsBody");
  tbody.innerHTML = filtered
    .map((r, idx) => {
      if (r.analysis_status === "skipped_empty") {
        return `
          <tr>
            <td><strong>${escapeHtml(r.review_id)}</strong></td>
            <td>${escapeHtml(r.product)}</td>
            <td>${escapeHtml(String(r.rating))}</td>
            <td><span class="badge badge-warn">Skipped (Empty)</span></td>
            <td>—</td>
            <td class="raw-text">Empty review text ignored during cleaning.</td>
            <td>—</td>
          </tr>`;
      }

      if (r.analysis_status === "analysis_failed") {
        return `
          <tr>
            <td><strong>${escapeHtml(r.review_id)}</strong></td>
            <td>${escapeHtml(r.product)}</td>
            <td>${escapeHtml(String(r.rating))}</td>
            <td><span class="badge badge-negative">Analysis Failed</span></td>
            <td>—</td>
            <td><div class="raw-text">${escapeHtml(r.review_text)}</div></td>
            <td>—</td>
          </tr>`;
      }

      const topicsHtml = (r.topics || [])
        .map((t) => `<span class="badge badge-topic">${escapeHtml(t)}</span>`)
        .join("");

      const flagsHtml = [
        r.status === "duplicate" ? `<span class="badge badge-warn">Duplicate of ${escapeHtml(r.duplicate_of)}</span>` : "",
        r.rating_mismatch ? `<span class="badge badge-warn">Rating Mismatch</span>` : "",
      ].join("");

      const actionHtml = r.needs_reply
        ? `<button class="btn-reply" onclick="handleSuggestReply(${idx}, this)">Suggest Reply</button>
           <div id="reply-${idx}" class="reply-box hidden"></div>`
        : `<span class="raw-text">No reply needed</span>`;

      return `
        <tr>
          <td><strong>${escapeHtml(r.review_id)}</strong></td>
          <td>${escapeHtml(r.product)}</td>
          <td>${escapeHtml(String(r.rating))}</td>
          <td>
            <span class="badge badge-${escapeHtml(r.sentiment)}">${escapeHtml(r.sentiment)}</span>
            <div>${flagsHtml}</div>
          </td>
          <td>${topicsHtml}</td>
          <td>
            <div><strong>${escapeHtml(r.summary || "")}</strong></div>
            <div class="raw-text">"${escapeHtml(r.review_text)}"</div>
          </td>
          <td>${actionHtml}</td>
        </tr>`;
    })
    .join("");
}

async function handleSuggestReply(idx, btn) {
  const filtered = getFilteredReviews();
  const review = filtered[idx];
  const replyBox = document.getElementById(`reply-${idx}`);

  btn.disabled = true;
  btn.textContent = "Generating...";

  try {
    const res = await fetch("/api/generate-reply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product: review.product,
        rating: review.rating,
        review_text: review.review_text,
        summary: review.summary,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed to generate reply");

    replyBox.innerHTML = `
      <div>${escapeHtml(data.reply)}</div>
      <button type="button" class="btn-copy" onclick="copyReplyText(this)">Copy Reply</button>
    `;
    replyBox.classList.remove("hidden");
    btn.textContent = "Regenerate Reply";
  } catch (err) {
    replyBox.textContent = `Error: ${err.message}`;
    replyBox.classList.remove("hidden");
    btn.textContent = "Retry Reply";
  } finally {
    btn.disabled = false;
  }
}

function copyReplyText(copyBtn) {
  const text = copyBtn.previousElementSibling.textContent;
  navigator.clipboard.writeText(text);
  copyBtn.textContent = "Copied!";
  setTimeout(() => (copyBtn.textContent = "Copy Reply"), 1500);
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}