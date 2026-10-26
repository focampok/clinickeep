# Sources: what is cited, and what is not

The calculator in `calc/` and the engine in `scenarios.py` measure nothing. Their default values say so on the page. This file lists what would have to be cited before a number can stop being an assumption.

Three fields already have a verified source (table 1). The rest stay declared as assumptions (tables 2 and 3). The three links in table 1 are the only links in `calc/calc.js`. `tests/test_calc_js.py` fails if any other link appears. An invented citation is worse than a missing one.

The formulas do not need a citation. `tests/test_scenarios.py` and `policy.py` check them. What is still open is where the **input numbers** come from.

On the page, the labels are the exact strings `FUENTE`, `SUPUESTO`, and `SUPUESTO — por citar`. The tests match those strings. This English note does not rename them.

---

## 1. Cited

These are no longer guesses about the equipment. A document sits behind them. On the page they carry the label **FUENTE**, with the full URL visible and the caveat beside it.

| Key | Profile | Default | Source | What it says, and what it does not say |
|---|---|---|---|---|
| `a_w` | PQS reference | 35 W | [PQS E003-066](https://extranet.who.int/prequal/sites/default/files/immunization_devices/pdf/e003/E003-066.pdf) | "0.85 kWh/24 h continuous ≈ 35 W; one AC model." That is the mean of the continuous cycle, not an inrush peak. On the **didactic** profile this same field is still an assumption waiting for a citation (8 W) |
| `t_lim_c` | both | 7.5 °C | [PQS E003-RF-021](https://extranet.who.int/prequal/key-resources/documents/pqs-performance-specification-e003rf021-refrigerator-or-combined) | "Vaccines +2 to +8 °C; PQS holdover is measured up to +10 °C; 7.5 °C is our margin." The 7.5 does **not** come from the document. It is the 8 °C edge of the band minus a sensor margin |
| `cortes_mes` | both | 1.3 | [IndexMundi · World Bank, outages per firm](https://www.indexmundi.com/facts/indicators/IC.ELC.OUTG/rankings/central-america) | "Guatemala, 1.3 outages per month, 2017, firms (World Bank Enterprise Surveys); no duration." A country average measured on firms, not a series from the site or from a clinic. It does not enter the hour sweeps |

## 2. No source at all: the calculator chooses these

| Key | Default | What it is | Label | What a citation would require |
|---|---|---|---|---|
| `nominal_wh` | 128 Wh | Nominal capacity of the battery pack | SUPUESTO — por citar | Datasheet of the installed pack. With `dod_pct` = 75% it must yield the 96 Wh usable in `config.py: E_UTIL_WH` (or that value has to change too). On the PQS profile the default is 400 Wh (300 Wh usable) |
| `dod_pct` | 75% | Usable depth of discharge | SUPUESTO — por citar | The maker's cycle-life sheet (cycles against depth of discharge), or the installation rule |
| `ciclos` | 300 cycles | Full cycles the battery is rated for | SUPUESTO — por citar | The battery datasheet (lead-acid is often hundreds; LiFePO4, thousands). The calculation assumes **one cycle per outage**, which is conservative |
| `cargador_w` | 30 W | Charger power | SUPUESTO — por citar | The nameplate of the charger that would be installed |

## 3. Copied from the repo, and still waiting for an external source

These come straight from `scenarios.py` (didactic profile) or `config.py`, where they are already declared as starting assumptions. The `origen` column in `calc.js` names the file they were copied from. They are labeled **SUPUESTO** because of where they come from. There is still no measurement and no manufacturer behind them.

| Key | Default | Origin in the repo | What a citation would require |
|---|---|---|---|
| `a_w` | 8 W | `scenarios.py: A_W` | Measure the mock fridge's average draw (a wattmeter, or the equipment nameplate). Table 1 has the same field for a real PQS fridge |
| `b_w` | 4 W (25 W on the PQS profile) | `scenarios.py: B_W` | Measure the hallway lights. On the PQS profile, 25 W is an assumption to be measured, not a source |
| `c_w` | 3 W (20 W on the PQS profile) | `scenarios.py: C_W` | Measure the waiting room. The 20 W on the PQS profile is an assumption too |
| `d_h` | 12 h | `scenarios.py: PERFILES['didactico'].d_h` | The outage length the site wants to cover: a local history |
| `eta` | 0.85 | `scenarios.py: ETA_CHARGE` | Charge curve from the charger or battery maker |
| `t_amb_c` | 25 °C | `scenarios.py: T_AMB_C` | Temperature where the fridge will sit (a log, ideally) |
| `tau_h` | 4 h | `config.py: TAU_H` | The fridge's time constant: a datasheet, or a temperature-decay test. This is what sets the holdover |
| `t_hi_c` | 5.0 °C | `config.py: T_HI_C` | The fridge setpoint (the top of the control band) |

## 4. What this is not

- It is not a forecast of outages. There is no measured series and no site history.
- The 7.5 °C in `t_lim_c` is **this project's** margin under the 2–8 °C band. The document in table 1 gives the band, not the margin.
- The holdover in this mock is for a box **without an ice lining**. The calculator and the dashboard say so. A PQS fridge with an ice lining holds for hours to days and would need less help. The model therefore understates that fridge's autonomy, which is the conservative direction.
- Battery life (`vida_anios`) assumes one full cycle per outage. Short outages make real life longer than the figure. Long outages and a small battery bring the figure closer to reality.
- The thermal model is a single lumped mass (one `tau`), not a thermal model of a real cabinet.

## 5. How the tests keep this true

`tests/test_calc_js.py` (skipped when `node` is missing) checks that:

1. every field in `DEFAULTS` has a label, and the label is one of the known ones (`SUPUESTO`, `SUPUESTO — por citar`, `FUENTE`);
2. every `FUENTE` label has a link, and the links are **only** the three in `URLS_PERMITIDAS`, each one listed;
3. `calc.js` contains no other loose URL, not in notes and not in origins;
4. the profiles in `calc.js` match `scenarios.py: PERFILES`;
5. the fields marked "por citar" appear in this file, and **every** field appears in this file, so none is left unreviewed;
6. `origen`, when it is not `null`, points at a file that actually exists in the repo.
