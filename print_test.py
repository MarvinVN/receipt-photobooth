from escpos.printer import File

p = File("/dev/usb/lp0")
p.set(align="center", bold=True, width=2, height=2)
p.text("PHOTOBOOTH\n")
p.set(align="center", bold=False, width=1, height=1)
p.text("hello world\n\n")
p.cut()
