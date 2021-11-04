# 本模块对多个设备进行同时同步
import struct
import time
import binascii
import asyncio  # for async BLE IO
from bleak import BleakScanner, BleakClient  # for BLE communication


def xuuid(hexnum):
    XSENS_BASE_UUID = "1517____-4947-11E9-8646-D663BD873D93"
    s = hex(hexnum)[2:]
    assert len(s) == 4
    return XSENS_BASE_UUID.replace("____", s)


class ResponseReader:

    def __init__(self, data):
        self.pos = 0
        self.data = data

    # parse arbitrary byte sequence as little-endian integer
    def b2i(b, signed=False):
        resp_int = int.from_bytes(b, "little", signed=False)  # 把十六进制bytes类型数据变为十进制的数据，反序，不反码；如b'\x01\x01\x07' 变为 459009
        return resp_int

    # returns number of remaining bytes
    def rem(self):
        return len(self.data) - self.pos

    # extract n raw bytes 可以读任意个bytes的数据
    def raw(self, n):
        rv = self.data[self.pos:self.pos + n]
        self.pos += n
        return rv

    # read 1 byte as int
    def u8(self):
        return ResponseReader.b2i(self.raw(1))

    # read 2 bytes as int
    def u16(self):
        return ResponseReader.b2i(self.raw(2))

    # read 4 bytes as int
    def u32(self):
        return ResponseReader.b2i(self.raw(4))

    # read 8 bytes as int
    def u64(self):
        return ResponseReader.b2i(self.raw(8))

    # read 4 bytes as a IEE754 float,用于浮点数定位
    def f32(self):
        return struct.unpack('f', self.raw(4))


# 给dot发送控制同步的相关消息
class MessageControl:
    # UUID string
    UUID = xuuid(0x7001)

    def __repr__(self):  # 定义成特殊变量，可以直接访问
        return pretty_print(self)


# 接收控制dot后，dot对自己发送的回应消息Ack
class MessageAcknowledge:
    # UUID string
    UUID = xuuid(0x7002)

    def read(r):
        '''用于接收ack信息'''
        assert r.rem() >= 4

        rv = MessageAcknowledge()
        rv.ack_mid = r.raw(1)
        rv.len = r.raw(1)
        reb = int.from_bytes(rv.len, 'little')  # 读取的是后面syid和sydata的长度
        rv.syid = r.raw(1)  # syid占去一个bytes
        rv.sydata = r.raw(reb - 1)
        rv.ack_checksum = r.raw(1)  # 读取最后一个bytes的checksum数据

        print('Acknowledge message:', rv.ack_mid.hex(),rv.len.hex(), rv.syid.hex(), rv.sydata.hex(), rv.ack_checksum.hex())

        return rv

    #
    def parse(b):
        r = ResponseReader(b)
        return MessageAcknowledge.read(r)

    def __repr__(self):  # 定义成特殊变量
        # ，可以直接访问
        return pretty_print(self)


# 接受dot发送的通知消息
class MessageNotification:
    # UUID string
    UUID = xuuid(0x7003)

    def read(r):
        assert r.rem() >= 3

        rv = MessageNotification()
        rv.mid = r.raw(1)
        rv.len = r.u8()  # len
        # 读取len长度的bytes
        rv.data = r.raw(rv.len)
        rv.checksum = r.raw(1)

        return rv

    def parse(b):
        r = ResponseReader(b)
        return MessageNotification.read(r)

    def __repr__(self):  # 定义成特殊变量
        # ，可以直接访问
        return pretty_print(self)


