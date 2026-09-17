#!/bin/bash
# Usage: ./run_simulation.sh --attack-type {passthrough|static|drift|complete_loss|degradation} --spawn-location {ornl|canberra}
set -euo pipefail

usage() {
    echo "Usage: $0 --attack-type {passthrough|static|drift|complete_loss|degradation} --spawn-location {ornl|canberra}" >&2
    exit 1
}

ATTACK_TYPE=""
SPAWN_LOCATION=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --attack-type) ATTACK_TYPE="$2"; shift 2 ;;
        --spawn-location) SPAWN_LOCATION="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; usage ;;
    esac
done

case "$ATTACK_TYPE" in
    passthrough|static|drift|complete_loss|degradation) ;;
    *) echo "Invalid --attack-type: '$ATTACK_TYPE'" >&2; usage ;;
esac

case "$SPAWN_LOCATION" in
    ornl|canberra) ;;
    *) echo "Invalid --spawn-location: '$SPAWN_LOCATION'" >&2; usage ;;
esac

cd "$(dirname "$0")"

bash clear_persistent.sh
mkdir -p logs

START_TS=$(date -u +%Y%m%dT%H%M%SZ)

# All artifacts for this run collect in one folder.
RUN_DIR="logs/${ATTACK_TYPE}_${SPAWN_LOCATION}_${START_TS}"
mkdir -p "$RUN_DIR"

read -r LAT LON ALT < <(python3 -c "
import yaml
coords = yaml.safe_load(open('plans/spawn_point_lookup.yaml'))['${SPAWN_LOCATION}']
print(coords['lat'], coords['lon'], coords['alt'])
")

SITL_LOG="${RUN_DIR}/sitl.log"
echo "Run start (UTC): ${START_TS}"
echo "Starting SITL (${SPAWN_LOCATION}) at ${LAT},${LON},${ALT}. Log: ${SITL_LOG}"
sim_vehicle.py -v ArduCopter \
    --custom-location="${LAT},${LON},${ALT},0" \
    --out udp:127.0.0.1:14550 \
    --out udp:127.0.0.1:14551 \
    > "$SITL_LOG" 2>&1 < <(tail -f /dev/null) &
SITL_PID=$!

cat <<EOF

SITL is starting (PID ${SITL_PID}, log: ${SITL_LOG}). While it initializes:
  1. Open QGroundControl: ./QGroundControl-x86_64.AppImage
  2. Plan view -> Open -> plans/${SPAWN_LOCATION}.plan -> Upload
  3. Fly view -> Start Mission when the simulation script says it's ready.

EOF

python3 -m simulation.run_simulation --attack-type "$ATTACK_TYPE" --spawn-location "$SPAWN_LOCATION" --output-dir "$RUN_DIR"

echo ""
echo "Simulation complete. Type 'kill' to stop SITL and save the flight log."

while true; do
    read -r -p "> " cmd
    if [[ "${cmd,,}" == "kill" ]]; then
        echo "Stopping simulation..."
        pkill -f 'build/sitl/bin/arducopter' || true
        pkill -f 'mavproxy.py.*5760' || true
        pkill -f 'xterm.*ArduCopter' || true
        sleep 2
        END_TS=$(date -u +%Y%m%dT%H%M%SZ)
        echo "Run start (UTC): ${START_TS}"
        echo "Run end   (UTC): ${END_TS}"
        {
            echo ""
            echo "gps-attack run start (UTC): ${START_TS}"
            echo "gps-attack run end   (UTC): ${END_TS}"
        } >> "$SITL_LOG"
        BIN_LOG=$(ls -t logs/*.BIN 2>/dev/null | head -1 || true)
        if [[ -n "$BIN_LOG" ]]; then
            cp "$BIN_LOG" "${RUN_DIR}/flight.bin"
            echo "Saved flight log: ${RUN_DIR}/flight.bin"
            # Extract vehicle metrics from the fully-flushed .bin (SITL is stopped).
            python3 -m simulation.extract_vehicle_metrics "${RUN_DIR}/flight.bin" -o "${RUN_DIR}/vehicle.csv"
            # The raw numbered DataFlash log and its index pointer are now
            # redundant (copied into the run folder); remove them to avoid confusion.
            rm -f "$BIN_LOG" logs/LASTLOG.TXT
        else
            echo "WARNING: no DataFlash .BIN found in logs/"
        fi
        echo "Run folder: ${RUN_DIR}"
        echo "Done."
        break
    fi
    echo "Type 'kill' to stop the simulation."
done
