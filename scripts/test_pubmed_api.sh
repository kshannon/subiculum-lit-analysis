#!/bin/bash

set -e

NUM_ARTICLES=3
OUTPUT_FILE="data/test/pubmed_api_test.xml"
SEARCH_QUERY="subiculum%5BTitle/Abstract%5D"  # URL-encoded: subiculum[Title/Abstract]
EMAIL="${PUBMED_EMAIL:-test@example.com}"
TOOL="subiculum-lit-analysis"
BASE_URL="https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

echo "=== PubMed API Test ==="
echo "Fetching ${NUM_ARTICLES} articles..."

SEARCH_URL="${BASE_URL}/esearch.fcgi?db=pubmed&term=${SEARCH_QUERY}&retmax=${NUM_ARTICLES}&retmode=json&email=${EMAIL}&tool=${TOOL}"

# Step 1: Get PMIDs
echo "→ Querying: ${SEARCH_QUERY}"
SEARCH_RESULT=$(curl -s --max-time 30 "${SEARCH_URL}" 2>&1)

if [ $? -ne 0 ]; then
    echo "FAILED: Network error connecting to PubMed"
    echo "Error: $SEARCH_RESULT"
    exit 1
fi

PMID_LIST=$(echo "$SEARCH_RESULT" | grep -o '"idlist":\[[^]]*\]' | grep -o '[0-9]\+' | tr '\n' ',' | sed 's/,$//' || true)

if [ -z "$PMID_LIST" ]; then
    echo "FAILED: Could not retrieve PMIDs from PubMed"
    echo "Response preview: ${SEARCH_RESULT:0:200}"
    exit 1
fi

echo "✓ Retrieved PMIDs: ${PMID_LIST}"

sleep 1

# Step 2: Fetch XML
FETCH_URL="${BASE_URL}/efetch.fcgi?db=pubmed&id=${PMID_LIST}&retmode=xml&email=${EMAIL}&tool=${TOOL}"
XML_DATA=$(curl -s --max-time 60 "${FETCH_URL}")

if [ -z "$XML_DATA" ]; then
    echo "FAILED: Could not fetch XML data"
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"
echo "$XML_DATA" > "$OUTPUT_FILE"

# Validate
ARTICLE_COUNT=$(grep -o "<PubmedArticle>" "$OUTPUT_FILE" | wc -l | tr -d ' ' || echo "0")

if [ "$ARTICLE_COUNT" -ge 1 ]; then
    FILE_SIZE=$(wc -c < "$OUTPUT_FILE" | tr -d ' ')
    echo "✓ Saved ${ARTICLE_COUNT} articles to: ${OUTPUT_FILE}"
    echo "✓ File size: ${FILE_SIZE} bytes"
    echo ""
    echo "======================================="
    echo "PASSED: PubMed API is working correctly"
    echo "======================================="
    exit 0
else
    echo "==========================================="
    echo "FAILED: XML file contains no valid articles"
    echo "==========================================="
    exit 1
fi
