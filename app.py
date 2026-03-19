import sys
import subprocess
import time
import numpy as np
import pyqtgraph as pg
import threading
import queue
from time import sleep
import csv
from datetime import datetime
from scipy.signal import butter, iirnotch, sosfilt, sosfilt_zi, lfilter, lfilter_zi

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QPainter, QPen, QColor
from PyQt6.QtWidgets import (
	QApplication, QMainWindow, QWidget, QStackedWidget,
	QPushButton, QLabel, QLineEdit,
	QVBoxLayout, QHBoxLayout, QGridLayout,
	QFileDialog, QFrame, QSpacerItem, QSizePolicy
)

# Try to import spidev (only available on Raspberry Pi)
try:
	import spidev
	SPI_AVAILABLE = True
except ImportError:
	SPI_AVAILABLE = False
	print("WARNING: spidev not available - running in simulation mode")

# Switched to lgpio for Raspberry Pi 5
try:
	import lgpio
	GPIO_AVAILABLE = True
except ImportError:
	GPIO_AVAILABLE = False
	print("WARNING: lgpio not available - DRDY pin won't be used")


class ADS1293:
	"""
	Driver for Texas Instruments ADS1293 ECG Chip
	5-Lead Configuration (TI Datasheet Section 9.2.2):
	- Lead I:  Channel 1 (IN2-IN1) = LA-RA
	- Lead II: Channel 2 (IN3-IN1) = LL-RA
	- Lead V:  Channel 3 (IN5-IN6) = V1-WCT
	- RLD output on IN4
	- Wilson Central Terminal on IN6
	"""

	# ── Operation Mode ───────────────────────────────────────────────────────────
	REG_CONFIG          = 0x00

	# ── Input Channel Selection ──────────────────────────────────────────────────
	REG_FLEX_CH1_CN     = 0x01
	REG_FLEX_CH2_CN     = 0x02
	REG_FLEX_CH3_CN     = 0x03
	REG_FLEX_PACE_CN    = 0x04
	REG_FLEX_VBAT_CN    = 0x05

	# ── Lead-off Detect ──────────────────────────────────────────────────────────
	REG_LOD_CN          = 0x06
	REG_LOD_EN          = 0x07
	REG_LOD_CURRENT     = 0x08
	REG_LOD_AC_CN       = 0x09

	# ── Common-Mode Detection and Right-Leg Drive ────────────────────────────────
	REG_CMDET_EN        = 0x0A
	REG_CMDET_CN        = 0x0B
	REG_RLD_CN          = 0x0C

	# ── Wilson Reference ─────────────────────────────────────────────────────────
	REG_WILSON_EN1      = 0x0D
	REG_WILSON_EN2      = 0x0E
	REG_WILSON_EN3      = 0x0F
	REG_WILSON_CN       = 0x10

	# ── Reference ────────────────────────────────────────────────────────────────
	REG_REF_CN          = 0x11

	# ── Oscillator ───────────────────────────────────────────────────────────────
	REG_OSC_CN          = 0x12

	# ── AFE Control ──────────────────────────────────────────────────────────────
	REG_AFE_RES         = 0x13
	REG_AFE_SHDN_CN     = 0x14
	REG_AFE_FAULT_CN    = 0x15
	REG_AFE_PACE_CN     = 0x17

	# ── Error Status (Read-Only) ─────────────────────────────────────────────────
	REG_ERROR_LOD       = 0x18
	REG_ERROR_STATUS    = 0x19
	REG_ERROR_RANGE1    = 0x1A
	REG_ERROR_RANGE2    = 0x1B
	REG_ERROR_RANGE3    = 0x1C
	REG_ERROR_SYNC      = 0x1D
	REG_ERROR_MISC      = 0x1E

	# ── Digital Registers ────────────────────────────────────────────────────────
	REG_DIGO_STRENGTH   = 0x1F
	REG_R2_RATE         = 0x21
	REG_R3_RATE_CH1     = 0x22
	REG_R3_RATE_CH2     = 0x23
	REG_R3_RATE_CH3     = 0x24
	REG_R1_RATE         = 0x25
	REG_DIS_EFILTER     = 0x26
	REG_DRDYB_SRC       = 0x27
	REG_SYNCB_CN        = 0x28
	REG_MASK_DRDYB      = 0x29
	REG_MASK_ERR        = 0x2A
	REG_ALARM_FILTER    = 0x2E
	REG_CH_CNFG         = 0x2F

	# ── Pace and ECG Data Read Back (Read-Only) ──────────────────────────────────
	REG_DATA_STATUS     = 0x30
	REG_DATA_CH1_ECG_H  = 0x37
	REG_DATA_CH1_ECG_M  = 0x38
	REG_DATA_CH1_ECG_L  = 0x39
	REG_DATA_CH2_ECG_H  = 0x3A
	REG_DATA_CH2_ECG_M  = 0x3B
	REG_DATA_CH2_ECG_L  = 0x3C
	REG_DATA_CH3_ECG_H  = 0x3D
	REG_DATA_CH3_ECG_M  = 0x3E
	REG_DATA_CH3_ECG_L  = 0x3F

	# ── Revision and Loop ────────────────────────────────────────────────────────
	REG_REVID           = 0x40
	REG_DATA_LOOP       = 0x50

	# GPIO pins
	DRDY_GPIO_PIN       = 27
	CHIP_ID             = 0
	RSTB_PIN            = 17

	def __init__(self, bus=0, device=0, sample_rate=853):
		if not SPI_AVAILABLE:
			raise RuntimeError("spidev not available - cannot initialize ADS1293")

		self.spi = spidev.SpiDev()
		self.spi.open(bus, device)
		self.spi.max_speed_hz = 4096000  # 4 MHz
		self.spi.mode = 0b01             # SPI Mode 1 (CPOL=0, CPHA=1)
		self.sample_rate = sample_rate

		# Setup DRDY GPIO pin using lgpio (Pi 5 compatible)
		self.drdy_available = GPIO_AVAILABLE
		if GPIO_AVAILABLE:
			try:
				self.chip_handle = lgpio.gpiochip_open(self.CHIP_ID)
				lgpio.gpio_claim_input(self.chip_handle, self.DRDY_GPIO_PIN, lgpio.SET_PULL_UP)

				# Hardware reset via RSTB
				lgpio.gpio_claim_output(self.chip_handle, self.RSTB_PIN, 1)
				lgpio.gpio_write(self.chip_handle, self.RSTB_PIN, 1)
				sleep(0.1)
				lgpio.gpio_write(self.chip_handle, self.RSTB_PIN, 0)
				sleep(0.1)
				lgpio.gpio_write(self.chip_handle, self.RSTB_PIN, 1)
				sleep(0.5)
			except Exception as e:
				print(f"  ✗ GPIO setup failed: {e}")
				self.drdy_available = False
		else:
			print("  ✗ GPIO not available - will poll DATA_STATUS over SPI")

	def write_register(self, address, value):
		self.spi.xfer2([address & 0x7F, value])
		sleep(0.01)

	def read_register(self, address):
		result = self.spi.xfer2([address | 0x80, 0x00])
		return result[1]

	def read_registers(self, start_address, count):
		cmd = [start_address | 0x80] + [0x00] * count
		result = self.spi.xfer2(cmd)
		return result[1:]

	def initialize(self):
		try:
			# Stop any ongoing conversion
			self.write_register(self.REG_CONFIG, 0x00)
			sleep(0.1)

			# ── 5-Lead ECG Configuration (TI Datasheet Table 14) ─────────────

			# 1. CH1: INP→IN2, INN→IN1 (Lead I: LA-RA)
			self.write_register(self.REG_FLEX_CH1_CN, 0x11)

			# 2. CH2: INP→IN3, INN→IN1 (Lead II: LL-RA)
			self.write_register(self.REG_FLEX_CH2_CN, 0x19)

			# 3. CH3: INP→IN5, INN→IN6 (Lead V: V1-WCT)
			self.write_register(self.REG_FLEX_CH3_CN, 0x2E)

			# 4. Common-mode detection on IN1, IN2, IN3
			self.write_register(self.REG_CMDET_EN, 0x07)

			# 5. RLD output → IN4
			self.write_register(self.REG_RLD_CN, 0x04)

			# 6. Wilson reference: buf1→IN1, buf2→IN2, buf3→IN3
			self.write_register(self.REG_WILSON_EN1, 0x01)
			self.write_register(self.REG_WILSON_EN2, 0x02)
			self.write_register(self.REG_WILSON_EN3, 0x03)

			# 7. Wilson output → IN6 (WCT)
			self.write_register(self.REG_WILSON_CN, 0x01)

			# 8. Internal reference
			self.write_register(self.REG_REF_CN, 0x00)
			self.write_register(self.REG_LOD_CN, 0x01)
			self.write_register(self.REG_LOD_EN, 0x37)
			self.write_register(self.REG_LOD_CURRENT, 0x02)


			# 9. Oscillator: crystal + start clock
			self.write_register(self.REG_OSC_CN, 0x00)
			sleep(0.1)
			self.write_register(self.REG_OSC_CN, 0x04)
			sleep(0.5)

			# 10. AFE standard resolution
			self.write_register(self.REG_AFE_RES, 0x00)

			# 11. All AFE channels active (no shutdown)
			self.write_register(self.REG_AFE_SHDN_CN, 0x00)

			self.write_register(self.REG_AFE_FAULT_CN, 0x07)

			# 12. Decimation rates: R2=5, R3=6 for all channels
			self.write_register(self.REG_R2_RATE, 0x02)
			self.write_register(self.REG_R3_RATE_CH1, 0x02)
			self.write_register(self.REG_R3_RATE_CH2, 0x02)
			self.write_register(self.REG_R3_RATE_CH3, 0x02)

			# 13. Alarm filter
			self.write_register(self.REG_ALARM_FILTER, 0x02)

			# 14. DRDYB source: CH1 ECG
			self.write_register(self.REG_DRDYB_SRC, 0x08)

			# 15. Enable CH1+CH2+CH3 ECG for loop readback
			self.write_register(self.REG_CH_CNFG, 0x70)

			# 16. Start conversion
			self.write_register(self.REG_CONFIG, 0x01)
			sleep(0.1)

			# Verify
			revid = self.read_register(self.REG_REVID)
			print(f"  REVID: 0x{revid:02X}")
			print("✓ ADS1293 5-Lead initialization complete")
			print(f"  Lead I (CH1): IN2-IN1 | Lead II (CH2): IN3-IN1 | Lead V (CH3): IN5-IN6")
			print(f"  RLD: IN4 | WCT: IN6 | {self.sample_rate} SPS")

			return True

		except Exception as e:
			print(f"✗ ADS1293 initialization failed: {e}")
			return False

	def hardware_reset(self):
		try:
			lgpio.gpio_write(self.chip_handle, self.RSTB_PIN, 0)
			sleep(0.2)
			lgpio.gpio_write(self.chip_handle, self.RSTB_PIN, 1)
			self.initialize()
		except Exception as e:
			print(f"Reset Failed: {e}")

	def wait_for_drdy(self, timeout_ms=200):
		if self.drdy_available:
			start = time.time()
			while lgpio.gpio_read(self.chip_handle, self.DRDY_GPIO_PIN) == 1:
				if (time.time() - start) * 1000 > timeout_ms:
					self.hardware_reset()
					return False
			return True
		else:
			start = time.time()
			while True:
				status = self.read_register(self.REG_DATA_STATUS)
				if status & 0x20:
					return True
				if (time.time() - start) * 1000 > timeout_ms:
					return False

	def _raw_to_mv(self, raw_unsigned):
		"""
		Convert unsigned 24-bit ADC code to differential input voltage in mV.

		From datasheet Equation 13:
			ADC_OUT = [3.5 * (Vinp - Vinm) / (2 * Vref) + 0.5] * ADC_MAX

		Solving for V_diff:
			V_diff = (ADC_OUT / ADC_MAX - 0.5) * 2 * Vref / 3.5

		With R2=5, R3=6, SDM @ 102.4kHz, R1=4 (Table 8):
			ADC_MAX = 0xB964F0
		"""
		ADC_MAX = 0xB964F0   # 12,149,488 for R2=5, R3=6
		VREF_MV = 2400.0     # Internal reference in mV
		INA_GAIN = 3.5       # Fixed instrumentation amplifier gain

		if raw_unsigned > ADC_MAX:
			return None  # Saturated / out of range

		return (raw_unsigned / ADC_MAX - 0.5) * 2.0 * VREF_MV / INA_GAIN

	def read_ecg_all_channels(self):
		"""
		Wait for DRDY then burst-read all 3 ECG channels (9 bytes: 0x37-0x3F).
		Returns (ch1_raw, ch2_raw, ch3_raw) as UNSIGNED 24-bit,
		or (None, None, None) on timeout.
		"""
		if not self.wait_for_drdy():
			return None, None, None

		data = self.read_registers(self.REG_DATA_CH1_ECG_H, 9)

		# Keep as unsigned — ADS1293 output is unsigned with midpoint at ADC_MAX/2
		ch1 = (data[0] << 16) | (data[1] << 8) | data[2]
		ch2 = (data[3] << 16) | (data[4] << 8) | data[5]
		ch3 = (data[6] << 16) | (data[7] << 8) | data[8]

		return ch1, ch2, ch3

	def read_ecg_samples(self):
		"""
		Read all 3 ECG channels and convert to millivolts.
		Returns (ch1_mv, ch2_mv, ch3_mv) or (None, None, None).
		"""
		ch1_raw, ch2_raw, ch3_raw = self.read_ecg_all_channels()
		if ch1_raw is None:
			return None, None, None

		results = []
		for raw in (ch1_raw, ch2_raw, ch3_raw):
			mv = self._raw_to_mv(raw)
			if mv is None:
				results.append(0.0)  # Saturated sample → zero
			else:
				results.append(mv)

		return results[0], results[1], results[2]

	def close(self):
		try:
			self.write_register(self.REG_CONFIG, 0x00)
			self.spi.close()
			if self.drdy_available:
				lgpio.gpiochip_close(self.chip_handle)
			print("ADS1293 closed")
		except:
			pass


