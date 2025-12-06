#!/usr/bin/env python3
"""
Test CrossRef API for citation/reference data enrichment.

Goal: Check if CrossRef has reference lists for papers missing
      citations in our PubMed dataset (58% of papers).

API Docs: https://api.crossref.org/swagger-ui/index.html
Rate Limit: Polite pool = 50 req/s with email header (no API key needed)
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
CROSSREF_API_BASE = "https://api.crossref.org/works"
RATE_LIMIT_DELAY = 0.5  # seconds (conservative, CrossRef allows 50/s with email)
MAILTO_EMAIL = "your.email@example.com"  # TODO: Load from settings.yaml


def get_papers_without_citations(limit=50):
    """Get sample of papers without citation data in our DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = """
    SELECT p.pmid, p.title, p.pub_year, p.doi
    FROM papers p
    LEFT JOIN citations c ON p.pmid = c.citing_pmid
    WHERE c.citing_pmid IS NULL
      AND p.doi IS NOT NULL  -- Need DOI for CrossRef lookup
      AND p.pub_year >= 2010  -- Focus on recent papers
    GROUP BY p.pmid
    ORDER BY p.pub_year DESC
    LIMIT ?;
    """

    cursor.execute(query, (limit,))
    results = cursor.fetchall()
    conn.close()

    return results


def query_crossref(doi):
    """
    Query CrossRef API for a paper by DOI.

    Returns reference list and metadata if available.
    """
    url = f"{CROSSREF_API_BASE}/{doi}"
    headers = {
        'User-Agent': f'SubiculumLitAnalysis/1.0 (mailto:{MAILTO_EMAIL})'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json().get('message', {})
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
    print("📚 CrossRef API Coverage Test")
    print("=" * 70)

    # Get sample of papers without citations
    print("\n📊 Fetching papers without citation data from our database...")
    papers = get_papers_without_citations(limit=50)
    print(f"✅ Found {len(papers)} papers (2010+) without citations in PubMed")

    # Track statistics
    stats = {
        'total_tested': 0,
        'found_in_crossref': 0,
        'has_references': 0,
        'total_refs_available': 0,
        'has_is_referenced_by': 0,
        'total_cited_by': 0
    }

    sample_results = []

    print("\n🔍 Testing CrossRef API...\n")

    for pmid, title, year, doi in papers[:100]:  # Test 100 (well under 50 req/s limit)
        stats['total_tested'] += 1

        print(f"[{stats['total_tested']}/100] PMID {pmid} ({year})")
        print(f"  Title: {title[:70]}...")
        print(f"  DOI: {doi}")

        # Query CrossRef
        data = query_crossref(doi)
        time.sleep(RATE_LIMIT_DELAY)

        if data:
            stats['found_in_crossref'] += 1

            # Check for reference list
            references = data.get('reference', [])
            ref_count = len(references)

            # Check for citation count (is-referenced-by-count)
            cited_by_count = data.get('is-referenced-by-count', 0)

            if ref_count > 0:
                stats['has_references'] += 1
                stats['total_refs_available'] += ref_count

            if cited_by_count > 0:
                stats['has_is_referenced_by'] += 1
                stats['total_cited_by'] += cited_by_count

            print(f"  ✅ Found in CrossRef!")
            print(f"     References: {ref_count}")
            print(f"     Cited by (CrossRef count): {cited_by_count}")

            # Show sample reference structure
            if references and len(references) > 0:
                sample_ref = references[0]
                print(f"     Sample ref: {sample_ref.get('unstructured', 'N/A')[:60]}...")

            sample_results.append({
                'pmid': pmid,
                'year': year,
                'doi': doi,
                'ref_count': ref_count,
                'cited_by_count': cited_by_count,
                'has_ref_dois': sum(1 for r in references if 'DOI' in r)
            })
        else:
            print(f"  ❌ Not found in CrossRef")

        print()

    # Print summary
    print("=" * 70)
    print("📈 RESULTS SUMMARY")
    print("=" * 70)
    print(f"Papers tested: {stats['total_tested']}")
    print(f"Found in CrossRef: {stats['found_in_crossref']} ({100*stats['found_in_crossref']/stats['total_tested']:.1f}%)")
    print(f"Papers with reference lists: {stats['has_references']} ({100*stats['has_references']/stats['total_tested']:.1f}%)")
    print(f"Papers with citation counts: {stats['has_is_referenced_by']} ({100*stats['has_is_referenced_by']/stats['total_tested']:.1f}%)")
    print(f"\nTotal references available: {stats['total_refs_available']}")
    print(f"Total 'cited by' count: {stats['total_cited_by']}")

    if stats['has_references'] > 0:
        print(f"Average refs per paper (when available): {stats['total_refs_available']/stats['has_references']:.1f}")

    # Check reference quality (DOIs vs unstructured)
    if sample_results:
        total_refs = sum(r['ref_count'] for r in sample_results)
        total_ref_dois = sum(r['has_ref_dois'] for r in sample_results)
        if total_refs > 0:
            print(f"\n📊 Reference quality:")
            print(f"   References with DOIs: {total_ref_dois}/{total_refs} ({100*total_ref_dois/total_refs:.1f}%)")

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
    print(f"Estimated recoverable from CrossRef: ~{estimated_recoverable} ({100*coverage_rate:.1f}%)")
    print(f"Estimated additional citation links: ~{int(estimated_recoverable * (stats['total_refs_available']/max(stats['has_references'],1)))}")

    print("\n💡 RECOMMENDATION:")
    if coverage_rate > 0.5:
        print("   ✅ CrossRef has EXCELLENT coverage!")
        print("   → Recommend building enrichment pipeline")
    elif coverage_rate > 0.2:
        print("   ⚠️  CrossRef has MODERATE coverage")
        print("   → May be worth enrichment, compare with other APIs")
    else:
        print("   ❌ CrossRef has LOW coverage")
        print("   → May not be worth the effort")

    print("\n📝 NOTE:")
    print("   CrossRef references may include:")
    print("   - Structured refs with DOIs (linkable)")
    print("   - Unstructured text refs (harder to link)")

    # Save sample results
    output_file = PROJECT_ROOT / "logs" / "crossref_test_results.json"
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
