# simple-spoof-and-jam

Toolbox for developing GPS spoofing attacks using ArduPilot SITL. The Python-based SDR injects fake GPS coordinates via MAVLink `GPS_INPUT` messages to trigger geofence breaches.

---

## Repository layout

```
simple-spoof-and-jam/
├── attack/
│   ├── presets/                Per-attack, per-location YAML configs
│   ├── gps_attack.py           Shared YAML + altitude activation
│   ├── spoofing_attack.py      Spoofing base: manipulates navigation content
│   ├── passthrough_attack.py   No spoofing; passes real position through
│   ├── fabric_attack.py        Jump to a fixed fabricated coordinate
│   ├── drift_attack.py         Gradually shifts position at a configured rate
│   ├── jamming_attack.py       Jamming base: manipulates quality/availability
│   ├── complete_loss_attack.py Withhold GPS_INPUT after activation (returns None)
│   ├── degradation_attack.py   Ramp GPS quality down while keeping content authentic
│   └── replay_attack.py        (WIP)
├── communication/
│   ├── sitl_connection.py      MAVLink connection + ArduPilot parameter management
│   ├── sitl_connection_config.py
│   └── sitl_connection_params.yaml
├── drone/
│   ├── configs/
│   │   └── gps_receiver_params.yaml   Signal quality + normalization constants
│   ├── drone.py                Composes GPS receiver, IMU, compass, and clock
│   ├── gps_receiver.py         Stores position/velocity; builds nominal GpsInputState
│   ├── gps_input_state.py      Effect-level GPS state passed to/from attacks
│   ├── imu.py
│   ├── compass.py
│   └── clock.py
├── spoofer/
│   ├── sdr.py                  Drives the GPS_INPUT send loop for the attack duration
│   ├── sdr_config.py
│   └── sdr_params.yaml
├── simulation/
│   └── run_simulation.py       Entry point; wires all components together
├── plans/
│   ├── ornl.plan               QGroundControl waypoint mission + geofence (ORNL, TN)
│   ├── canberra.plan           QGroundControl waypoint mission + geofence (Canberra, AU)
│   └── spawn_point_lookup.yaml Maps spawn-location names to GPS coordinates
├── tests/
│   ├── attack/                 Unit tests for each attack class
│   ├── communication/          Unit tests for SitlConnection
│   └── drone/                  Unit tests for GpsReceiver
├── logs/                       ArduPilot .bin DataFlash logs
├── run_simulation.sh           Quickstart: SITL + attack + timestamped log save
├── pyproject.toml
└── requirements.txt
```

---

## Local Installation

Tested on Ubuntu 22.04. All commands run from the repo root unless noted. The local dependencies only need to set up once regardless of how many GPS attack simulations are run later.

### Step 1: Clone and build ArduPilot SITL

Clone ArduPilot to `~/ardupilot`, outside this repo so its lifecycle stays independent.

```bash
git clone --branch Copter-4.6.3 --recursive https://github.com/ArduPilot/ardupilot.git ~/ardupilot
cd ~/ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
```

`sim_vehicle.py` and `mavproxy.py` need to be on `PATH`. Rather than scattering exports through `~/.bashrc`, keep them in one dedicated profile and source it from `~/.bashrc`:

```bash
cat > ~/.ardupilot_profile << 'EOF'
# ArduPilot SITL tooling for simple-spoof-and-jam local development.
# sim_vehicle.py lives in the clone; mavproxy.py is pip-installed to ~/.local/bin.
export PATH="$HOME/ardupilot/Tools/autotest:$HOME/.local/bin:$PATH"
EOF

cat >> ~/.bashrc << 'EOF'

if [ -f ~/.ardupilot_profile ]; then
    source ~/.ardupilot_profile
fi
EOF
```

Open a new terminal and verify:

```bash
which sim_vehicle.py
which mavproxy.py
```

### Step 2: Install Python dependencies

From the repo root (not the ardupilot directory):

```bash
pip3 install -r requirements.txt --break-system-packages
```

Dependencies: `pymavlink`, `pyyaml`, `matplotlib`, `numpy`.

### Step 3: Install QGroundControl

Download the latest AppImage from the
[QGroundControl daily builds](https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html)
page, then make it executable:

```bash
chmod +x QGroundControl-x86_64.AppImage
./QGroundControl-x86_64.AppImage
```

After opening QGroundControl and verifying that the GUI loads, you can close it for now.

### Removing the local setup

