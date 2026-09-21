from machine import Pin, ADC, PWM
import utime

pot = ADC(Pin(26))
led = PWM(Pin(14))
led.freq(1000)

while True:
    value = pot.read_u16()      # 0..65535
    led.duty_u16(value)         # PWM brightness
    utime.sleep_ms(20)
