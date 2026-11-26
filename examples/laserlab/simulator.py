"""
Simulated Tango devices of the imaginary laser lab, for the example displays.

    python simulator.py [instance]       # default instance: laserlab, TANGO_HOST must be set

All devices run in one device server (LaserLabSim/<instance>). On start, the devices listed in lists/*.json
(keys DEVICE and CLASS) are registered in the Tango database, the same lists the group panels show.

The devices are coupled, so that the displays have something to show:

- a pressure gauge follows the turbo pump of its chamber (pumped, stopped: fore vacuum, vented),
- a valve opens only with vacuum on both sides, and closes when the vacuum is lost (interlock),
- the beam monitors see the beam only while the laser is ON and the shutters in front of them are OPEN,
- the in-vacuum CCD sees XUV only with the probe beam on, both valves open and vacuum in the sample chamber.

Every device has the commands SimulateFault (state FAULT) and Reset, see simulation.ui.
"""

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import tango
from tango import AttrQuality, AttrWriteType, DevState
from tango.server import Device, attribute, command, run

SERVER = "LaserLabSim"
LISTS = Path(__file__).resolve().parent / "lists"
START = time.monotonic()
C_MM_PER_FS = 2.99792458e-4  # speed of light

REGISTRY = {}  # device name -> device, to couple the devices of this process

# Parameters of the devices, by device name
MODEL = {
    # base pressure with the turbo pump at full speed (mbar), quality warning and alarm above
    "laserlab/gauge/hhg": {"pump": "laserlab/turbo/hhg", "base": 2e-4, "warning": 2e-3, "alarm": 2e-2},
    "laserlab/gauge/tm": {"pump": "laserlab/turbo/tm", "base": 3e-7, "warning": 1e-5, "alarm": 1e-3},
    "laserlab/gauge/sample": {"pump": "laserlab/turbo/sample", "base": 8e-8, "warning": 1e-5, "alarm": 1e-3},
    # the gauges on both sides of a valve
    "laserlab/valve/hhg_tm": {"gauges": ("laserlab/gauge/hhg", "laserlab/gauge/tm")},
    "laserlab/valve/tm_sample": {"gauges": ("laserlab/gauge/tm", "laserlab/gauge/sample")},
    # the devices that must let the beam pass (ON, OPEN, RUNNING)
    "laserlab/bpm/probe": {"gates": ("laserlab/laser/1",), "center": (30.0, 34.0)},
    "laserlab/bpm/pump": {"gates": ("laserlab/laser/1", "laserlab/shutter/pump"), "center": (33.0, 31.0)},
    "laserlab/ccd/sample": {
        "gates": ("laserlab/laser/1", "laserlab/shutter/probe", "laserlab/valve/hhg_tm", "laserlab/valve/tm_sample"),
        "gauge": "laserlab/gauge/sample",
    },
    # temperature (degC) and humidity (%) of the lab domains
    "laserlab/env/laser": {"temperature": 21.0, "humidity": 40.0},
    "laserlab/env/beamline": {"temperature": 22.0, "humidity": 36.0},
    "laserlab/env/endstation": {"temperature": 22.5, "humidity": 38.0},
}

PASS_STATES = (DevState.ON, DevState.OPEN, DevState.RUNNING)


def load_devices():
    """All (device, class) of lists/*.json."""
    devices = {}
    for path in sorted(LISTS.glob("*.json")):
        for row in json.loads(path.read_text()):
            devices[row["DEVICE"].lower()] = row["CLASS"]
    return devices


def noise(scale=1.0):
    return random.gauss(0.0, scale)


def elapsed():
    return time.monotonic() - START


def device(name):
    """A device of this process, updated to now, or None."""
    dev = REGISTRY.get(name)
    if dev is not None:
        dev.refresh()
    return dev


def passes(names):
    """True if all named devices let the beam pass."""
    return all((dev := device(name)) is not None and dev.get_state() in PASS_STATES for name in names)


def gauge_pressure(name):
    dev = device(name)
    return None if dev is None else 10**dev.log_pressure


