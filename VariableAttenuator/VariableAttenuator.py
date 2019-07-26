#!/usr/bin/env python

import socket
import time
from BaseDriver import LabberDriver


class Driver(LabberDriver):
    """

    """
    address = "10.21.42.129"
    port = 23
    buffer_size = 512

    def performOpen(self, options={}):
        """
        Perform the operation of opening the instrument connection

        :param options:
        :return: NoneType
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.address, self.port))
        except Exception as e:
            self.getValueFromUserDialog(value="Don't put anything here", text=str(e), title="Burn after reading")
        else:
            self._receive()

    def performClose(self, options={}):
        """

        :param options:
        :return:
        """

        self.socket.close()

    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """

        :param quant:
        :param value:
        :param sweepRate:
        :param options:
        :return:
        """
        if quant.name == "Attenuation":
            self.set_attenuation(value)
        return value

    def performGetValue(self, quant, options={}):
        """

        :param quant:
        :param options:
        :return:
        """
        if quant.name == "Attenuation":
            return self.get_attenuation()

    def _send(self, command):
        """

        :param command:
        :return:
        """
        self.socket.send(str.encode(command + "\r\n"))
        time.sleep(0.6)
        return

    def _receive(self):
        """

        :return:
        """
        return self.socket.recv(self.buffer_size)

    def _ask(self, command):
        """

        :param command:
        :return:
        """
        self._send(command)
        return self._receive()

    def set_attenuation(self, value):
        """

        :param value:
        :return:
        """
        self._send(":SETATT={}".format(float(value)))
        self._receive()
        return value

    def get_attenuation(self):
        """

        :return:
        """
        return float(self._ask(":ATT?"))


def main():
    att = Driver()
    att.performOpen()
    print(att._ask(":MN?"))


if __name__ == "__main__":
    main()
