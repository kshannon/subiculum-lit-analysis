PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_metadata (key, value) VALUES
    ('schema_version', '1.0.0'),
    ('created_date', '2025-11-10'),
    ('last_updated', '2025-11-10'),
    ('description', 'Subiculum literature analysis database');

CREATE TABLE IF NOT EXISTS papers (
    pmid INTEGER PRIMARY KEY,
    doi TEXT,
    pmc_id TEXT,
    title TEXT NOT NULL,
    abstract TEXT,
    language TEXT DEFAULT 'eng',
    journal_name TEXT,
    journal_issn TEXT,
    journal_iso_abbrev TEXT,
    pub_year INTEGER,
    pub_month INTEGER,
    pub_day INTEGER,
    pub_date_full TEXT,
    volume TEXT,
    issue TEXT,
    pages TEXT,
    publication_status TEXT,
    fetch_date TEXT NOT NULL,
    fetch_status TEXT DEFAULT 'complete',
    location_url TEXT,
    UNIQUE(pmid)
);

CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(pub_year);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_journal ON papers(journal_name);
CREATE INDEX IF NOT EXISTS idx_papers_title ON papers(title);

CREATE TABLE IF NOT EXISTS authors (
    author_id INTEGER PRIMARY KEY AUTOINCREMENT,
    last_name TEXT NOT NULL,
    fore_name TEXT,
    initials TEXT,
    orcid TEXT,
    UNIQUE(last_name, fore_name, orcid)
);

CREATE INDEX IF NOT EXISTS idx_authors_orcid ON authors(orcid);

CREATE TABLE IF NOT EXISTS paper_authors (
    pmid INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    author_position INTEGER NOT NULL,
    affiliation TEXT,
    FOREIGN KEY (pmid) REFERENCES papers(pmid) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES authors(author_id),
    PRIMARY KEY (pmid, author_id),
    UNIQUE (pmid, author_position)
);

CREATE INDEX IF NOT EXISTS idx_paper_authors_author ON paper_authors(author_id);

CREATE TABLE IF NOT EXISTS citations (
    citing_pmid INTEGER NOT NULL,
    cited_pmid INTEGER,
    cited_doi TEXT,
    citation_text TEXT,
    FOREIGN KEY (citing_pmid) REFERENCES papers(pmid) ON DELETE CASCADE,
    PRIMARY KEY (citing_pmid, cited_pmid, cited_doi)
);

CREATE INDEX IF NOT EXISTS idx_citations_cited ON citations(cited_pmid);

