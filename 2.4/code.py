from machine import Pin, UART
import utime
 
# Nahrajte stejný soubor na obě Pico a nastavte správnou roli.
DEVICE_ROLE = "led"
 
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
 
if DEVICE_ROLE == "button":
    button = Pin(13, Pin.IN, Pin.PULL_UP)
    state = not button.value()
    candidate = state
    candidate_since = utime.ticks_ms()
    uart.write(b"1" if state else b"0")
 
    while True:
        reading = not button.value()
        if reading != candidate:
            candidate = reading
            candidate_since = utime.ticks_ms()
        elif candidate != state and utime.ticks_diff(
            utime.ticks_ms(), candidate_since
        ) >= 30:
            state = candidate
            uart.write(b"1" if state else b"0")
        utime.sleep_ms(5)
 
elif DEVICE_ROLE == "led":
    led = Pin(14, Pin.OUT)
 
    while True:
        if uart.any():
            value = uart.read(1)
            if value == b"1":
                led.on()
            elif value == b"0":
                led.off()
        utime.sleep_ms(5)
 
else:
    raise ValueError('DEVICE_ROLE must be "button" or "led"')
 