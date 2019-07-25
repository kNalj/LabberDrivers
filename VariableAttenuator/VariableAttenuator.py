import InstrumentDriver
import socket


class Driver(InstrumentDriver):
    """

    """
    address = ""
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
            self.socket.connect(self.address, self.port)
        except Exception as e:
            self.getValueFromUserDialog(value="Don't put anything here", text=str(e), title="Burn after reading")
        else:
            self._receive()
        return

    def preformClose(self, bError=False, options={}):
        """

        :param bError:
        :param options:
        :return:
        """

        self.socket.close()

    def _send(self, command):
        """

        :param command:
        :return:
        """
        self.socket.send(str.encode(command + "\r\n"))
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

    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """

        :param quant:
        :param value:
        :param sweepRate:
        :param options:
        :return:
        """



def main():
    att = Driver()
    att.performOpen()
    print(att._ask(":MN?"))


if __name__ == "__main__":
    main()