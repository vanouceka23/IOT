from machine import Pin
import utime

led_onboard = Pin('LED', Pin.OUT)
while True:
        led_onboard.on()
        utime.sleep(1)
        led_onboard.off()
        utime.sleep(1)