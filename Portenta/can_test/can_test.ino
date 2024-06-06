#include "CAN.h"

CAN can1(PB_8, PB_9);  // CAN1 RX, TX pins

int main() {
    // Initialize CAN bus
    if (can1.frequency(500000) != 0) { // Set CAN bit rate to 500kbps
        printf("Error initializing CAN bus!\n");
        return -1;
    }
    printf("CAN bus initialized\n");

    // Set up random seed
    srand(time(NULL));

    while(1) {
        // Create random CAN message
        CANMessage msg;
        msg.id = rand() % 2048; // Random CAN ID (0 to 2047)
        msg.len = rand() % 8 + 1; // Random data length (1 to 8 bytes)
        for (int i = 0; i < msg.len; i++) {
            msg.data[i] = rand() % 256; // Random data bytes
        }

        // Send CAN message
        if (can1.write(msg)) {
            printf("Sent CAN message with ID: %d, Length: %d\n", msg.id, msg.len);
            for (int i = 0; i < msg.len; i++) {
                printf("Data[%d]: %d\n", i, msg.data[i]);
            }
        } else {
            printf("Failed to send CAN message!\n");
        }

        // Wait for a random interval before sending the next message
        wait_ms(rand() % 1000 + 100); // Random interval between 100ms and 1s
    }
}
