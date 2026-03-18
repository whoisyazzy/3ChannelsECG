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
	Configuration based on TI datasheet examples for single-lead ECG:
	- Lead I: Channel 1 (IN2-IN1) = LA-RA
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
	REG_DATA_CH1_PACE_H = 0x31
	REG_DATA_CH1_PACE_L = 0x32
	REG_DATA_CH2_PACE_H = 0x33
	REG_DATA_CH2_PACE_L = 0x34
	REG_DATA_CH3_PACE_H = 0x35
	REG_DATA_CH3_PACE_L = 0x36
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

	# DRDY GPIO pin (Pi header pin 13 = GPIO 27)
	DRDY_GPIO_PIN       = 27
	CHIP_ID             = 0 # Standard for Pi 5
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
				#print(f"  ✓ DRDY GPIO pin {self.DRDY_GPIO_PIN} configured (lgpio)")
				# Hardware reset via RSTB
				lgpio.gpio_claim_output(self.chip_handle, self.RSTB_PIN, 1)
				lgpio.gpio_write(self.chip_handle, self.RSTB_PIN, 1)
				sleep(0.1)
				lgpio.gpio_write(self.chip_handle, self.RSTB_PIN, 0)
				sleep(0.1)
				lgpio.gpio_write(self.chip_handle, self.RSTB_PIN, 1)
				sleep(0.5)
				#print("  ✓ Hardware reset via RSTB (GPIO 17)")
			except Exception as e:
				print(f"  ✗ GPIO setup failed: {e} - will poll DATA_STATUS over SPI")
				self.drdy_available = False
		else:
			print("  ✗ GPIO not available - will poll DATA_STATUS over SPI")


		# Debug counter
		#   self.debug_counter = 0
		#   self.debug_interval = 250  # Print every 250 samples (~4x/sec at 1000 SPS)

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
			#print("Initializing ADS1293...")

			# Stop any ongoing conversion
			self.write_register(self.REG_CONFIG, 0x00)
			sleep(0.1)

			# 1. Channel 1: IN2(+) LA, IN1(-) RA
			self.write_register(self.REG_FLEX_CH1_CN, 0x11)
			#print("  ✓ Channel 1: IN2-IN1 (Lead I, LA-RA)")

			# 2. Disable CH2 and CH3
			self.write_register(self.REG_FLEX_CH2_CN, 0x00)
			self.write_register(self.REG_FLEX_CH3_CN, 0x00)
			#print("  ✓ CH2/CH3 disabled")

			# 3. Common-mode detection on IN1 + IN2
			self.write_register(self.REG_CMDET_EN, 0x03)
			#print("  ✓ Common-mode detection on IN1+IN2")

			# 4. RLD output to IN4
			self.write_register(self.REG_RLD_CN, 0x04)
			#print("  ✓ RLD connected to IN4")

			# 5. Wilson terminal disabled (single lead)
			self.write_register(self.REG_WILSON_EN1, 0x00)
			self.write_register(self.REG_WILSON_EN2, 0x00)
			self.write_register(self.REG_WILSON_CN, 0x00)

			# 6. Reference: both internal refs ON
			self.write_register(self.REG_REF_CN, 0x00)
			#print("  ✓ Internal reference enabled")

			# 7. Oscillator: crystal first, then start clock
			self.write_register(self.REG_OSC_CN, 0x00)  # Use crystal, STRTCLK=0
			sleep(0.1)                                  # Wait for crystal to stabilize
			self.write_register(self.REG_OSC_CN, 0x04)  # Assert STRTCLK
			sleep(0.5)
			#print("  ✓ Oscillator: crystal + STRTCLK asserted")

			# 8. AFE high-resolution mode for CH1
			self.write_register(self.REG_AFE_RES, 0x00)  # EN_HIRES_CH1 (changed from 0x00)
			#print("  ✓ AFE high-resolution mode for CH1")

			# 9. Decimation rates → 1000 SPS
			# self.write_register(self.REG_R1_RATE, 0x01)
			self.write_register(self.REG_R2_RATE, 0x02)      # R2 = 8 (changed from 0x02)
			self.write_register(self.REG_R3_RATE_CH1, 0x02)  # R3 = 128
			#print(f"  ✓ Decimation: R2=8, R3=128 → {self.sample_rate} SPS")

			# 10. Power down CH2/CH3 AFE
			self.write_register(self.REG_AFE_SHDN_CN, 0x36)
			#print("  ✓ CH2/CH3 AFE powered down")

			# 11. Alarm filter
			self.write_register(self.REG_ALARM_FILTER, 0x02)

			# 12. DRDYB source: CH1 ECG = 0x08
			self.write_register(self.REG_DRDYB_SRC, 0x08)
			#print("  ✓ DRDYB source: CH1 ECG")

			# 13. CH_CNFG: STS_EN (bit 0) + E1_EN (bit 4) for streaming
			self.write_register(self.REG_CH_CNFG, 0x10)
			#print("  ✓ Loop readback: DATA_STATUS + CH1 ECG")

			# 14. Start conversion
			self.write_register(self.REG_CONFIG, 0x01)
			sleep(0.1)

			# Verify REVID
			revid = self.read_register(self.REG_REVID)
			#print(f"  ✓ REVID: 0x{revid:02X} (expected 0x01)")

			#print("✓ ADS1293 initialization complete!")
			#print(f"  Lead I: CH1 (IN2-IN1, LA-RA) | RLD: IN4 | {self.sample_rate} SPS")
			err_status = self.read_register(self.REG_ERROR_STATUS)
			err_lod = self.read_register(self.REG_ERROR_LOD)
			err_range1 = self.read_register(self.REG_ERROR_RANGE1)
			#print(f" ERROR STATUS: 0x{err_status}")
			#print(f" ERROR_LOD: 0x{err_lod}")
			#print(f" ERROR_RANGE1: 0x{err_range1}")

			configs = [
				(0x01, 0x11, "FLEX_CH1"),
				(0x0A, 0x03, "CMDET_EN"),
				(0x0C, 0x04, "RLD_CN"),
				(0x12, 0x04, "OSC_CN"),
				(0x14, 0x36, "AFE_SHDN"),
				(0x21, 0x02, "R2_RATE"),
				(0x22, 0x02, "R3_RATE_CH1"),
				(0x27, 0x08, "DRDYB_SRC"),
				(0x2F, 0x10, "CH_CNFG"),
				(0x00, 0x01, "CONFIG"),
]
			#for addr, expected, name in configs:
					#val = self.read_register(addr)
					#match = "✓" if val == expected else "✗"
					#print(f"  {match} {name} (0x{addr:02X}): wrote 0x{expected:02X}, read 0x{val:02X}")
			return True

		except Exception as e:
			print(f"✗ ADS1293 initialization failed: {e}")
			return False

	def wait_for_drdy(self, timeout_ms=200):
		"""
		Wait for DRDY pin to go LOW (active low = data ready) using lgpio.
		Falls back to SPI polling if GPIO not available.
		"""
		if self.drdy_available:
			start = time.time()
			# lgpio_read returns 1 when HIGH, 0 when LOW
			while lgpio.gpio_read(self.chip_handle, self.DRDY_GPIO_PIN) == 1:
				if (time.time() - start) * 1000 > timeout_ms:
					print("DRDY GPIO timeout")
					return False
			return True
		else:
			# Fallback: poll DATA_STATUS over SPI
			start = time.time()
			while True:
				status = self.read_register(self.REG_DATA_STATUS)
				if status & 0x20:  # E1_DRDY = bit 5
					return True
				if (time.time() - start) * 1000 > timeout_ms:
					return False

	def read_ecg_ch1(self):
		"""
		Wait for DRDY then direct burst-read of CH1 ECG registers 0x37-0x39.
		(Original implementation maintained)
		"""
		if not self.wait_for_drdy():
			return None

		data = self.read_registers(self.REG_DATA_CH1_ECG_H, 3)
		raw = (data[0] << 16) | (data[1] << 8) | data[2]
		return raw if raw < 0x800000 else raw - 0x1000000

	def read_ecg_sample(self, channel=1):
		"""
		Read one ECG sample and convert to millivolts.
		"""
		try:
			raw_value = self.read_ecg_ch1()
			if raw_value is None:
				return None
				
			if abs(raw_value) > 8000000:
				return 0.0

			voltage_raw = (raw_value / 8388607.0) * 2400.0
			gain_correction = 1.0
			voltage_mv = voltage_raw / gain_correction

			#self.debug_counter += 1
			#if self.debug_counter >= self.debug_interval:
				#self.debug_counter = 0
				#print(f"Raw ADC: {raw_value:8d} | Raw mV: {voltage_raw:8.2f} | Corrected mV: {voltage_mv:6.3f}")

			return voltage_mv

		except Exception as e:
			print(f"Error reading ECG sample: {e}")
			return None

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
	"""Background thread for continuous ECG data acquisition"""

	def __init__(self, ads1293, data_queue, sample_rate=853):
		super().__init__()
		self.ads1293 = ads1293
		self.data_queue = data_queue
		self.sample_rate = sample_rate
		self.running = False
		self.daemon = True

		# Bandpass 0.5-40 Hz
		self.sos_bp = butter(4, [0.5, 40.0], btype='bandpass', fs=sample_rate, output='sos')
		self.zi_bp = sosfilt_zi(self.sos_bp)

		# 60 Hz notch
		self.b_notch60, self.a_notch60 = iirnotch(60.0, Q=30.0, fs=sample_rate)
		self.zi_notch60 = lfilter_zi(self.b_notch60, self.a_notch60)

		# 120 Hz notch
		self.b_notch120, self.a_notch120 = iirnotch(120.0, Q=30.0, fs=sample_rate)
		self.zi_notch120 = lfilter_zi(self.b_notch120, self.a_notch120)

	def run(self):
		self.running = True

		# Initialize filter states at actual DC level to prevent startup transient
		print("Waiting for first valid sample to initialize filters...")
		first_sample = None
		while first_sample is None and self.running:
			first_sample = self.ads1293.read_ecg_sample(channel=1)
		if first_sample is not None:
			self.zi_bp = sosfilt_zi(self.sos_bp) * first_sample
			self.zi_notch60 = lfilter_zi(self.b_notch60, self.a_notch60) * first_sample
			self.zi_notch120 = lfilter_zi(self.b_notch120, self.a_notch120) * first_sample
			
			# Warmup: run filters for 2 seconds, discard output
			warmup_samples = int(self.sample_rate * 2)
			for _ in range(warmup_samples):
				s = self.ads1293.read_ecg_sample(channel=1)
				if s is not None:
					filtered, self.zi_bp = sosfilt(self.sos_bp, [s], zi=self.zi_bp)
					filtered, self.zi_notch60 = lfilter(self.b_notch60, self.a_notch60, filtered, zi=self.zi_notch60)
					filtered, self.zi_notch120 = lfilter(self.b_notch120, self.a_notch120, filtered, zi=self.zi_notch120)



		while self.running:
			try:
				raw_sample = self.ads1293.read_ecg_sample(channel=1)

				if raw_sample is None:
					continue

				# Apply filter chain
				filtered, self.zi_bp = sosfilt(self.sos_bp, [raw_sample], zi=self.zi_bp)
				filtered, self.zi_notch60 = lfilter(self.b_notch60, self.a_notch60, filtered, zi=self.zi_notch60)
				filtered, self.zi_notch120 = lfilter(self.b_notch120, self.a_notch120, filtered, zi=self.zi_notch120)
				sample = filtered[0]

				if not self.data_queue.full():
					if abs(sample) > 5.0:
						sample =0.0
					self.data_queue.put(sample)

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
	"""Main GUI window — home page + ECG dashboard."""

	def __init__(self, use_hardware=True):
		super().__init__()
		self.setWindowTitle("ECG Monitor")
		self.setObjectName("root")

		self.use_hardware = use_hardware and SPI_AVAILABLE
		self.ads1293 = None
		self.acquisition_thread = None

		self.recording = False
		self.buffer = []
		self.sample_rate = 853
		self.display_seconds = 4
		self.display_samples = self.sample_rate * self.display_seconds
		self.data = np.zeros(self.display_samples)
		self.data_queue = queue.Queue(maxsize=4096)
		self.sim_time = 0

		if self.use_hardware:
			try:
				self.ads1293 = ADS1293(bus=0, device=0, sample_rate=self.sample_rate)
				if self.ads1293.initialize():
					self.acquisition_thread = ECGAcquisitionThread(
						self.ads1293, self.data_queue, sample_rate=self.sample_rate
					)
					self.acquisition_thread.start()
					print("✓ Hardware mode active")
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

		subtitle = QLabel("ADS1293 - Real-Time Cardiac Monitoring")
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
		footer = QLabel("Lead I  |  0.5-40 Hz Bandpass  |  853 SPS")
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
		self.btn_save = QPushButton("Save ECG")
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

		# ECG plot
		pg.setConfigOption('background', '#0d1117')
		pg.setConfigOption('foreground', '#8b9ab0')

		self.plot = pg.PlotWidget()
		self.plot.setLabel('left', 'mV', color='#8b9ab0')
		self.plot.setLabel('bottom', 'Time (s)', color='#8b9ab0')
		self.plot.setTitle("Lead I - ADS1293", color='#c9d1d9', size='13pt')
		self.plot.showGrid(x=True, y=True, alpha=0.15)
		self.plot.getPlotItem().getAxis('left').setTextPen('#8b9ab0')
		self.plot.getPlotItem().getAxis('bottom').setTextPen('#8b9ab0')

		self.time_axis = np.linspace(0, self.display_seconds, self.display_samples)
		self.curve = self.plot.plot(
			self.time_axis, self.data,
			pen=pg.mkPen(color='#00e5a0', width=1.5)
		)

		self.plot.setYRange(-0.7, 2.0)
		self.plot.setXRange(0, self.display_seconds)
		self.plot.getAxis('bottom').setTickSpacing(major=1.0, minor=0.2)

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
		main.addWidget(self.plot)
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
		self.timer.start(20)

	def _go_home(self):
		if self.recording:
			self.stop_recording()
		self.timer.stop()
		self.stack.setCurrentIndex(0)

	def start_recording(self):
		self.recording = True
		self.buffer.clear()
		mode = "Hardware" if self.use_hardware else "Simulation"
		self.status.setText(f"Status: Recording... ({mode})")
		self.btn_start.setEnabled(False)
		self.btn_stop.setEnabled(True)
		print("Started recording")

	def stop_recording(self):
		self.recording = False
		mode = "Hardware" if self.use_hardware else "Simulation"
		self.status.setText(f"Status: Stopped ({mode}) - {len(self.buffer)} samples")
		self.btn_start.setEnabled(True)
		self.btn_stop.setEnabled(False)
		print(f"Stopped recording - captured {len(self.buffer)} samples")

	def save_data(self):
		pid = self.patient_id.text().strip()
		name = self.patient_name.text().strip()

		if not pid or not name:
			self.status.setText("Status: Enter Patient ID + Name before saving")
			return

		if len(self.buffer) == 0:
			self.status.setText("Status: No data to save - record first!")
			return

		try:
			timestamp = datetime.now().strftime("%Y%m%d_%")
			filename = f"ecg_{pid}_{name}_{timestamp}.csv"

			with open(filename, 'w', newline='') as f:
				writer = csv.writer(f)
				writer.writerow(["time (s)", "ecg (V)"])
				for i, sample in enumerate(self.buffer):
					writer.writerow([i / self.sample_rate, sample/1000])

			self.status.setText(f"Status: Saved {len(self.buffer)} samples to {filename}")
			print(f"Saved {len(self.buffer)} samples to {filename}")

		except Exception as e:
			self.status.setText(f"Status: Save failed - {str(e)}")
			print(f"Save error: {e}")

	def process_data(self):
		filepath, _ = QFileDialog.getOpenFileName(
			self, "Select ECG Data File", "", "CSV Files (*.csv);;All Files (*)"
		)
		if not filepath:
			return

		self.status.setText(f"Status: Processing {filepath}...")
		print(f"Selected file for processing: {filepath}")

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
			try:
				while not self.data_queue.empty():
					sample = self.data_queue.get_nowait()

					if self.recording:
						self.buffer.append(sample)

					self.data = np.roll(self.data, -1)
					self.data[-1] = sample
			except queue.Empty:
				pass
		else:
			self.sim_time += 1
			sample = 0.8 * np.sin(self.sim_time / 15.0) + 0.2 * np.random.randn()

			if self.recording:
				self.buffer.append(sample)

			self.data = np.roll(self.data, -1)
			self.data[-1] = sample

		self.curve.setData(self.time_axis, self.data)

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
	print("ECG Monitor - ADS1293 on Raspberry Pi 5")
	print("=" * 60)
	print(f"SPI Available: {SPI_AVAILABLE}")
	print(f"GPIO Available: {GPIO_AVAILABLE} (lgpio)")
	print()

	app = QApplication(sys.argv)
	app.setStyleSheet(APP_STYLESHEET)

	window = MainWindow(use_hardware=True)
	window.resize(1000, 720)
	window.show()

	sys.exit(app.exec())


if __name__ == "__main__":
	main()
