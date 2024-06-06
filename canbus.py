import sys
import os
import errno
import time
import random
import serial

CANUSB_INJECT_SLEEP_GAP_DEFAULT = 200  # ms
CANUSB_TTY_BAUD_RATE_DEFAULT = 2000000

CANUSB_SPEED = {
    1000000: 0x01,
    800000: 0x02,
    500000: 0x03,
    400000: 0x04,
    250000: 0x05,
    200000: 0x06,
    125000: 0x07,
    100000: 0x08,
    50000: 0x09,
    20000: 0x0a,
    10000: 0x0b,
    5000: 0x0c
}

CANUSB_MODE = {
    'CANUSB_MODE_NORMAL': 0x00,
    'CANUSB_MODE_LOOPBACK': 0x01,
    'CANUSB_MODE_SILENT': 0x02,
    'CANUSB_MODE_LOOPBACK_SILENT': 0x03
}

CANUSB_FRAME = {
    'CANUSB_FRAME_STANDARD': 0x01,
    'CANUSB_FRAME_EXTENDED': 0x02
}

CANUSB_PAYLOAD_MODE = {
    'CANUSB_INJECT_PAYLOAD_MODE_RANDOM': 0,
    'CANUSB_INJECT_PAYLOAD_MODE_INCREMENTAL': 1,
    'CANUSB_INJECT_PAYLOAD_MODE_FIXED': 2
}

terminate_after = 0
program_running = True
inject_payload_mode = CANUSB_PAYLOAD_MODE['CANUSB_INJECT_PAYLOAD_MODE_FIXED']
inject_sleep_gap = CANUSB_INJECT_SLEEP_GAP_DEFAULT
print_traffic = 1


def canusb_int_to_speed(speed):
    return CANUSB_SPEED.get(speed, 0)

def generate_checksum(data):
    return sum(data) & 0xff

def frame_is_complete(frame):
    if frame:
        if frame[0] != 0xaa:
            return True

    if len(frame) < 2:
        return False

    if frame[1] == 0x55:  # Command frame...
        if len(frame) >= 20:  # ...always 20 bytes.
            return True
        else:
            return False
    elif (frame[1] >> 4) == 0xc:  # Data frame...
        if len(frame) >= (frame[1] & 0xf) + 5:  # ...payload and 5 bytes.
            return True
        else:
            return False

    return True

def frame_send(tty_fd, frame):
    result = tty_fd.write(frame)
    if result == -1:
        sys.stderr.write("write() failed: {}\n".format(os.strerror(errno)))
        return -1

    return result

def frame_recv(tty_fd, frame_len_max):
    global program_running  # program_running değişkenini global olarak tanımlıyoruz.

    frame = bytearray()
    while program_running:
        byte = tty_fd.read(1)
        if not byte:
            time.sleep(0.01)  # Wait for data
            continue

        frame.append(byte[0])

        if frame_is_complete(frame):
            break

        if len(frame) == frame_len_max:
            sys.stderr.write("frame_recv() failed: Overflow\n")
            return -1

    return frame

def command_settings(tty_fd, speed, mode, frame):
    cmd_frame = bytearray([0xaa, 0x55, 0x12, speed, frame]) + bytearray(14) + bytearray([mode, 0x01]) + \
                bytearray(4) + bytearray([generate_checksum([0x12, speed, frame, mode, 0x01])])

    if frame_send(tty_fd, cmd_frame) < 0:
        return -1

    return 0

def send_data_frame(tty_fd, frame, id_lsb, id_msb, data, data_length_code):
    data_frame = bytearray([0xaa])  # Packet Start

    data_frame.append(0x00 | (0xC0 if frame == CANUSB_FRAME['CANUSB_FRAME_EXTENDED'] else 0x00) |
                      (data_length_code & 0x0F))  # CAN Bus Data Frame Information

    data_frame += bytearray([id_lsb, id_msb])  # ID

    data_frame += data[:data_length_code]  # Data

    data_frame.append(0x55)  # End of frame

    if frame_send(tty_fd, data_frame) < 0:
        sys.stderr.write("Unable to send frame!\n")
        return -1

    return 0

def hex_value(c):
    if 0x30 <= c <= 0x39:  # '0' - '9'
        return c - 0x30
    elif 0x41 <= c <= 0x46:  # 'A' - 'F'
        return (c - 0x41) + 10
    elif 0x61 <= c <= 0x66:  # 'a' - 'f'
        return (c - 0x61) + 10
    else:
        return -1

