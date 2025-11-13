#!/usr/bin/env python3
"""
Integration Test #2: Validates parser against real PubMed XML fixture.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from transform.xml_parser import parse_xml_batch


def test_parse_complete_xml():
    print("\n=== Testing XML Parsing ===\n")

    # Load fixture
    fixture_path = Path(__file__).parent.parent / "data" / "test" / "pubmed_api_test.xml"
    print(f"Step 1: Loading fixture from {fixture_path.name}...")

    with open(fixture_path, "r") as f:
        xml_data = f.read()

    print(f"  ✓ Loaded {len(xml_data)} bytes of XML")

    # Parse XML
    print("\nStep 2: Parsing XML...")
    papers = parse_xml_batch(xml_data)

    print(f"  ✓ Parsed {len(papers)} papers")
    assert len(papers) >= 1, "Should parse at least 1 paper"

    # Validate first paper structure
    print("\nStep 3: Validating first paper structure...")
    paper = papers[0]

    # Required fields (per schema NOT NULL)
    assert "pmid" in paper and paper["pmid"] is not None, "PMID required (NOT NULL)"
    assert "title" in paper and paper["title"] is not None, "title required (NOT NULL)"
    assert isinstance(paper["pmid"], int), "PMID must be integer"
    assert isinstance(paper["title"], str), "title must be string"

    print(f"  ✓ PMID: {paper['pmid']}")
    print(f"  ✓ Title: {paper['title'][:50]}...")

    # Check all expected fields exist (schema-driven)
    expected_fields = [
        'pmid', 'doi', 'pmc_id', 'title', 'abstract', 'language',
        'journal_name', 'journal_issn', 'journal_iso_abbrev',
        'pub_year', 'pub_month', 'pub_day',
        'volume', 'issue', 'pages', 'publication_status',
        'authors', 'citations'
    ]

    for field in expected_fields:
        assert field in paper, f"Missing field: {field}"

    print(f"  ✓ All {len(expected_fields)} expected fields present")

    # Validate nested entities
    print("\nStep 4: Validating nested entities...")

    # Authors (list of dicts)
    assert isinstance(paper["authors"], list), "authors must be list"
    if paper["authors"]:
        author = paper["authors"][0]
        # Required: last_name, position (per schema NOT NULL)
        assert "last_name" in author and author["last_name"] is not None
        assert "position" in author and author["position"] is not None
        print(f"  ✓ Authors: {len(paper['authors'])} found")

    # Citations (list of dicts)
    assert isinstance(paper["citations"], list), "citations must be list"
    if paper["citations"]:
        print(f"  ✓ Citations: {len(paper['citations'])} found")

    # Validate all papers
    print("\nStep 5: Validating all papers...")
    pmids = [p["pmid"] for p in papers]
    print(f"  ✓ PMIDs: {', '.join(str(p) for p in pmids[:5])}...")

    assert len(pmids) == len(set(pmids)), "All PMIDs must be unique"
    assert all(isinstance(p, int) for p in pmids), "All PMIDs must be integers"

    print("===============================")
    print("\nXML Parsing Test PASSED\n")
    print("===============================")


if __name__ == "__main__":
    test_parse_complete_xml()
