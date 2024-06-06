
import os
import sys
import serial
import time
import random

CANUSB_TTY_BAUD_RATE_DEFAULT = 2000000
CANUSB_INJECT_SLEEP_GAP_DEFAULT = 200

# Define CANUSB speed enumeration
class CANUSB_SPEED:
    CANUSB_SPEED_1000000 = 0x01
    CANUSB_SPEED_800000  = 0x02
    CANUSB_SPEED_500000  = 0x03
    CANUSB_SPEED_400000  = 0x04
    CANUSB_SPEED_250000  = 0x05
    CANUSB_SPEED_200000  = 0x06
    CANUSB_SPEED_125000  = 0x07
    CANUSB_SPEED_100000  = 0x08
    CANUSB_SPEED_50000   = 0x09
    CANUSB_SPEED_20000   = 0x0a
    CANUSB_SPEED_10000   = 0x0b
    CANUSB_SPEED_5000    = 0x0c

# Define CANUSB mode enumeration
class CANUSB_MODE:
    CANUSB_MODE_NORMAL          = 0x00
    CANUSB_MODE_LOOPBACK        = 0x01
    CANUSB_MODE_SILENT          = 0x02
    CANUSB_MODE_LOOPBACK_SILENT = 0x03

# Define CANUSB frame enumeration
class CANUSB_FRAME:
    CANUSB_FRAME_STANDARD = 0x01
    CANUSB_FRAME_EXTENDED = 0x02

# Define CANUSB payload mode enumeration
class CANUSB_PAYLOAD_MODE:
    CANUSB_INJECT_PAYLOAD_MODE_RANDOM      = 0
    CANUSB_INJECT_PAYLOAD_MODE_INCREMENTAL = 1
    CANUSB_INJECT_PAYLOAD_MODE_FIXED       = 2

# Convert integer speed to CANUSB_SPEED enumeration
def canusb_int_to_speed(speed):
    speed_map = {
        1000000: CANUSB_SPEED.CANUSB_SPEED_1000000,
        800000: CANUSB_SPEED.CANUSB_SPEED_800000,
        500000: CANUSB_SPEED.CANUSB_SPEED_500000,
        400000: CANUSB_SPEED.CANUSB_SPEED_400000,
        250000: CANUSB_SPEED.CANUSB_SPEED_250000,
        200000: CANUSB_SPEED.CANUSB_SPEED_200000,
        125000: CANUSB_SPEED.CANUSB_SPEED_125000,
        100000: CANUSB_SPEED.CANUSB_SPEED_100000,
        50000: CANUSB_SPEED.CANUSB_SPEED_50000,
        20000: CANUSB_SPEED.CANUSB_SPEED_20000,
        10000: CANUSB_SPEED.CANUSB_SPEED_10000,
        5000: CANUSB_SPEED.CANUSB_SPEED_5000,
    }
    return speed_map.get(speed, None)

# Generate checksum for given data
def generate_checksum(data):
    checksum = sum(data)
    return checksum & 0xFF

# Send frame over serial port
def frame_send(ser, frame):
    ser.write(frame)

# Receive frame from serial port
def frame_recv(ser, max_frame_len):
    frame = bytearray()
    while True:
        byte = ser.read(1)
        if not byte:
            break
        frame.append(byte[0])

        if len(frame) >= max_frame_len:
            break

    return frame

# Send command settings
def command_settings(ser, speed, mode, frame):
    cmd_frame = bytearray([0xAA, 0x55, 0x12, speed, frame, 0, 0, 0, 0, 0, 0, 0, 0, mode, 0x01, 0, 0, 0, 0, 0])
    checksum = generate_checksum(cmd_frame[2:])
    cmd_frame.append(checksum)
    frame_send(ser, cmd_frame)

