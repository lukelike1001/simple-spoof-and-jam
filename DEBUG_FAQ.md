# gps-attack Debugging FAQ

# Reverting Ardupilot Back to Normal (Removing Persisted Parameters)

tl;dr Run this easy-to-use script to delete Ardupilot run artifacts:

```bash
./clear_persistent.sh
```

A longer explanation for reverting Ardupilot is provided below.

## Step 1: Stop SITL

Hit `Ctrl+C` in the `sim_vehicle.py` terminal (if you're currently running any of the `gps-attack` tests).

## Step 2: Delete `eeprom.bin`

It contains all the persisted parameters in Ardupilot, so delete the file to return to ArduPilot's factory default settings.

```bash
rm eeprom.bin
```

## Step 3: Clean up MAVProxy run artifacts (optional)

While optional, you can clean up other MAVProxy run artifacts so they don't clutter your view.

```bash
rm -f mav.parm mav.tlog mav.tlog.raw
```

## Step 4: Reluanch SITL:

```bash
sim_vehicle.py -v ArduCopter \
    --out udp:127.0.0.1:14550 \
    --out udp:127.0.0.1:14551
```

Wait for the `EKF3 IMU0 is using GPS` message. Then, open QGroundControl, go to Plan, and open whatever `.plan` file you would like. There should be no persisted gps-attack parameters by this point.

# ArduPilot Custom Location Formatting

Take the following ArduPilot script as an example:

```bash
sim_vehicle.py -v ArduCopter \
    --custom-location=35.93051398,-84.31067453,0,0 \
    --out udp:127.0.0.1:14550 \
    --out udp:127.0.0.1:14551
```

Let's break down how the `custom-location` structure works.

```
--custom-location=35.93051398,-84.31067453, 0,     0
                  └────┬─────┘└─────┬──────┘└┬┘  └──┬──┘
                   latitude    longitude    alt  heading

```

1. **Latitude:** degrees, decimal format (35.93°N)
2. **Longitude:** degrees, decimal format (-84.31°W)
3. **Altitude:** meters above sea level (MSL), where the vehicle spawns
4. **Heading:** degrees, compass heading the vehicle faces at spawn (0 = North)


Therefore, in this example, the Oak Ridge National Lab coordinates are (35.93°N, -84.31°W), with a spawn altitude of 0 m MSL and a heading of 0°. Cruise altitude is set in `plans/ornl.plan` (25 m AGL), not in `--custom-location`.

# ORNL baseline flight is "Not Ready"

Let's say you reached Step 6 in the baseline flight example and see a yellow "Not Ready" message as shown here:

![Baseline Fake Bug](icons/ornl_baseline_fake_bug.png)

Moreso, you may see this error in Terminal 1 (and also the QGroundControl log):

```
[22:56:11.367 ] Critical: PreArm: Fence enabled, need position estimate
```

However, you do not have to worry about this message. **Just wait** until you see this message pop up in Terminal 1: `APM: EKF3 IMU0 is using GPS`. If you're fast at going through the directions before the GPS connection, you'll confuse ArduPilot and QGroundControl!

You'll eventually see the yellow "Not Ready" turn into a green "Ready" message, and you can continue the baseline example as normal.