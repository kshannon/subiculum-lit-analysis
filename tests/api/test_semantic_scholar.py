#!/usr/bin/env python3
"""
Test Semantic Scholar API for citation/reference data enrichment.

Goal: Check if Semantic Scholar has reference lists for papers missing
      citations in our PubMed dataset (58% of papers).

API Docs: https://api.semanticscholar.org/api-docs/graph
Rate Limit: 100 requests/5 minutes (free tier)
"""

import sqlite3
import requests
import time
from pathlib import Path
import json

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "raw" / "subiculum_literature.db"

# API configuration
S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
RATE_LIMIT_DELAY = 3.1  # seconds (100 requests per 5 min = ~3s per request)


def get_papers_without_citations(limit=50):
    """Get sample of papers without citation data in our DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = """
    SELECT p.pmid, p.title, p.pub_year, p.doi
    FROM papers p
    LEFT JOIN citations c ON p.pmid = c.citing_pmid
    WHERE c.citing_pmid IS NULL
      AND p.doi IS NOT NULL  -- Need DOI for S2 lookup
      AND p.pub_year >= 2010  -- Focus on recent papers
    GROUP BY p.pmid
    ORDER BY p.pub_year DESC
    LIMIT ?;
    """

    cursor.execute(query, (limit,))
    results = cursor.fetchall()
    conn.close()

    return results


def query_semantic_scholar(doi):
    """
    Query Semantic Scholar API for a paper by DOI.

    Returns references, citations, and metadata if available.
    """
    url = f"{S2_API_BASE}/paper/DOI:{doi}"
    params = {
        'fields': 'title,year,citationCount,referenceCount,references,citations,externalIds'
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None  # Paper not found
        else:
            print(f"  ⚠️  API error {response.status_code}: {response.text}")
            return None

    except Exception as e:
        print(f"  ❌ Request failed: {e}")
        return None


def main():
    print("=" * 70)
    print("🔬 Semantic Scholar API Coverage Test")
    print("=" * 70)

    # Get sample of papers without citations
    print("\n📊 Fetching papers without citation data from our database...")
    papers = get_papers_without_citations(limit=50)
    print(f"✅ Found {len(papers)} papers (2010+) without citations in PubMed")

    # Track statistics
    stats = {
        'total_tested': 0,
        'found_in_s2': 0,
        'has_references': 0,
        'has_citations': 0,
        'total_refs_available': 0,
        'total_cites_available': 0
    }

    sample_results = []

    print("\n🔍 Testing Semantic Scholar API...\n")

    for pmid, title, year, doi in papers[:50]:  # Test first 50 (within 100/5min limit)
        stats['total_tested'] += 1

        print(f"[{stats['total_tested']}/50] PMID {pmid} ({year})")
        print(f"  Title: {title[:70]}...")
        print(f"  DOI: {doi}")

        # Query S2
        data = query_semantic_scholar(doi)
        time.sleep(RATE_LIMIT_DELAY)

        if data:
            stats['found_in_s2'] += 1

            ref_count = data.get('referenceCount', 0)
            cite_count = data.get('citationCount', 0)

            if ref_count and ref_count > 0:
                stats['has_references'] += 1
                stats['total_refs_available'] += ref_count

            if cite_count and cite_count > 0:
                stats['has_citations'] += 1
                stats['total_cites_available'] += cite_count

            print(f"  ✅ Found in S2!")
            print(f"     References: {ref_count}")
            print(f"     Citations: {cite_count}")

            sample_results.append({
                'pmid': pmid,
                'year': year,
                'doi': doi,
                'ref_count': ref_count,
                'cite_count': cite_count
            })
        else:
            print(f"  ❌ Not found in Semantic Scholar")

        print()

    # Print summary
    print("=" * 70)
    print("📈 RESULTS SUMMARY")
    print("=" * 70)
    print(f"Papers tested: {stats['total_tested']}")
    print(f"Found in Semantic Scholar: {stats['found_in_s2']} ({100*stats['found_in_s2']/stats['total_tested']:.1f}%)")
    print(f"Papers with reference lists: {stats['has_references']} ({100*stats['has_references']/stats['total_tested']:.1f}%)")
    print(f"Papers with citation counts: {stats['has_citations']} ({100*stats['has_citations']/stats['total_tested']:.1f}%)")
    print(f"\nTotal references available: {stats['total_refs_available']}")
    print(f"Total citations available: {stats['total_cites_available']}")

    if stats['has_references'] > 0:
        print(f"Average refs per paper (when available): {stats['total_refs_available']/stats['has_references']:.1f}")

    # Extrapolate to full dataset
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM papers p
        LEFT JOIN citations c ON p.pmid = c.citing_pmid
        WHERE c.citing_pmid IS NULL AND p.doi IS NOT NULL
    """)
    total_without_citations = cursor.fetchone()[0]
    conn.close()

    coverage_rate = stats['has_references'] / stats['total_tested'] if stats['total_tested'] > 0 else 0
    estimated_recoverable = int(total_without_citations * coverage_rate)

    print("\n" + "=" * 70)
    print("🎯 EXTRAPOLATED IMPACT")
    print("=" * 70)
    print(f"Papers in our DB without citations (with DOI): {total_without_citations}")
    print(f"Estimated recoverable from Semantic Scholar: ~{estimated_recoverable} ({100*coverage_rate:.1f}%)")
    print(f"Estimated additional citation links: ~{int(estimated_recoverable * (stats['total_refs_available']/max(stats['has_references'],1)))}")

    print("\n💡 RECOMMENDATION:")
    if coverage_rate > 0.5:
        print("   ✅ Semantic Scholar has EXCELLENT coverage!")
        print("   → Recommend building enrichment pipeline")
    elif coverage_rate > 0.2:
        print("   ⚠️  Semantic Scholar has MODERATE coverage")
        print("   → May be worth enrichment, test other APIs too")
    else:
        print("   ❌ Semantic Scholar has LOW coverage")
        print("   → Test other APIs (CrossRef, OpenCitations)")

    # Save sample results
    output_file = PROJECT_ROOT / "logs" / "semantic_scholar_test_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            'stats': stats,
            'sample_results': sample_results,
            'total_without_citations': total_without_citations,
            'estimated_recoverable': estimated_recoverable
        }, f, indent=2)

    print(f"\n📄 Detailed results saved to: {output_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
