import asyncio
import struct
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError

# 设备信息
TARGET_NAME = "47L124000"
SERVICE_UUID = "0000180c-0000-1000-8000-00805f9b34fb"
CHAR_WRITE_UUID = "0000150a-0000-1000-8000-00805f9b34fb"   # 写特征
CHAR_NOTIFY_UUID = "0000150b-0000-1000-8000-00805f9b34fb"  # 通知特征（接收气压数据）

# 构造 B0 指令（开启气压上报，17字节）
B0_CMD = bytes.fromhex("B001D064" + "00" * 13)

def parse_pressure(data: bytearray) -> float:
    """解析气压数据包，返回气压值（单位: kPa）"""
    if len(data) < 11:
        return None
    # 取第9、10字节（小端序有符号短整型）
    pressure_bytes = data[9:11]
    raw = struct.unpack("<h", pressure_bytes)[0]
    return raw / 100.0

async def notification_handler(sender, data: bytearray):
    """气压通知回调函数"""
    pressure = parse_pressure(data)
    if pressure is not None:
        print(f"实时气压: {pressure:.2f} kPa")

async def check_bluetooth_available():
    """检查蓝牙是否可用，不可用则抛出异常"""
    try:
        # 尝试进行一次短暂扫描，如果蓝牙未开启通常 Bleak 会抛出 BleakError
        await BleakScanner.discover(timeout=2.0)
    except BleakError as e:
        raise RuntimeError("蓝牙未开启或不可用，请开启蓝牙后重试。") from e
    except Exception as e:
        # 其他异常也可能导致无法使用，统一提示
        raise RuntimeError(f"蓝牙检查失败: {e}") from e

async def main():
    # 第一步：检查蓝牙状态
    print("正在检查蓝牙状态...")
    try:
        await check_bluetooth_available()
    except RuntimeError as e:
        print(f"错误: {e}")
        return
    print("蓝牙状态正常。")

    # 第二步：扫描目标设备
    print("正在扫描设备...")
    device = await BleakScanner.find_device_by_name(TARGET_NAME, timeout=10.0)
    if device is None:
        print(f"未找到设备 {TARGET_NAME}")
        return

    print(f"找到设备: {device.name} ({device.address})")
    async with BleakClient(device) as client:
        print("已连接")

        # 启用通知特征
        await client.start_notify(CHAR_NOTIFY_UUID, notification_handler)
        print("已开启气压通知")

        # 发送 B0 指令启动主动上报
        await client.write_gatt_char(CHAR_WRITE_UUID, B0_CMD, response=False)
        print("已发送开启上报指令，接收气压数据中...（按 Ctrl+C 停止）")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n停止接收")

if __name__ == "__main__":
    asyncio.run(main())