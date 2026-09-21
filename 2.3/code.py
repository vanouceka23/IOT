from machine import Pin, PWM
import utime

# Ultrasonic sensor HC-SR04
trigger = Pin(18, Pin.OUT)
echo = Pin(19, Pin.IN)

# Servo motor
servo = PWM(Pin(15))
servo.freq(50)


def set_servo_angle(angle):
    angle = max(0, min(180, angle))
    duty = int(1638 + (angle / 180) * 6554)
    servo.duty_u16(duty)


def get_distance_cm():
    trigger.low()
    utime.sleep_us(2)
    trigger.high()
    utime.sleep_us(10)
    trigger.low()

    start = 0
    stop = 0
    timeout = utime.ticks_add(utime.ticks_us(), 20000)  # 20 ms timeout

    while echo.value() == 0 and utime.ticks_diff(timeout, utime.ticks_us()) > 0:
        start = utime.ticks_us()

    while echo.value() == 1 and utime.ticks_diff(timeout, utime.ticks_us()) > 0:
        stop = utime.ticks_us()

    if start == 0 or stop == 0 or stop <= start:
        return 0

    duration = stop - start
    distance = duration / 58.0
    return distance


while True:
    dist = get_distance_cm()

    if dist < 5:
        dist = 5
    if dist > 30:
        dist = 30

    angle = int((dist - 5) * 180 / (30 - 5))
    set_servo_angle(angle)

    print("Distance:", round(dist, 1), "cm   Angle:", angle)
    utime.sleep_ms(100)
