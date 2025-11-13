"""PubMed XML parser using pure functions (functional programming approach)."""

import logging
from datetime import datetime
from typing import Optional, List, Dict

from lxml import etree

logger = logging.getLogger(__name__)


def parse_xml_batch(xml_string: str) -> List[Dict]:
    """
    Parse PubMed XML string into list of paper dictionaries.

    Skips papers missing required fields (PMID, title) with logged warnings.
    """
    root = etree.fromstring(xml_string.encode('utf-8'))
    articles = root.findall('.//PubmedArticle')

    papers = []
    for article in articles:
        paper = parse_paper(article)
        if paper:
            papers.append(paper)

    return papers


def parse_paper(article_elem: etree.Element) -> Optional[Dict]:
    """
    Parse single <PubmedArticle> element into paper dictionary.

    Returns None if required fields (PMID, title) are missing.
    """
    # Extract PMID (required)
    pmid_elem = article_elem.find('.//MedlineCitation/PMID')
    if pmid_elem is None or not pmid_elem.text:
        logger.warning("Skipping paper - missing PMID")
        return None

    pmid = int(pmid_elem.text)

    # Extract title (required)
    title_elem = article_elem.find('.//Article/ArticleTitle')
    if title_elem is None or not title_elem.text:
        logger.warning(f"Skipping paper - missing title (PMID: {pmid})")
        return None

    title = title_elem.text.strip()

    # Extract optional identifiers
    doi = None
    pmc_id = None
    for article_id in article_elem.findall('.//ArticleIdList/ArticleId'):
        id_type = article_id.get('IdType')
        if id_type == 'doi':
            doi = article_id.text
        elif id_type == 'pmc':
            pmc_id = article_id.text

    # Extract abstract (optional, may have multiple parts)
    abstract_parts = []
    for abstract_text in article_elem.findall('.//Abstract/AbstractText'):
        label = abstract_text.get('Label')
        text = abstract_text.text or ''
        if label:
            abstract_parts.append(f"{label}: {text}")
        else:
            abstract_parts.append(text)
    abstract = ' '.join(abstract_parts).strip() if abstract_parts else None

    # Extract journal info (optional)
    journal_elem = article_elem.find('.//Journal')
    journal_name = _get_text(journal_elem, 'Title') if journal_elem is not None else None
    journal_issn = _get_text(journal_elem, 'ISSN') if journal_elem is not None else None
    journal_iso = _get_text(journal_elem, 'ISOAbbreviation') if journal_elem is not None else None

    # Extract publication date (optional)
    pub_date = article_elem.find('.//JournalIssue/PubDate')
    pub_year = None
    pub_month = None
    pub_day = None
    if pub_date is not None:
        year_elem = pub_date.find('Year')
        month_elem = pub_date.find('Month')
        day_elem = pub_date.find('Day')

        pub_year = int(year_elem.text) if year_elem is not None and year_elem.text else None
        pub_month = _normalize_month(month_elem.text) if month_elem is not None and month_elem.text else None
        pub_day = int(day_elem.text) if day_elem is not None and day_elem.text else None

    # Extract volume, issue, pages (optional)
    volume = _get_text(article_elem, './/JournalIssue/Volume')
    issue = _get_text(article_elem, './/JournalIssue/Issue')
    pages = _get_text(article_elem, './/Pagination/MedlinePgn')

    # Extract language (optional)
    language = _get_text(article_elem, './/Language')

    # Extract publication status (optional)
    medline_citation = article_elem.find('.//MedlineCitation')
    publication_status = medline_citation.get('Status') if medline_citation is not None else None

    # Parse nested entities
    authors = parse_authors(article_elem, pmid)
    citations = parse_citations(article_elem)

    return {
        'pmid': pmid,
        'doi': doi,
        'pmc_id': pmc_id,
        'title': title,
        'abstract': abstract,
        'language': language,
        'journal_name': journal_name,
        'journal_issn': journal_issn,
        'journal_iso_abbrev': journal_iso,
        'pub_year': pub_year,
        'pub_month': pub_month,
        'pub_day': pub_day,
        'volume': volume,
        'issue': issue,
        'pages': pages,
        'publication_status': publication_status,
        'authors': authors,
        'citations': citations
    }


def parse_authors(article_elem: etree.Element, pmid: int) -> List[Dict]:
    """
    Parse author list from <AuthorList>.

    Skips authors missing last_name (required per schema) with logged warning.
    """
    author_list = article_elem.find('.//AuthorList')
    if author_list is None:
        return []

    authors = []
    for position, author_elem in enumerate(author_list.findall('Author'), start=1):
        # Extract last_name (required per schema)
        last_name_elem = author_elem.find('LastName')
        if last_name_elem is None or not last_name_elem.text:
            logger.warning(f"Skipping author with missing last_name (PMID: {pmid}, position: {position})")
            continue

        last_name = last_name_elem.text.strip()

        # Extract optional fields
        fore_name = _get_text(author_elem, 'ForeName')
        initials = _get_text(author_elem, 'Initials')

        # Extract ORCID (optional)
        orcid = None
        for identifier in author_elem.findall('Identifier'):
            if identifier.get('Source') == 'ORCID':
                orcid = identifier.text
                break

        # Extract affiliation (optional, use first if multiple)
        affiliation = _get_text(author_elem, 'AffiliationInfo/Affiliation')

        authors.append({
            'last_name': last_name,
            'fore_name': fore_name,
            'initials': initials,
            'orcid': orcid,
            'affiliation': affiliation,
            'position': position
        })

    return authors


def parse_citations(article_elem: etree.Element) -> List[Dict]:
    """
    Parse reference list (papers cited by this paper).

    Each citation may have PMID, DOI, or both.
    """
    reference_list = article_elem.find('.//ReferenceList')
    if reference_list is None:
        return []

    citations = []
    for reference in reference_list.findall('Reference'):
        cited_pmid = None
        cited_doi = None

        # Extract PMID and DOI from ArticleIdList
        for article_id in reference.findall('.//ArticleIdList/ArticleId'):
            id_type = article_id.get('IdType')
            if id_type == 'pubmed':
                cited_pmid = int(article_id.text) if article_id.text else None
            elif id_type == 'doi':
                cited_doi = article_id.text

        # Skip if no identifier
        if not cited_pmid and not cited_doi:
            continue

        # Extract citation text (optional)
        citation_text = _get_text(reference, 'Citation')

        citations.append({
            'cited_pmid': cited_pmid,
            'cited_doi': cited_doi,
            'citation_text': citation_text
        })

    return citations


# Helper functions

def _get_text(element: Optional[etree.Element], xpath: str) -> Optional[str]:
    """Safely extract text content from element via XPath."""
    if element is None:
        return None

    child = element.find(xpath)
    if child is not None and child.text:
        return child.text.strip()
    return None


def _normalize_month(month_str: str) -> Optional[int]:
    """Convert month name or number to integer (1-12)."""
    # Try parsing as integer first
    try:
        month = int(month_str)
        return month if 1 <= month <= 12 else None
    except ValueError:
        pass

    # Month name mapping
    months = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12
    }

    return months.get(month_str.lower())
