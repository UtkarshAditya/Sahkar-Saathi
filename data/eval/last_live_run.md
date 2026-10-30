# Last live run

**Date:** 28 October 2026. **One run, on a Windows laptop with Docker Desktop.** Six scripted
turns, one attempt each. This is a status snapshot, not a benchmark. Every number below was
measured in this run; nothing is estimated.

## What was running

| Part               | Value                                                                                                                                                                                     |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| LLM                | `llama3.1:8b` (Q4_K_M, 4.6 GB) on Ollama 0.40.11, on the host. 42% of the loaded model was in GPU memory (RTX 3050 Laptop), the rest on the CPU. `LLM_TIMEOUT=150`, `LLM_JSON_MODE=true`. |
| Embedding model    | `intfloat/multilingual-e5-small`                                                                                                                                                          |
| Vector store       | Qdrant, collection `sahkar_saathi_chunks`, `TOP_K=4`                                                                                                                                      |
| Real services      | retriever, answer service. `DEMO_CACHE=false`. Speech and grievance guide were left on their defaults (stubs).                                                                            |
| `SCORE_THRESHOLD`  | **0.83**, chosen from data (see below)                                                                                                                                                    |
| Free memory (host) | 0.3 GB of 15.7 GB when measured, so the machine was under memory pressure during the run                                                                                                  |

## Corpus: what was ingested

`ingest_corpus` took 329 s: **13 documents, 2,806 chunks, 2,806 vectors**. PostgreSQL and
Qdrant agree, every chunk text is identical to its Qdrant payload, and no text starts with
`passage: `.

| Document                  | Chunks | Pages |
| ------------------------- | -----: | ----: |
| TN-COOP-RULES-1988        |  1,415 |   317 |
| TN-COOP-ACT-1983          |    792 |   145 |
| CEN-PIB-INITIATIVES-2026  |    175 |    36 |
| CEN-MSCS-ACT-2023         |    157 |    22 |
| SCH-RBI-KCC-2026-SFB      |     55 |     5 |
| SCH-RBI-KCC-2026-CB       |     54 |     5 |
| SCH-RBI-KCC-2026-RCB      |     47 |     4 |
| SCH-RBI-KCC-2026-RRB      |     47 |     4 |
| CEN-CEA-INFO-NOTE-2026-07 |     32 |     7 |
| CEN-CRCS-FAQ              |     19 |     4 |
| GRV-CRCS-OMBUDSMAN        |      6 |     2 |
| CEN-CRCS-ABOUT-CEA        |      4 |     1 |
| CEN-MSCS-NOTIF-2023       |      3 |     1 |

**26 documents have `use_in_corpus=Y`. 13 have a file; 13 do not. Low-text (probably scanned)
files: 0.** The 13 without a file have zero chunks:

- **Download failed (11 direct PDF links), none because of a certificate:**
  - `CEN-MSCS-ACT-2002`: indiacode.nic.in answered HTTP 504 (also after a 240 s timeout).
  - `CEN-PARL-ANS-BYLAWS-2023`, `SCH-PARL-ANS-PMFBY-CLAIMS-2020`: eparlib.nic.in does not resolve (DNS).
  - `CEN-PARL-ANS-MSCS-2025`, `CEN-PARL-ANS-PACS-SOFTWARE-2025`, `CEN-PARL-ANS-FUNCTIONAL-PACS-2023`,
    `GRV-PARL-ANS-OMBUDSMAN-2026`: eparlib.sansad.in connection timed out.
  - `CEN-PARL-ANS-MSCS-2024`, `SCH-PARL-ANS-PMFBY-PREMIUM-2023`, `SCH-PARL-ANS-PMFBY-CROPS-2023`,
    `CEN-PARL-ANS-PACS-COMP-2024`: rsdebate.nic.in redirects every PDF URL to the sansad.in
    home page (returns HTML, not a PDF).
