from gpiozero import LED, Button
from time import sleep
 
led = LED(17)
tlacitko = Button(27)
 
while True:
    if tlacitko.is_pressed:
        led.on()
        sleep(0.5)
        led.off()
        sleep(0.5)
    else:
        led.off()
        sleep(0.1)