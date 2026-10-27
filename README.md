# ClinicKeep

ClinicKeep is an energy-priority policy for a clinic that loses the grid. The same code runs in MicroPython on an ESP32 in Wokwi and in ordinary Python, so the firmware and the scenario engine share one policy.

When the grid fails, the waiting room opens first, then the hallway lights. The vaccine fridge is never opened by software. The policy estimates how long the fridge can still run, and how long the box stays inside the safe band after that. It reports a duration, not a clock time.

It does not generate energy. It is not a certified medical device, and it does not use machine learning. With a long outage the limit is still the battery. The physical prototype is the next step. What ships here is the policy, the simulated firmware, the scenario sweeps, and a sizing calculator.

Zones, as named in `policy.py`: **A** vaccine fridge (critical), **B** hallway lights, **C** waiting room. States: `NORMAL`, `CORTE`, `AHORRO`, `CRITICO`, `RESTAURACION`, `FALLO_SENSOR`.

## What you can open

Everything a visitor can click shows a **simulation**. The live dashboard says so in a permanent banner. It is not a feed from a clinic.

| Where | What |
|---|---|
| [clinickeep.focampo.com](https://clinickeep.focampo.com) | Read-only dashboard. Railway backup: [clinickeep-production.up.railway.app](https://clinickeep-production.up.railway.app) |
| [/calc](https://clinickeep.focampo.com/calc) | Sizing calculator. Every input is marked `FUENTE`, `SUPUESTO`, or computed |
| `site/` | Static project sheet, in English, with a control for Latin American Spanish. Netlify publishes this directory (`netlify.toml`) |
| This repository | Policy, tests, Wokwi project, and the scenario engine |

Further reading for a judge: [manual demo](docs/DEMO_CHECKLIST.md), [what is cited and what is not](docs/FUENTES_PENDIENTES.md), [how the live service is deployed](README_DEPLOY.md).

## The didactic result

Assumptions, not measurements: 96 Wh usable, A = 8 W, B = 4 W, C = 3 W, holdover 0.53 h.

| | Fridge runs out of energy | Protected hours (with holdover) |
|---|---|---|
| Without ClinicKeep | 6.4 h | 6.9 h |
| With ClinicKeep | 11.0 h | 11.5 h |

The +66% figure is this cell's protected hours, 6.9 h to 11.5 h. It depends on how much non-critical load B and C draw. When that load is 0%, the improvement is 0%. Less load in B and C means a smaller benefit. The sweep is scenario S2a, below.

## Design rules

1. **A (the fridge) is never opened by software.** `relay_a` is always `True`.
2. **Shedding during an outage is monotone.** B does not close again until the grid returns. When the grid drops, only C opens. B opens in `AHORRO`, when total autonomy falls below `T_RESERVA_H` (6 h, a starting assumption).
3. **Confirm timers in real time; account for energy in simulated time** (`k`, the SIM clock: 1, 60, or 600).
4. **Safe time = autonomy of A + thermal holdover**, both on the same clock.
5. If the power sensor fails while the grid is down, the conservative mode opens B and C and keeps A. If the temperature sensor fails, only the holdover disappears.

Alerts are durations ("move the vaccines in X h Y min"), not wall-clock times.

## Run it on Linux

```bash
cd clinickeep
python3 -m venv .venv
source .venv/bin/activate
pip install pytest matplotlib
pytest -q          # 103 passed (without node: 98 passed, 5 skipped)
python3 demo.py    # one simulated outage, with and without ClinicKeep
```

## Run it in Wokwi

The project is in `wokwi/` (ESP32 DevKit C V4 + MicroPython). `config.py` and `policy.py` there are **copies of the repository root**. Do not edit them in `wokwi/`. `build_firmware.py` copies them before packing (`--sync-only` only syncs), and `tests/test_sync.py` fails if they diverge.

Pinout: `docs/PINOUT.md`. Circuit: `docs/SCHEMA.md`. Relay polarity: `docs/RELAY_CHECK.md`. Step-by-step demo: `docs/DEMO_CHECKLIST.md`.

**The INA219 is future hardware.** Wokwi has no such part. In the simulation, zone A power is **emulated with a potentiometer** (GPIO35), behind `read_power_a_w()`. The real sensor would sit on the I²C bus shared with the OLED (address 0x40), in series with the zone A load. Integrating it replaces that function only. The policy stays untouched.

### Import on wokwi.com

1. Create a **MicroPython ESP32** project on [wokwi.com](https://wokwi.com).
2. Copy into the project: `diagram.json`, `main.py`, `config.py`, `policy.py`, `ssd1306.py`.
3. Press Start. The OLED should show `NORMAL`, state of charge, B/C, and the badge `SIM x1`.
4. Manual demo (full table in `docs/DEMO_CHECKLIST.md`):
   - Slide switch (GPIO34): left = grid present; right = outage. **This is the control to use on camera.**
   - Red **manual outage** button (GPIO14) or the `G` key: a shortcut for a grid loss. **Manual only.** The CI scenario does not use it. CI drops the grid over serial with `GRID0` / `GRID1`.
   - Blue **SIM k** button (GPIO13) or the `K` key: cycles `k` through 1 → 60 → 600.
   - Potentiometer (GPIO35): zone A power, 0–20 W; about 40% ≈ 8 W.
5. The serial monitor prints JSON once a second (`t_ms`, `k`, `mode`, `soc`, relays, and the rest).

### Wokwi CLI / MCP, locally

```bash
cd wokwi
pip install littlefs-python   # only to pack the filesystem
python3 build_firmware.py    # downloads MicroPython and writes firmware.bin
export WOKWI_CLI_TOKEN=wok_...   # https://wokwi.com/dashboard/ci
wokwi-cli . --scenario scenario_accept.yaml --timeout 120000
```

Optional serial commands for CI: `GRID0` / `GRID1` / `GRID`, `K=1` / `K=60` / `K=600`.

### Acceptance criteria (checked in the simulator)

| # | Criterion | Result |
|---|---|---|
| 1 | Grid present: B and C closed, mode `NORMAL` | OK |
| 2 | On outage: ~2 s of real time, then C opens, mode `CORTE` | OK (~2.0 s) |
| 3 | With k=600: ~12 s to `AHORRO` (B opens); ~60 s to `CRITICO` plus the alarm | OK (~12 s / ~62 s) |
| 4 | A never opens (`relay_a` always true) | OK |
| 5 | Grid returns: 5 s, then B closes; +3 s, then C closes; `NORMAL` | OK |

Run log: `evidence/wokwi_accept_serial.log`.

## Declared simplifications

- In the policy demo the battery returns to 100% when the grid returns. The calculator models recharge separately.
- The thermal parameters (`TAU_H` and the temperature limits) are assumptions. They need a vaccine-fridge datasheet, or they must stay declared as a range. The holdover model is a single thermal mass, τ = 4 h, for a box **without an ice lining**. A PQS fridge with an ice lining holds for hours to days and would need less of this help. Stating the short holdover is the conservative claim.

## Scenarios

These are sensitivity sweeps, not a forecast of outages. Inputs are assumptions unless a row in [docs/FUENTES_PENDIENTES.md](docs/FUENTES_PENDIENTES.md) marks them `FUENTE`.

- **S2a.** Improvement against battery size and the share of non-critical load, for a 12 h outage. On the didactic profile (408 rows) the mean is about +51%, from 0% (no non-critical load) to about +373% at the extreme cell.
- **S2b.** Which outages the fridge still covers.
- **S3.** Recharge between outages (one outage a day, charge efficiency 0.85, 156 cells). The honest result: recharge barely depends on ClinicKeep (1 of 156 cells). It depends on outage length and charger size.

The 7.23 h → 12.70 h reading is a separate offline case for a domestic fridge. It is not the demo above, and it is not a vaccine fridge. Prefer the table in this file.

## Files

| File | What it is |
|---|---|
| `config.py` | Parameters. All of them start as assumptions; cite a source or keep them declared |
| `policy.py` | State machine, SIM clock, autonomy, holdover, and safe time |
| `tests/test_policy.py` | 14 tests of the policy |
| `demo.py` | One simulated outage, with and without ClinicKeep |
| `scenarios.py` | S2a / S2b / S3 engine (the same `policy.step`) → CSV |
| `plots.py` | Heatmaps (matplotlib) |
| `tests/test_scenarios.py` | Checks against a closed-form result, and monotonicity |
| `tests/test_sync.py` | `wokwi/policy.py` and `config.py` match the root copies |
| `PROMPT_correcciones.md` | Agent prompt: four corrections from phase 1 |
| `tools/gen_pinout.py` | Generates `docs/PINOUT.md` and `docs/SCHEMA.md` from the diagram |
| `calc/index.html` + `calc/calc.js` | Sizing calculator (plain JS, no build): protected hours with and without ClinicKeep, whether the outage is covered, and whether the charger keeps up. Served at `/calc` |
| `calc/test_calc.mjs` | Compares `calc.js` row by row with the CSVs from `scenarios.py` (Node, no dependencies) |
| `tests/test_calc_js.py` | Hooks that comparison into pytest (skipped without `node`) and watches the assumption labels |
| `tests/test_calc_html.py` | What the page must contain: simulation notice, footer, light/dark theme, keyboard, 360 px, copy, and CSV |
| `tools/publish_calc.py` | Copies `calc/` to `server/static/calc/` and warns if assumptions drift from `scenarios.py` / `config.py` |
| `docs/FUENTES_PENDIENTES.md` | Assumptions that still have no source, and what a citation would require |
| `docs/PINOUT.md` | GPIO pinout (generated; do not edit by hand) |
| `docs/SCHEMA.md` | Circuit in text, plus the Cirkit project link |
| `docs/RELAY_CHECK.md` | Relay polarity and the safe state (measured in the simulator) |
| `docs/DEMO_CHECKLIST.md` | Manual demo: what to move, and what should appear |
| `site/` | Static landing page. `netlify.toml` sets the publish directory to `site`, with no build command |
