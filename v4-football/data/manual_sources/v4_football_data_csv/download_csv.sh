#!/bin/bash
# Download football-data.co.uk CSV files for V4 price-aware replay audit
# Usage: bash download_csv.sh

set -euo pipefail

BASE_URL="https://www.football-data.co.uk/mmz4281"
RAW_DIR="$(cd "$(dirname "$0")" && pwd)/raw"
mkdir -p "$RAW_DIR"

# League definitions: CODE|NAME
LEAGUES=(
  "E0|English Premier League"
  "SP1|Spanish La Liga"
  "D1|German Bundesliga"
  "I1|Italian Serie A"
  "F1|French Ligue 1"
  "P1|Portuguese Primeira Liga"
  "N1|Dutch Eredivisie"
  "B1|Belgian Pro League"
  "T1|Turkish Süper Lig"
)

# Season codes (season_code|season_label|status)
# 2526 = 2025/26 (current, partial)
# 2425 = 2024/25
# 2324 = 2023/24
# 2223 = 2022/23
# 2122 = 2021/22
# 2021 = 2020/21
SEASONS=(
  "2526|2025/26|CURRENT_PARTIAL"
  "2425|2024/25|COMPLETE"
  "2324|2023/24|COMPLETE"
  "2223|2022/23|COMPLETE"
  "2122|2021/22|COMPLETE"
  "2021|2020/21|COMPLETE"
)

TOTAL=$(( ${#LEAGUES[@]} * ${#SEASONS[@]} ))
COUNT=0
FAIL=0
MISSING=0

echo "=========================================="
echo "V4 Football-Data.co.uk CSV Downloader"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "Target: ${#LEAGUES[@]} leagues × ${#SEASONS[@]} seasons = ${TOTAL} files"
echo "Output: ${RAW_DIR}"
echo "=========================================="
echo ""

for LEAGUE_ENTRY in "${LEAGUES[@]}"; do
  LEAGUE_CODE="${LEAGUE_ENTRY%%|*}"
  LEAGUE_NAME="${LEAGUE_ENTRY##*|}"

  for SEASON_ENTRY in "${SEASONS[@]}"; do
    IFS='|' read -r SEASON_CODE SEASON_LABEL SEASON_STATUS <<< "$SEASON_ENTRY"

    URL="${BASE_URL}/${SEASON_CODE}/${LEAGUE_CODE}.csv"
    OUTFILE="${RAW_DIR}/${LEAGUE_CODE}_${SEASON_CODE}.csv"

    HTTP_CODE=$(curl -s -o "$OUTFILE" -w "%{http_code}" --connect-timeout 10 --max-time 30 "$URL" 2>/dev/null || echo "000")

    COUNT=$((COUNT + 1))

    if [ "$HTTP_CODE" = "200" ]; then
      FILE_SIZE=$(wc -c < "$OUTFILE" | tr -d ' ')
      echo "[OK]   ${COUNT}/${TOTAL} ${LEAGUE_CODE} ${SEASON_LABEL} (${LEAGUE_NAME}) — ${FILE_SIZE} bytes"
    elif [ "$HTTP_CODE" = "404" ]; then
      MISSING=$((MISSING + 1))
      rm -f "$OUTFILE"
      echo "[404]  ${COUNT}/${TOTAL} ${LEAGUE_CODE} ${SEASON_LABEL} (${LEAGUE_NAME}) — NOT FOUND"
    else
      FAIL=$((FAIL + 1))
      rm -f "$OUTFILE"
      echo "[FAIL] ${COUNT}/${TOTAL} ${LEAGUE_CODE} ${SEASON_LABEL} (${LEAGUE_NAME}) — HTTP ${HTTP_CODE}"
    fi
  done
done

echo ""
echo "=========================================="
echo "Download complete."
echo "Expected: ${TOTAL}"
echo "Downloaded: $((TOTAL - MISSING - FAIL))"
echo "Not found (404): ${MISSING}"
echo "Failed: ${FAIL}"
echo "=========================================="
echo ""
echo "Files in ${RAW_DIR}:"
ls -la "${RAW_DIR}/" 2>/dev/null || echo "(empty)"
