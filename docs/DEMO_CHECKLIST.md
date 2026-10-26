# Manual demo checklist (Wokwi)

Use this for the video or a live demo on [wokwi.com](https://wokwi.com), or through the Wokwi MCP. Cause the outage with the **slide switch**. The red button is a manual shortcut. The CI scenario does **not** use it: CI drops and restores the grid over serial with `GRID0` / `GRID1`.

`config.py` and `policy.py` inside `wokwi/` are copies of the repository root. If you change the policy, run `python3 wokwi/build_firmware.py` before simulating.

## Before you start

1. Open the `wokwi/` project (ESP32 DevKit C V4 + MicroPython).
2. Rebuild `firmware.bin` if any `.py` file changed:
   `python3 wokwi/build_firmware.py`.
3. Keep the serial monitor visible. It prints one JSON object per second.

## Steps

| # | What you do | What you should see |
|---|---|---|
| 0 | Press Start | About 2 s with **both non-critical loads unpowered** (the safe-start window), then `NORMAL`. That is expected. It is the safety property. |
| 1 | Switch to the **left** (grid present) | OLED: `NORMAL`, `SoC 100%`, `B:ON C:ON`, badge `SIM x1`. Green LED (B) and yellow LED (C) **on**. Serial: `"mode": "NORMAL"`, `relay_b` and `relay_c` `true`. |
| 2 | Switch to the **right** (outage) | After about 2 s: mode `CORTE`. The yellow LED (C, waiting room) goes **off**. The green LED (B) stays on. Serial: `events: ["grid_down","shed_c"]`. |
| 3 | Press **SIM k** (or the `K` key) until `SIM x600` | The simulated clock runs at ×600. After about 12 s: mode `AHORRO` and the green LED (B) goes **off**. Both non-critical loads are now unpowered. |
| 4 | Wait | About 60 s of real time after the outage: mode `CRITICO` and the **buzzer sounds**. A (the fridge) **never** turns off. |
| 5 | Switch back to the **left** (grid returns) | After about 5 s: `RESTAURACION` and the green LED (B) turns on. 3 s later C closes (`NORMAL`, both LEDs on). The buzzer stops. |
| 6 | Turn the potentiometer (GPIO35) | Zone A power changes (0–20 W; about 40% ≈ 8 W). At a higher power, the outage reaches `AHORRO` sooner. |

The red **manual outage** button (or the `G` key) does the same thing as step 2 without moving the switch. If the switch is already on "grid present", the button wins: while it is held, the grid counts as down.

## What must never happen

- Zone A loses power because the software decided so. `relay_a` is always `true`, and A has no relay.
- B opens and then closes again during an outage. Shedding is monotone.
- On startup, the non-critical loads are powered before the policy's first decision. That window is the safe start.

## Useful serial commands

`GRID0` (grid down) · `GRID1` (grid present) · `GRID` (read the switch again) · `K=1` · `K=60` · `K=600`.

`wokwi/scenario_accept.yaml` uses these for the outage and the restore.
