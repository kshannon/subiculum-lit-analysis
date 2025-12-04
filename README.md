# subiculum-lit-analysis

Broad literature analysis of the subiculum.

## Table of Contents

- [Data Access](#data-access)
- [Getting Started & Project Setup](#getting-started--project-setup)
- [Project Data Schema](#project-data-schema)
- [Search Strategy](#search-strategy)


## Data Access

### NCBI API Usage (PubMed)

This project uses the NCBI Entrez E-Utilities API￼ to programmatically access PubMed metadata related to neuroscience research papers. I strictly adhere to the NCBI API guidelines, data usage policies￼and the Entrez programming utilities usage guidelines to ensure respectful and compliant access to public biomedical research data.

**Compliance Summary**
  - Rate Limits Respected: No more than 3 requests per second, with large batch queries run during off-peak hours (9 PM–5 AM ET or weekends).
  - Identification Headers Included: All requests include the tool and email parameters for accountability.
  - Metadata Only: These API requests retrieves public abstracts and metadata only, no copyrighted content.
  - Proper Attribution: The NCBI and U.S. National Library of Medicine (NLM) are clearly acknowledged as the data providers.
  - Non-Commercial Academic Use: All data usage is strictly for academic research and educational purposes.

For more information, please see: [NCBI Data Usage Policies](https://www.ncbi.nlm.nih.gov/home/about/policies/), and [API guidelines](https://www.ncbi.nlm.nih.gov/books/NBK25497/#chapter2.Usage_Guidelines_and_Requiremen)


## Getting Started & Project Setup

This project uses [`pixi`](https://prefix.dev/docs/pixi/) for cross-platform reproducibility and env management, e.g. precise lib pinning. To get started, assuming you have installed pixi on your system, run the following commands:

1. Install Pixi, then clone the repo.

```bash
# Clone the repo and enter it
git clone https://github.com/yourname/subiculum-lit-analysis.git
cd subiculum-lit-analysis
```

2. Create and activate the Pixi environment.

```bash
pixi install
pixi shell
```

3. **Configure settings:**

```bash
# Copy the settings template
cp settings-template.yaml settings.yaml

# Edit settings.yaml with your information
# At minimum, update the email field (REQUIRED by NCBI)
# Optionally add your NCBI API key for 10 req/s (vs 3 req/s without)
```

**Key settings to configure:**

| Setting | Description | Required | Default |
|---------|-------------|----------|---------|
| `pubmed.email` | Your email address (NCBI requirement) | **Yes** | `your.email@example.com` |
| `pubmed.api_key` | NCBI API key for higher rate limits | No | Empty (will prompt securely) |
| `batch.size` | Number of papers per batch | No | 100 |
| `logging.level` | Log verbosity (DEBUG/INFO/WARNING/ERROR) | No | INFO |
| `dry_run.enabled` | Test mode without database writes | No | false |

Get an NCBI API key (free) at: https://www.ncbi.nlm.nih.gov/account/settings/

See [`settings-template.yaml`](settings-template.yaml) for full configuration options and detailed descriptions.

4. **Test API connectivity** (recommended):

```bash
pixi run test-api

# you should see
✨ Pixi task (test-api): bash scripts/test_api.sh: (Test PubMed API connectivity (fetches 3 articles))                                                      
=== PubMed API Test ===
Fetching 3 articles...
→ Querying: subiculum%5BTitle/Abstract%5D
✓ Retrieved PMIDs: 41213811,41194528,41174500
✓ Saved 3 articles to: data/test/pubmed_api_test.xml
✓ File size: 94877 bytes

✅ PASSED: PubMed API is working correctly
```

This verifies your connection to NCBI's PubMed API by fetching 3 sample articles and saving them to `data/test/pubmed_api_test.xml`. The test passes if it successfully retrieves and validates the XML data.

5. **Run integration tests** (optional, recommended for development):

```bash
pixi run integration-tests

# Expected output
=== Testing PubMed API Integration ===
Step 1: Running ESearch...
  ✓ Found 3461 total papers
  ✓ WebEnv: MCID_67890abcdef...
  ✓ Query key: 1
Step 2: Fetching 3 papers via EFetch...
  ✓ Retrieved 94877 bytes of XML
Step 3: Validating XML structure...
  ✓ Found 3 PubmedArticle elements
✅ API Integration Test PASSED

=== Testing XML Parsing ===
Step 1: Loading fixture from pubmed_sample.xml...
  ✓ Loaded 94877 bytes of XML
Step 2: Parsing XML...
  ✓ Parsed 3 papers
Step 3: Validating first paper structure...
  ✓ PMID: 41213811
  ✓ Title: Hippocampal Subfield Susceptibility...
  ✓ All 13 expected fields present
Step 4: Validating nested entities...
  ✓ Authors: 9 found
  ✓ MeSH terms: 8 found
  ✓ Citations: 85 found
✅ XML Parsing Test PASSED

=== Testing Database Integration ===
Step 1: Creating in-memory database...
Step 2: Applying schema from schema.sql...
  ✓ Schema applied successfully
Step 3: Loading and parsing XML fixture...
  ✓ Parsed 3 papers from fixture
Step 4: Inserting papers into database...
  ✓ Papers inserted: 3
  ✓ Authors inserted: 18
  ✓ Citations inserted: 254
  ✓ MeSH terms inserted: 24
Step 5: Verifying data in tables...
  ✓ Papers in DB: 3
  ✓ Authors in DB: 18
Step 6: Verifying foreign key constraints...
  ✓ No orphaned paper-author links
  ✓ No orphaned author references
✅ Database Integration Test PASSED
```

> **Note:** The simple API test (step 4) is a quick connectivity check using bash/curl, while integration tests validate the full Python ETL pipeline components. Run the API test first to ensure network connectivity, then run integration tests to validate the implementation.


## Project Data Schema

The pixi `init-db` task creates the `subiculum_literature.db` SQLite database and applies the full schema from schema.sql. See Database Schema Design￼for table descriptions, normalization rationale, and query examples in the project Wiki. The schema includes tables for papers, authors, citations, MeSH terms, keywords, grants, and more. For more information on schema design, please see the github wiki entry.

## Search Strategy

This project queries PubMed using a hybrid of MeSH terms and title/abstract matches to capture a high-quality dataset of neuroscience papers related to the subiculum: `(subiculum[MeSH Terms] OR subiculum[Title/Abstract])`. This approach balances precision and coverage, ensuring both curated relevance and access to the latest research.

**Current query:** `subiculum[Title/Abstract]`

**Results:** 3,576 papers in database (99.7% success rate)

**Future expansions:**
- Broader MeSH-based query: `subiculum[MeSH]` (~10K papers)
- Related structures: entorhinal cortex, CA1, dentate gyrus
- Incremental updates for newly published papers


## Running the Pipeline

### Initial Data Collection

To fetch all papers from PubMed and populate the database:

```bash
# 1. Initialize the database (creates tables)
pixi run init-db

# 2. Run the complete ETL pipeline
pixi run run-pipeline

# Expected output:
# Starting ETL pipeline
# Search query: subiculum[Title/Abstract]
# Total papers found: 3,461
# Already fetched: 0 papers
# Papers remaining to fetch: 3,461
#
# --- Batch 1/35 (papers 1-100) ---
# Parsed 100 papers from XML
# Batch results: 100 inserted, 0 failed, 0 skipped
# ...
#
# === Pipeline Complete ===
# Total papers inserted: 3,430
# Total papers failed: 22
# Total papers in database: 3,430
```

**Database size:** 41 MB (3,576 papers)

**What happens:**
1. ESearch: Queries PubMed for all matching PMIDs
2. Batch fetching: Retrieves papers in batches of 100
3. XML parsing: Extracts metadata (title, authors, citations, etc.)
4. Database loading: Inserts into SQLite with transactions
5. Idempotency: Tracks successfully fetched papers in `fetch_log` table

**On subsequent runs:**
- Pipeline skips already-fetched papers (uses `fetch_log` table)
- Only fetches new/failed papers
- Safe to re-run anytime

### Recovering Failed Papers

Some papers may fail due to duplicate citations in PubMed XML data. To retry:

```bash
pixi run python scripts/fetch_failed_papers.py

# Output:
# Found 22 unique failed PMIDs
# [1/22] Fetching PMID 28673769...
#   Deduplicated citations: 84 → 83
#   ✓ Successfully inserted PMID 28673769
# ...
# === Retry Complete ===
# Successfully inserted: 21/22
# Still failing: 1
```

This script deduplicates citations before inserting, recovering most failures.

### Fetching Additional Papers

To expand the dataset with different search queries:

1. **Edit `settings.yaml`:**
```yaml
search:
  query: "subiculum[MeSH Terms]"  # Broader query (~10K papers)
```

2. **Run pipeline again:**
```bash
pixi run run-pipeline
```

Pipeline automatically skips existing papers and only fetches new ones.

**Alternative search strategies:**

| Query | Papers | Description |
|-------|--------|-------------|
| `subiculum[Title/Abstract]` | ~3,500 | Current - high precision |
| `subiculum[MeSH Terms]` | ~10,000 | Professionally indexed papers |
| `subiculum[Title/Abstract] AND alzheimer*[Title/Abstract]` | ~200 | Disease-specific subset |
| `subiculum[Title/Abstract] AND epilep*[Title/Abstract]` | ~150 | Epilepsy research |
| `hippocampus[MeSH] AND CA1[Title/Abstract]` | ~5,000 | Related hippocampal subfield |
