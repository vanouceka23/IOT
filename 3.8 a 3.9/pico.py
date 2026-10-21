from machine import ADC, Pin, UART
from time import sleep

potentiometer = ADC(Pin(26))
uart = UART(0, baudrate=115200, tx=Pin(0))

while True:
    uart.write("{}\n".format(potentiometer.read_u16()))
    sleep(0.05)