class ECGAcquisitionThread(threading.Thread):
	"""Background thread for continuous 3-channel ECG data acquisition"""

	def __init__(self, ads1293, data_queues, sample_rate=853):
		super().__init__()
		self.ads1293 = ads1293
		self.data_queues = data_queues  # List of 3 queues [ch1_q, ch2_q, ch3_q]
		self.sample_rate = sample_rate
		self.running = False
		self.daemon = True

		# Create filter chains for each channel
		self.filters = []
		for _ in range(3):
			f = {}
			f['sos_bp'] = butter(4, [0.5, 40.0], btype='bandpass', fs=sample_rate, output='sos')
			f['zi_bp'] = sosfilt_zi(f['sos_bp'])
			f['b_n60'], f['a_n60'] = iirnotch(60.0, Q=30.0, fs=sample_rate)
			f['zi_n60'] = lfilter_zi(f['b_n60'], f['a_n60'])
			f['b_n120'], f['a_n120'] = iirnotch(120.0, Q=30.0, fs=sample_rate)
			f['zi_n120'] = lfilter_zi(f['b_n120'], f['a_n120'])
			self.filters.append(f)

	def _reset_filter(self, ch_idx, dc=0.0):
		"""Reset filter states for a channel."""
		f = self.filters[ch_idx]
		f['zi_bp'] = sosfilt_zi(f['sos_bp']) * dc
		f['zi_n60'] = lfilter_zi(f['b_n60'], f['a_n60']) * dc
		f['zi_n120'] = lfilter_zi(f['b_n120'], f['a_n120']) * dc

	def _apply_filter(self, ch_idx, sample):
		"""Apply bandpass + notch filter chain to a single sample."""
		f = self.filters[ch_idx]
		filtered, f['zi_bp'] = sosfilt(f['sos_bp'], [sample], zi=f['zi_bp'])
		filtered, f['zi_n60'] = lfilter(f['b_n60'], f['a_n60'], filtered, zi=f['zi_n60'])
		filtered, f['zi_n120'] = lfilter(f['b_n120'], f['a_n120'], filtered, zi=f['zi_n120'])
		return filtered[0]

	def run(self):
		self.running = True

		# Wait for first valid samples to initialize filter states
		print("Waiting for first valid sample to initialize filters...")
		first = None
		while first is None and self.running:
			first = self.ads1293.read_ecg_samples()
			if first[0] is None:
				first = None

		if first is not None:
			for i in range(3):
				self._reset_filter(i, first[i])

			# Warmup: run filters for 2 seconds, discard output
			warmup_samples = int(self.sample_rate * 2)
			for _ in range(warmup_samples):
				samples = self.ads1293.read_ecg_samples()
				if samples[0] is not None:
					for i in range(3):
						self._apply_filter(i, samples[i])
			print("Filter warmup complete — 3-channel acquisition running")

		self.error_count = 0
		while self.running:
			try:
				samples = self.ads1293.read_ecg_samples()
				if samples[0] is None:
					continue

				# Every 100 samples clear error registers
				self.error_count += 1
				if self.error_count >= 100:
					self.ads1293.read_register(0x19)  # Clear ERROR_STATUS
					self.ads1293.read_register(0x1A)  # Clear ERROR_RANGE1
					self.ads1293.read_register(0x1B)  # Clear ERROR_RANGE2
					self.ads1293.read_register(0x1C)  # Clear ERROR_RANGE3
					self.ads1293.read_register(self.ads1293.REG_ERROR_LOD)
					self.error_count = 0

				lod_status = self.ads1293.read_register(self.ads1293.REG_ERROR_LOD)

				IN1 = lod_status & 0x01
				IN2 = lod_status & 0x02
				IN3 = lod_status & 0x04
				IN4 = lod_status & 0x08
				IN5 = lod_status & 0x10
				IN6 = lod_status & 0x20	

				for i in range(3):
					if i == 0 and (IN1 or IN2):
						filtered = 0.0
					elif i == 1 and (IN1 or IN3):
						filtered = 0.0
					elif i == 2 and (IN5 or IN6):
						filtered = 0.0
					else:
						filtered = self._apply_filter(i, samples[i])

						# Clamp and reset on artifact
						if abs(filtered) > 2.0:
							filtered = 0.0
							self._reset_filter(i, 0.0) 

					if not self.data_queues[i].full():
						self.data_queues[i].put(filtered)

			except Exception as e:
				print(f"Acquisition error: {e}")
				sleep(0.1)

	def stop(self):
		self.running = False
		print("ECG acquisition thread stopped")


