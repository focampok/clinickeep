# ClinicKeep — firmware MicroPython (ESP32 / Wokwi)
# Ejecuta policy.step() cada ~500 ms. Zona A no tiene rele.

from machine import Pin, ADC, I2C, PWM, WDT
from time import ticks_ms, ticks_diff, sleep_ms
import json
import sys
import uselect
import onewire
import ds18x20
import ssd1306
from config import Config
import policy

# --- Pines ---
PIN_GRID = 34
PIN_POT_A = 35
PIN_DS = 4
PIN_RELAY_B = 26
PIN_RELAY_C = 27
PIN_BUZZER = 25
PIN_BTN_K = 13
PIN_BTN_OUTAGE = 14  # pulsador CI/MCP: pulsado = sin red (slide switch sigue en 34)
PIN_SDA = 21
PIN_SCL = 22

P_B_W = 4.0
P_C_W = 3.0
P_A_MAX_W = 20.0
LOOP_MS = 500
JSON_EVERY_MS = 1000
K_CYCLE = (1, 60, 600)
BOOT_GUARD_MS = 2000   # ventana de arranque seguro (reles abiertos; ver al final)

# --- Polaridad de los reles: UNICA fuente de verdad ---
# El atributo `transistor` de wokwi-relay-module invierte la entrada. Medido en el
# simulador (evidencia en docs/RELAY_CHECK.md):
#   "pnp" -> IN BAJO energiza la bobina (contacto COM-NO cerrado = carga CON energia)
#   "npn" -> IN ALTO energiza la bobina
# Debe coincidir con diagram.json: si cambias el transistor, cambia SOLO esta linea.
RELAY_ACTIVE_LEVEL = 0                       # nivel que CIERRA (energiza) el rele
RELAY_OPEN_LEVEL = 1 - RELAY_ACTIVE_LEVEL    # nivel SEGURO: carga sin energia

# 1. Reles ABIERTOS antes de cualquier otra cosa: las cargas no criticas no se
#    energizan hasta que la politica tome su primera decision.
relay_b = Pin(PIN_RELAY_B, Pin.OUT, value=RELAY_OPEN_LEVEL)
relay_c = Pin(PIN_RELAY_C, Pin.OUT, value=RELAY_OPEN_LEVEL)

# 2. Watchdog
wdt = WDT(timeout=8000)

# Entradas / salidas
grid_pin = Pin(PIN_GRID, Pin.IN)
btn_k = Pin(PIN_BTN_K, Pin.IN, Pin.PULL_UP)
btn_outage = Pin(PIN_BTN_OUTAGE, Pin.IN, Pin.PULL_UP)
adc_a = ADC(Pin(PIN_POT_A))
adc_a.atten(ADC.ATTN_11DB)
try:
    adc_a.width(ADC.WIDTH_12BIT)
except AttributeError:
    pass

buzzer = PWM(Pin(PIN_BUZZER), freq=2000, duty=0)

i2c = I2C(0, scl=Pin(PIN_SCL), sda=Pin(PIN_SDA), freq=400000)
oled = None
try:
    oled = ssd1306.SSD1306_I2C(128, 64, i2c)
except Exception as e:
    print("OLED init failed:", e)

ow = onewire.OneWire(Pin(PIN_DS))
ds = ds18x20.DS18X20(ow)
roms = ds.scan()
_ds_converting = False
_ds_t0 = 0
_last_temp = None
_temp_ok = False

cfg = Config()
st = policy.new_state()
k = 1
_btn_prev = 1
_last_json_ms = 0
_t_prev = ticks_ms()
# None = leer interruptor; True/False = override por serie (MCP/CI).
# Comandos (linea): GRID0 | GRID1 | GRID | K=1|60|600
_grid_override = None
_stdin_poll = uselect.poll()
_stdin_poll.register(sys.stdin, uselect.POLLIN)
_cmd_buf = ""

# Arrancar conversion de temperatura
if roms:
    try:
        ds.convert_temp()
        _ds_converting = True
        _ds_t0 = ticks_ms()
    except Exception:
        pass


def read_grid():
    if _grid_override is not None:
        return _grid_override
    # Pulsador CORTE (MCP/CI): activo en bajo = sin red
    if btn_outage.value() == 0:
        return False
    # Interruptor a la izquierda (cerrado a 3V3) = hay red
    return grid_pin.value() == 1


def _apply_cmd(cmd):
    global _grid_override, k
    if not cmd:
        return
    if cmd == "GRID0":
        _grid_override = False
        print('{"cmd":"GRID0"}')
    elif cmd == "GRID1":
        _grid_override = True
        print('{"cmd":"GRID1"}')
    elif cmd == "GRID":
        _grid_override = None
        print('{"cmd":"GRID"}')
    elif cmd in ("K=1", "K=60", "K=600"):
        k = int(cmd.split("=")[1])
        print('{"cmd":"K","k":%d}' % k)


def poll_serial_cmds():
    """Override de red / k por serie (slide switch sin automation control en MCP)."""
    global _cmd_buf
    while _stdin_poll.poll(0):
        ch = sys.stdin.read(1)
        if not ch:
            break
        if ch in ("\n", "\r"):
            _apply_cmd(_cmd_buf.strip().upper())
            _cmd_buf = ""
        elif len(_cmd_buf) < 32:
            _cmd_buf += ch


