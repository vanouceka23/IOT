from machine import ADC, Pin, PWM
from time import sleep


pot = ADC(26)
led = PWM(Pin(15))
led.freq(1000)


while True:
	hodnota = pot.read_u16()
	led.duty_u16(hodnota)
	sleep(0.01)