APP_STYLESHEET = """
QMainWindow, QWidget#root {
	background-color: #0d1117;
}
QWidget#homePage {
	background-color: #0d1117;
}
QWidget#ecgPage {
	background-color: #0d1117;
}
QLabel#appTitle {
	color: #00e5a0;
	font-size: 42px;
	font-weight: bold;
	letter-spacing: 3px;
}
QLabel#appSubtitle {
	color: #8b9ab0;
	font-size: 14px;
	letter-spacing: 1px;
}
QLabel#sectionLabel {
	color: #c9d1d9;
	font-size: 12px;
	font-weight: bold;
}
QLabel#statusLabel {
	color: #8b9ab0;
	font-size: 12px;
	padding: 4px 0px;
}
QLabel#modeChip {
	color: #0d1117;
	background-color: #00e5a0;
	border-radius: 8px;
	padding: 3px 10px;
	font-size: 11px;
	font-weight: bold;
}
QLineEdit {
	background-color: #161b22;
	border: 1px solid #30363d;
	border-radius: 6px;
	color: #c9d1d9;
	padding: 8px 12px;
	font-size: 13px;
	selection-background-color: #00e5a0;
	selection-color: #0d1117;
}
QLineEdit:focus {
	border: 1px solid #00e5a0;
}
QLineEdit::placeholder {
	color: #484f58;
}
QPushButton#launchBtn {
	background-color: #00e5a0;
	color: #0d1117;
	border: none;
	border-radius: 8px;
	padding: 14px 40px;
	font-size: 16px;
	font-weight: bold;
	letter-spacing: 1px;
}
QPushButton#launchBtn:hover {
	background-color: #00fdb4;
}
QPushButton#launchBtn:pressed {
	background-color: #00b87c;
}
QPushButton#backBtn {
	background-color: transparent;
	color: #8b9ab0;
	border: 1px solid #30363d;
	border-radius: 6px;
	padding: 6px 16px;
	font-size: 12px;
}
QPushButton#backBtn:hover {
	border-color: #8b9ab0;
	color: #c9d1d9;
}
QPushButton#actionBtn {
	background-color: #161b22;
	color: #c9d1d9;
	border: 1px solid #30363d;
	border-radius: 6px;
	padding: 8px 16px;
	font-size: 13px;
}
QPushButton#actionBtn:hover {
	background-color: #21262d;
	border-color: #8b9ab0;
}
QPushButton#actionBtn:disabled {
	color: #484f58;
	border-color: #21262d;
}
QPushButton#startBtn {
	background-color: #1a4731;
	color: #00e5a0;
	border: 1px solid #00e5a0;
	border-radius: 6px;
	padding: 8px 16px;
	font-size: 13px;
	font-weight: bold;
}
QPushButton#startBtn:hover {
	background-color: #1f5a3d;
}
QPushButton#startBtn:disabled {
	background-color: #161b22;
	color: #484f58;
	border-color: #21262d;
}
QPushButton#stopBtn {
	background-color: #3d1a1a;
	color: #f85149;
	border: 1px solid #f85149;
	border-radius: 6px;
	padding: 8px 16px;
	font-size: 13px;
	font-weight: bold;
}
QPushButton#stopBtn:hover {
	background-color: #5a2020;
}
QPushButton#stopBtn:disabled {
	background-color: #161b22;
	color: #484f58;
	border-color: #21262d;
}
QFrame#divider {
	color: #21262d;
}
"""

