from machine import Pin
import utime

button = Pin(15, Pin.IN, Pin.PULL_UP)
led = Pin(14, Pin.OUT)

while True:
    if button.value() == 0:   # tlačítko stisknuto
        led.on()
        utime.sleep(1)
        led.off()
        utime.sleep(1)          # rozsvítí externí LED
    else:
        led.off()             # LED zhasne
