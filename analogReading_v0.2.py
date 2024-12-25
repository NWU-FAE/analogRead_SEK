
import datetime as dt
import os
import sys
import time

import pandas as pd
import pyqtgraph as pg
import sensirion_fastedf as fastedf
import serial.tools.list_ports
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, \
    QComboBox, QLineEdit, QSplitter, QFrame, QHBoxLayout, QTextEdit, QDoubleSpinBox, QCheckBox
from sensirion_shdlc_driver import ShdlcSerialPort, ShdlcConnection
from sensirion_shdlc_sensorbridge import SensorBridgeShdlcDevice


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
        self.plot_widget.setLabel('left', 'Voltage',units='v')
        self.plot_widget.setLabel('bottom', 'Time', units='s')
        self.plot_widget.addLegend()

        self.result_text_item = pg.TextItem(color='r')


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

        # 创建 Port1 和 Port2 的复选框和标签

        self.port1_checkbox = QCheckBox('Port1')
        self.port1_checkbox.setChecked(True)
        self.port1_checkbox.stateChanged.connect(self.on_port1_checkbox_changed)
        self.port2_checkbox = QCheckBox('Port2')
        self.port2_checkbox.setChecked(True)
        self.port2_checkbox.stateChanged.connect(self.on_port2_checkbox_changed)
        group1_layout_hbox = QHBoxLayout()
        group1_layout_hbox.addWidget(self.port1_checkbox)
        group1_layout_hbox.addWidget(self.port2_checkbox)

        # 将水平布局添加到 group1_layout 中
        group1_layout.addLayout(group1_layout_hbox)

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
        self.custom_header_input.setText("{'TestName':'Logi','Port1':{'SensorName':'Sen66_1','SensorId':'11','SampleRate':'1'},'Port2':{'SensorName':'Sen66_2','SensorId':'222','SampleRate':'1'}}")
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
        self.y1_data=[]

        # 初始化定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)

        # 连接设备
        self.device = None
        self.shdlc_port = None
        self.select_port = None
        self.file_name = None
        self.SEK_ports=['Port1','Port2']
        self.port_dict = {'Port1': 0, 'Port2': 1}

        # 初始化 TextItem
        self.voltage_text_item = pg.TextItem(color='g')
        self.result_text_item = pg.TextItem(color='g')

        # 固定 TextItem 的位置
        self.plot_widget.addItem(self.voltage_text_item)
        self.plot_widget.addItem(self.result_text_item)
        self.voltage_text_item.setPos(0.5, 5.5)  # 上方中部
        self.result_text_item.setPos(0.5, 5.0)  # 上方中部

    def on_port1_checkbox_changed(self, state):
        if state == Qt.Checked:
            self.SEK_ports.append('Port1')
        else:
            self.SEK_ports.remove('Port1')

    def on_port2_checkbox_changed(self, state):
        if state == Qt.Checked:
            self.SEK_ports.append('Port2')
        else:
            self.SEK_ports.remove('Port2')

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
        column_metadata = {'Epoch_UTC': {'Format': '.2f', 'Type': 'float64', 'Unit': 's'}}
                           # 'voltage': {'Format': '.1f', 'Type': 'float', 'Unit': 'V'},
                           # 'calcuted_value': {'Format': '.1f', 'Type': 'float', 'Unit': 'U'}}

        header = {'appinfo': 'desigen by NWU'}
        header.update(eval(self.custom_header_input.toPlainText()))
        # 检查文件是否存在
        current_time = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        testname = header.get('TestName') if 'TestName' in header else ''

        if not(testname =='' ):
            self.file_name = current_time+'_'+testname+'.edf'
        else:
            self.file_name = f"{current_time}.edf"
        columns = ['Epoch_UTC']
        for port in self.SEK_ports:
            if port in header:
                column = port+header[port]['SensorName']+header[port]['SensorId']+'voltage'
                columns = columns+[column]
                column_metadata.update({column: {'Format': '.1f', 'Type': 'float', 'Unit': 'V'}})
                column = port+header[port]['SensorName']+header[port]['SensorId']+'calcuted_value'
                columns = columns+[column]
                column_metadata.update({column: {'Format': '.1f', 'Type': 'float', 'Unit': 'U'}})
        df = pd.DataFrame(columns=columns)
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

                for port in self.SEK_ports:
                    self.device.set_supply_voltage(self.port_dict[port], voltage=power_voltage)
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
        if self.SEK_ports == []:
            print("Please select at least one port.")
            return
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
                for port in self.SEK_ports:
                    self.device.switch_supply_off(self.port_dict[port])
                self.shdlc_port.close()
                self.device = None
                self.shdlc_port = None
                print("Device disconnected successfully.")
            except Exception as e:
                print(f"Failed to disconnect device: {e}")
    def update_data(self):
        if self.device:
            try:
                df = pd.DataFrame()
                title=''
                self.plot_widget.clear()
                self.x_data.append(time.time())
                for port in self.SEK_ports:
                    volt = self.device.measure_voltage(self.port_dict[port])
                    if port == 'Port1':
                        self.y_data.append(volt)
                        self.plot_widget.plot(self.x_data, self.y_data, pen='r', name=port)
                    if port == 'Port2':
                        self.y1_data.append(volt)
                        self.plot_widget.plot(self.x_data, self.y1_data, pen='g', name=port)



                    # 动态设置 Y 轴范围

                    # 计算公式结果
                    formula = self.formula_input.text()
                    if formula:
                        try:
                            result = eval(formula.replace('x', str(volt)))
                        except Exception as e:
                            result = None
                    header=eval(self.custom_header_input.toPlainText())
                    column1 = port + header[port]['SensorName'] + header[port]['SensorId'] + 'voltage'
                    column2 = port + header[port]['SensorName'] + header[port]['SensorId'] + 'calcuted_value'
                    if result is not None:
                        title = title + f"{port}Voltage: {volt:.3f} V Result: {result:.3f} &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                        df['Epoch_UTC']=[time.time()]
                        df[column1]=[volt]
                        df[column2]=[result]

                df.to_csv(self.file_name, header=False, sep=str("\t"), float_format=None,
                                      encoding='utf-8', lineterminator=u"\n", mode='a', index=False)
                self.plot_widget.setTitle(title, color='#000000', size='12pt')
                    # else:
                    #     self.plot_widget.setTitle(f"Voltage: {volt:.3f} V \nResult: Invalid formula or calculation error")

            except Exception as e:
                print(f"Failed to read voltage: {e}")


pg.setConfigOptions(background='w')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SensorApp()
    window.show()
    sys.exit(app.exec_())