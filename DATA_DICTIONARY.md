# Data Dictionary

## DB Attribute Definitions

Non-obvious database attributes and abbreviations:

- **pmid** - PubMed Unique Identifier; primary key assigned by NCBI to each article
- **pmc_id** - PubMed Central ID; identifier for open-access full-text articles (e.g., PMC12345)
- **doi** - Digital Object Identifier; persistent identifier for scholarly articles (e.g., 10.1016/j.example.2023.01.001)
- **journal_iso_abbrev** - ISO 4 abbreviated journal name (e.g., "J. Neurosci." for "Journal of Neuroscience")
- **journal_issn** - International Standard Serial Number; unique 8-digit identifier for serial publications
- **pub_date_full** - ISO 8601 formatted date string (YYYY-MM-DD); derived from pub_year, pub_month, pub_day with padding for incomplete dates
- **publication_status** - Publication status from PubMed (e.g., "Publisher", "PubMed", "MEDLINE")
- **fetch_date** - ISO 8601 timestamp when this record was fetched from PubMed API
- **fetch_status** - Status of fetch operation; "complete" if all data retrieved, "partial" if incomplete
- **fore_name** - Author's first and middle names (as opposed to last_name); may include multiple names
- **orcid** - Open Researcher and Contributor ID; persistent digital identifier for researchers (e.g., 0000-0001-2345-6789)
- **author_position** - 1-indexed position in author list; preserves author order for citation purposes
- **descriptor_ui** - MeSH descriptor unique identifier (e.g., D006624 for "Hippocampus")
- **descriptor_name** - Human-readable MeSH (Medical Subject Headings) term text
- **is_major_topic** - Boolean flag; TRUE if this term/keyword is a major focus of the paper, FALSE if minor
- **qualifier_names** - Semicolon-separated list of MeSH qualifiers that refine the descriptor (e.g., "anatomy & histology; physiology")
- **grant_acronym** - Abbreviated name of funding agency (e.g., "NIH", "NSF", "NIMH")
- **pub_type_ui** - Publication type unique identifier assigned by PubMed
- **pub_type_name** - Human-readable publication type (e.g., "Journal Article", "Review", "Meta-Analysis")
- **fetch_success** - Boolean; TRUE if fetch and insertion succeeded, FALSE if failed
- **fetch_duration_ms** - Time elapsed during fetch operation in milliseconds
- **retry_count** - Number of retry attempts for this PMID (used for transient failures)
- **webenv** - Entrez History Server WebEnv key; server-side session identifier for cached search results (expires after 8 hours)
- **query_key** - Entrez History query identifier; references a specific query within a WebEnv session
- **citing_pmid** - PMID of the paper making the citation (source)
- **cited_pmid** - PMID of the paper being cited (target)
- **cited_doi** - DOI of the cited paper (used when PMID unavailable)


## PubMed XML Source Data

This data dictionary documents the complete data pipeline from PubMed XML to SQLite database for neuroscience literature analysis. The pipeline extracts, transforms, and loads (ETL) bibliometric metadata from NCBI's PubMed database via the E-utilities API. 
 
- **Primary Source:** NCBI PubMed via E-utilities API
- **API Documentation:** https://www.ncbi.nlm.nih.gov/books/NBK25499/
- **XML Format:** PubMed XML DTD (https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_190101.dtd)
- **Coverage:** Biomedical literature from MEDLINE, life science journals, and online books

**Document Structure:** PubMed XML responses contain one or more `<PubmedArticle>` elements, each representing a single paper.

### Key XML Paths

