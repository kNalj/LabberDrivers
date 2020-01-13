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
        :type options
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
        :type options:
        :return: NoneType
        """

        self.socket.close()

    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """

        :param quant:
        :param value:
        :param sweepRate: The speed at which the quantity will be swept
        :param options:
        :return:
        :rtype: None | int | float | bool | str
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
        """Send a command to the instrument. After sending a command sleep for 0.6 seconds to give the instrument
        time to do the required action.

        :param command: A command that we are sending to an instrument
        :type command: str
        :return: NoneType
        """
        self.socket.send(str.encode(command + "\r\n"))
        time.sleep(0.6)
        return

    def _receive(self):
        """
        Read the data from the instruments standard event buffer. When a command is sent to an instrument the response
        is stored in the standard event buffer. In order to obtain  the result from the instrument we have to read this
        buffer.

        :return: Content of the instruments standard event buffer after sending the command
        :rtype: str
        """
        return self.socket.recv(self.buffer_size)

    def _ask(self, command):
        """
        Send a command and instantly read a reply from the instrument. To be used when getting an instrument value.
        First we send a command to query some instrument value, instrument replies by setting that value in the
        standard event buffer. Then we read and return the value from the standard event buffer.

        :param command: A command that we are sending to an instrument
        :type command: str
        :return: Content of the instruments standard event buffer after sending the command
        :rtype: str
        """
        self._send(command)
        return self._receive()

    def set_attenuation(self, value):
        """
        A method used to set the attenuation of the instrument.

        :param value: value to which to set the attenuation to.
        :return: the very same value that was passed to the method. The one we attempted to set the attenuation to.
        :rtype: float
        """
        self._send(":SETATT={}".format(float(value)))
        self._receive()
        return value

    def get_attenuation(self):
        """
        Method that gets the value of attenuation.

        :return: Real value of the attenuation
        :rtype: float
        """
        return float(self._ask(":ATT?"))


def main():
    att = Driver()
    att.performOpen()
    print(att._ask(":MN?"))


if __name__ == "__main__":
    main()