def quality(value, warning=None, alarm=None, low_warning=None):
    if alarm is not None and value > alarm:
        return AttrQuality.ATTR_ALARM
    if (warning is not None and value > warning) or (low_warning is not None and value < low_warning):
        return AttrQuality.ATTR_WARNING
    return AttrQuality.ATTR_VALID


class SimDevice(Device):
    """Common part: time steps, simulated faults, State and Status."""

    def init_device(self):
        super().init_device()
        self.name = self.get_name().lower()
        self.model = MODEL.get(self.name, {})
        self.fault = None
        self._last = time.monotonic()
        self._phase = random.uniform(0, 2 * math.pi)
        self.setup()
        REGISTRY[self.name] = self
        self.refresh(step=False)  # the devices it depends on may not exist yet

    def setup(self):
        """Initial values of the simulation."""

    def step(self, dt):
        """Advance the simulation by dt seconds."""

    def simulated_state(self):
        """(DevState, status) without fault."""
        return DevState.ON, "The device is ON."

    def refresh(self, step=True):
        now = time.monotonic()
        dt, self._last = now - self._last, now
        if step and dt > 0:
            self.step(dt)
        if self.fault:
            state, status = DevState.FAULT, f"Simulated fault: {self.fault}. Use Reset to clear it."
        else:
            state, status = self.simulated_state()
        self.set_state(state)
        self.set_status(status)

    def always_executed_hook(self):
        self.refresh()

    def dev_state(self):
        self.refresh()
        return self.get_state()

    def dev_status(self):
        self.refresh()
        return self.get_status()

    def check_no_fault(self):
        if self.fault:
            raise RuntimeError(f"{self.name} is in FAULT ({self.fault}), Reset first")

    @command(dtype_in=str, doc_in="reason (optional)")
    def SimulateFault(self, reason):
        self.fault = reason or "fault injected from the simulation panel"
        self.refresh()

    @command
    def Reset(self):
        self.fault = None
        self.refresh()


class Laser(SimDevice):
    def setup(self):
        self.emitting = True

    def simulated_state(self):
        if self.emitting:
            return DevState.ON, "The laser is emitting."
        return DevState.OFF, "The laser is off."

    def _on(self):
        return self.emitting and not self.fault

    def _power(self):
        return 5.0 * (1 + 0.004 * math.sin(elapsed() / 30 + self._phase) + noise(0.002)) if self._on() else 0.0

    @attribute(dtype=float, unit="W", format="%.3f", doc="average output power")
    def power(self):
        return self._power()

    @attribute(dtype=float, unit="mJ", format="%.3f")
    def pulse_energy(self):
        return self._power() / 1000.0 * 1e3

    @attribute(dtype=float, unit="nm", format="%.1f")
    def wavelength(self):
        return 800.0 + noise(0.05)

    @attribute(dtype=float, unit="Hz", format="%.0f")
    def repetition_rate(self):
        return 1000.0

    @attribute(dtype=float, unit="fs", format="%.1f")
    def pulse_duration(self):
        return 35.0 + noise(0.3) if self._on() else 0.0

    @command
    def On(self):
        self.check_no_fault()
        self.emitting = True

    @command
    def Off(self):
        self.emitting = False


class ThorlabsMFF(SimDevice):
    """Motorized flip mount used as shutter: position 1 blocks the beam (CLOSE), position 2 lets it pass (OPEN)."""

    def setup(self):
        self._position = 2
        self._target = 2
        self._arrival = 0.0
        self._transit_time = 500
        self.serial = f"37{random.randint(100000, 999999)}"

    def step(self, dt):
        if self._target != self._position and time.monotonic() >= self._arrival:
            self._position = self._target

    def simulated_state(self):
        if self._target != self._position:
            return DevState.MOVING, f"Flipping to position {self._target}."
        if self._position == 2:
            return DevState.OPEN, "Position 2: open, the beam passes."
        return DevState.CLOSE, "Position 1: closed, the beam is blocked."

    def _move(self, position):
        self.check_no_fault()
        if position not in (1, 2):
            raise ValueError("position must be 1 (closed) or 2 (open)")
        if position != self._target:
            self._target = position
            self._arrival = time.monotonic() + self._transit_time / 1000

    @attribute(dtype=int, access=AttrWriteType.READ_WRITE, min_value=1, max_value=2, doc="1: closed, 2: open")
    def position(self):
        return self._position

    @position.write
    def position(self, value):
        self._move(int(value))

    @attribute(dtype=int, unit="ms", access=AttrWriteType.READ_WRITE, min_value=300, max_value=2800)
    def transit_time(self):
        return self._transit_time

    @transit_time.write
    def transit_time(self, value):
        self._transit_time = int(value)

    @attribute(dtype=str)
    def serial_number(self):
        return self.serial

    @command
    def Open(self):
        self._move(2)

    @command
    def Close(self):
        self._move(1)