If you no longer need to use or prototype with the `simple-spoof-and-jam` repo, you can remove the local setup by following these instructions.

```bash
rm ~/.ardupilot_profile
```

Then delete this block from the end of `~/.bashrc`:

```bash
if [ -f ~/.ardupilot_profile ]; then
    source ~/.ardupilot_profile
fi
```

---

## Quickstart: `run_simulation.sh`

```bash
./run_simulation.sh --attack-type passthrough --spawn-location ornl
./run_simulation.sh --attack-type fabric --spawn-location canberra
```

Run the script, then open QGroundControl with the matching `.plan` file. Then, arm the flight and start the mission to run the selected mission. You are also highly encouraged to read the detailed walkthrough in the next section to better understand how the repo works.

---

## Detailed Walkthrough: ORNL Passthrough Attack

This section describes how to use `run_simulation.py` rather than the quickstart script, showing what happens behind-the-scenes to set up and run the GPS spoofing attack. To demonstrate this, we will use a passthrough case (a benign attack that doesn't spoof neither the position nor velocity) set with a spawn point at ORNL.

### Step 1: Start SITL

Open a dedicated terminal in the repo root. `sim_vehicle.py` is an executable installed on your PATH by the prereqs script. **Do not prefix it with `python`.** SITL binds two MAVLink outputs: UDP 14550 for QGroundControl, UDP 14551 for the Python scripts.

Spawn altitude is **0 m MSL** from `plans/spawn_point_lookup.yaml`; cruise altitude is **25 m AGL** in `plans/ornl.plan`. The start timestamp is recorded automatically when you run `run_simulation.py` in Step 2.

```bash
sim_vehicle.py -v ArduCopter \
    --custom-location=35.93051398,-84.31067453,0,0 \
    --out udp:127.0.0.1:14550 \
    --out udp:127.0.0.1:14551
```

You should see a new `ArduCopter` window pop up.
<p align="center">
    <img src="icons/arducopter.png" alt="ArduCopter Window" width="400">
</p>

**NOTE:** For questions about how ArduPilot formats `custom-location`, see [DEBUG_FAQ.md](DEBUG_FAQ.md#ardupilot-custom-location-formatting).

### Step 2: Apply baseline parameters

In a different terminal (Terminal 2):

```bash
python3 simulation/run_simulation.py --attack-type passthrough --spawn-location ornl
```

This script starts the GPS attack simulation, with a specified attack type and a spawn location. Leave this terminal running: when the vehicle disarms after landing, it copies the DataFlash log to `logs/passthrough_ornl_<start>_<end>.bin`.

### Step 3: Open QGroundControl

Open QGroundControl in another terminal (Terminal 3).

```bash
./QGroundControl-x86_64.AppImage
```

It auto-connects to SITL on UDP 14550.

### Step 4: Configure QGroundControl.

Inside QGroundControl, use the GUI and apply the following steps:

a. <img src="icons/qgroundcontrol_plan.png" alt="Plan" width="100"> Go to **Plan** view. (Click the "Q" icon in the top-left corner for the drop-down.)

b. <img src="icons/qgroundcontrol_open.png" alt="Open" width="100"> Click the file icon → **Open** → select `plans/ornl.plan`

c. <img src="icons/qgroundcontrol_upload.png" alt="Upload" width="100"> Click **Upload** to send the mission and geofence to SITL.

### Step 5: Arm and fly

**CRITICAL STEP**: Wait until the console prints `APM: EKF3 IMU0 is using GPS` before proceeding, because the simulated GPS fix is required for arming. The vehicle spawns near Oak Ridge, TN (35.93°, -84.31°) See [DEBUG_FAQ.md](DEBUG_FAQ.md#ornl-baseline-flight-is-not-ready) if you see a yellow "Not Ready" message.

In QGroundControl **Fly** view, hold the **Start Mission** slider-arm button.

![ORNL Arm and Fly](icons/ornl_arm_and_fly.png)

**Expected:** drone takes off to 25 m, flies to all waypoints, then RTLs home. No fence breach alert fires.

When it lands and disarms, Terminal 2 should print `Flight finished (disarmed).` and `Saved flight log: logs/passthrough_ornl_<start>_<end>.bin`. Then Ctrl+C the `sim_vehicle.py` terminal.

![ORNL Finished Flight](icons/ornl_finished_flight.png)

AUTO-01 is complete when that timestamped `.bin` exists and the QGroundControl map shows a clean rectangular path with no geofence breach.

---