# 进行同步的各种操作类（包括start/stop/get_status。。。）
class SyncControl:

    def __init__(self):
        self.get_sync_status_bytes = b'\x02\x01\x08\xF5'  # 获取同步状态指令 b'\x02\x01\x08\xF5';bytes([2]) + bytes([1]) + bytes([8]) + bytes([245])
        self.stop_sync_bytes = b'\x02\x01\x02\xFB'  # 停止同步指令
        self.start_sync_bytes = b''  # 还要再后面加上mac和checksum
        self.sync_status_result = [] # 建立一个用于记录传感器是否同步的列表，已同步的dot加True

        self.mes_c = MessageControl()
        self.notify = MessageNotification()
        self.ack = MessageAcknowledge()

    def cal_checksum(self, str16):
        '''
        计算偶数长度的十六进制的checksum值
        :param str16: 传入字符串形式的16进制的字符串
        :return:
        '''
        sum = 0
        for i in range(0, len(str16), 2):
            # print(lis[i:i+2])
            mac_str2 = str16[i:i + 2]
            mac_2b = binascii.unhexlify(mac_str2)
            data = int.from_bytes(mac_2b, 'little')
            sum += data
        checksum_bytes = bytes([-sum & 0xff])  # 注意这里要用bytes()函数，不能用hex()函数（取的是数字），

        return checksum_bytes

    def handle_mac_addr(self, mac_addr):
        '''
        用于处理根dot的同步mac地址
        :param mac_addr: 根节点的mac地址：'D4:CA:6E:F1:73:27'
        :return: None
        '''
        mac_addr_list = mac_addr.split(':')
        mac_addr_list.reverse()  # BLE协议中要求进行反转
        mac_str = ''.join(mac_addr_list)  # 转换成16进制字符串

        checksum_str = '020701' + mac_str  # 拼接出checksum的16进制字符
        checksum_bytes = self.cal_checksum(checksum_str)
        self.start_sync_bytes = binascii.unhexlify(checksum_str) + checksum_bytes

    async def get_sync_status(self, *args):
        '''获取dot的同步信息的notify'''
        sync_status = False # 记录所连接的所有dot是否都同步了

        def callback(sender: int, data: bytearray):
            print(f"notify:长度--{sender}；内容--{data.hex()[:10]}")  # 其中的前10个是有效的
            # notify返回的消息种类只有50和51
            if '4' in data.hex():
                self.sync_status_result.append(True)
                print('已经同步成功！')
            else:
                self.sync_status_result.append(False)
                print('暂未同步！')

        for client in args[0]:
            await client.start_notify(self.notify.UUID, callback)
            await client.write_gatt_char(self.mes_c.UUID, self.get_sync_status_bytes, True)
            await asyncio.sleep(0.2)  # 等待获取到的notify 有待修改，更新速度
            await client.stop_notify(self.notify.UUID)

        if False not in self.sync_status_result:
            sync_status = True

        return sync_status



    async def start_sync(self, *args):
        '''对root_mac发送指令，让他进行广播，断开root_mac，然后对其它dot发送指令，告诉他们向root_mac进行同步'''
        clients = args[0]
        root_mac = clients[0].address
        self.handle_mac_addr(root_mac)  # 加根节点的mac地址
        print('正在发送的同步报文：', self.start_sync_bytes.hex(), '报文长度：', len(self.start_sync_bytes))
        print('被同步的dot的mac地址：', root_mac)

        await clients[0].write_gatt_char(self.mes_c.UUID, self.start_sync_bytes, True)
        await clients[0].disconnect()

        for client in clients[1:]:
            await client.write_gatt_char(self.mes_c.UUID, self.start_sync_bytes)
            print('[%s]---dot正在被同步' % client.address)
            await client.disconnect()
        time.sleep(14)  # 等待同步时间，后期可以加上进度条，或者完善速度,要绝对的停止，使用asyncio.sleep()可能会运行后面的代码

        for client in clients:
            await client.connect()
            while not client.is_connected:
                await client.connect()
            print(client.is_connected)
            print('[%s]---dot已经重新连接！' % client.address)
            resp = await client.read_gatt_char(self.ack.UUID)
            MessageAcknowledge.parse(resp)
            print(resp)

        self.start_sync_bytes = '020701'  # 下一次可以正常的运行


    async def stop_sync(self, *args):
        '''获取dot的同步信息的notify'''

        def callback(sender: int, data: bytearray):
            print(f"notify:长度--{sender}；内容--{data.hex()[:10]}")  # 其中的前10个是有效的

        for client in args[0]:
            await client.start_notify(self.notify.UUID, callback)
            await client.write_gatt_char(self.mes_c.UUID, self.stop_sync_bytes, True)
            await asyncio.sleep(0.2)  # 等待获取到的notify
            await client.stop_notify(self.notify.UUID)


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


async def run():
    sync_c = SyncControl()
    ble_list = await scan_for_DOT_BLEDevices()
    clients = []
    for ble in ble_list:
        client = BleakClient(ble)
        clients.append(client)
        await client.connect()
        while not client.is_connected:  # 建立一个循环，保证dot一直连接状态
            await client.connect()
    try:
        # 先进行判断是否同步了
        sync_res = await sync_c.get_sync_status(clients)
        if not sync_res:
            await sync_c.start_sync(clients)

    except Exception as e:
        print(e)

    finally:
        for client in clients:
            await client.disconnect()


# loop = asyncio.get_event_loop()
# loop.run_until_complete(run())