class VacuumValve(SimDevice):
    TRANSIT = 2.0  # s

    def setup(self):
        self._open = True
        self._target = True
        self._arrival = 0.0
        self._cycles = random.randint(200, 3000)
        self._closed_by_interlock = False

    def pressures(self):
        return [gauge_pressure(name) for name in self.model.get("gauges", ())]

    def interlock_ok(self):
        """Vacuum (below 1e-2 mbar) on both sides."""
        return all(p is not None and p < 1e-2 for p in self.pressures())

    def step(self, dt):
        if self._target != self._open and time.monotonic() >= self._arrival:
            self._open = self._target
            self._cycles += 1
        if self._target and not self.interlock_ok():
            self._move(False)
            self._closed_by_interlock = True

    def simulated_state(self):
        if self._target != self._open:
            return DevState.MOVING, "Opening." if self._target else "Closing."
        if self._open:
            return DevState.OPEN, "The valve is open."
        if self._closed_by_interlock:
            return DevState.CLOSE, "Closed by the interlock: no vacuum on one side."
        return DevState.CLOSE, "The valve is closed."

    def _move(self, target):
        if target != self._target:
            self._target = target
            self._arrival = time.monotonic() + self.TRANSIT

    @attribute(dtype=bool, doc="opening allowed: vacuum on both sides")
    def interlock(self):
        return self.interlock_ok()

    @attribute(dtype=int, doc="number of open/close cycles")
    def cycles(self):
        return self._cycles

    @attribute(dtype=float, unit="mbar", format="%.2e")
    def upstream_pressure(self):
        return self.pressures()[0]

    @attribute(dtype=float, unit="mbar", format="%.2e")
    def downstream_pressure(self):
        return self.pressures()[1]

    @command
    def Open(self):
        self.check_no_fault()
        if not self.interlock_ok():
            raise RuntimeError("Interlock: no vacuum on one side of the valve")
        self._closed_by_interlock = False
        self._move(True)

    @command
    def Close(self):
        self._closed_by_interlock = False
        self._move(False)


