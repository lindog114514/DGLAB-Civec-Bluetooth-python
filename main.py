import asyncio
import struct
import sys
from bleak import BleakScanner, BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

DEVICE_NAME = "47L124000"

# 服务 UUID
SERVICE_CTRL_UUID = "0000180C-0000-1000-8000-00805F9B34FB"
SERVICE_BATTERY_UUID = "0000180A-0000-1000-8000-00805F9B34FB"

# 特征 UUID
CHAR_WRITE_UUID = "0000150A-0000-1000-8000-00805F9B34FB"
CHAR_NOTIFY_UUID = "0000150B-0000-1000-8000-00805F9B34FB"
CHAR_BATTERY_UUID = "00001500-0000-1000-8000-00805F9B34FB"

# B0 指令：启动气压上报（17 字节）
START_PRESSURE_REPORT_CMD = bytes([
    0xB0, 0x01, 0xD0, 0x64,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00
])

# 66 指令：重置气压（12 字节）
RESET_PRESSURE_CMD = bytes([
    0x66, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x02
])

def parse_pressure(data: bytes) -> float:
    if len(data) < 17:
        raise ValueError(f"数据长度异常，期望 17 字节，实际 {len(data)} 字节")
    pressure_raw = struct.unpack('<h', data[8:10])[0]
    return pressure_raw / 100.0

async def notification_handler(sender: BleakGATTCharacteristic, data: bytearray):
    try:
        pressure = parse_pressure(bytes(data))
        led_color = data[0]
        print(f"[气压] {pressure:.2f} kPa   (指示灯: 0x{led_color:02X})")
    except Exception as e:
        print(f"解析气压数据出错: {e} 原始数据: {data.hex()}")

async def check_bluetooth_available() -> bool:
    print("正在检测蓝牙适配器状态...")
    try:
        await BleakScanner.discover(timeout=1, return_adv=False)
        print("蓝牙适配器正常")
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in [
            "bluetooth", "adapter", "not enabled", "no adapter",
            "permission", "access denied", "10050", "10051"
        ]):
            print("\n❌ 错误：电脑未开启蓝牙或蓝牙适配器不可用！")
            print("   请确保：")
            print("   1. 系统蓝牙已打开")
            print("   2. 已授予 Python 蓝牙权限")
            print("   3. 蓝牙驱动正常工作")
        else:
            print(f"\n❌ 蓝牙检测失败: {e}")
        return False

async def main():
    # 检测蓝牙
    if not await check_bluetooth_available():
        sys.exit(1)

    # 扫描设备
    print(f"正在扫描设备名称 '{DEVICE_NAME}' ...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME)
    if device is None:
        print(f"未找到设备 '{DEVICE_NAME}'，请确认：")
        print("  - 设备已开机且蓝牙图标为黄色（若未变黄，请连按5次开机键）")
        print("  - 设备未与其他手机/电脑连接")
        return

    print(f"找到设备: {device.name} [{device.address}]")
    client = BleakClient(device)

    try:
        await client.connect()
        print("已连接")

        # 读取电量 - 直接使用 UUID
        battery_data = await client.read_gatt_char(CHAR_BATTERY_UUID)
        battery_percent = battery_data[0]
        print(f"当前电量: {battery_percent}%")

        # 订阅气压通知
        await client.start_notify(CHAR_NOTIFY_UUID, notification_handler)
        print("已订阅气压通知")

        # 发送 B0 指令启动气压上报
        await client.write_gatt_char(CHAR_WRITE_UUID, START_PRESSURE_REPORT_CMD)
        print("已发送启动气压上报指令，开始接收数据...")

        # 可选：重置气压（按需取消注释）
        # await client.write_gatt_char(CHAR_WRITE_UUID, RESET_PRESSURE_CMD)
        # print("已发送气压重置指令")

        print("实时气压值 (Ctrl+C 停止):")
        await asyncio.Event().wait()

    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        if client.is_connected:
            try:
                await client.stop_notify(CHAR_NOTIFY_UUID)
            except:
                pass
            await client.disconnect()
            print("已断开连接")

if __name__ == "__main__":
    asyncio.run(main())