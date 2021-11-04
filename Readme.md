Synchronization Tool for Xsens Dot
==

Introduction
--

It's a simple tool to synchronize XSENS dot just use python. it developed based on [Xsens DOT BLE protocol](D:\Data\DeskReflect\dataanalys-lufei\PyQt5-study\Xdc-live\Xsens DOT BLE Services Specifications.pdf). if you want to used xsens dot to collect datas, the first step is synchronizing the dots, This code enables xsens dots to be synchronized to a root dot which is scan the first time.



Support system
--

* windows



## Requirements

- python>=3.8

- install bleak package before

  

How to use
--

1. first open the Bluetooth
2. run the ```main.py```



TODO
--

Thanks for [Adam Kewley](https://github.com/adamkewley) sharing the [xdc (XSens DOT Connector)](https://github.com/adamkewley/xsens-dot-connector) respositories, I may write some tools to get more than one dot data and save them.



Problems
--

* it may synchronize less than four xsens dots, because it run in windows system.

* How to use python to collect several dots data at the same times is a big problems for me, **Welcome to communicate with me**

