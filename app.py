import os
import sys
import shutil
import subprocess
import time
import numpy as np
import pandas as pd
import pyqtgraph as pg
import threading
import queue
from time import sleep
import csv
from scipy.signal import butter, iirnotch, sosfilt, sosfilt_zi, lfilter, lfilter_zi
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QPainter, QPen, QColor, QIntValidator
from PyQt6.QtWidgets import (
	QApplication, QMainWindow, QWidget, QStackedWidget,
	QPushButton, QLabel, QLineEdit,
	QVBoxLayout, QHBoxLayout, QGridLayout,
	QFileDialog, QFrame, QSpacerItem, QSizePolicy,
	QDialog, QDialogButtonBox, QComboBox, QMessageBox,
	QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea
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
		self.ch3_settle_counter =0
		self.ch3_settling = False
		

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
		CH3_SETTLE_SAMPLES = 2000

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
					elif i == 2:
						if IN5 or IN6:
							filtered = 0.0
							self.ch3_settling = True
							self.ch3_settle_counter = 0
						elif self.ch3_settling:
							# LOD cleared — run filter but discard output
							self._apply_filter(i, samples[i])
							filtered = 0.0
							self.ch3_settle_counter += 1
							if self.ch3_settle_counter >= CH3_SETTLE_SAMPLES:
								self.ch3_settling = False
								print("CH3 settled")
						else:
							filtered = self._apply_filter(i, samples[i])
					else:
						filtered = self._apply_filter(i, samples[i])

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
	font-size: 26px;
	font-weight: bold;
	letter-spacing: 3px;
}
QLabel#appSubtitle {
	color: #8b9ab0;
	font-size: 11px;
	letter-spacing: 1px;
}
QLabel#sectionLabel {
	color: #c9d1d9;
	font-size: 10px;
	font-weight: bold;
}
QLabel#statusLabel {
	color: #8b9ab0;
	font-size: 10px;
	padding: 2px 0px;
}
QLabel#modeChip {
	color: #0d1117;
	background-color: #00e5a0;
	border-radius: 6px;
	padding: 2px 8px;
	font-size: 10px;
	font-weight: bold;
}
QLineEdit {
	background-color: #161b22;
	border: 1px solid #30363d;
	border-radius: 5px;
	color: #c9d1d9;
	padding: 4px 8px;
	font-size: 11px;
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
	border-radius: 7px;
	padding: 8px 24px;
	font-size: 14px;
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
	border-radius: 5px;
	padding: 4px 10px;
	font-size: 11px;
}
QPushButton#backBtn:hover {
	border-color: #8b9ab0;
	color: #c9d1d9;
}
QPushButton#actionBtn {
	background-color: #161b22;
	color: #c9d1d9;
	border: 1px solid #30363d;
	border-radius: 5px;
	padding: 5px 10px;
	font-size: 11px;
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
	border-radius: 5px;
	padding: 5px 10px;
	font-size: 11px;
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
	border-radius: 5px;
	padding: 5px 10px;
	font-size: 11px;
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
QPushButton#channelBtn {
	background-color: #1a2332;
	color: #00e5a0;
	border: 1px solid #00e5a0;
	border-radius: 5px;
	padding: 4px 8px;
	font-size: 11px;
	font-weight: bold;
	min-width: 44px;
}
QPushButton#channelBtn:hover {
	background-color: #1f3040;
}
QPushButton#exitBtn {
	background-color: #3d1a1a;
	color: #f85149;
	border: 1px solid #f85149;
	border-radius: 7px;
	padding: 8px 24px;
	font-size: 14px;
	font-weight: bold;
	letter-spacing: 1px;
}
QPushButton#exitBtn:hover {
	background-color: #5a2020;
}
QPushButton#exitBtn:pressed {
	background-color: #7a2828;
}
QFrame#divider {
	color: #21262d;
}
QWidget#loadingPage {
	background-color: #0d1117;
}
QLabel#loadingStatus {
	color: #8b9ab0;
	font-size: 15px;
	letter-spacing: 2px;
}
QWidget#resultsPage {
	background-color: #0d1117;
}
QLabel#summaryCard {
	background-color: #161b22;
	color: #c9d1d9;
	border: 1px solid #30363d;
	border-radius: 8px;
	padding: 10px 16px;
	font-size: 11px;
}
QLabel#summaryCardAIS {
	background-color: #1a4731;
	color: #00e5a0;
	border: 1px solid #00e5a0;
	border-radius: 8px;
	padding: 10px 16px;
	font-size: 13px;
	font-weight: bold;
}
QFrame#metricCard {
	background-color: #161b22;
	border: 1px solid #30363d;
	border-radius: 8px;
}
QLabel#metricCardName {
	color: #8b9ab0;
	font-size: 10px;
	letter-spacing: 1px;
}
QLabel#metricCardValue {
	color: #c9d1d9;
	font-size: 18px;
	font-weight: bold;
}
QScrollArea {
	background-color: transparent;
	border: none;
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
		self.setFixedHeight(40)

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


class ProcessParamsDialog(QDialog):
	"""Dialog to collect NLI, age, and gender before running the analysis script."""

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Process ECG")
		self.setMinimumWidth(280)

		layout = QVBoxLayout(self)
		layout.setSpacing(12)
		layout.setContentsMargins(20, 20, 20, 20)

		# NLI
		layout.addWidget(QLabel("NLI"))
		self.nli_input = QLineEdit()
		self.nli_input.setPlaceholderText("Enter NLI value")
		self.nli_input.setFixedHeight(32)
		layout.addWidget(self.nli_input)

		# Age
		layout.addWidget(QLabel("Age"))
		self.age_input = QLineEdit()
		self.age_input.setPlaceholderText("Enter age")
		self.age_input.setValidator(QIntValidator(0, 150, self))
		self.age_input.setFixedHeight(32)
		layout.addWidget(self.age_input)

		# Gender
		layout.addWidget(QLabel("Gender"))
		self.gender_input = QComboBox()
		self.gender_input.addItems(["F", "M"])
		self.gender_input.setFixedHeight(32)
		layout.addWidget(self.gender_input)

		# Buttons
		buttons = QDialogButtonBox(
			QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
		)
		buttons.accepted.connect(self._on_accept)
		buttons.rejected.connect(self.reject)
		layout.addWidget(buttons)

	def _on_accept(self):
		if not self.nli_input.text().strip():
			self.nli_input.setFocus()
			return
		if not self.age_input.text().strip():
			self.age_input.setFocus()
			return
		self.accept()

	def values(self):
		return (
			self.nli_input.text().strip(),
			int(self.age_input.text().strip()),
			self.gender_input.currentText(),
		)

class SettingsDialog(QDialog):
	def __init__(self, current_max_duration=60, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Settings")
		self.setModal(True)
		self.resize(320, 140)

		layout = QVBoxLayout(self)

		label = QLabel("Processing duration (seconds):")
		label.setStyleSheet("font-size: 14px;")
		layout.addWidget(label)

		self.max_duration_input = QLineEdit(str(current_max_duration))
		self.max_duration_input.setPlaceholderText("Enter Signal Processing Duration In Seconds")
		self.max_duration_input.setValidator(QIntValidator(1, 3600, self))
		self.max_duration_input.setFixedHeight(32)
		layout.addWidget(self.max_duration_input)

		buttons = QDialogButtonBox(
			QDialogButtonBox.StandardButton.Ok |
			QDialogButtonBox.StandardButton.Cancel
		)
		buttons.accepted.connect(self.validate_and_accept)
		buttons.rejected.connect(self.reject)
		layout.addWidget(buttons)

	def validate_and_accept(self):
		if not self.max_duration_input.text().strip():
			self.max_duration_input.setFocus()
			return
		self.accept()

	def value(self):
		return int(self.max_duration_input.text().strip())
class MainWindow(QMainWindow):
	"""Main GUI window for 3-channel ECG dashboard"""

	LEAD_NAMES = ["Lead I (LA-RA)", "Lead II (LL-RA)", "Lead V (V1-WCT)"]
	LEAD_COLORS = ['#00ff00', '#00ccff', '#ffaa00']  # Green, Cyan, Orange

	def __init__(self, use_hardware=True):
		super().__init__()
		self.setWindowTitle("ECG Monitor")
		self.setObjectName("root")
		self.max_duration = 60
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
		self.active_channel = -1  # -1 = all, 0/1/2 = single channel

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

		self.stack.addWidget(self._build_home_page())     # index 0
		self.stack.addWidget(self._build_ecg_page())      # index 1
		self.stack.addWidget(self._build_loading_page())  # index 2
		self.stack.addWidget(self._build_results_page())  # index 3

		self.timer = QTimer()
		self.timer.timeout.connect(self.update_plot)

		self._analysis_process = None
		self._loading_dot_count = 0
		self._loading_anim_timer = QTimer()
		self._loading_anim_timer.timeout.connect(self._update_loading_dots)
		self._poll_timer = QTimer()
		self._poll_timer.timeout.connect(self._check_processing_done)

	def get_ecg_duration_seconds(self, filepath):
		try:
			with open(filepath, "r", newline="") as f:
				reader = csv.reader(f)
				rows = list(reader)

			if len(rows) <= 1:
				return 0.0

			# Try to use the last value in the time column
			try:
				last_time = float(rows[-1][0])
				return last_time
			except (ValueError, IndexError):
				# Fallback: estimate from number of samples
				sample_count = len(rows) - 1  # exclude header
				return sample_count / self.sample_rate

		except Exception as e:
			print(f"Duration check error: {e}")
			return 0.0
	# -- Page builders ----------------------------------------------------------
	def open_settings(self):
		dialog = SettingsDialog(self.max_duration, self)
		if dialog.exec():
			self.max_duration = dialog.value()
			self.status.setText(f"Processing duration set to {self.max_duration} s")
			QMessageBox.information(
				self,
				"Settings Updated",
				f"Processing duration is now set to {self.max_duration} seconds."
			)
	def _build_home_page(self):
		page = QWidget()
		page.setObjectName("homePage")

		outer = QVBoxLayout(page)
		outer.setContentsMargins(0, 0, 0, 0)
		outer.setSpacing(0)

		# -- Content card -------------------------------------------------------
		card = QWidget()
		card.setObjectName("homePage")
		card_layout = QVBoxLayout(card)
		card_layout.setContentsMargins(40, 16, 40, 16)
		card_layout.setSpacing(0)

		# Title
		title = QLabel("ECG MONITOR")
		title.setObjectName("appTitle")
		title.setAlignment(Qt.AlignmentFlag.AlignCenter)

		card_layout.addWidget(title)
		card_layout.addSpacing(24)

		def _home_btn(label, slot):
			btn = QPushButton(label)
			btn.setObjectName("launchBtn")
			btn.setFixedHeight(40)
			btn.setFixedWidth(200)
			btn.clicked.connect(slot)
			row = QHBoxLayout()
			row.addStretch()
			row.addWidget(btn)
			row.addStretch()
			return row

		card_layout.addLayout(_home_btn("Launch Live ECG",   self._launch_ecg))
		card_layout.addSpacing(10)
		card_layout.addLayout(_home_btn("Process ECG File",  self.process_data))
		card_layout.addSpacing(10)
		card_layout.addLayout(_home_btn("Settings",          self.open_settings))
		card_layout.addSpacing(10)

		exit_btn = QPushButton("Exit")
		exit_btn.setObjectName("exitBtn")
		exit_btn.setFixedHeight(40)
		exit_btn.setFixedWidth(200)
		exit_btn.clicked.connect(QApplication.instance().quit)
		exit_row = QHBoxLayout()
		exit_row.addStretch()
		exit_row.addWidget(exit_btn)
		exit_row.addStretch()
		card_layout.addLayout(exit_row)
		card_layout.addStretch()

		outer.addWidget(card)

		return page

	def _build_ecg_page(self):
		page = QWidget()
		page.setObjectName("ecgPage")

		mode_text = "Hardware Mode" if self.use_hardware else "Simulation Mode"
		self.status = QLabel(f"Idle ({mode_text})")
		self.status.setObjectName("statusLabel")

		self.btn_start = QPushButton("Start")
		self.btn_start.setObjectName("startBtn")
		self.btn_stop = QPushButton("Stop")
		self.btn_stop.setObjectName("stopBtn")
		self.btn_save = QPushButton("Save")
		self.btn_save.setObjectName("actionBtn")
		self.btn_back = QPushButton("< Home")
		self.btn_back.setObjectName("backBtn")
		self.btn_stop.setEnabled(False)

		# Channel toggle button
		self.btn_channel = QPushButton("All")
		self.btn_channel.setObjectName("channelBtn")
		self.btn_channel.setFixedHeight(28)
		self.btn_channel.setFixedWidth(44)
		self.btn_channel.setToolTip("Toggle displayed channel")

		# ECG plots — one per lead
		pg.setConfigOption('background', '#000000')
		pg.setConfigOption('foreground', '#8b9ab0')

		self.time_axis = np.linspace(0, self.display_seconds, self.display_samples)
		self.plots = []
		self.curves = []

		for i in range(3):
			plot = pg.PlotWidget()
			plot.setLabel('left', 'mV', color='#8b9ab0')
			plot.setTitle(self.LEAD_NAMES[i], color='#c9d1d9', size='10pt')
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

		# Bottom control bar
		controls = QHBoxLayout()
		controls.setSpacing(8)
		controls.addWidget(self.btn_start)
		controls.addWidget(self.btn_stop)
		controls.addStretch()
		controls.addWidget(self.btn_save)
		controls.addWidget(self.btn_channel)
		controls.addWidget(self.btn_back)

		main = QVBoxLayout(page)
		self.ecg_main_layout = main
		main.setContentsMargins(10, 8, 10, 8)
		main.setSpacing(6)
		for plot in self.plots:
			main.addWidget(plot, stretch=1)
		main.addLayout(controls)

		self.btn_start.clicked.connect(self.start_recording)
		self.btn_stop.clicked.connect(self.stop_recording)
		self.btn_save.clicked.connect(self.save_data)
		self.btn_back.clicked.connect(self._go_home)
		self.btn_channel.clicked.connect(self._toggle_channel)

		return page

	def _build_loading_page(self):
		page = QWidget()
		page.setObjectName("loadingPage")

		outer = QVBoxLayout(page)
		outer.setContentsMargins(0, 0, 0, 0)
		outer.setSpacing(0)

		trace = EcgTraceWidget()
		outer.addWidget(trace)

		center = QWidget()
		center_layout = QVBoxLayout(center)
		center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
		center_layout.setSpacing(20)

		title = QLabel("Analyzing ECG Data")
		title.setObjectName("appTitle")
		title.setAlignment(Qt.AlignmentFlag.AlignCenter)
		center_layout.addWidget(title)

		self.loading_label = QLabel("Processing")
		self.loading_label.setObjectName("loadingStatus")
		self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		center_layout.addWidget(self.loading_label)

		outer.addStretch()
		outer.addWidget(center)
		outer.addStretch()
		return page

	def _build_results_page(self):
		page = QWidget()
		page.setObjectName("resultsPage")

		layout = QVBoxLayout(page)
		layout.setContentsMargins(16, 12, 16, 12)
		layout.setSpacing(12)

		# Header
		header = QHBoxLayout()
		btn_back_results = QPushButton("< Back")
		btn_back_results.setObjectName("backBtn")
		btn_back_results.setFixedHeight(28)
		btn_back_results.clicked.connect(lambda: self.stack.setCurrentIndex(0))
		title_lbl = QLabel("Analysis Results")
		title_lbl.setObjectName("appTitle")
		title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
		header.addWidget(btn_back_results)
		header.addStretch()
		header.addWidget(title_lbl)
		header.addStretch()
		layout.addLayout(header)

		# Summary cards
		cards_row = QHBoxLayout()
		cards_row.setSpacing(12)

		self.card_nli = QLabel("NLI\n—")
		self.card_nli.setObjectName("summaryCard")
		self.card_nli.setAlignment(Qt.AlignmentFlag.AlignCenter)

		self.card_ais = QLabel("Predicted AIS\n—")
		self.card_ais.setObjectName("summaryCardAIS")
		self.card_ais.setAlignment(Qt.AlignmentFlag.AlignCenter)

		self.card_symptoms = QLabel("Predicted Symptoms\n—")
		self.card_symptoms.setObjectName("summaryCard")
		self.card_symptoms.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.card_symptoms.setWordWrap(True)

		cards_row.addWidget(self.card_nli, 1)
		cards_row.addWidget(self.card_ais, 1)
		cards_row.addWidget(self.card_symptoms, 3)
		layout.addLayout(cards_row)

		# Divider
		divider = QFrame()
		divider.setFrameShape(QFrame.Shape.HLine)
		divider.setObjectName("divider")
		layout.addWidget(divider)

		# Scrollable metric cards area
		scroll = QScrollArea()
		scroll.setWidgetResizable(True)
		scroll.setFrameShape(QFrame.Shape.NoFrame)

		self.cards_container = QWidget()
		self.cards_container.setObjectName("resultsPage")
		self.cards_grid = QGridLayout(self.cards_container)
		self.cards_grid.setSpacing(10)
		self.cards_grid.setContentsMargins(4, 4, 4, 4)

		scroll.setWidget(self.cards_container)
		layout.addWidget(scroll, stretch=1)

		return page

	# -- Navigation -------------------------------------------------------------

	def _toggle_channel(self):
		"""Cycle through: All → Lead I → Lead II → Lead V → All"""
		channel_labels = ["I", "II", "V"]
		self.active_channel = self.active_channel + 1 if self.active_channel < 2 else -1
		if self.active_channel == -1:
			self.btn_channel.setText("All")
			for plot in self.plots:
				plot.setVisible(True)
				self.ecg_main_layout.setStretchFactor(plot, 1)
		else:
			self.btn_channel.setText(channel_labels[self.active_channel])
			for i, plot in enumerate(self.plots):
				plot.setVisible(i == self.active_channel)

	def _launch_ecg(self):
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
		self.status.setText(f"Recording... ({mode})")
		self.btn_start.setEnabled(False)
		self.btn_stop.setEnabled(True)
		print("Started recording")

	def stop_recording(self):
		self.recording = False
		total = len(self.buffers[0])
		mode = "Hardware" if self.use_hardware else "Simulation"
		self.status.setText(f"Stopped ({mode}) - {total} samples/ch")
		self.btn_start.setEnabled(True)
		self.btn_stop.setEnabled(False)
		print(f"Stopped recording - captured {total} samples/ch")

	def save_data(self):
		if len(self.buffers[0]) == 0:
			self.status.setText("No data to save - record first!")
			return

		filepath, _ = QFileDialog.getSaveFileName(
			self, "Save ECG Data", "recording.csv", "CSV Files (*.csv);;All Files (*)"
		)
		if not filepath:
			return

		try:
			with open(filepath, 'w', newline='') as f:
				writer = csv.writer(f)
				writer.writerow(["time (s)", "ecg (V)"])
				for i, sample in enumerate(self.buffers[0]):
					writer.writerow([round(i / self.sample_rate, 6), round(sample / 1000.0, 9)])

			total = len(self.buffers[0])
			filename = filepath.split('/')[-1]
			self.status.setText(f"Saved {total} samples to {filename}")
			print(f"Saved {total} samples (CH1) to {filepath}")

		except Exception as e:
			self.status.setText(f"Save failed - {str(e)}")

	def process_data(self):
		filepath, _ = QFileDialog.getOpenFileName(
			self, "Select ECG Data File", "", "CSV Files (*.csv);;All Files (*)"
		)
		if not filepath:
			return

		duration = self.get_ecg_duration_seconds(filepath)

		if duration < self.max_duration:
			self.status.setText(
				f"Error: ECG duration ({duration:.2f}s) is less than required {self.max_duration}s"
			)
			QMessageBox.warning(
				self,
				"Invalid ECG Duration",
				f"The selected ECG file is only {duration:.2f} seconds long.\n"
				f"It must be at least {self.max_duration} seconds."
			)
			return

		dialog = ProcessParamsDialog(self)
		if dialog.exec() != QDialog.DialogCode.Accepted:
			return

		nli, age, gender = dialog.values()

		# Clear stale cache before each run
		if os.path.exists("cache"):
			shutil.rmtree("cache")
			print("Cleared cache folder")

		try:
			self._analysis_process = subprocess.Popen([
				sys.executable, "Analysis.py",
				"--csv", os.path.basename(filepath),
				"--nli", nli,
				"--age", str(age),
				"--gender", gender,
				"--max_duration", str(self.max_duration),
			])
			print(f"Processing: {filepath} | NLI={nli} age={age} gender={gender} max_duration={self.max_duration}")
			# Show loading page and start polling
			self._loading_dot_count = 0
			self.loading_label.setText("Processing")
			self.stack.setCurrentIndex(2)
			self._loading_anim_timer.start(400)
			self._poll_timer.start(500)
		except Exception as e:
			self.status.setText(f"Processing failed - {str(e)}")
			print(f"Processing error: {e}")

	def _update_loading_dots(self):
		self._loading_dot_count = (self._loading_dot_count + 1) % 4
		self.loading_label.setText("Processing" + " ." * self._loading_dot_count)

	def _check_processing_done(self):
		if self._analysis_process is None or self._analysis_process.poll() is not None:
			self._poll_timer.stop()
			self._loading_anim_timer.stop()
			returncode = self._analysis_process.returncode if self._analysis_process else -1
			if returncode == 0:
				self._load_results()
				self.stack.setCurrentIndex(3)
			else:
				self.stack.setCurrentIndex(0)
				self.status.setText(f"Processing failed (exit code {returncode})")

	def _load_results(self):
		try:
			metrics = pd.read_csv(os.path.join("cache", "sci_ecg_metrics.csv"))
		except Exception:
			metrics = pd.DataFrame()

		try:
			preds = pd.read_csv(os.path.join("cache", "sci_condition_predictions.csv"))[["Data ID", "Predicted Labels"]]
		except Exception:
			preds = pd.DataFrame(columns=["Data ID", "Predicted Labels"])

		ais_label, nli_val = "Not Applicable", "—"
		try:
			ais_df = pd.read_csv(os.path.join("cache", "ais_prediction.csv"))
			if not ais_df.empty:
				ais_label = str(ais_df["Predicted AIS"].iloc[0])
				nli_val   = str(ais_df["NLI"].iloc[0])
		except Exception:
			pass

		# Update summary cards
		self.card_nli.setText(f"NLI\n{nli_val}")
		self.card_ais.setText(f"Predicted AIS\n{ais_label}")

		if not preds.empty:
			all_syms = ";".join(preds["Predicted Labels"].fillna("").tolist())
			unique = list(dict.fromkeys(s.strip() for s in all_syms.split(";") if s.strip()))
			self.card_symptoms.setText("Predicted Symptoms\n" + ("\n".join(unique) if unique else "None detected"))
		else:
			self.card_symptoms.setText("Predicted Symptoms\n—")

		# Average metrics across intervals
		if not metrics.empty:
			numeric_cols = metrics.select_dtypes(include=[np.number]).columns.tolist()
			avg = metrics[numeric_cols].mean()
		else:
			avg = pd.Series(dtype=float)

		# Clear previous cards
		while self.cards_grid.count():
			item = self.cards_grid.takeAt(0)
			if item.widget():
				item.widget().deleteLater()

		# Metric groups: (group_title, [(column_name, display_label), ...])
		GROUPS = [
			("Heart Rate & Rhythm", [
				("Heart Rate (bpm)",     "Heart Rate"),
				("Heart Rate Std (bpm)", "HR Std"),
			]),
			("RR Intervals", [
				("RR Interval (ms)", "RR Mean"),
				("RR Std (ms)",      "RR Std"),
				("RR Min (ms)",      "RR Min"),
				("RR Max (ms)",      "RR Max"),
			]),
			("HRV", [
				("SDNN (ms)",   "SDNN"),
				("RMSSD (ms)",  "RMSSD"),
				("pNN50 (%)",   "pNN50"),
			]),
			("Conduction", [
				("PR Interval (ms)", "PR Interval"),
			]),
			("Ventricular", [
				("QRS Duration (ms)", "QRS Duration"),
				("QTc (ms)",          "QTc"),
			]),
			("Repolarization / ST", [
				("T Wave Amplitude (mV)", "T Wave Amp"),
				("ST Level Mean (mV)",    "ST Mean"),
				("ST Level Std (mV)",     "ST Std"),
			]),
		]

		COLS_PER_ROW = 4
		grid_row = 0
		grid_col = 0

		for group_title, metrics_list in GROUPS:
			# Section header spanning full width
			section_lbl = QLabel(group_title.upper())
			section_lbl.setObjectName("sectionLabel")
			section_lbl.setContentsMargins(4, 8, 0, 2)
			if grid_col != 0:
				grid_row += 1
				grid_col = 0
			self.cards_grid.addWidget(section_lbl, grid_row, 0, 1, COLS_PER_ROW)
			grid_row += 1
			grid_col = 0

			for col_name, display_name in metrics_list:
				val = avg.get(col_name, None)
				if val is None or pd.isna(val):
					val_text = "—"
				else:
					val_text = f"{val:.2f}"

				# Extract unit from column name (text inside parentheses)
				unit = ""
				if "(" in col_name:
					unit = col_name[col_name.index("(")+1 : col_name.index(")")]

				card = QFrame()
				card.setObjectName("metricCard")
				card.setMinimumHeight(80)
				card_layout = QVBoxLayout(card)
				card_layout.setContentsMargins(12, 10, 12, 10)
				card_layout.setSpacing(4)

				name_lbl = QLabel(display_name)
				name_lbl.setObjectName("metricCardName")

				val_lbl = QLabel(val_text)
				val_lbl.setObjectName("metricCardValue")

				unit_lbl = QLabel(unit)
				unit_lbl.setObjectName("metricCardName")

				card_layout.addWidget(name_lbl)
				card_layout.addWidget(val_lbl)
				card_layout.addWidget(unit_lbl)
				card_layout.addStretch()

				self.cards_grid.addWidget(card, grid_row, grid_col)
				grid_col += 1
				if grid_col >= COLS_PER_ROW:
					grid_col = 0
					grid_row += 1

			if grid_col != 0:
				grid_row += 1
				grid_col = 0

		# Push cards to top
		self.cards_grid.setRowStretch(grid_row, 1)

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
	window.showFullScreen()

	sys.exit(app.exec())


if __name__ == "__main__":
	main()