class TurboPump(SimDevice):
    RATED = 1000.0  # Hz
    RAMP_UP, RAMP_DOWN = 40.0, 90.0  # s from 0 to rated speed and back

    def setup(self):
        self._running = True
        self._speed = self.RATED
        self._accelerating = False
        self._temperature = 38.0
        self.vented = False

    def step(self, dt):
        target = self.RATED if self._running and not self.fault else 0.0
        self._accelerating = self._speed < target
        if self._speed < target:
            self._speed = min(target, self._speed + self.RATED / self.RAMP_UP * dt)
        elif self._speed > target:
            self._speed = max(target, self._speed - self.RATED / self.RAMP_DOWN * dt)
        heat = 25.0 + 13.0 * self.speed_fraction() + (6.0 if self._accelerating else 0.0)
        self._temperature += (heat - self._temperature) * (1 - math.exp(-dt / 60.0))

    def speed_fraction(self):
        return self._speed / self.RATED

    def simulated_state(self):
        if self._running:
            if self._speed >= 0.99 * self.RATED:
                return DevState.ON, "The pump runs at rated speed."
            return DevState.MOVING, f"Accelerating, {self.speed_fraction():.0%} of rated speed."
        if self._speed > 1.0:
            return DevState.MOVING, f"Decelerating, {self.speed_fraction():.0%} of rated speed."
        return DevState.OFF, "The pump is off, vented." if self.vented else "The pump is off."

    @attribute(dtype=float, unit="Hz", format="%.0f")
    def speed(self):
        return max(0.0, self._speed + noise(0.05)) if self._speed > 0 else 0.0

    @attribute(dtype=float, unit="Hz", format="%.0f")
    def rated_speed(self):
        return self.RATED

    def _current(self):
        if self._speed < 1.0 and not self._running:
            return 0.0
        return (2.4 if self._accelerating else 0.4 + 0.3 * self.speed_fraction()) + noise(0.02)

    @attribute(dtype=float, unit="A", format="%.2f")
    def current(self):
        return self._current()

    @attribute(dtype=float, unit="W", format="%.1f")
    def power(self):
        return 24.0 * self._current()

    @attribute(dtype=float, unit="°C", format="%.1f", max_warning=55.0, max_alarm=65.0)
    def temperature(self):
        return self._temperature + noise(0.05)

    @attribute(dtype=bool, doc="the vent valve of the pump is open")
    def vent_open(self):
        return self.vented

    @command
    def Start(self):
        self.check_no_fault()
        self.vented = False
        self._running = True

    @command
    def Stop(self):
        self._running = False

    @command(doc_in="open the vent valve, once the pump stands still")
    def Vent(self):
        if self._running or self._speed > 0.05 * self.RATED:
            raise RuntimeError("Stop the pump and wait until it stands still before venting")
        self.vented = True


class PressureGauge(SimDevice):
    def setup(self):
        self.log_pressure = math.log10(self.model.get("base", 1e-7))

    def step(self, dt):
        pump = device(self.model.get("pump", ""))
        base = math.log10(self.model.get("base", 1e-7))
        if pump is None:
            target = base
        elif pump.vented:
            target = 3.0  # 1000 mbar
        else:
            fore = math.log10(5e-2)  # turbo pump stopped, backing pump only
            target = fore + (base - fore) * pump.speed_fraction() ** 4
        tau = 8.0 if target < self.log_pressure else 25.0  # s, per decade
        self.log_pressure += (target - self.log_pressure) * (1 - math.exp(-dt / tau))

    @attribute(dtype=float, unit="mbar", format="%.2e")
    def pressure(self):
        value = 10**self.log_pressure * (1 + noise(0.01))
        if self.fault:
            return value, time.time(), AttrQuality.ATTR_INVALID
        return value, time.time(), quality(value, self.model.get("warning"), self.model.get("alarm"))

    @attribute(dtype=str)
    def gauge_type(self):
        return "Pirani / cold cathode"

    @attribute(dtype=float, unit="mbar", format="%.2e", doc="pressure with the turbo pump at full speed")
    def base_pressure(self):
        return self.model.get("base", 1e-7)


class TempHumiditySensor(SimDevice):
    def _temperature(self):
        t0 = self.model.get("temperature", 21.0)
        return t0 + 0.3 * math.sin(elapsed() / 600 + self._phase) + noise(0.01)

    def _humidity(self):
        h0 = self.model.get("humidity", 40.0)
        return h0 + 2.0 * math.sin(elapsed() / 900 + 2 * self._phase) + noise(0.05)

    @attribute(dtype=float, unit="°C", format="%.2f")
    def temperature(self):
        value, t0 = self._temperature(), self.model.get("temperature", 21.0)
        return value, time.time(), quality(value, warning=t0 + 1.0, low_warning=t0 - 1.0)

    @attribute(dtype=float, unit="%", format="%.1f", max_warning=55.0, max_alarm=65.0)
    def humidity(self):
        return self._humidity()

    @attribute(dtype=float, unit="°C", format="%.2f", doc="Magnus formula")
    def dew_point(self):
        t, h = self._temperature(), max(1e-3, self._humidity())
        gamma = math.log(h / 100) + 17.62 * t / (243.12 + t)
        return 243.12 * gamma / (17.62 - gamma)


