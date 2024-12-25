
import datetime as dt
import os
import sys
import time

import pandas as pd
import pyqtgraph as pg
import sensirion_fastedf as fastedf
import serial.tools.list_ports
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, \
    QComboBox, QLineEdit, QSplitter, QFrame, QHBoxLayout, QTextEdit, QDoubleSpinBox
from sensirion_shdlc_driver import ShdlcSerialPort, ShdlcConnection
from sensirion_shdlc_sensorbridge import SensorBridgePort, SensorBridgeShdlcDevice


class SensorApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # 设置窗口标题
        self.setWindowTitle("Sensor Voltage Monitor")

        # 创建一个中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 使用 QSplitter 将控件和绘图区分开
        splitter = QSplitter()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(splitter)

        # 创建控件容器
        control_container = QWidget()
        control_layout = QVBoxLayout(control_container)  # 减小控件之间的间距

        # 创建一个 PlotWidget
        self.plot_widget = pg.PlotWidget(axisItems={'bottom': pg.DateAxisItem()})
        self.plot_widget.setLabel('left', 'Voltage')

        self.plot_widget.setYRange(0, 6)  # 设置 Y 轴范围为 0 到 6

        # 第一组控件
        group1_layout = QVBoxLayout()
        self.serial_port_label = QLabel("Select Serial Port:")
        group1_layout.addWidget(self.serial_port_label)
        self.serial_port_combo = QComboBox()
        self.update_serial_ports()
        group1_layout.addWidget(self.serial_port_combo)

        self.power_label = QLabel("Select Power Supply:")
        group1_layout.addWidget(self.power_label)
        self.power_combo = QComboBox()
        self.power_combo.addItems(["3.3V", "5V"])
        group1_layout.addWidget(self.power_combo)

        self.port_label = QLabel("Select Sensor Bridge Port:")
        group1_layout.addWidget(self.port_label)
        self.port_combo = QComboBox()
        self.port_combo.addItems(['ONE','TWO'])
        group1_layout.addWidget(self.port_combo)

        control_layout.addLayout(group1_layout)

        group5_layout = QVBoxLayout()
        self.sampling_rate_label = QLabel("Sampling Frequency (Hz):")
        group5_layout.addWidget(self.sampling_rate_label)
        self.sampling_rate_spinbox = QDoubleSpinBox()
        self.sampling_rate_spinbox.setRange(0.01, 1000)  # 设置范围从1到1000 Hz
        self.sampling_rate_spinbox.setSingleStep(0.01)
        self.sampling_rate_spinbox.setValue(1)  # 默认值为1 Hz
        self.sampling_rate_spinbox.valueChanged.connect(self.update_sampling_rate)
        group5_layout.addWidget(self.sampling_rate_spinbox)

        control_layout.addLayout(group5_layout)




        # 第二组控件
        group2_layout = QVBoxLayout()
        self.formula_label = QLabel("Enter Formula (use x for voltage):")
        group2_layout.addWidget(self.formula_label)
        self.formula_input = QLineEdit()
        self.formula_input.setText("x")
        group2_layout.addWidget(self.formula_input)

        self.custom_header_label = QLabel("Enter Custom Header:")
        group2_layout.addWidget(self.custom_header_label)
        self.custom_header_input = QTextEdit()
        self.custom_header_input.setFixedHeight(100)
        self.custom_header_input.setText("{'name':'NWU','SensorName':'Sen66','SensorId':'123'}")
        group2_layout.addWidget(self.custom_header_input)

        # 添加分割线
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        line2.setStyleSheet("border: 50px solid #FFFFFF; background-color: #FFFFFF;")  # 加粗50倍，颜色与背景相同
        control_layout.addLayout(group2_layout)
        control_layout.addWidget(line2)

        # 第三组控件
        group3_layout = QHBoxLayout()  # 使用 QHBoxLayout 将按钮放在同一行
        self.open_port_button = QPushButton("Open Port")
        self.open_port_button.clicked.connect(self.toggle_connection)
        group3_layout.addWidget(self.open_port_button)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.toggle_data_collection)
        group3_layout.addWidget(self.start_button)



        control_layout.addLayout(group3_layout)

        control_layout.addStretch()

        # 将控件容器和绘图区添加到 QSplitter
        splitter.addWidget(control_container)
        splitter.addWidget(self.plot_widget)

        # 初始化数据
        self.x_data = []
        self.y_data = []

        # 初始化定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)

        # 连接设备
        self.device = None
        self.shdlc_port = None
        self.select_port = None
        self.file_name = None

        # 初始化 TextItem
        self.voltage_text_item = pg.TextItem(color='g')
        self.result_text_item = pg.TextItem(color='g')

        # 固定 TextItem 的位置
        self.plot_widget.addItem(self.voltage_text_item)
        self.plot_widget.addItem(self.result_text_item)
        self.voltage_text_item.setPos(0.5, 5.5)  # 上方中部
        self.result_text_item.setPos(0.5, 5.0)  # 上方中部

    def timeToEpochUTC(inputTimeStr, ):
        # Convert string to datetime object
        inputTime = dt.datetime.strptime(inputTimeStr, '%Y-%m-%dT%H:%M:%S')
        # Add timezone to datetime object
        inputTime = inputTime.replace(tzinfo=pytz.timezone('Europe/Zurich'))
        # Return seconds since 1970
        return (inputTime - dt.datetime(1970, 1, 1, 0, 0, 0, 0, pytz.timezone('UTC'))).total_seconds()

    def update_serial_ports(self):
        # 获取系统中所有可用的串口
        ports = serial.tools.list_ports.comports()
        self.serial_port_combo.clear()
        for port in ports:
            self.serial_port_combo.addItem(port.device)

    def create_edf_file(self):
        column_metadata = {'Epoch_UTC': {'Format': '.2f', 'Type': 'float64', 'Unit': 's'},
                           'voltage': {'Format': '.1f', 'Type': 'float', 'Unit': 'V'},
                           'calcuted_value': {'Format': '.1f', 'Type': 'float', 'Unit': 'U'}}

        header = {'appinfo': 'desigen by NWU'}
        header.update(eval(self.custom_header_input.toPlainText()))
        # 检查文件是否存在
        current_time = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        sensorId = header.get('SensorId') if 'SensorId' in header else ''
        sensorName=header.get('SensorName') if 'SensorName' in header else ''
        if not(sensorId =='' and sensorName != ''):
            self.file_name = current_time+'_'+sensorName+'_'+sensorId+'.edf'
        else:
            self.file_name = f"{current_time}.edf"
        df = pd.DataFrame(columns=['Epoch_UTC', 'voltage', 'calcuted_value'])
        if not(os.path.exists(self.file_name)):
            fastedf.to_edf(df, self.file_name, header=header, column_metadata=column_metadata)

    def connect_device(self):
        if self.device is None or self.shdlc_port is None:
            try:
                baudrate = 460800
                port = self.serial_port_combo.currentText()
                self.shdlc_port = ShdlcSerialPort(port=port, baudrate=baudrate)
                self.device = SensorBridgeShdlcDevice(ShdlcConnection(self.shdlc_port), slave_address=0)
                power_voltage = float(self.power_combo.currentText().replace("V", ""))
                if self.port_combo.currentText() == "ONE":
                    self.select_port = SensorBridgePort.ONE
                elif self.port_combo.currentText() == "TWO":
                    self.select_port = SensorBridgePort.TWO
                else:
                    raise ValueError("Invalid port selection.")

                self.device.set_supply_voltage(self.select_port, voltage=power_voltage)
                print("Device connected successfully.")
            except Exception as e:
                print(f"Failed to connect to device: {e}")
        else:
            print("Device already connected.")

    def update_sampling_rate(self):
        sampling_rate = self.sampling_rate_spinbox.value()
        if sampling_rate > 0:
            interval = int(1000 / sampling_rate)  # 将 Hz 转换为毫秒
            self.timer.setInterval(interval)
    def toggle_data_collection(self):
        if self.timer.isActive():
            self.timer.stop()
            self.start_button.setText("Start")

            # self.disconnect_device()
        else:
            if self.device is not None and self.shdlc_port is not None:
                self.timer.start(1000)  # 每秒更新一次
                self.start_button.setText("Stop")
                self.create_edf_file()
            else:
                print("Please open the port first.")

    def toggle_connection(self):
        if self.device is not None or self.shdlc_port is not None:
            self.open_port_button.setText("Open Port")
            self.disconnect_device()
            if self.timer.isActive():
                self.timer.stop()
        else:
            self.open_port_button.setText("Close Port")
            self.connect_device()

    def disconnect_device(self):
        if self.device and self.shdlc_port:
            try:
                self.device.switch_supply_off(self.select_port)
                self.shdlc_port.close()
                self.device = None
                self.shdlc_port = None
                print("Device disconnected successfully.")
            except Exception as e:
                print(f"Failed to disconnect device: {e}")
    def update_data(self):
        if self.device:
            try:
                volt = self.device.measure_voltage(self.select_port)
                self.x_data.append(time.time())
                self.y_data.append(volt)
                self.plot_widget.clear()
                self.plot_widget.plot(self.x_data, self.y_data, pen='r')
                self.plot_widget.setYRange(0, 6)  # 动态设置 Y 轴范围

                # 计算公式结果
                formula = self.formula_input.text()
                if formula:
                    try:
                        result = eval(formula.replace('x', str(volt)))
                    except Exception as e:
                        result = None

                if result is not None:
                    self.plot_widget.setTitle(f"Voltage: {volt:.3f} V \nResult: {result:.3f}")
                    df = pd.DataFrame({'Epoch_UTC': [time.time()], 'voltage': [volt], 'calcuted_value': [result]})
                    df['Epoch_UTC'].astype('datetime64[ns]')
                    df.to_csv(self.file_name, header=False, sep=str("\t"), float_format=None,
                                  encoding='utf-8', lineterminator=u"\n", mode='a', index=False)

                    # 更新 TextItem
                    self.voltage_text_item.setText(f"Voltage: {volt:.3f} V")
                    self.result_text_item.setText(f"Result: {result:.3f}")
                else:
                    self.plot_widget.setTitle(f"Voltage: {volt:.3f} V \nResult: Invalid formula or calculation error")

            except Exception as e:
                print(f"Failed to read voltage: {e}")


pg.setConfigOptions(background='w')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SensorApp()
    window.show()
    sys.exit(app.exec_())