| Field | XML Path | Data Type | Description |
|-------|----------|-----------|-------------|
| **PMID** | `/PubmedArticle/MedlineCitation/PMID` | Integer | PubMed Unique Identifier (primary key) |
| **DOI** | `/PubmedArticle/PubmedData/ArticleIdList/ArticleId[@IdType='doi']` | String | Digital Object Identifier |
| **PMC ID** | `/PubmedArticle/PubmedData/ArticleIdList/ArticleId[@IdType='pmc']` | String | PubMed Central ID (e.g., PMC12345) |
| **Title** | `/PubmedArticle/MedlineCitation/Article/ArticleTitle` | Text | Article title |
| **Abstract** | `/PubmedArticle/MedlineCitation/Article/Abstract/AbstractText` | Text | Abstract text (may be structured with labels) |
| **Language** | `/PubmedArticle/MedlineCitation/Article/Language` | String(3) | ISO 639-2 language code (e.g., 'eng') |
| **Journal Name** | `/PubmedArticle/MedlineCitation/Article/Journal/Title` | Text | Full journal name |
| **Journal ISSN** | `/PubmedArticle/MedlineCitation/Article/Journal/ISSN` | String | International Standard Serial Number |
| **Journal Abbrev** | `/PubmedArticle/MedlineCitation/Article/Journal/ISOAbbreviation` | Text | ISO journal abbreviation |
| **Publication Year** | `/PubmedArticle/MedlineCitation/Article/Journal/JournalIssue/PubDate/Year` | Integer | 4-digit year |
| **Publication Month** | `/PubmedArticle/MedlineCitation/Article/Journal/JournalIssue/PubDate/Month` | Integer | 1-12 or month name |
| **Publication Day** | `/PubmedArticle/MedlineCitation/Article/Journal/JournalIssue/PubDate/Day` | Integer | 1-31 |
| **Volume** | `/PubmedArticle/MedlineCitation/Article/Journal/JournalIssue/Volume` | String | Journal volume number |
| **Issue** | `/PubmedArticle/MedlineCitation/Article/Journal/JournalIssue/Issue` | String | Journal issue number |
| **Pagination** | `/PubmedArticle/MedlineCitation/Article/Pagination/MedlinePgn` | String | Page range (e.g., "123-45") |

### Author Information

**XML Path:** `/PubmedArticle/MedlineCitation/Article/AuthorList/Author`

| Field | XML Subpath | Data Type | Notes |
|-------|-------------|-----------|-------|
| Last Name | `LastName` | Text | Required for valid author |
| Fore Name | `ForeName` | Text | Full first/middle name(s) |
| Initials | `Initials` | String | Author initials (e.g., "JD") |
| ORCID | `Identifier[@Source='ORCID']` | String | ORCID iD (e.g., 0000-0001-2345-6789) |
| Affiliation | `AffiliationInfo/Affiliation` | Text | Institutional affiliation (first only if multiple) |

### MeSH Terms (Medical Subject Headings)

**XML Path:** `/PubmedArticle/MedlineCitation/MeshHeadingList/MeshHeading`

| Field | XML Subpath | Data Type | Description |
|-------|-------------|-----------|-------------|
| Descriptor UI | `DescriptorName[@UI]` | String | Unique MeSH identifier (e.g., D006624) |
| Descriptor Name | `DescriptorName` | Text | MeSH term text (e.g., "Hippocampus") |
| Major Topic | `DescriptorName[@MajorTopicYN]` | Boolean | Y = major topic, N = minor |
| Qualifiers | `QualifierName` | Text[] | MeSH qualifiers (e.g., "anatomy & histology") |

### Keywords

**XML Path:** `/PubmedArticle/MedlineCitation/KeywordList/Keyword`

| Field | XML Subpath | Data Type | Description |
|-------|-------------|-----------|-------------|
| Keyword | `Keyword` | Text | Author-provided keyword |
| Major Topic | `Keyword[@MajorTopicYN]` | Boolean | Y/N indicator |

### Publication Types

**XML Path:** `/PubmedArticle/MedlineCitation/Article/PublicationTypeList/PublicationType`

| Field | XML Subpath | Data Type | Description |
|-------|-------------|-----------|-------------|
| Pub Type UI | `PublicationType[@UI]` | String | Publication type ID |
| Pub Type Name | `PublicationType` | Text | Type name (e.g., "Journal Article", "Review") |

### Grant Information

**XML Path:** `/PubmedArticle/MedlineCitation/Article/GrantList/Grant`

| Field | XML Subpath | Data Type | Description |
|-------|-------------|-----------|-------------|
| Grant ID | `GrantID` | String | Grant/award number |
| Acronym | `Acronym` | String | Agency acronym (e.g., "NIH", "NSF") |
| Agency | `Agency` | Text | Full funding agency name |
| Country | `Country` | String | Country of funding agency |

### References (Citations)

**XML Path:** `/PubmedArticle/PubmedData/ReferenceList/Reference`

| Field | XML Subpath | Data Type | Description |
|-------|-------------|-----------|-------------|
| Cited PMID | `ArticleIdList/ArticleId[@IdType='pubmed']` | Integer | PMID of cited paper |
| Cited DOI | `ArticleIdList/ArticleId[@IdType='doi']` | String | DOI of cited paper |
| Citation Text | `Citation` | Text | Full citation string |
