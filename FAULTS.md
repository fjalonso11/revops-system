# FAULTS.md — Fault Disposition Ledger

Every fault or design gap found in this build gets a line here, in one of three states:

- **FIXED** — resolved, with a date and (where relevant) a commit.
- **ACCEPTED** — a known limitation we are choosing to live with, with the reason and date. Not a to-do. Revisit only if the stated condition changes.
- **BLOCKS** — must be resolved before a named milestone. Names the milestone.

The rule from the design post-mortem (July 14-18): a detected fault must never sit *undisposed*. The failure mode this ledger prevents is a real warning firing repeatedly into nothing (e.g. the MRR reconciliation flag that fired for weeks and was ignored). If it is here with a disposition, it is handled. If it is not here, it has not been looked at.

---

## FIXED

| Date | Fault | Resolution |
|---|---|---|
| 2026-07-14 | Fault #1 — dummy-company enrichment. Exa neural search returns the nearest real match for a fake domain, producing valid-looking rows about a different company. | Stale `fintechmx.com` deleted; Kavak enrichment content-verified against a real a16z source. The content-check (read a real enrichment's source against its company name) is the check that discharges this class. |
| 2026-07-27 | **client.py association bug.** `fetch_all_deals` read HubSpot associations with attribute access (`deal.associations.companies.results[0].id`); the SDK returns a **dict**, so the lookup silently failed and every deal synced with `company_id = NULL`. No error, green sync. | Added `_first_association_id()` — reads both dict and object shapes. Found only by refusing to trust a green sync and running the JOIN. Committed + pushed. |
| 2026-07-27 | **Fault #2 — churn-check hardcoded domain.** The n8n node sent a hardcoded `kavak.com` because nothing upstream could name the at-risk company; `at_risk_domains` was structurally always `[]`. | Rewrote `/exa/churn-check` to resolve all at-risk companies from deal data (`resolve_at_risk_companies`), run Exa + Claude per company, return a list. Empty result is valid — no fallback company. Verified end to end: Kontigo + Conekta delivered to Slack. Committed + pushed. |
| 2026-07-27 | **MRR reconciliation "bug."** `/ai/analyze` flagged ending MRR contradicting active MRR for weeks. | Not a formula bug — the math was always correct. Root cause: test data had no beginning base (all deals closed inside the window) and empty company revenue fields. Fixed with data: backdated base deals (~50 days) + populated Annual Revenue on the three base companies. NRR now computes to 92.5% at period_days=30, `total_active_mrr` coheres at 30000. |
| 2026-07-27 | Deals table not congruent — deals existed with no company association, blocking Fault #2. | Rebuilt: six real deals (all four types) each associated to a real company; company revenue populated. Verified by SQL join. |

---

## ACCEPTED

| Date | Limitation | Reason |
|---|---|---|
| 2026-07-27 | **Sync is upsert-only — it never deletes.** A row removed from HubSpot persists in Supabase until manually deleted. | Deletions are rare in real CRM use; this only surfaced because we were cleaning dummy data. Building a safe reconciliation-delete (that won't wipe the table on a bad API response) is disproportionate work for the MVP. **Not a defect to design around.** Removals need a manual Supabase delete. Revisit only if real-client usage shows frequent deletions. |
| 2026-07-27 | **Silent snapshot failures.** `save_all_period_snapshots()` is wrapped in try/except and logged non-fatal. If it fails daily, the pipeline stays green and `prior_metrics` returns None. | Never verified, but invisible for current purposes and non-blocking for the video demo. Real later — worth making the failure loud (post to Slack) before relying on trend context. Not urgent. |
| 2026-07-27 | **Velocity sample-size behavior unmeasured.** Ships `"0 of 7"` alongside a null average, assuming Claude discounts it. Never tested. | Non-blocking; invisible on camera. Worth a two-prompt check later. |
| 2026-07-27 | Conekta churn-alert severity label shows `exa_severity` (external only) while the narrative weighs internal+external, so the header can read "low" while the body treats the risk as real. | Cosmetic. Invisible in a demo. Polish later if the label ever reads as underselling. |

---

## WATCH

| Date | Item | Note |
|---|---|---|
| 2026-07-27 | **`/ai/analyze` returns 500 intermittently.** Failed during n8n testing (Internal Server Error), then ran green on the scheduled pipeline minutes later. App itself healthy (`/health` ok). | Appears transient (Claude API hiccup), not a deploy break — nothing we changed touches `/ai/analyze`. NOT confirmed permanently fine; transient errors recur. If it recurs, read the Railway traceback; it is real and worth diagnosing (possibly tied to metric edge cases). |

---

## BLOCKS

| Item | Blocks | Note |
|---|---|---|
| P1 #5 — connect real client HubSpot data | First paying client | Only remaining hard commercial blocker. The upsert-only sync (ACCEPTED above) should be reviewed at this milestone, since real client data may see more deletions. |

---

*Contract enforcement: `test_contracts.py` guards the three contracted functions (`_first_association_id`, `resolve_at_risk_companies`, `_check_one_company`) against silent contract removal. Graduating more external-facing functions into enforcement is tracked in that file's `EXTERNAL_FACING_TODO`.*

*Last updated: 2026-07-27*