- **Web pages that could not be printed (2):**
  - `TN-RCS-ADMIN-DEPT`: rcs.tn.gov.in has an expired certificate (`ERR_CERT_DATE_INVALID`).
  - `GRV-TN-GRIEVANCE-DAY`: the URL returns "File not found".

**Printed from web pages with headless Chrome (7, certificate checks on):** the three CRCS
pages and the four RBI Kisan Credit Card Directions. The RBI PDF files (`rbidocs.rbi.org.in`)
are behind a CAPTCHA, so the RBI web pages were printed instead; they contain the Directions text. The
FAQ page was printed with its collapsed answers expanded (a display change only).
**Three of these files (`CEN-CRCS-FAQ`, `GRV-CRCS-OMBUDSMAN`, `CEN-CRCS-ABOUT-CEA`) are PDFs
named `*_en.html`**, because `sources.csv` gives those names as `local_path`.

Chunk-quality notes: chunks are fixed 500-character windows (median 500, shortest 52), so they
start and end mid-word. 9 chunks contain `(cid:` glyph artifacts and 3 contain the CRCS site
maintenance banner.

## SCORE_THRESHOLD: how 0.83 was chosen

`eval_retrieval` ran on 11 questions (6 in scope, 5 out of scope). The hit rate is **not
measured**, because no question lists `expect_doc_ids` yet.

| Group        | Top-score range | Mean  |
| ------------ | --------------- | ----- |
| In scope (6) | 0.844 to 0.861  | 0.854 |
| Out of scope | 0.772 to 0.813  | 0.801 |

10th percentile of in-scope scores 0.848; 90th percentile of out-of-scope scores 0.813;
**suggested 0.83, with no warnings** (the ranges do not overlap and each group has at least 5).

**Limits of that number:**

- The six "in-scope" questions are all PMFBY questions, and this corpus has no PMFBY
  loss-reporting document. They measure how a question is phrased, not whether it can be answered.
- As a cross-check I scored 9 ad-hoc probes (not committed): questions this corpus can answer
  (general body meetings, the Election Authority, the Ombudsman, KCC, inspecting accounts,
  the two cooperative conversations) scored **0.855 to 0.891**. The unanswerable PMFBY
  question scored **0.862**. So 0.83 separates off-topic questions from on-topic ones, and
  **cannot** separate an on-topic question the corpus lacks.
- Margins are small. The election question scored 0.8125 (0.0175 under the threshold). The
  Hindi PMFBY question scored **0.8298, 0.0002 under**, and was declined by score alone.
  Scores for the same question: English 0.8617, Tamil 0.8410, Hindi 0.8298.

## Acceptance: `python scripts/acceptance.py` (live, `DEMO_CACHE=false`)

`Answers: 6 live, 0 demo (is_demo=true), 0 without an answer.` **6 turns: 4 passed, 2 failed.**

| Conversation (turn)        | Result | Status   | Cit. | Top score | Latency | What happened                                                                                                                                                                                                             |
| -------------------------- | ------ | -------- | ---: | --------: | ------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| pmfby-loss-en              | FAIL   | declined |    0 |    0.8617 |  16.1 s | Expected an answer containing "72". The LLM declined. No ingested document contains "72 hours"; the one that states it (`SCH-PARL-ANS-PMFBY-CLAIMS-2020`) could not be downloaded. **A correct decline for this corpus.** |
| pmfby-loss-hi-ta (hi)      | FAIL   | declined |    0 |    0.8298 |  0.04 s | Declined by score (below 0.83) before the LLM was called. Same missing document.                                                                                                                                          |
| pmfby-loss-hi-ta (ta)      | PASS\* | answered |    1 |    0.8410 |  78.9 s | **\*A wrong answer that the test cannot detect** (see below).                                                                                                                                                             |
| coop-member-tn (en)        | PASS   | answered |    2 |    0.8674 |   7.0 s | "Yes, you can attend the general body meeting." Cites TN Act s.32 and TN Rules r.46 (general meetings). Plausible and on topic; a person should check the wording against those sections.                                 |
| grievance-deposit (en)     | PASS\* | answered |    1 |    0.8549 |  10.6 s | **\*A wrong answer that the test cannot detect** (see below).                                                                                                                                                             |
| out-of-scope-election (en) | PASS   | declined |    0 |    0.8125 |  0.03 s | Declined by score.                                                                                                                                                                                                        |