CREATE TABLE IF NOT EXISTS keywords (
    keyword_id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_keywords (
    pmid INTEGER NOT NULL,
    keyword_id INTEGER NOT NULL,
    is_major_topic BOOLEAN DEFAULT 0,
    FOREIGN KEY (pmid) REFERENCES papers(pmid) ON DELETE CASCADE,
    FOREIGN KEY (keyword_id) REFERENCES keywords(keyword_id),
    PRIMARY KEY (pmid, keyword_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_keywords_keyword ON paper_keywords(keyword_id);
CREATE INDEX IF NOT EXISTS idx_keywords_text ON keywords(keyword);

CREATE TABLE IF NOT EXISTS mesh_terms (
    mesh_id INTEGER PRIMARY KEY AUTOINCREMENT,
    descriptor_ui TEXT UNIQUE,
    descriptor_name TEXT NOT NULL,
    UNIQUE(descriptor_ui)
);

CREATE TABLE IF NOT EXISTS paper_mesh_terms (
    pmid INTEGER NOT NULL,
    mesh_id INTEGER NOT NULL,
    is_major_topic BOOLEAN DEFAULT 0,
    qualifier_names TEXT,
    FOREIGN KEY (pmid) REFERENCES papers(pmid) ON DELETE CASCADE,
    FOREIGN KEY (mesh_id) REFERENCES mesh_terms(mesh_id),
    PRIMARY KEY (pmid, mesh_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_mesh_term ON paper_mesh_terms(mesh_id);
CREATE INDEX IF NOT EXISTS idx_mesh_descriptor_ui ON mesh_terms(descriptor_ui);
CREATE INDEX IF NOT EXISTS idx_mesh_descriptor_name ON mesh_terms(descriptor_name);

CREATE TABLE IF NOT EXISTS grants (
    grant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    grant_number TEXT NOT NULL,
    grant_acronym TEXT,
    agency TEXT NOT NULL,
    country TEXT,
    UNIQUE(grant_number, agency)
);

CREATE TABLE IF NOT EXISTS paper_grants (
    pmid INTEGER NOT NULL,
    grant_id INTEGER NOT NULL,
    FOREIGN KEY (pmid) REFERENCES papers(pmid) ON DELETE CASCADE,
    FOREIGN KEY (grant_id) REFERENCES grants(grant_id),
    PRIMARY KEY (pmid, grant_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_grants_pmid ON paper_grants(pmid);
CREATE INDEX IF NOT EXISTS idx_paper_grants_grant ON paper_grants(grant_id);
CREATE INDEX IF NOT EXISTS idx_grants_agency ON grants(agency);

CREATE TABLE IF NOT EXISTS publication_types (
    pub_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pub_type_ui TEXT UNIQUE,
    pub_type_name TEXT NOT NULL,
    UNIQUE(pub_type_ui)
);

CREATE TABLE IF NOT EXISTS paper_publication_types (
    pmid INTEGER NOT NULL,
    pub_type_id INTEGER NOT NULL,
    FOREIGN KEY (pmid) REFERENCES papers(pmid) ON DELETE CASCADE,
    FOREIGN KEY (pub_type_id) REFERENCES publication_types(pub_type_id),
    PRIMARY KEY (pmid, pub_type_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_pub_types_pmid ON paper_publication_types(pmid);
CREATE INDEX IF NOT EXISTS idx_paper_pub_types_type ON paper_publication_types(pub_type_id);

CREATE TABLE IF NOT EXISTS fetch_log (
    pmid INTEGER PRIMARY KEY,
    fetch_attempt_date TEXT NOT NULL,
    fetch_success BOOLEAN NOT NULL,
    fetch_duration_ms INTEGER,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    FOREIGN KEY (pmid) REFERENCES papers(pmid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fetch_log_success ON fetch_log(fetch_success);
CREATE INDEX IF NOT EXISTS idx_fetch_log_date ON fetch_log(fetch_attempt_date);
CREATE INDEX IF NOT EXISTS idx_fetch_log_retry ON fetch_log(retry_count);

CREATE TABLE IF NOT EXISTS paper_search_sources (
    pmid INTEGER NOT NULL,
    search_type TEXT NOT NULL,
    search_query TEXT NOT NULL,
    found_date TEXT NOT NULL,
    FOREIGN KEY (pmid) REFERENCES papers(pmid) ON DELETE CASCADE,
    PRIMARY KEY (pmid, search_type)
);

CREATE INDEX IF NOT EXISTS idx_paper_search_sources_type ON paper_search_sources(search_type);

CREATE TABLE IF NOT EXISTS paper_open_access (
    pmid INTEGER PRIMARY KEY,
    pmc_id TEXT,
    is_open_access BOOLEAN DEFAULT 0,
    pmc_url TEXT,
    pdf_url TEXT,
    license TEXT,
    FOREIGN KEY (pmid) REFERENCES papers(pmid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_paper_open_access_available ON paper_open_access(is_open_access);

CREATE VIEW IF NOT EXISTS v_papers_with_authors AS
SELECT
    p.pmid,
    p.title,
    p.pub_year,
    GROUP_CONCAT(
        a.last_name || ', ' || COALESCE(a.fore_name, a.initials),
        '; '
    ) as authors,
    COUNT(DISTINCT pa.author_id) as author_count
FROM papers p
LEFT JOIN paper_authors pa ON p.pmid = pa.pmid
LEFT JOIN authors a ON pa.author_id = a.author_id
GROUP BY p.pmid;

CREATE VIEW IF NOT EXISTS v_citation_counts AS
SELECT
    p.pmid,
    p.title,
    p.pub_year,
    COUNT(DISTINCT c.citing_pmid) as times_cited,
    (SELECT COUNT(*) FROM citations WHERE citing_pmid = p.pmid) as references_count
FROM papers p
LEFT JOIN citations c ON p.pmid = c.cited_pmid
GROUP BY p.pmid;

CREATE VIEW IF NOT EXISTS v_papers_with_keywords AS
SELECT
    p.pmid,
    p.title,
    GROUP_CONCAT(k.keyword, '; ') as keywords
FROM papers p
LEFT JOIN paper_keywords pk ON p.pmid = pk.pmid
LEFT JOIN keywords k ON pk.keyword_id = k.keyword_id
GROUP BY p.pmid;

CREATE VIEW IF NOT EXISTS v_papers_by_search_source AS
SELECT
    p.pmid,
    p.title,
    p.pub_year,
    GROUP_CONCAT(pss.search_type, ', ') as search_sources,
    COUNT(DISTINCT pss.search_type) as source_count
FROM papers p
LEFT JOIN paper_search_sources pss ON p.pmid = pss.pmid
GROUP BY p.pmid;

CREATE VIEW IF NOT EXISTS v_open_access_papers AS
SELECT
    p.pmid,
    p.title,
    p.pub_year,
    p.journal_name,
    oa.pmc_id,
    oa.is_open_access,
    oa.pmc_url,
    oa.pdf_url,
    oa.license
FROM papers p
LEFT JOIN paper_open_access oa ON p.pmid = oa.pmid
WHERE oa.is_open_access = 1;

CREATE TRIGGER IF NOT EXISTS update_last_modified
AFTER INSERT ON papers
BEGIN
    UPDATE schema_metadata
    SET value = datetime('now')
    WHERE key = 'last_updated';
END;

VACUUM;
ANALYZE;
