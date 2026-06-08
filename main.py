print("本程序没有经过实物测试如果有任何问题请联系qq:1936219518")
print("")
import asyncio
import struct
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError

# 设备信息
TARGET_NAME = "47L124000"
CHAR_WRITE_UUID = "0000150a-0000-1000-8000-00805f9b34fb"   # 写特征 (0x180C -> 0x150A)
CHAR_NOTIFY_UUID = "0000150b-0000-1000-8000-00805f9b34fb"  # 通知特征 (0x180C -> 0x150B)

# 正确的启动指令：0x50 01 D0 + 7字节填充 00（共10字节）
B0_CMD = bytes.fromhex("5001D0" + "00" * 7)

def parse_pressure(data: bytearray) -> float | None:
    """
    解析气压数据，返回 kPa 值。
    严格按照文档中 JavaScript 示例推导：
    - 数据总长 17 字节
    - data[0] = 0xD0 (HEAD)
    - data[1] = 指示灯颜色
    - data[9:11] = 气压值（小端有符号 int16）
    """
    if len(data) < 11:
        return None
    if data[0] != 0xD0:          # 非气压消息，忽略
        return None
    pressure_bytes = data[9:11]
    raw = struct.unpack("<h", pressure_bytes)[0]
    return raw / 100.0

async def notification_handler(sender, data: bytearray):
    """
    收到设备数据时：
    1. 立即输出原始数据（十六进制）
    2. 尝试解析气压值并输出
    """
    print(f"收到数据: {data.hex()}", flush=True)
    pressure = parse_pressure(data)
    if pressure is not None:
        print(f"实时气压: {pressure:.2f} kPa", flush=True)

async def check_bluetooth_available():
    """检查蓝牙是否可用"""
    try:
        await BleakScanner.discover(timeout=2.0)
    except BleakError as e:
        raise RuntimeError("蓝牙未开启或不可用，请开启蓝牙后重试。") from e
    except Exception as e:
        raise RuntimeError(f"蓝牙检查失败: {e}") from e

async def main():
    # 1. 检查蓝牙状态
    print("正在检查蓝牙状态...")
    try:
        await check_bluetooth_available()
    except RuntimeError as e:
        print(f"错误: {e}")
        return
    print("蓝牙状态正常。")

    # 2. 扫描设备
    print("正在扫描设备...")
    device = await BleakScanner.find_device_by_name(TARGET_NAME, timeout=10.0)
    if device is None:
        print(f"未找到设备 {TARGET_NAME}")
        return

    print(f"找到设备: {device.name} ({device.address})")
    async with BleakClient(device) as client:
        print("已连接")

        # 3. 先开启 Notify（监听 0x180C -> 0x150B）
        print(f"正在开启 Notify: {CHAR_NOTIFY_UUID}")
        try:
            await client.start_notify(CHAR_NOTIFY_UUID, notification_handler)
            print("已开启气压通知监听")
        except Exception as e:
            print(f"开启 Notify 失败: {e}")
            return

        # 4. 发送正确的启动指令到 0x180C -> 0x150A
        print(f"发送数据: {B0_CMD.hex()} -> 特征 {CHAR_WRITE_UUID}", flush=True)
        try:
            await client.write_gatt_char(CHAR_WRITE_UUID, B0_CMD, response=False)
            print("启动指令已发送，等待接收气压数据...（按 Ctrl+C 停止）")
        except Exception as e:
            print(f"发送指令失败: {e}")
            return

        # 5. 保持运行，接收通知
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n停止接收。")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        # 无论正常结束还是发生异常，都暂停窗口以便查看日志
        input("按回车键退出...")