from machine import I2C, Pin
import time


# Raspberry Pi Pico pins
I2C_ID = 0
I2C_SDA = 0
I2C_SCL = 1


class I2cLcd:
	ENABLE = 0x04
	BACKLIGHT = 0x08

	def __init__(self, i2c, address, columns=16, rows=2):
		self.i2c = i2c
		self.address = address
		self.columns = columns
		self.rows = rows
		time.sleep_ms(20)
		self._write4(0x30)
		time.sleep_ms(5)
		self._write4(0x30)
		time.sleep_ms(1)
		self._write4(0x30)
		time.sleep_ms(1)
		self._write4(0x20)
		self.command(0x28)  # 4-bit mode, 2 rows
		self.command(0x0C)  # display on, cursor off
		self.command(0x06)  # move cursor right
		self.clear()

	def _write(self, value):
		try:
			self.i2c.writeto(self.address, bytes((value | self.BACKLIGHT,)))
		except OSError as error:
			raise RuntimeError(
				"I2C LCD timeout - zkontroluj SDA/SCL, GND a napetove urovne"
			) from error

	def _write4(self, value):
		self._write(value | self.ENABLE)
		self._write(value & ~self.ENABLE)

	def command(self, value):
		self._write4(value & 0xF0)
		self._write4((value << 4) & 0xF0)
		time.sleep_us(50)

	def write_char(self, value):
		self._write4((value & 0xF0) | 0x01)
		self._write4(((value << 4) & 0xF0) | 0x01)

	def clear(self):
		self.command(0x01)
		time.sleep_ms(2)

	def set_cursor(self, column, row):
		self.command(0x80 | (0x40 * row + column))

	def write(self, text):
		for character in text:
			self.write_char(ord(character))


i2c = I2C(I2C_ID, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100000)
addresses = i2c.scan()
if not addresses:
	raise RuntimeError("LCD nebyl nalezen. Zkontroluj SDA=GPIO0, SCL=GPIO1 a GND")

print("I2C zarizeni:", [hex(address) for address in addresses])

lcd_address = 0x27 if 0x27 in addresses else addresses[0]
if 0x3F in addresses:
	lcd_address = 0x3F

lcd = I2cLcd(i2c, lcd_address)
lcd.set_cursor(0, 0)
lcd.write("Hello World!")
lcd.set_cursor(0, 1)
lcd.write("LCD works")