def read_power_a_w():
    raw = adc_a.read()
    if raw < 0:
        raw = 0
    if raw > 4095:
        raw = 4095
    return (raw / 4095.0) * P_A_MAX_W


def update_temp():
    global _ds_converting, _ds_t0, _last_temp, _temp_ok, roms
    if not roms:
        try:
            roms = ds.scan()
        except Exception:
            roms = []
        if not roms:
            _temp_ok = False
            return
    try:
        if not _ds_converting:
            ds.convert_temp()
            _ds_converting = True
            _ds_t0 = ticks_ms()
        elif ticks_diff(ticks_ms(), _ds_t0) >= 750:
            _last_temp = ds.read_temp(roms[0])
            _temp_ok = True
            _ds_converting = False
    except Exception:
        _temp_ok = False
        _ds_converting = False


def apply_outputs(out):
    relay_b.value(RELAY_ACTIVE_LEVEL if out["relay_b"] else RELAY_OPEN_LEVEL)
    relay_c.value(RELAY_ACTIVE_LEVEL if out["relay_c"] else RELAY_OPEN_LEVEL)
    if out["alarm"]:
        buzzer.duty(512)
    else:
        buzzer.duty(0)


def fmt_h(h):
    if h is None:
        return "n/d"
    if h >= 100:
        return ">99h"
    return "{:.1f}h".format(h)


def draw_oled(out):
    if oled is None:
        return
    oled.fill(0)
    oled.text(out["mode"][:10], 0, 0)
    oled.text("SIM x{}".format(k), 72, 0)
    oled.text("SoC {:.0f}%".format(out["soc"] * 100.0), 0, 12)
    oled.text("B:{} C:{}".format(
        "ON" if out["relay_b"] else "OFF",
        "ON" if out["relay_c"] else "OFF"), 0, 24)
    oled.text("AutA " + fmt_h(out["aut_a_h"]), 0, 36)
    oled.text("Safe " + fmt_h(out["safe_h"]), 0, 48)
    oled.show()


def emit_json(t_ms, out):
    hold = out["holdover_h"]
    line = {
        "t_ms": t_ms,
        "k": k,
        "mode": out["mode"],
        # Red filtrada y alarma: ya los calcula la politica; se emiten tal cual
        # para que el dashboard no tenga que deducirlos del modo.
        "grid_ok": out["grid_ok"],
        "alarm": out["alarm"],
        "soc": round(out["soc"], 4),
        "relay_a": out["relay_a"],
        "relay_b": out["relay_b"],
        "relay_c": out["relay_c"],
        "aut_a_h": None if out["aut_a_h"] is None else round(out["aut_a_h"], 3),
        "aut_total_h": None if out["aut_total_h"] is None else round(out["aut_total_h"], 3),
        "holdover_h": None if hold is None else round(hold, 3),
        "safe_h": None if out["safe_h"] is None else round(out["safe_h"], 3),
        # Sensores: temp_c es None mientras no haya lectura valida del DS18B20.
        "temp_c": None if _last_temp is None else round(_last_temp, 2),
        "temp_ok": _temp_ok,
        "events": out["events"],
    }
    print(json.dumps(line))


def poll_k_button():
    global k, _btn_prev
    v = btn_k.value()
    if _btn_prev == 1 and v == 0:
        # flanco de bajada: ciclar k
        idx = 0
        for i, val in enumerate(K_CYCLE):
            if val == k:
                idx = i
                break
        k = K_CYCLE[(idx + 1) % len(K_CYCLE)]
    _btn_prev = v


# Ventana de arranque seguro: B y C quedan en el nivel ABIERTO hasta la primera
# decision de la politica. Evita energizar cargas no criticas antes de tener
# lecturas validas y permite al CI comprobar el estado seguro con expect-pin.
print('{"boot":"clinickeep","relays":"open"}')
_t_boot = ticks_ms()
while ticks_diff(ticks_ms(), _t_boot) < BOOT_GUARD_MS:
    wdt.feed()
    sleep_ms(50)
print('{"boot_ready":true}')

while True:
    wdt.feed()
    now = ticks_ms()
    dt_ms = ticks_diff(now, _t_prev)
    if dt_ms < 0:
        dt_ms = LOOP_MS
    _t_prev = now
    dt_s = dt_ms / 1000.0
    if dt_s <= 0:
        dt_s = LOOP_MS / 1000.0
    if dt_s > 2.0:
        dt_s = LOOP_MS / 1000.0

    poll_serial_cmds()
    poll_k_button()
    update_temp()

    grid_raw = read_grid()
    p_a = read_power_a_w()
    # potencia total = A + cargas activas de B/C segun estado actual de reles
    p_total = p_a
    if st.b_on:
        p_total += P_B_W
    if st.c_on:
        p_total += P_C_W

    out = policy.step(
        st, cfg, grid_raw, p_total, p_a, dt_s,
        k=k,
        t_amb_c=_last_temp,
        power_ok=True,
        temp_ok=_temp_ok,
    )
    apply_outputs(out)
    draw_oled(out)

    if ticks_diff(now, _last_json_ms) >= JSON_EVERY_MS:
        _last_json_ms = now
        emit_json(now, out)

    # Mantener periodo ~500 ms
    elapsed = ticks_diff(ticks_ms(), now)
    wait = LOOP_MS - elapsed
    if wait > 0:
        sleep_ms(wait)
