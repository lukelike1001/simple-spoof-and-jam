#!/bin/bash
# Usage: ./run_simulation.sh --attack-type {passthrough|fabric|drift|complete_loss|degradation} --spawn-location {ornl|canberra}
set -euo pipefail

usage() {
    echo "Usage: $0 --attack-type {passthrough|fabric|drift|complete_loss|degradation} --spawn-location {ornl|canberra}" >&2
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
    passthrough|fabric|drift|complete_loss|degradation) ;;
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

read -r LAT LON ALT < <(python3 -c "
import yaml
coords = yaml.safe_load(open('plans/spawn_point_lookup.yaml'))['${SPAWN_LOCATION}']
print(coords['lat'], coords['lon'], coords['alt'])
")

SITL_LOG="logs/${ATTACK_TYPE}_${SPAWN_LOCATION}_${START_TS}.log"
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

python3 simulation/run_simulation.py --attack-type "$ATTACK_TYPE" --spawn-location "$SPAWN_LOCATION"

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
        RUN_STEM="${ATTACK_TYPE}_${SPAWN_LOCATION}_${START_TS}_${END_TS}"
        echo "Run start (UTC): ${START_TS}"
        echo "Run end   (UTC): ${END_TS}"
        {
            echo ""
            echo "gps-attack run start (UTC): ${START_TS}"
            echo "gps-attack run end   (UTC): ${END_TS}"
        } >> "$SITL_LOG"
        mv "$SITL_LOG" "logs/${RUN_STEM}.log"
        BIN_LOG=$(ls -t logs/*.BIN 2>/dev/null | head -1 || true)
        if [[ -n "$BIN_LOG" ]]; then
            cp "$BIN_LOG" "logs/${RUN_STEM}.bin"
            echo "Saved flight log: logs/${RUN_STEM}.bin"
        else
            echo "WARNING: no DataFlash .BIN found in logs/"
        fi
        echo "Done."
        break
    fi
    echo "Type 'kill' to stop the simulation."
done
