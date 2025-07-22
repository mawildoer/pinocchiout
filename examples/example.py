from pinocchiout.data import get_chip_package_and_core
from pinocchiout.tableator import Tableator

package, core = get_chip_package_and_core("STM32G431C6", "UFQFPN48")

solver = Tableator(package, core)

solver.add_req("spi", peripheral_kind="spi", peripheral_signal_names=["MOSI", "MISO", "SCK"])
solver.add_req("i2c", peripheral_kind="i2c", peripheral_signal_names=["SCL", "SDA"])
solver.add_req("usb", peripheral_kind="usb", peripheral_signal_names=["DM", "DP"])
solver.add_req("can", peripheral_kind="can", peripheral_signal_names=["TX", "RX"])
# solver.add_req(
#     "ucpd", peripheral_kind="ucpd", peripheral_signal_names=["DBCC1", "DBCC2", "FRSTX1", "FRSTX2", "CC1", "CC2"]
# )
solver.add_req(
    "motor-pwm",
    peripheral_name=r"TIM[1|8]",
    peripheral_signal_names=["CH1", "CH2", "CH3"],
)
solver.add_req(
    "current-sense",
    peripheral_name=r"ADC[1|2]",
    peripheral_signal_names=[r"IN[0-9]+"] * 3,
)
# solver.reserve_pin("PB8")  # boot select pin

solver.solve()