def gaussian_image(shape, center, sigma, amplitude, background, noise_level):
    y, x = np.indices(shape)
    spot = amplitude * np.exp(
        -((x - center[0]) ** 2) / (2 * sigma[0] ** 2) - (y - center[1]) ** 2 / (2 * sigma[1] ** 2)
    )
    return spot + background + np.random.normal(0.0, noise_level, shape)


class BeamMonitor(SimDevice):
    """Camera based beam position monitor: beam profile, centroid, width and intensity."""

    SIZE = 64

    def setup(self):
        self._exposure = 2.0

    def beam(self):
        return not self.fault and passes(self.model.get("gates", ()))

    def _centroid(self):
        cx, cy = self.model.get("center", (32.0, 32.0))
        t = elapsed()
        return cx + 1.2 * math.sin(t / 45) + noise(0.15), cy + 0.8 * math.cos(t / 70) + noise(0.15)

    def simulated_state(self):
        if self.beam():
            return DevState.ON, "Beam detected."
        return DevState.ON, "No beam on the monitor."

    def _beam_value(self, value):
        if self.beam():
            return value, time.time(), AttrQuality.ATTR_VALID
        return float("nan"), time.time(), AttrQuality.ATTR_INVALID

    @attribute(dtype=((float,),), max_dim_x=SIZE, max_dim_y=SIZE)
    def image(self):
        amplitude = 200.0 * self._exposure if self.beam() else 0.0
        return gaussian_image((self.SIZE, self.SIZE), self._centroid(), (5.0, 4.0), amplitude, 10.0, 3.0)

    @attribute(dtype=float, unit="px", format="%.2f")
    def centroid_x(self):
        return self._beam_value(self._centroid()[0])

    @attribute(dtype=float, unit="px", format="%.2f")
    def centroid_y(self):
        return self._beam_value(self._centroid()[1])

    @attribute(dtype=float, unit="px", format="%.2f")
    def sigma_x(self):
        return self._beam_value(5.0 + noise(0.05))

    @attribute(dtype=float, unit="px", format="%.2f")
    def sigma_y(self):
        return self._beam_value(4.0 + noise(0.05))

    @attribute(dtype=float, unit="counts", format="%.0f")
    def intensity(self):
        return (2 * math.pi * 20.0 * 200.0 * self._exposure if self.beam() else 0.0) * (1 + noise(0.01))

    @attribute(dtype=float, unit="ms", format="%.1f", access=AttrWriteType.READ_WRITE, min_value=0.1, max_value=100)
    def exposure_time(self):
        return self._exposure

    @exposure_time.write
    def exposure_time(self, value):
        self._exposure = float(value)


class Camera(SimDevice):
    """In-vacuum CCD: cooled sensor, acquisition (RUNNING) with an XUV spot if the beam reaches it."""

    SIZE = 128

    def setup(self):
        self._acquiring = True
        self._exposure = 0.5
        self._setpoint = -60.0
        self._sensor = -60.0
        self._frames = 0
        self._next_frame = time.monotonic()

    def step(self, dt):
        rate = 0.5  # K/s
        self._sensor += max(-rate * dt, min(rate * dt, self._setpoint - self._sensor))
        now = time.monotonic()
        if self._acquiring and not self.fault:
            while self._next_frame <= now:
                self._frames += 1
                self._next_frame += max(0.05, self._exposure)
        else:
            self._next_frame = now

    def xuv(self):
        pressure = gauge_pressure(self.model.get("gauge", ""))
        vacuum = pressure is None or pressure < 1e-4  # XUV is absorbed in air
        return self._acquiring and not self.fault and vacuum and passes(self.model.get("gates", ()))

    def simulated_state(self):
        if self._acquiring:
            return DevState.RUNNING, "Acquiring, XUV on the sensor." if self.xuv() else "Acquiring, no XUV."
        return DevState.ON, "Idle."

    @attribute(dtype=((np.uint16,),), max_dim_x=SIZE, max_dim_y=SIZE)
    def image(self):
        amplitude = 3000.0 * self._exposure if self.xuv() else 0.0
        center = (64 + 2 * math.sin(elapsed() / 50), 60 + noise(0.3))
        image = gaussian_image((self.SIZE, self.SIZE), center, (4.0, 9.0), amplitude, 300.0, 8.0)
        return np.clip(image, 0, 65535).astype(np.uint16)

    @attribute(dtype=float, unit="counts", format="%.0f")
    def max_counts(self):
        return 300.0 + (3000.0 * self._exposure if self.xuv() else 0.0) + noise(8.0)

    @attribute(dtype=int)
    def frame_number(self):
        return self._frames

    @attribute(dtype=float, unit="s", format="%.3f", access=AttrWriteType.READ_WRITE, min_value=0.001, max_value=60)
    def exposure_time(self):
        return self._exposure

    @exposure_time.write
    def exposure_time(self, value):
        self._exposure = float(value)

    @attribute(dtype=float, unit="°C", format="%.1f")
    def sensor_temperature(self):
        value = self._sensor + noise(0.02)
        return value, time.time(), quality(value, warning=self._setpoint + 5.0)

    @attribute(dtype=float, unit="°C", format="%.1f", access=AttrWriteType.READ_WRITE, min_value=-80, max_value=20)
    def temperature_setpoint(self):
        return self._setpoint

    @temperature_setpoint.write
    def temperature_setpoint(self, value):
        self._setpoint = float(value)

    @command
    def Start(self):
        self.check_no_fault()
        self._acquiring = True

    @command
    def Stop(self):
        self._acquiring = False


