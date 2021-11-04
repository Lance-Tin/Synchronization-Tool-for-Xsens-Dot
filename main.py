# 主程序入口
import asyncio  # for async BLE IO
from bleak import BleakScanner, BleakClient  # for BLE communication
import Synchronize

# 扫描设备函数
async def scan_for_DOT_BLEDevices():
    # scanners: https://bleak.readthedocs.io/en/latest/api.html#scanning-clients
    ble_devices = await BleakScanner.discover()
    rv = []
    for ble_device in ble_devices:
        # BLEDevice: https://bleak.readthedocs.io/en/latest/api.html#class-representing-ble-devices
        if "xsens dot" in ble_device.name.lower():  # 手动过滤
            rv.append(ble_device)
            print(rv[-1].address, 'has been found')
    return rv  # 这里的rv是名称加地址，可以使用.address方法返回其MAC地址


# 运行主设备
async def main():
    sync_c = Synchronize.SyncControl()
    ble_list = await scan_for_DOT_BLEDevices()
    clients = []

    for ble in ble_list:
        client = BleakClient(ble)
        clients.append(client)
        await client.connect()
        while not client.is_connected:  # 建立一个循环，保证dot一直连接状态
            await client.connect()
            await asyncio.sleep(2) # 给3秒的时间进行连接
            break

    try:
        # 先进行heading reset操作
        # 先进行判断是否同步了
        sync_res = await sync_c.get_sync_status(clients)
        if not sync_res:
            await sync_c.start_sync(clients)

        # 调用数据采集模块开始进行数据采集

    except Exception as e:
        print(e)

    finally:
        for client in clients:
            await client.disconnect()


loop = asyncio.get_event_loop()
loop.run_until_complete(main())