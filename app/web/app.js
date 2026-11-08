let benchmarks = [];
let activeDialogue = null;
let selectedRating = 4;
let selectedTags = new Set();
let rubricScores = {};
let lastSubmissionId = null;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));

async function init() {
  setupEventListeners();
  await loadBenchmarks();
}

async function loadBenchmarks() {
  try {
    const res = await fetch("/benchmarks");
    if (!res.ok) throw new Error();
    benchmarks = await res.json();
    const select = $("benchmark-select");
    benchmarks.forEach((bm, i) => {
      const opt = document.createElement("option");
      opt.value = i;
      opt.textContent = `${bm.benchmark_id} - ${bm.title}`;
      select.appendChild(opt);
    });

    if (benchmarks.length > 0) {
      loadBenchmarkCase(0);
    }
  } catch (err) {
    console.error("Failed to load benchmarks", err);
  }
}

function loadBenchmarkCase(index) {
  const bm = benchmarks[index];
  if (!bm) return;
  activeDialogue = bm;
  $("turn-badge").textContent = `${bm.conversation.length} Turns`;

  // Render chat thread
  $("chat-thread").innerHTML = bm.conversation.map(turn => `
    <div class="chat-bubble ${turn.role === "assistant" ? "assistant" : "user"}">
      <div class="bubble-meta">${turn.role === "assistant" ? "🤖 AI Assistant" : "👤 User"} · Turn ${turn.turn_index}</div>
      <div>${esc(turn.content)}</div>
    </div>
  `).join("");

  // Render rubric dimensions
  rubricScores = {};
  const rubrics = bm.suggested_rubric || ["helpfulness", "accuracy", "tone", "safety", "clarity"];
  $("rubric-list").innerHTML = rubrics.map(dim => {
    rubricScores[dim] = 4;
    return `
      <div class="rubric-row">
        <span>${esc(dim.replace(/_/g, " "))}</span>
        <select data-dim="${esc(dim)}" class="rubric-select">
          <option value="5">5 - Flawless</option>
          <option value="4" selected>4 - Good</option>
          <option value="3">3 - Acceptable</option>
          <option value="2">2 - Poor</option>
          <option value="1">1 - Defective</option>
        </select>
      </div>
    `;
  }).join("");

  document.querySelectorAll(".rubric-select").forEach(sel => {
    sel.addEventListener("change", (e) => {
      rubricScores[e.target.dataset.dim] = parseInt(e.target.value, 10);
    });
  });

  // Reset tags and feedback
  selectedTags.clear();
  document.querySelectorAll(".tag-chip").forEach(c => c.classList.remove("active"));
  $("reviewer-notes").value = "";
  $("evidence-quote").value = "";
  $("quality-tier").textContent = "UNRATED";
  $("quality-tier").className = "pill tier-pill";
  $("submission-result").hidden = true;
  $("btn-download-md").hidden = true;
  $("btn-download-dpo").hidden = true;
}

function setupEventListeners() {
  $("benchmark-select").addEventListener("change", (e) => {
    if (e.target.value !== "") {
      loadBenchmarkCase(parseInt(e.target.value, 10));
    }
  });

  // Rating buttons
  document.querySelectorAll(".star-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".star-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      selectedRating = parseInt(btn.dataset.val, 10);
    });
  });

  // Failure tags
  document.querySelectorAll(".tag-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const tag = chip.dataset.tag;
      if (selectedTags.has(tag)) {
        selectedTags.delete(tag);
        chip.classList.remove("active");
      } else {
        selectedTags.add(tag);
        chip.classList.add("active");
      }
    });
  });

  $("btn-submit-review").addEventListener("click", submitReview);

  $("btn-download-md").addEventListener("click", () => {
    if (lastSubmissionId) {
      window.open(`/api/reviews/${lastSubmissionId}/report`, "_blank");
    }
  });

  $("btn-download-dpo").addEventListener("click", () => {
    if (lastSubmissionId) {
      window.open(`/api/reviews/${lastSubmissionId}/dpo`, "_blank");
    }
  });

  $("btn-export-jsonl").addEventListener("click", () => {
    window.open("/api/export/jsonl", "_blank");
  });
}

async function submitReview() {
  if (!activeDialogue) return;
  const quote = $("evidence-quote").value.trim();
  const notes = $("reviewer-notes").value.trim();

  const scoresPayload = Object.entries(rubricScores).map(([dim, score]) => ({
    dimension: dim,
    score: score,
    rationale: `Scored ${score}/5 by human reviewer`,
    evidence_quote: quote
  }));

  const payload = {
    title: activeDialogue.title,
    conversation: activeDialogue.conversation,
    scores: scoresPayload,
    failure_tags: Array.from(selectedTags),
    overall_rating: selectedRating,
    reviewer_notes: notes || "Review completed with standardized rubric.",
    reviewer_id: "expert-reviewer-01"
  };

  const btn = $("btn-submit-review");
  btn.disabled = true;
  btn.textContent = "Saving…";

  try {
    const res = await fetch("/api/reviews", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.detail || "Submission failed");

    lastSubmissionId = result.dialogue_id;
    const card = result.scorecard;

    // Update quality tier pill
    const tierPill = $("quality-tier");
    tierPill.textContent = card.quality_tier;
    tierPill.className = "pill tier-pill " +
      (card.quality_tier.includes("GOLD") ? "tier-gold" :
       card.quality_tier.includes("ACCEPTABLE") ? "tier-acceptable" :
       card.quality_tier.includes("REVISION") ? "tier-warn" : "tier-reject");

    // Display result card
    const resCard = $("submission-result");
    resCard.hidden = false;
    resCard.innerHTML = `
      <strong>Review Stored: <code>${card.dialogue_id.slice(0, 8)}</code></strong><br />
      Adjusted RLHF Score: <strong>${card.adjusted_quality_score} / 5.0</strong> (Raw: ${card.raw_average_score})<br />
      Training Readiness: <strong>${card.is_ready_for_training ? "✅ Ready for Fine-Tuning" : "❌ Rejected / Defective"}</strong><br />
      Penalties Applied: ${card.failure_count} failure tag(s)
    `;

    $("btn-download-md").hidden = false;
    $("btn-download-dpo").hidden = false;
  } catch (err) {
    alert("Error submitting review: " + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Submit Annotation & Score";
  }
}

window.addEventListener("DOMContentLoaded", init);