ECG_TRACE = [
	0, 0, 0, 0, 0.05, 0.1, 0.05, 0,
	0, -0.1, 0.3, 1.0, -0.3, 0, 0.1, 0.15,
	0.12, 0.1, 0.08, 0.06, 0.04, 0.02, 0,
	0, 0, 0, 0, 0, 0, 0, 0,
]


class EcgTraceWidget(QWidget):
	"""Decorative static ECG trace drawn in the home page header."""

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setFixedHeight(80)

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)
		pen = QPen(QColor("#00e5a0"), 2)
		painter.setPen(pen)

		w, h = self.width(), self.height()
		mid_y = h / 2
		scale_y = h * 0.38
		repeats = (w // (len(ECG_TRACE) * 4)) + 2
		points = ECG_TRACE * repeats
		n = len(points)
		x_step = w / max(n - 1, 1)

		for i in range(n - 1):
			x1 = i * x_step
			y1 = mid_y - points[i] * scale_y
			x2 = (i + 1) * x_step
			y2 = mid_y - points[i + 1] * scale_y
			painter.drawLine(int(x1), int(y1), int(x2), int(y2))


class MainWindow(QMainWindow):
	"""Main GUI window for 3-channel ECG dashboard"""

	LEAD_NAMES = ["Lead I (LA-RA)", "Lead II (LL-RA)", "Lead V (V1-WCT)"]
	LEAD_COLORS = ['#00ff00', '#00ccff', '#ffaa00']  # Green, Cyan, Orange

	def __init__(self, use_hardware=True):
		super().__init__()
		self.setWindowTitle("ECG Monitor")
		self.setObjectName("root")

		self.use_hardware = use_hardware and SPI_AVAILABLE
		self.ads1293 = None
		self.acquisition_thread = None

		self.recording = False
		self.buffers = [[], [], []]  # One buffer per channel
		self.sample_rate = 853
		self.display_seconds = 4
		self.display_samples = self.sample_rate * self.display_seconds
		self.sim_time = 0

		# Data arrays and queues for 3 channels
		self.data = [np.zeros(self.display_samples) for _ in range(3)]
		self.data_queues = [queue.Queue(maxsize=4096) for _ in range(3)]

		if self.use_hardware:
			try:
				self.ads1293 = ADS1293(bus=0, device=0, sample_rate=self.sample_rate)
				if self.ads1293.initialize():
					self.acquisition_thread = ECGAcquisitionThread(
						self.ads1293, self.data_queues, sample_rate=self.sample_rate
					)
					self.acquisition_thread.start()
					print("✓ Hardware mode active — 3 channels")
				else:
					print("✗ Hardware initialization failed - falling back to simulation")
					self.use_hardware = False
					self.ads1293 = None
			except Exception as e:
				print(f"✗ Hardware error: {e} - using simulation mode")
				self.use_hardware = False
				self.ads1293 = None

		self.stack = QStackedWidget()
		self.setCentralWidget(self.stack)

		self.stack.addWidget(self._build_home_page())   # index 0
		self.stack.addWidget(self._build_ecg_page())    # index 1

		self.timer = QTimer()
		self.timer.timeout.connect(self.update_plot)

	# -- Page builders ----------------------------------------------------------

	def _build_home_page(self):
		page = QWidget()
		page.setObjectName("homePage")

		outer = QVBoxLayout(page)
		outer.setContentsMargins(0, 0, 0, 0)
		outer.setSpacing(0)

		# Decorative ECG trace banner
		trace = EcgTraceWidget()
		outer.addWidget(trace)

		# -- Content card -------------------------------------------------------
		card = QWidget()
		card.setObjectName("homePage")
		card_layout = QVBoxLayout(card)
		card_layout.setContentsMargins(60, 40, 60, 50)
		card_layout.setSpacing(0)

		# Title
		title = QLabel("ECG MONITOR")
		title.setObjectName("appTitle")
		title.setAlignment(Qt.AlignmentFlag.AlignCenter)

		subtitle = QLabel("ADS1293 - Real-Time Cardiac Monitoring (3-Lead)")
		subtitle.setObjectName("appSubtitle")
		subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

		mode_text = "Hardware" if self.use_hardware else "Simulation"
		mode_chip = QLabel(f"  {mode_text} Mode  ")
		mode_chip.setObjectName("modeChip")
		mode_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
		mode_chip.setFixedHeight(24)

		mode_row = QHBoxLayout()
		mode_row.addStretch()
		mode_row.addWidget(mode_chip)
		mode_row.addStretch()

		card_layout.addWidget(title)
		card_layout.addSpacing(6)
		card_layout.addWidget(subtitle)
		card_layout.addSpacing(10)
		card_layout.addLayout(mode_row)
		card_layout.addSpacing(40)

		# Patient info form
		pid_label = QLabel("PATIENT ID")
		pid_label.setObjectName("sectionLabel")
		self.home_patient_id = QLineEdit()
		self.home_patient_id.setPlaceholderText("e.g. P-00123")
		self.home_patient_id.setFixedHeight(40)

		name_label = QLabel("PATIENT NAME")
		name_label.setObjectName("sectionLabel")
		self.home_patient_name = QLineEdit()
		self.home_patient_name.setPlaceholderText("First Last")
		self.home_patient_name.setFixedHeight(40)

		form = QVBoxLayout()
		form.setSpacing(10)
		form.addWidget(pid_label)
		form.addWidget(self.home_patient_id)
		form.addSpacing(14)
		form.addWidget(name_label)
		form.addWidget(self.home_patient_name)

		form_wrapper = QHBoxLayout()
		form_wrapper.addStretch(1)
		inner = QVBoxLayout()
		inner.addLayout(form)
		inner.setContentsMargins(0, 0, 0, 0)
		form_frame = QWidget()
		form_frame.setLayout(inner)
		form_frame.setFixedWidth(380)
		form_wrapper.addWidget(form_frame)
		form_wrapper.addStretch(1)

		card_layout.addLayout(form_wrapper)
		card_layout.addSpacing(36)

		# Launch button
		launch_btn = QPushButton("Launch Live ECG")
		launch_btn.setObjectName("launchBtn")
		launch_btn.setFixedHeight(52)
		launch_btn.setFixedWidth(260)
		launch_btn.clicked.connect(self._launch_ecg)

		btn_row = QHBoxLayout()
		btn_row.addStretch()
		btn_row.addWidget(launch_btn)
		btn_row.addStretch()

		card_layout.addLayout(btn_row)
		card_layout.addStretch()

		outer.addWidget(card)

		# Footer
		footer = QLabel("Lead I  |  Lead II  |  Lead V  |  0.5-40 Hz Bandpass  |  853 SPS")
		footer.setObjectName("appSubtitle")
		footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
		footer.setContentsMargins(0, 0, 0, 16)
		outer.addWidget(footer)

		return page

	def _build_ecg_page(self):
		page = QWidget()
		page.setObjectName("ecgPage")

		mode_text = "Hardware Mode" if self.use_hardware else "Simulation Mode"
		self.status = QLabel(f"Status: Idle ({mode_text})")
		self.status.setObjectName("statusLabel")

		self.patient_id = QLineEdit()
		self.patient_id.setPlaceholderText("Patient ID")
		self.patient_id.setFixedHeight(34)

		self.patient_name = QLineEdit()
		self.patient_name.setPlaceholderText("Patient Name")
		self.patient_name.setFixedHeight(34)

		self.btn_start = QPushButton("Start Recording")
		self.btn_start.setObjectName("startBtn")
		self.btn_stop = QPushButton("Stop Recording")
		self.btn_stop.setObjectName("stopBtn")
		self.btn_save = QPushButton("Save ECG Data")
		self.btn_save.setObjectName("actionBtn")
		self.btn_process = QPushButton("Process")
		self.btn_process.setObjectName("actionBtn")
		self.btn_back = QPushButton("< Home")
		self.btn_back.setObjectName("backBtn")
		self.btn_stop.setEnabled(False)

		# Header bar
		pid_lbl = QLabel("PATIENT ID")
		pid_lbl.setObjectName("sectionLabel")
		name_lbl = QLabel("PATIENT NAME")
		name_lbl.setObjectName("sectionLabel")

		header = QHBoxLayout()
		header.setSpacing(16)

		pid_col = QVBoxLayout()
		pid_col.setSpacing(4)
		pid_col.addWidget(pid_lbl)
		pid_col.addWidget(self.patient_id)

		name_col = QVBoxLayout()
		name_col.setSpacing(4)
		name_col.addWidget(name_lbl)
		name_col.addWidget(self.patient_name)

		header.addWidget(self.btn_back)
		header.addSpacing(8)
		header.addLayout(pid_col)
		header.addLayout(name_col)
		header.addStretch()
		header.addWidget(self.status)

		# ECG plots — one per lead
		pg.setConfigOption('background', '#000000')
		pg.setConfigOption('foreground', '#8b9ab0')

		self.time_axis = np.linspace(0, self.display_seconds, self.display_samples)
		self.plots = []
		self.curves = []

		for i in range(3):
			plot = pg.PlotWidget()
			plot.setLabel('left', 'mV', color='#8b9ab0')
			plot.setTitle(self.LEAD_NAMES[i], color='#c9d1d9', size='13pt')
			plot.showGrid(x=True, y=True, alpha=0.15)
			plot.setYRange(-1.0, 1.5)
			plot.setXRange(0, self.display_seconds)
			plot.setMouseEnabled(x=False, y=False)
			plot.getPlotItem().setMenuEnabled(False)
			plot.getPlotItem().getAxis('left').setTextPen('#8b9ab0')
			plot.getPlotItem().getAxis('bottom').setTextPen('#8b9ab0')

			x_axis = plot.getAxis('bottom')
			x_axis.setTickSpacing(major=1.0, minor=0.2)

			if i < 2:
				plot.setLabel('bottom', '')
			else:
				plot.setLabel('bottom', 'Time (s)', color='#8b9ab0')

			curve = plot.plot(
				self.time_axis, self.data[i],
				pen=pg.mkPen(self.LEAD_COLORS[i], width=1.5)
			)
			self.plots.append(plot)
			self.curves.append(curve)

		# Control bar
		controls = QHBoxLayout()
		controls.setSpacing(10)
		controls.addWidget(self.btn_start)
		controls.addWidget(self.btn_stop)
		controls.addStretch()
		controls.addWidget(self.btn_save)
		controls.addWidget(self.btn_process)

		main = QVBoxLayout(page)
		main.setContentsMargins(20, 16, 20, 16)
		main.setSpacing(12)
		main.addLayout(header)
		for plot in self.plots:
			main.addWidget(plot)
		main.addLayout(controls)

		self.btn_start.clicked.connect(self.start_recording)
		self.btn_stop.clicked.connect(self.stop_recording)
		self.btn_save.clicked.connect(self.save_data)
		self.btn_process.clicked.connect(self.process_data)
		self.btn_back.clicked.connect(self._go_home)

		return page

	# -- Navigation -------------------------------------------------------------

	def _launch_ecg(self):
		pid = self.home_patient_id.text().strip()
		name = self.home_patient_name.text().strip()
		self.patient_id.setText(pid)
		self.patient_name.setText(name)
		self.stack.setCurrentIndex(1)
		self.timer.start(20)  # 50 FPS

	def _go_home(self):
		if self.recording:
			self.stop_recording()
		self.timer.stop()
		self.stack.setCurrentIndex(0)

	def start_recording(self):
		self.recording = True
		for buf in self.buffers:
			buf.clear()
		mode = "Hardware" if self.use_hardware else "Simulation"
		self.status.setText(f"Status: Recording... ({mode})")
		self.btn_start.setEnabled(False)
		self.btn_stop.setEnabled(True)
		print("Started recording")

	def stop_recording(self):
		self.recording = False
		total = len(self.buffers[0])
		mode = "Hardware" if self.use_hardware else "Simulation"
		self.status.setText(f"Status: Stopped ({mode}) - {total} samples/ch")
		self.btn_start.setEnabled(True)
		self.btn_stop.setEnabled(False)
		print(f"Stopped recording - captured {total} samples/ch")

	def save_data(self):
		pid = self.patient_id.text().strip()
		name = self.patient_name.text().strip()

		if not pid or not name:
			self.status.setText("Status: Enter Patient ID + Name before saving")
			return

		if len(self.buffers[0]) == 0:
			self.status.setText("Status: No data to save - record first!")
			return

		try:
			timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
			filename = f"ecg_{pid}_{name}_{timestamp}.csv"

			with open(filename, 'w', newline='') as f:
				writer = csv.writer(f)
				writer.writerow([
					"Sample", "LeadI_mV", "LeadII_mV", "LeadV_mV",
					"Patient_ID", "Patient_Name"
				])
				for i in range(len(self.buffers[0])):
					ch1 = self.buffers[0][i] if i < len(self.buffers[0]) else 0.0
					ch2 = self.buffers[1][i] if i < len(self.buffers[1]) else 0.0
					ch3 = self.buffers[2][i] if i < len(self.buffers[2]) else 0.0
					writer.writerow([i, ch1, ch2, ch3, pid, name])

			total = len(self.buffers[0])
			self.status.setText(f"Status: Saved {total} samples to {filename}")
			print(f"Saved {total} samples × 3 channels to {filename}")

		except Exception as e:
			self.status.setText(f"Status: Save failed - {str(e)}")

	def process_data(self):
		filepath, _ = QFileDialog.getOpenFileName(
			self, "Select ECG Data File", "", "CSV Files (*.csv);;All Files (*)"
		)
		if not filepath:
			return

		self.status.setText(f"Status: Processing {filepath}...")
		processing_script = ""  # TODO: set path to ML script

		if not processing_script:
			self.status.setText("Status: Processing script path not configured yet")
			print("WARNING: processing_script path is empty")
			return

		try:
			subprocess.Popen([sys.executable, processing_script, filepath])
			self.status.setText(f"Status: Processing started for {filepath}")
		except Exception as e:
			self.status.setText(f"Status: Processing failed - {str(e)}")
			print(f"Processing error: {e}")

	def update_plot(self):
		if self.use_hardware:
			for i in range(3):
				try:
					while not self.data_queues[i].empty():
						sample = self.data_queues[i].get_nowait()

						if self.recording:
							self.buffers[i].append(sample)

						self.data[i] = np.roll(self.data[i], -1)
						self.data[i][-1] = sample
				except queue.Empty:
					pass
		else:
			# Simulation mode — generate fake 3-channel ECG
			self.sim_time += 1
			for i in range(3):
				amplitude = [0.8, 1.2, 0.6][i]
				phase = [0, 0.1, 0.2][i]
				sample = amplitude * np.sin((self.sim_time + phase) / 15.0) + 0.1 * np.random.randn()

				if self.recording:
					self.buffers[i].append(sample)

				self.data[i] = np.roll(self.data[i], -1)
				self.data[i][-1] = sample

		for i in range(3):
			self.curves[i].setData(self.time_axis, self.data[i])

	def closeEvent(self, event):
		if self.acquisition_thread:
			self.acquisition_thread.stop()
			self.acquisition_thread.join(timeout=2.0)

		if self.ads1293:
			self.ads1293.close()

		event.accept()
		print("Application closed")


def main():
	print("=" * 60)
	print("ECG Dashboard - ADS1293 5-Lead (3 Channel)")
	print("=" * 60)
	print(f"SPI Available: {SPI_AVAILABLE}")
	print(f"GPIO Available: {GPIO_AVAILABLE} (lgpio)")
	print()

	app = QApplication(sys.argv)
	app.setStyleSheet(APP_STYLESHEET)

	window = MainWindow(use_hardware=True)
	window.resize(1000, 900)
	window.show()

	sys.exit(app.exec())


if __name__ == "__main__":
	main()
