"""
Robot Arm Controller - Python Kütüphanesi
Nucleo F401RE ile UART üzerinden haberleşir.
"""

import serial
import time


class RobotArm:
    def __init__(self, port='COM3', baudrate=115200, timeout=1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None

    def connect(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            time.sleep(2)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print(f"[OK] {self.port} portuna bağlandı.")
            return True
        except serial.SerialException as e:
            print(f"[HATA] Bağlanılamadı: {e}")
            return False

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def _send(self, command):
        if not self.ser or not self.ser.is_open:
            return None
        cmd = command.strip() + '\n'
        self.ser.write(cmd.encode('ascii'))
        return self.ser.readline().decode('ascii', errors='ignore').strip()

    def ping(self):
        return self._send('P')

    def home(self):
        return self._send('H')

    def set_servo(self, index, angle):
        if not (0 <= index <= 5): return None
        if not (0 <= angle <= 180): return None
        return self._send(f'S{index}:{angle:.1f}')

    def set_all_servos(self, angles):
        if len(angles) != 6: return None
        return self._send('A:' + ','.join(f'{a:.1f}' for a in angles))

    def stepper_move(self, target_step):
        return self._send(f'M:{target_step}')

    def stepper_stop(self):
        return self._send('X')

    def stepper_zero(self):
        return self._send('Z')

    def stepper_position(self):
        return self._send('Q')

    def read_pot(self):
        response = self._send('R')
        if response and response.startswith('POT:'):
            try:
                return int(response[4:])
            except ValueError:
                return None
        return None     