class DelayStage(SimDevice):
    """Linear stage with a retroreflector: the delay is twice the path from the zero position."""

    def setup(self):
        self._position = self._target = 150.0
        self._velocity = 5.0
        self._zero = 150.0

    def step(self, dt):
        distance = self._target - self._position
        travel = self._velocity * dt
        self._position = self._target if abs(distance) <= travel else self._position + math.copysign(travel, distance)

    def simulated_state(self):
        if self._position != self._target:
            return DevState.MOVING, f"Moving to {self._target:.4f} mm."
        return DevState.ON, "In position."

    def _move(self, position):
        self.check_no_fault()
        self._target = min(300.0, max(0.0, float(position)))

    @attribute(dtype=float, unit="mm", format="%.4f", access=AttrWriteType.READ_WRITE, min_value=0, max_value=300)
    def position(self):
        return self._position + noise(5e-5)  # encoder jitter

    @position.write
    def position(self, value):
        self._move(value)

    @attribute(dtype=float, unit="fs", format="%.1f", access=AttrWriteType.READ_WRITE)
    def delay(self):
        return 2 * (self._position - self._zero) / C_MM_PER_FS

    @delay.write
    def delay(self, value):
        self._move(self._zero + float(value) * C_MM_PER_FS / 2)

    @attribute(dtype=float, unit="mm", format="%.4f", access=AttrWriteType.READ_WRITE, min_value=0, max_value=300)
    def zero_position(self):
        return self._zero

    @zero_position.write
    def zero_position(self, value):
        self._zero = float(value)

    @attribute(dtype=float, unit="mm/s", format="%.2f", access=AttrWriteType.READ_WRITE, min_value=0.01, max_value=50)
    def velocity(self):
        return self._velocity

    @velocity.write
    def velocity(self, value):
        self._velocity = float(value)

    @command
    def Stop(self):
        self._target = self._position


CLASSES = [
    Laser,
    ThorlabsMFF,
    VacuumValve,
    TurboPump,
    PressureGauge,
    TempHumiditySensor,
    BeamMonitor,
    Camera,
    DelayStage,
]


def register(instance):
    """Register the devices of lists/*.json in the Tango database."""
    db = tango.Database()
    server = f"{SERVER}/{instance}"
    known = {cls.__name__ for cls in CLASSES}
    for name, cls in load_devices().items():
        if cls not in known:
            raise SystemExit(f"{name}: no simulation for the class {cls}")
        info = tango.DbDevInfo()
        info.name, info._class, info.server = name, cls, server
        db.add_device(info)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("instance", nargs="?", default="laserlab")
    args, tango_args = parser.parse_known_args(argv)
    register(args.instance)
    run(CLASSES, args=[SERVER, args.instance, *tango_args])


if __name__ == "__main__":
    sys.exit(main())