def convert_from_hex(hex_string, bin_string):
    n1, n2, high = 0, 0, -1

    while n1 < len(hex_string):
        if hex_value(ord(hex_string[n1])) >= 0:
            if high == -1:
                high = ord(hex_string[n1])
            else:
                bin_string[n2] = hex_value(high) * 16 + hex_value(ord(hex_string[n1]))
                n2 += 1
                if n2 >= len(bin_string):
                    sys.stdout.write("hex string truncated to {} bytes\n".format(n2))
                    break
                high = -1
        n1 += 1

    return n2

def inject_data_frame(tty_fd, hex_id, hex_data):
    global program_running
    binary_data = bytearray(8)
    binary_id_lsb, binary_id_msb = 0, 0

    gap_sec = int(inject_sleep_gap / 1000)
    gap_nsec = int((inject_sleep_gap * 1000000) % 1000000000)

    # Set seed value for pseudo random numbers.
    random.seed()
    
    data_len = convert_from_hex(hex_data, binary_data)
    if data_len == 0:
        sys.stderr.write("Unable to convert data from hex to binary!\n")
        return -1

    id_length = len(hex_id)
    if id_length == 1:
        binary_id_lsb = hex_value(ord(hex_id[0]))
    elif id_length == 2:
        binary_id_lsb = (hex_value(ord(hex_id[0])) * 16) + hex_value(ord(hex_id[1]))
    elif id_length == 3:
        binary_id_msb = hex_value(ord(hex_id[0]))
        binary_id_lsb = (hex_value(ord(hex_id[1])) * 16) + hex_value(ord(hex_id[2]))
    else:
        sys.stderr.write("Unable to convert ID from hex to binary!\n")
        return -1

    while program_running:
        if gap_sec or gap_nsec:
            time.sleep(inject_sleep_gap / 1000)

        if inject_payload_mode == CANUSB_PAYLOAD_MODE['CANUSB_INJECT_PAYLOAD_MODE_RANDOM']:
            for i in range(data_len):
                binary_data[i] = random.randint(0, 255)
        elif inject_payload_mode == CANUSB_PAYLOAD_MODE['CANUSB_INJECT_PAYLOAD_MODE_INCREMENTAL']:
            for i in range(data_len):
                binary_data[i] += 1

        error = send_data_frame(tty_fd, CANUSB_FRAME['CANUSB_FRAME_STANDARD'], binary_id_lsb, binary_id_msb,
                                binary_data, data_len)

        if error == -1:
            return error

    return 0

def dump_data_frames(tty_fd):
    while True:
        frame = frame_recv(tty_fd, 32)

        if not True:
            break

        ts = time.time()
        sys.stdout.write("{:.6f} ".format(ts))

        if frame == -1:
            sys.stdout.write("Frame recieve error!\n")
        else:
            frame_len = len(frame)
            if frame_len >= 6 and frame[0] == 0xaa and (frame[1] >> 4) == 0xc:
                sys.stdout.write("Frame ID: {:02x}{:02x}, Data: ".format(frame[3], frame[2]))
                for i in range(frame_len - 2, 3, -1):
                    sys.stdout.write("{:02x} ".format(frame[i]))
                sys.stdout.write("\n")
            else:
                sys.stdout.write("Unknown: ")
                for i in range(frame_len):
                    sys.stdout.write("{:02x} ".format(frame[i]))
                sys.stdout.write("\n")

        if terminate_after and (terminate_after == 0):
            program_running = False

def adapter_init(tty_device, baudrate):
    global program_running  # program_running değişkenini global olarak tanımlıyoruz.

    try:
        tty_fd = serial.Serial(tty_device, baudrate, timeout=0)
    except serial.SerialException as e:
        sys.stderr.write("open({}) failed: {}\n".format(tty_device, str(e)))
        program_running = False  # Seri port açma başarısız olursa program_running False olacak.

        return -1

    return tty_fd

def sigterm_handler(signum, frame):
    global program_running
    program_running = False


def main():
    global terminate_after, inject_sleep_gap, inject_payload_mode, program_running

    # Default values
    tty_device = '/dev/ttyUSB1'
    speed = canusb_int_to_speed(500000)
    baudrate = CANUSB_TTY_BAUD_RATE_DEFAULT
    inject_id = '123'
    inject_data = None

    tty_fd = adapter_init(tty_device, baudrate)
    if tty_fd == -1:
        return 1

    command_settings(tty_fd, speed, CANUSB_MODE['CANUSB_MODE_NORMAL'], CANUSB_FRAME['CANUSB_FRAME_STANDARD'])

    if inject_data is None:
        # Dumping mode (default).
        dump_data_frames(tty_fd)
    else:
        # Inject mode.
        if inject_id is None:
            sys.stderr.write("Please specify a ID for injection!\n")
            return 2
        if inject_data_frame(tty_fd, inject_id, inject_data) == -1:
            return 1
        else:
            return 0

    return 0


if __name__ == "__main__":

    sys.exit(main())
