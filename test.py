import serial
import time

# Seri portunuzu ve baud rate'i burada belirtin
port = '/dev/ttyUSB0'
baud_rate = 20000000

try:
    ser = serial.Serial(port, baud_rate, timeout=1)
    print(f"Bağlantı kuruldu: {port} @ {baud_rate} baud")
except Exception as e:
    print(f"Seri port açılırken hata oluştu: {e}")
    exit()

try:
    while True:
            data = ser.readline()
        
            print(data)
   
except KeyboardInterrupt:
    print("Çıkış yapılıyor...")
except Exception as e:
    print(f"Veri okuma sırasında hata oluştu: {e}")
finally:
    ser.close()
    print("Seri port kapatıldı.")