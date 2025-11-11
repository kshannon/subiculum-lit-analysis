# subiculum-lit-analysis
Broad literature analysis of the subiculum.

## Project Setup

This project uses [`pixi`](https://prefix.dev/docs/pixi/) for cross-platform reproducibility and env management, e.g. precise lib pinning. To get started, assuming you have installed pixi on your system, run the following commands:

```bash
# Clone the repo and enter it
git clone https://github.com/yourname/subiculum-lit-analysis.git
cd subiculum-lit-analysis

# Create and activate the environment
pixi install
```

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

## Search Strategy:
This project queries PubMed using a hybrid of MeSH terms and title/abstract matches to capture a high-quality dataset of neuroscience papers related to the subiculum:`(subiculum[MeSH Terms] OR subiculum[Title/Abstract])`. This approach balances precision and coverage, ensuring both curated relevance and access to the latest research.