**Why the two starred PASSes are wrong** (read from the answers and the cited passages):

- **Tamil PMFBY:** the answer repeats the question text as if it were the answer (twice) and
  adds "write to the bank". The cited passage is one fragment, `ans for cultivation of
crops as indicated at paragraph 12 above.`, from an RBI Direction. Nothing in it answers
  the question. It is 100% Tamil script; I cannot judge fluency, so a person should read it.
  A repeat run gave the same answer in 87.7 s.
- **Deposit refusal:** the answer says to complain to the Registrar and that "the Registrar
  may grant permission ... to refund the deposit after a period of six months ...". The cited
  passage (TN Rules p.18) is about the Registrar **refusing to register a proposed society**.
  The answer applies that rule, including its time limit, to a member's deposit in an existing society.
- **Why the tests pass them:** the deposit turn has `status: null` and `citations: null`
  (still marked `TODO_owner: Varsha`), and the Tamil turn has no `must_contain`.

**Hindi and Tamil text:** the Hindi decline text is Hindi script and reads correctly to me, but it
is machine-written and still needs a fluent reader. An earlier Hindi answer (at threshold 0.5)
was grammatical Devanagari but wrong in content: it cited the PIB p.25 passage about a training
MoU between NCCT and the Crop Insurance Division. The Tamil answer is above.

## Latency

- All 6 acceptance requests: **median 8.8 s, slowest 78.9 s** (Tamil). The two score-declines
  took 0.03 s and 0.04 s because the LLM is not called.
- The 4 requests that called the LLM: 7.0, 10.6, 16.1 and 78.9 s, **median 13.3 s**.
- Repeats: Tamil 87.7 s, cooperative 5.3 s, deposit 9.3 s. The first call after the model swap
  (`sahkar-llama31` to `llama3.1:8b`) included loading time: English PMFBY took 24.8 s.
- The Tamil answers are 10x slower than the English ones.

## Open problems (for the owners)

1. **PMFBY documents (Zainab):** none of the three PMFBY `Y` documents has a file, so the
   first demo conversation cannot pass on live data. The `72 hours` rule is not in the corpus.
   The PDF has to be fetched from a browser or the Drive. Also: five `Y` rows have a
   `.html` `local_path`; the 4 sansad.in-redirected rows need new URLs; `rcs.tn.gov.in` has an
   expired certificate; the `cra.tn.gov.in` page URL is dead.
2. **Wrong answers that pass (Varsha):** the deposit and Tamil turns above. Add `must_contain`
   or a stricter `status` and `citations` to those turns, once the right sources exist.
3. **Answer quality in Tamil (Varsha):** an echo of the question, 79 to 88 s. `llama3.1:8b` on
   this machine is not usable for Tamil answers as configured.
4. **Faithfulness (Varsha):** nothing checks that an answer's claims follow from its cited
   passage; the deposit answer shows the model can cite a passage and misapply it.
5. **Threshold (Zainab):** 0.83 is provisional. Add real in-scope questions with
   `expect_doc_ids` and near-topic out-of-scope questions, then re-run `eval_retrieval`.
   Cross-lingual scores are lower, so one threshold penalises Hindi and Tamil.
6. **Chunking and extraction (Zainab):** fixed windows cut mid-word, a 52-character fragment
   was cited in the Tamil answer, 9 `(cid:` chunks, 3 banner chunks. The Qdrant client is
   1.20.0 and the server 1.13.4; the client warns about the difference.
7. **Nothing here measures Hindi or Tamil speech, the grievance guide or the Quality
   dashboard.** Speech and grievance were on their defaults.
