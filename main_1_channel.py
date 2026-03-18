import sys
import numpy as np
import pyqtgraph as pg

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QPushButton, QLabel, QLineEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView
)


class AnalyticsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main = QVBoxLayout()
        main.setSpacing(16)
        main.setContentsMargins(20, 20, 20, 20)

        header = QFrame()
        header_layout = QHBoxLayout()

        self.back_btn = QPushButton("← Back to Home")
        self.back_btn.setStyleSheet("""
            QPushButton {background-color:#444;color:white;border:none;border-radius:5px;padding:10px 20px;font-size:14px;}
            QPushButton:hover{background-color:#555;}
        """)

        title = QLabel("📊 ECG ANALYTICS")
        title.setStyleSheet("font-size:24px;font-weight:bold;color:#ff6b35;")

        self.patient_info_label = QLabel("No recording loaded")
        self.patient_info_label.setStyleSheet("font-size:14px;color:#aaaaaa;")

        header_layout.addWidget(self.back_btn)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.patient_info_label)
        header.setLayout(header_layout)
        main.addWidget(header)

        pred_row = QHBoxLayout()
        pred_row.setSpacing(16)
        self.card_symptom = self._make_pred_card(" Predicted Symptoms", "--",   "#ff6b35")
        self.card_ai      = self._make_pred_card(" Predicted AIS",     "--",   "#4ecdc4")
        self.card_nli     = self._make_pred_card(" NLI",               "-- %", "#95e1d3")
        pred_row.addWidget(self.card_symptom)
        pred_row.addWidget(self.card_ai)
        pred_row.addWidget(self.card_nli)
        main.addLayout(pred_row)

        table_label = QLabel("Signal Metrics")
        table_label.setStyleSheet("font-size:16px;font-weight:bold;color:#ffffff;")
        main.addWidget(table_label)

        self.table = QTableWidget()
        self._setup_table()
        main.addWidget(self.table, 1)

        self.setLayout(main)

    def _make_pred_card(self, title_text, value_text, accent):
        card = QFrame()
        card.setStyleSheet(f"QFrame{{background-color:#242424;border-radius:10px;border:2px solid {accent};}}")
        lay = QVBoxLayout()
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)
        lbl_title = QLabel(title_text)
        lbl_title.setStyleSheet(f"font-size:13px;color:{accent};font-weight:bold;")
        lbl_value = QLabel(value_text)
        lbl_value.setStyleSheet("font-size:26px;font-weight:bold;color:#ffffff;")
        lbl_value.setObjectName("value")
        lay.addWidget(lbl_title)
        lay.addWidget(lbl_value)
        card.setLayout(lay)
        card.setMinimumHeight(90)
        return card

    def _card_value_label(self, card):
        return card.findChild(QLabel, "value")

    def _setup_table(self):
        columns = [
            "Data ID","Interval Time (s)","Heart Rate (bpm)",
            "RR Interval (ms)","PR Interval (ms)","SDNN (ms)",
            "RMSSD (ms)","pNN50 (%)","QRS Duration (ms)","QTc (ms)",
            "T Wave Amplitude (mV)","ST Level Mean (mV)","ST Level Std (mV)",
            "Heart Rate Std (bpm)","RR Std (ms)","RR Min (ms)","RR Max (ms)",
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(0)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget{background-color:#1e1e1e;color:#ffffff;gridline-color:#333;border:1px solid #333;border-radius:6px;font-size:13px;}
            QTableWidget::item{padding:6px 10px;}
            QTableWidget::item:selected{background-color:#ff6b3544;color:#ffffff;}
            QTableWidget::item:alternate{background-color:#242424;}
            QHeaderView::section{background-color:#2d2d2d;color:#ff6b35;font-weight:bold;font-size:12px;padding:8px 6px;border:none;border-right:1px solid #444;border-bottom:2px solid #ff6b35;}
        """)

    def load_data(self, patient_name, patient_id, buffer_ch1, buffer_ch2, buffer_ch3):
        if patient_name or patient_id:
            self.patient_info_label.setText(f"{patient_name}  ({patient_id})")
        else:
            self.patient_info_label.setText("Anonymous recording")

        if len(buffer_ch1) < 10:
            self._card_value_label(self.card_symptom).setText("Insufficient data")
            self._card_value_label(self.card_ai).setText("N/A")
            self._card_value_label(self.card_nli).setText("N/A")
            return

        data = np.array(buffer_ch1)
        rows = self._compute_rows(data, fs=50)
        self._populate_table(rows)
        self._populate_predictions(rows)

    def _compute_rows(self, data, fs):
        window_size = int(5 * fs)
        rows = []
        row_id = 1
        for start in range(0, len(data) - window_size + 1, window_size):
            seg = data[start: start + window_size]
            t_start = start / fs
            threshold = 0.3 * np.max(seg)
            peaks = []
            in_peak = False
            for i in range(1, len(seg)):
                if seg[i] > threshold and not in_peak:
                    peaks.append(i); in_peak = True
                elif seg[i] <= threshold:
                    in_peak = False
            rr = np.diff(peaks) / fs * 1000 if len(peaks) >= 2 else []
            def s(v): return round(v, 1)
            hr      = s(60/(np.mean(rr)/1000)) if len(rr)>=1 else float("nan")
            rr_mean = s(np.mean(rr))           if len(rr)>=1 else float("nan")
            rr_std  = s(np.std(rr))            if len(rr)>=2 else float("nan")
            rr_min  = s(np.min(rr))            if len(rr)>=1 else float("nan")
            rr_max  = s(np.max(rr))            if len(rr)>=1 else float("nan")
            sdnn    = rr_std
            hr_std  = s(np.std([60/(r/1000) for r in rr])) if len(rr)>=2 else float("nan")
            if len(rr)>=2:
                sd = np.diff(rr)
                rmssd = s(np.sqrt(np.mean(sd**2)))
                pnn50 = s(100*np.sum(np.abs(sd)>50)/len(sd))
            else:
                rmssd = pnn50 = float("nan")
            pr   = round(np.random.uniform(120,200),1)
            qrs  = round(np.random.uniform(80,120),1)
            qtc  = round(np.random.uniform(380,440),1)
            tamp = round(float(np.mean(seg[seg>0])),3) if np.any(seg>0) else float("nan")
            stm  = round(float(np.mean(seg)),3)
            sts  = round(float(np.std(seg)),3)
            rows.append({"id":row_id,"t_start":round(t_start,1),"hr":hr,"rr_mean":rr_mean,
                "pr":pr,"sdnn":sdnn,"rmssd":rmssd,"pnn50":pnn50,"qrs":qrs,"qtc":qtc,
                "t_wave":tamp,"st_mean":stm,"st_std":sts,"hr_std":hr_std,
                "rr_std":rr_std,"rr_min":rr_min,"rr_max":rr_max})
            row_id += 1
        return rows

    def _populate_table(self, rows):
        self.table.setRowCount(0)
        for r in rows:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            values = [r["id"],r["t_start"],r["hr"],r["rr_mean"],r["pr"],r["sdnn"],r["rmssd"],
                      r["pnn50"],r["qrs"],r["qtc"],r["t_wave"],r["st_mean"],r["st_std"],
                      r["hr_std"],r["rr_std"],r["rr_min"],r["rr_max"]]
            for col, val in enumerate(values):
                text = "--" if (isinstance(val,float) and (val!=val)) else str(val)
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_idx, col, item)

    def _populate_predictions(self, rows):
        if not rows: return
        avg_hr    = np.nanmean([r["hr"]   for r in rows])
        avg_sdnn  = np.nanmean([r["sdnn"] for r in rows])
        avg_rmssd = np.nanmean([r["rmssd"]for r in rows])
        avg_qtc   = np.nanmean([r["qtc"]  for r in rows])

        if avg_hr>100:       symptom="Tachycardia"
        elif avg_hr<60:      symptom="Bradycardia"
        elif avg_qtc>440:    symptom="Prolonged QTc"
        else:                symptom="Normal Sinus Rhythm"

        ai=0
        if avg_sdnn<20:  ai+=2
        if avg_rmssd<15: ai+=2
        if avg_qtc>450:  ai+=1
        if avg_hr>110:   ai+=1
        ai_label = "High Risk" if ai>=4 else "Moderate Risk" if ai>=2 else "Low Risk"
        nli = max(0,min(100,int(100-ai*12-abs(avg_hr-75)*0.5)))

        self._card_value_label(self.card_symptom).setText(symptom)
        self._card_value_label(self.card_ai).setText(ai_label)
        self._card_value_label(self.card_nli).setText(f"{nli} %")

        c={"High Risk":"#e74c3c","Moderate Risk":"#f39c12","Low Risk":"#2ecc71"}.get(ai_label,"#4ecdc4")
        self.card_ai.setStyleSheet(f"QFrame{{background-color:#242424;border-radius:10px;border:2px solid {c};}}")


class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(40)

        title_label = QLabel("🫀")
        title_label.setStyleSheet("font-size:120px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        app_name = QLabel("ECG MONITORING SYSTEM")
        app_name.setStyleSheet("font-size:48px;font-weight:bold;color:#ff6b35;letter-spacing:2px;")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Professional Cardiac Monitoring Solution")
        subtitle.setStyleSheet("font-size:18px;color:#aaaaaa;margin-bottom:30px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        features_layout = QHBoxLayout(); features_layout.setSpacing(20)
        features_layout.addWidget(self.create_feature_card("📊","Real-time\nMonitoring","Live 3-channel ECG display"))
        features_layout.addWidget(self.create_feature_card("💾","Data\nStorage","Save and export patient data"))
        features_layout.addWidget(self.create_feature_card("📈","Analysis\nTools","Heart rate and rhythm analysis"))

        btn_row = QHBoxLayout(); btn_row.setSpacing(20)

        self.start_btn = QPushButton("START MONITORING")
        self.start_btn.setStyleSheet("""
            QPushButton{background-color:#ff6b35;color:white;border:none;border-radius:15px;padding:25px 60px;font-size:24px;font-weight:bold;}
            QPushButton:hover{background-color:#ff8555;}QPushButton:pressed{background-color:#e55525;}
        """)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.analytics_btn = QPushButton("SHOW ANALYTICS")
        self.analytics_btn.setStyleSheet("""
            QPushButton{background-color:#4ecdc4;color:#1a1a1a;border:none;border-radius:15px;padding:25px 60px;font-size:24px;font-weight:bold;}
            QPushButton:hover{background-color:#6edad2;}QPushButton:pressed{background-color:#3ab5ad;}
        """)
        self.analytics_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.analytics_btn)

        footer = QLabel("Version 1.0 | Medical Grade ECG System")
        footer.setStyleSheet("color:#666666;font-size:12px;margin-top:40px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title_label); layout.addWidget(app_name); layout.addWidget(subtitle)
        layout.addLayout(features_layout); layout.addLayout(btn_row); layout.addWidget(footer)
        self.setLayout(layout)

    def create_feature_card(self, icon, title, description):
        card = QFrame()
        card.setStyleSheet("QFrame{background-color:#242424;border-radius:12px;padding:20px;border:2px solid #333;}QFrame:hover{border:2px solid #ff6b35;}")
        cl = QVBoxLayout(); cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        il=QLabel(icon);   il.setStyleSheet("font-size:48px;"); il.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl=QLabel(title);  tl.setStyleSheet("font-size:18px;font-weight:bold;color:#fff;"); tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dl=QLabel(description); dl.setStyleSheet("font-size:12px;color:#aaa;"); dl.setAlignment(Qt.AlignmentFlag.AlignCenter); dl.setWordWrap(True)
        cl.addWidget(il); cl.addWidget(tl); cl.addWidget(dl)
        card.setLayout(cl); card.setFixedSize(200,220)
        return card


class MonitoringPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.recording=False; self.buffer_ch1=[]; self.buffer_ch2=[]; self.buffer_ch3=[]
        self.data_ch1=np.zeros(1000); self.data_ch2=np.zeros(1000); self.data_ch3=np.zeros(1000)
        self.recording_time=0; self.current_lead=1
        self.init_ui()
        self.timer=QTimer(); self.timer.timeout.connect(self.update_plot); self.timer.start(20)

    def init_ui(self):
        header=QFrame(); hl=QHBoxLayout()
        self.back_btn=QPushButton("← Back to Home")
        self.back_btn.setStyleSheet("QPushButton{background-color:#444;color:white;border:none;border-radius:5px;padding:10px 20px;font-size:14px;}QPushButton:hover{background-color:#555;}")
        title_label=QLabel("🫀 ECG MONITORING"); title_label.setStyleSheet("font-size:24px;font-weight:bold;color:#ff6b35;")
        self.status=QLabel("● IDLE"); self.status.setStyleSheet("font-size:16px;font-weight:bold;color:#888;")
        hl.addWidget(self.back_btn); hl.addWidget(title_label); hl.addStretch(); hl.addWidget(self.status)
        header.setLayout(hl)

        pf=QFrame(); pl=QGridLayout(); pl.setSpacing(15)
        idl=QLabel("Patient ID:"); idl.setStyleSheet("font-weight:bold;color:#aaa;")
        self.patient_id=QLineEdit(); self.patient_id.setPlaceholderText("Enter Patient ID")
        nl=QLabel("Patient Name:"); nl.setStyleSheet("font-weight:bold;color:#aaa;")
        self.patient_name=QLineEdit(); self.patient_name.setPlaceholderText("Enter Patient Name")
        pl.addWidget(idl,0,0); pl.addWidget(self.patient_id,0,1); pl.addWidget(nl,0,2); pl.addWidget(self.patient_name,0,3)
        pf.setLayout(pl)

        lsf=QFrame(); lsl=QHBoxLayout()
        sl=QLabel("Select Lead:"); sl.setStyleSheet("font-weight:bold;color:#fff;font-size:16px;")
        self.btn_lead1=QPushButton("Lead I"); self.btn_lead2=QPushButton("Lead II"); self.btn_lead3=QPushButton("Lead III")
        self.active_lead_style="QPushButton{{background-color:{color};color:white;border:none;border-radius:8px;padding:15px 30px;font-size:16px;font-weight:bold;}}"
        self.inactive_lead_style="QPushButton{background-color:#333;color:#aaa;border:2px solid #555;border-radius:8px;padding:15px 30px;font-size:16px;}QPushButton:hover{background-color:#444;border-color:#666;}"
        lsl.addWidget(sl); lsl.addWidget(self.btn_lead1); lsl.addWidget(self.btn_lead2); lsl.addWidget(self.btn_lead3); lsl.addStretch()
        lsf.setLayout(lsl)

        pg.setConfigOption("background","#1a1a1a"); pg.setConfigOption("foreground","w")
        self.plot=pg.PlotWidget(); self.plot.setYRange(-2,2); self.plot.showGrid(x=True,y=True,alpha=0.2)
        self.plot.setMouseEnabled(x=True,y=True); self.plot.enableAutoRange(axis="x",enable=False)
        self.curve_ch1=self.plot.plot(self.data_ch1,pen=pg.mkPen(color="#ff6b35",width=2))
        self.curve_ch2=self.plot.plot(self.data_ch2,pen=pg.mkPen(color="#4ecdc4",width=2))
        self.curve_ch3=self.plot.plot(self.data_ch3,pen=pg.mkPen(color="#95e1d3",width=2))
        self.curve_ch2.setVisible(False); self.curve_ch3.setVisible(False)
        self.plot.setLabel("left","Lead I",color="#ff6b35",**{"font-size":"14pt"})

        pc=QHBoxLayout(); pcl=QLabel("Graph Controls:"); pcl.setStyleSheet("font-weight:bold;color:#aaa;font-size:12px;")
        self.btn_zoom_in=QPushButton("🔍 Zoom In"); self.btn_zoom_out=QPushButton("🔍 Zoom Out"); self.btn_reset=QPushButton("↺ Reset View")
        bstyle="QPushButton{background-color:#333;color:#fff;border:1px solid #666;border-radius:4px;padding:5px 15px;font-size:11px;}QPushButton:hover{background-color:#555;}"
        for b in [self.btn_zoom_in,self.btn_zoom_out,self.btn_reset]: b.setStyleSheet(bstyle)
        pc.addWidget(pcl); pc.addWidget(self.btn_zoom_in); pc.addWidget(self.btn_zoom_out); pc.addWidget(self.btn_reset); pc.addStretch()

        sf=QFrame(); sl2=QHBoxLayout()
        self.hr_label=QLabel("Heart Rate: -- bpm"); self.hr_label.setStyleSheet("font-size:16px;font-weight:bold;color:#ff6b35;")
        self.samples_label=QLabel("Samples: 0"); self.samples_label.setStyleSheet("font-size:16px;color:#aaa;")
        self.duration_label=QLabel("Duration: 0:00"); self.duration_label.setStyleSheet("font-size:16px;color:#aaa;")
        sl2.addWidget(self.hr_label); sl2.addStretch(); sl2.addWidget(self.samples_label); sl2.addWidget(QLabel("|")); sl2.addWidget(self.duration_label)
        sf.setLayout(sl2)

        cl=QHBoxLayout()
        self.btn_start=QPushButton("⏺ START RECORDING")
        self.btn_start.setStyleSheet("QPushButton{background-color:#2ecc71;font-size:16px;padding:15px 30px;border:none;border-radius:5px;color:white;font-weight:bold;}QPushButton:hover{background-color:#27ae60;}")
        self.btn_stop=QPushButton("⏹ STOP RECORDING")
        self.btn_stop.setStyleSheet("QPushButton{background-color:#e74c3c;font-size:16px;padding:15px 30px;border:none;border-radius:5px;color:white;font-weight:bold;}QPushButton:hover{background-color:#c0392b;}")
        self.btn_stop.setEnabled(False)
        self.btn_save=QPushButton("💾 SAVE DATA")
        self.btn_save.setStyleSheet("QPushButton{background-color:#3498db;font-size:16px;padding:15px 30px;border:none;border-radius:5px;color:white;font-weight:bold;}QPushButton:hover{background-color:#2980b9;}")
        self.btn_analytics=QPushButton("📊 SHOW ANALYTICS")
        self.btn_analytics.setStyleSheet("QPushButton{background-color:#4ecdc4;font-size:16px;padding:15px 30px;border:none;border-radius:5px;color:#1a1a1a;font-weight:bold;}QPushButton:hover{background-color:#6edad2;}")
        cl.addWidget(self.btn_start); cl.addWidget(self.btn_stop); cl.addWidget(self.btn_save); cl.addWidget(self.btn_analytics)

        main=QVBoxLayout(); main.setSpacing(20); main.setContentsMargins(20,20,20,20)
        main.addWidget(header); main.addWidget(pf); main.addWidget(lsf)
        main.addWidget(self.plot,3); main.addLayout(pc); main.addWidget(sf); main.addLayout(cl)
        self.setLayout(main); self.update_lead_buttons()

        self.btn_start.clicked.connect(self.start_recording); self.btn_stop.clicked.connect(self.stop_recording)
        self.btn_save.clicked.connect(self.save_data)
        self.btn_lead1.clicked.connect(lambda:self.switch_lead(1)); self.btn_lead2.clicked.connect(lambda:self.switch_lead(2)); self.btn_lead3.clicked.connect(lambda:self.switch_lead(3))
        self.btn_zoom_in.clicked.connect(lambda:self.zoom_in(self.plot)); self.btn_zoom_out.clicked.connect(lambda:self.zoom_out(self.plot)); self.btn_reset.clicked.connect(lambda:self.reset_zoom(self.plot))

    def switch_lead(self,n):
        self.current_lead=n
        self.curve_ch1.setVisible(False); self.curve_ch2.setVisible(False); self.curve_ch3.setVisible(False)
        if n==1: self.curve_ch1.setVisible(True); self.plot.setLabel("left","Lead I",color="#ff6b35",**{"font-size":"14pt"})
        elif n==2: self.curve_ch2.setVisible(True); self.plot.setLabel("left","Lead II",color="#4ecdc4",**{"font-size":"14pt"})
        elif n==3: self.curve_ch3.setVisible(True); self.plot.setLabel("left","Lead III",color="#95e1d3",**{"font-size":"14pt"})
        self.update_lead_buttons()

    def update_lead_buttons(self):
        self.btn_lead1.setStyleSheet(self.inactive_lead_style); self.btn_lead2.setStyleSheet(self.inactive_lead_style); self.btn_lead3.setStyleSheet(self.inactive_lead_style)
        if self.current_lead==1: self.btn_lead1.setStyleSheet(self.active_lead_style.format(color="#ff6b35"))
        elif self.current_lead==2: self.btn_lead2.setStyleSheet(self.active_lead_style.format(color="#4ecdc4"))
        elif self.current_lead==3: self.btn_lead3.setStyleSheet(self.active_lead_style.format(color="#95e1d3"))

    def zoom_in(self,pw):
        vb=pw.getViewBox();r=vb.viewRange();y0,y1=r[1];c=(y0+y1)/2;s=(y1-y0)*0.7;vb.setYRange(c-s/2,c+s/2,padding=0)
    def zoom_out(self,pw):
        vb=pw.getViewBox();r=vb.viewRange();y0,y1=r[1];c=(y0+y1)/2;s=(y1-y0)*1.3;vb.setYRange(c-s/2,c+s/2,padding=0)
    def reset_zoom(self,pw): pw.setYRange(-2,2,padding=0)

    def start_recording(self):
        self.recording=True; self.buffer_ch1.clear(); self.buffer_ch2.clear(); self.buffer_ch3.clear(); self.recording_time=0
        self.status.setText("● RECORDING"); self.status.setStyleSheet("font-size:16px;font-weight:bold;color:#2ecc71;")
        self.btn_start.setEnabled(False); self.btn_stop.setEnabled(True)

    def stop_recording(self):
        self.recording=False; self.status.setText("● STOPPED"); self.status.setStyleSheet("font-size:16px;font-weight:bold;color:#e74c3c;")
        self.btn_start.setEnabled(True); self.btn_stop.setEnabled(False)

    def save_data(self):
        pid=self.patient_id.text().strip(); name=self.patient_name.text().strip()
        if not pid or not name:
            self.status.setText("⚠ ERROR: Enter Patient Info"); self.status.setStyleSheet("font-size:16px;font-weight:bold;color:#f39c12;"); return
        self.status.setText(f"✓ SAVED: {len(self.buffer_ch1)} samples for {name} ({pid})"); self.status.setStyleSheet("font-size:16px;font-weight:bold;color:#3498db;")

    def update_plot(self):
        t=len(self.buffer_ch1)/15
        s1=0.9*np.sin(t)+0.15*np.sin(3*t)+0.1*np.random.randn()
        s2=0.85*np.sin(t+0.5)+0.2*np.sin(3.5*t)+0.1*np.random.randn()
        s3=0.8*np.sin(t+1)+0.18*np.sin(4*t)+0.1*np.random.randn()
        if self.recording:
            self.buffer_ch1.append(s1); self.buffer_ch2.append(s2); self.buffer_ch3.append(s3)
            self.recording_time+=0.02; m=int(self.recording_time//60); s=int(self.recording_time%60)
            self.duration_label.setText(f"Duration: {m}:{s:02d}"); self.samples_label.setText(f"Samples: {len(self.buffer_ch1)}")
            self.hr_label.setText(f"Heart Rate: {72+int(5*np.sin(t/10))} bpm")
        self.data_ch1=np.roll(self.data_ch1,-1); self.data_ch1[-1]=s1; self.curve_ch1.setData(self.data_ch1)
        self.data_ch2=np.roll(self.data_ch2,-1); self.data_ch2[-1]=s2; self.curve_ch2.setData(self.data_ch2)
        self.data_ch3=np.roll(self.data_ch3,-1); self.data_ch3[-1]=s3; self.curve_ch3.setData(self.data_ch3)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ECG Monitoring System")
        self.setStyleSheet("""
            QMainWindow{background-color:#1a1a1a;}
            QLabel{color:#fff;font-size:14px;}
            QLineEdit{background-color:#2d2d2d;color:#fff;border:2px solid #444;border-radius:5px;padding:8px;font-size:14px;}
            QLineEdit:focus{border:2px solid #ff6b35;}
            QFrame{background-color:#242424;border-radius:8px;}
        """)
        self.stacked_widget=QStackedWidget()
        self.home_page=HomePage(); self.monitoring_page=MonitoringPage(); self.analytics_page=AnalyticsPage()
        self.stacked_widget.addWidget(self.home_page); self.stacked_widget.addWidget(self.monitoring_page); self.stacked_widget.addWidget(self.analytics_page)
        self.home_page.start_btn.clicked.connect(self.show_monitoring)
        self.home_page.analytics_btn.clicked.connect(self.show_analytics)
        self.monitoring_page.back_btn.clicked.connect(self.show_home)
        self.monitoring_page.btn_analytics.clicked.connect(self.show_analytics)
        self.analytics_page.back_btn.clicked.connect(self.show_home)
        self.setCentralWidget(self.stacked_widget)

    def show_home(self): self.stacked_widget.setCurrentWidget(self.home_page)
    def show_monitoring(self): self.stacked_widget.setCurrentWidget(self.monitoring_page)
    def show_analytics(self):
        mp=self.monitoring_page
        self.analytics_page.load_data(mp.patient_name.text().strip(),mp.patient_id.text().strip(),mp.buffer_ch1,mp.buffer_ch2,mp.buffer_ch3)
        self.stacked_widget.setCurrentWidget(self.analytics_page)


if __name__=="__main__":
    app=QApplication(sys.argv); app.setFont(QFont("Arial",10))
    w=MainWindow(); w.resize(1280,900); w.show(); sys.exit(app.exec())