# Send data frame
def send_data_frame(ser, frame, id_lsb, id_msb, data, data_length_code):
    data_frame = bytearray([0xAA, 0x00])
    data_frame[1] |= 0xC0  # Bit 7 Always 1, Bit 6 Always 1
    if frame == CANUSB_FRAME.CANUSB_FRAME_STANDARD:
        data_frame[1] &= 0xDF  # STD frame
    else:  # CANUSB_FRAME_EXTENDED
        data_frame[1] |= 0x20  # EXT frame
    data_frame[1] &= 0xEF  # 0=Data
    data_frame[1] |= data_length_code  # DLC=data_len
    data_frame.extend([id_lsb, id_msb])
    data_frame.extend(data)
    data_frame.append(0x55)
    frame_send(ser, data_frame)

# Inject data frame
def inject_data_frame(ser, hex_id, hex_data, payload_mode, sleep_gap):
    data_len = len(hex_data) // 2
    binary_data = bytearray.fromhex(hex_data)
    binary_id_lsb, binary_id_msb = 0, 0

    if len(hex_id) == 1:
        binary_id_lsb = int(hex_id[0], 16)
    elif len(hex_id) == 2:
        binary_id_lsb = int(hex_id, 16)
    elif len(hex_id) == 3:
        binary_id_msb = int(hex_id[0], 16)
        binary_id_lsb = int(hex_id[1:], 16)
    else:
        raise ValueError("Invalid ID format")

    while True:
        time.sleep(sleep_gap / 1000.0)
        if payload_mode == CANUSB_PAYLOAD_MODE.CANUSB_INJECT_PAYLOAD_MODE_RANDOM:
            binary_data = bytearray(random.getrandbits(8) for _ in range(data_len))
        elif payload_mode == CANUSB_PAYLOAD_MODE.CANUSB_INJECT_PAYLOAD_MODE_INCREMENTAL:
            binary_data = bytearray((byte + 1) % 256 for byte in binary_data)

        send_data_frame(ser, CANUSB_FRAME.CANUSB_FRAME_STANDARD, binary_id_lsb, binary_id_msb, binary_data, data_len)
        
def receive_data_frames(ser):
    while True:
        frame = frame_recv(ser, max_frame_len=32)
        if frame:
            print("Received frame:", frame)
            # Burada frame verisini işleyebilirsiniz, istediğiniz gibi kullanabilirsiniz

def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="CANUSB interface")
    parser.add_argument("-d", "--device", help="Serial device", required=True)
    parser.add_argument("-s", "--speed", type=int, help="CAN speed (bps)", required=True)
    parser.add_argument("-b", "--baudrate", type=int, default=CANUSB_TTY_BAUD_RATE_DEFAULT, help="Baudrate")
    parser.add_argument("-i", "--id", help="ID to inject (hex)")
    parser.add_argument("-j", "--data", help="Data to inject (hex)")
    parser.add_argument("-g", "--gap", type=int, default=CANUSB_INJECT_SLEEP_GAP_DEFAULT, help="Sleep gap (ms)")
    parser.add_argument("-m", "--mode", type=int, choices=[0, 1, 2], default=2, help="Payload mode (0=random, 1=incremental, 2=fixed)")
    args = parser.parse_args()

    # Convert speed to CANUSB_SPEED enum
    speed_enum = canusb_int_to_speed(args.speed)
    if speed_enum is None:
        print("Invalid CAN speed specified")
        return

    # Open serial port
    try:
        ser = serial.Serial(args.device, args.baudrate)
    except serial.SerialException as e:
        print(f"Failed to open serial port: {e}")
        return

    # Set CAN speed and mode
    command_settings(ser, speed_enum, CANUSB_MODE.CANUSB_MODE_NORMAL, CANUSB_FRAME.CANUSB_FRAME_STANDARD)

    # If ID and data provided, inject data frames
    if args.id and args.data:
        try:
            inject_data_frame(ser, args.id, args.data, args.mode, args.gap)
        except ValueError as e:
            print(f"Error: {e}")

    # Close serial port
    ser.close()

if __name__ == "__main__":
    main()