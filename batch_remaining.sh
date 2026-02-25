#!/bin/bash
# Batch process TI datasheets one at a time with timeout
cd /home/ubuntu/.openclaw/workspace/projects/opendatasheet

PDFS=(
    tps2420_ds.pdf
    lm5067_ds.pdf
    lm5068_ds.pdf
    tps2595_ds.pdf
    tps2590_ds.pdf
    tps25940_ds.pdf
    tps2660_ds.pdf
    tps2661_ds.pdf
    tps2662_ds.pdf
    tps2663_ds.pdf
    tps1663_ds.pdf
    tps1h100-q1_ds.pdf
    lm66100_ds.pdf
    lm66200_ds.pdf
    tps2113_ds.pdf
    tps2113a_ds.pdf
    tps2114_ds.pdf
    lm5051_ds.pdf
)

DONE=0
FAIL=0
SKIP=0
FAILED_LIST=""

for pdf in "${PDFS[@]}"; do
    json_name="${pdf%.pdf}.json"
    json_path="data/extracted_v2/$json_name"
    
    # Skip if already exists and has content
    if [ -f "$json_path" ] && [ "$(stat -c%s "$json_path" 2>/dev/null)" -gt 100 ]; then
        # Check if it has an error
        has_error=$(python3 -c "import json; d=json.load(open('$json_path')); print('error' in d.get('extraction',{}))" 2>/dev/null)
        if [ "$has_error" != "True" ]; then
            echo "⏭ Skip (exists): $pdf"
            SKIP=$((SKIP+1))
            continue
        else
            echo "🔄 Re-processing (had error): $pdf"
            rm -f "$json_path"
        fi
    fi
    
    echo ""
    echo "=========================================="
    echo "Processing: $pdf"
    echo "=========================================="
    
    timeout 180 python3 process_one.py "$pdf"
    rc=$?
    
    if [ $rc -eq 0 ]; then
        DONE=$((DONE+1))
    elif [ $rc -eq 124 ]; then
        echo "⏰ TIMEOUT: $pdf"
        FAIL=$((FAIL+1))
        FAILED_LIST="$FAILED_LIST $pdf(timeout)"
    else
        echo "❌ FAILED: $pdf (exit=$rc)"
        FAIL=$((FAIL+1))
        FAILED_LIST="$FAILED_LIST $pdf"
    fi
    
    # Rate limit
    echo "⏳ Waiting 8s..."
    sleep 8
done

echo ""
echo "=========================================="
echo "BATCH COMPLETE"
echo "=========================================="
echo "Done: $DONE  Skipped: $SKIP  Failed: $FAIL"
if [ -n "$FAILED_LIST" ]; then
    echo "Failed:$FAILED_LIST"
fi
