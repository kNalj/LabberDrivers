from BaseDriver import LabberDriver
import numpy as np
import serial
import logging


class Driver(LabberDriver):
    fullrange = 8192
    halfrange = fullrange / 2
    communication_bytes = 4
    numdacs = 16
    pol_num = np.zeros(numdacs)
    polarity = ['BIP', 'BIP', 'BIP', 'BIP']

    def performOpen(self, options={}):
        """
        Perform the operation of opening the instrument connection

        :param options:
        :return:
        """

        self.ser = serial.Serial()
        self.ser.port = "COM5"
        self.ser.baudrate = 10000000
        self.ser.bytesize = serial.EIGHTBITS  # number of bits per bytes
        self.ser.parity = serial.PARITY_ODD  # set parity check: no parity
        self.ser.stopbits = serial.STOPBITS_ONE  # number of stop bits
        self.ser.timeout = 1  # non-block read
        self.ser.xonxoff = False  # disable software flow control
        self.ser.rtscts = False  # disable hardware (RTS/CTS) flow control
        self.ser.dsrdtr = False  # disable hardware (DSR/DTR) flow control

        try:
            self.ser.open()
        except:
            logging.warning('Error open serial port')
            print('error open serial port')
            self.ser.close()
            self.ser.open()
            raise Exception()

        if not self.ser.isOpen():
            logging.error('Serial port not open')
            print('serial port not open')
            raise Exception()
        else:
            for i in range(int(self.numdacs / 4)):
                self.set_pol_dacrack(self.polarity[i], np.arange(1 + i * 4, 1 + (i + 1) * 4), get_all=False)

        logging.info('Serial port opened: ' + self.ser.portstr)

    def performClose(self, options={}):
        """
        Perform the close instrument connection operation.

        :param options:
        :return: NoneType
        """
        logging.debug('Closing serial connection')
        print('closing serial connection')

        self.ser.close()

    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """
        Perform the Set Value instrument operation. This function should return the actual value set by the instrument

        :param quant: Quantity to be changed
        :type quant:
        :param value: Value to which to set the parameter to
        :type value:
        :param sweepRate: How fast should the value change
        :type sweepRate: float
        :param options:
        :return:
        :rtype: None | int | float | str
        """

        if quant.name in ['Dac1', 'Dac2', 'Dac3', 'Dac4', 'Dac5', 'Dac6', 'Dac7', 'Dac8']:
            dacNr = int(list(quant.name)[-1])

            self.do_set_dac(value, dacNr)

            self.wait(0.005)  # NOTE: really needed?

        if 'Polarity' in quant.name:
            if not value.upper() in ['POS', 'NEG', 'BIP']:
                raise Exception('Value should be POS, NEG, BIP')
            quant.setValue(value.upper())
            pass

        return value

    def performGetValue(self, quant, options={}):
        """
        Get the current value of certain quantity.

        :param quant:
        :type quant:
        :param options:
        :return:
        :rtype
        """
        if quant.name in ['Dac1', 'Dac2', 'Dac3', 'Dac4', 'Dac5', 'Dac6', 'Dac7', 'Dac8']:
            dacNr = int(list(quant.name)[-1])
            if dacNr < 1 or dacNr > 8:
                raise Exception('Invalid dacNr')
            pol_offset = self._polarity_offset(dacNr)

            logging.info('Reading dac%s', dacNr)
            mvoltages = self._get_dacs()
            logging.info(mvoltages)
            return mvoltages[dacNr - 1]

        if 'Polarity' in quant.name:
            value = quant.getValue()

        return value

    def _polarity_offset(self, dacNr):
        """
        Read the polarity of a certain dac and return the offset according to the polarity.

        :param dacNr: number of dac that is being changed
        :type dacNr:
        :return:
        """
        # first ask for the polarity
        if dacNr < 1 or dacNr > 8:
            raise Exception('dacNr invalid')
        if dacNr <= 4:
            polarity = self.readValueFromOther('Polarity 1-4')
        elif dacNr <= 8:
            polarity = self.readValueFromOther('Polarity 5-8')

        # set the offset according to the polarity
        if polarity == 'NEG':
            pol_offset = 4000
        elif polarity == 'BIP':
            pol_offset = 2000
        elif polarity == 'POS':
            pol_offset = 0
        return pol_offset

    def reset(self):
        '''
        Resets all dacs to 0 volts

        Input:
            None

        Output:
            None
        '''
        logging.info('Resetting instrument')
        self.set_dacs_zero()
        self.get_all()

    def set_dacs_zero(self):
        for i in range(self.numdacs):
            self.do_set_dac(0, i + 1)

    def reinitialize_dacs(self):
        bytetosend = 0b11100000  # 111 is a re init all dacs
        message = "%c" % (bytetosend)
        reply = self._send_and_read(message.encode(), self.communication_bytes)
        return reply

    # Conversion of data
    def _mvoltage_to_bytes(self, mvoltage):
        """
        Converts a mvoltage on a -4V to 4V scale to a 20-bit equivalent
        output is a list of three bytes

        Input:
            mvoltage (float) : a mvoltage in the -4000mV-4000mV range

        Output:
            (dataH, dataL) (int, int) : The high and low value byte equivalent
        """

        bytevalue = int(round((mvoltage + self.halfrange) / self.fullrange * 1048575.0))
        return bytevalue

    def _numbers_to_mvoltages(self, byte_mess):
        """
        Converts a list of bytes to a list containing
        the corresponding mvoltages
        """
        values = list(range(self.numdacs))
        for i in range(self.numdacs):
            # takes two bytes, converts it to a 20 bit int and then divides by
            # the range and adds the offset due to the polarity (not implemented)

            values[i] = ((byte_mess[5 + 4 * i] * 65536 + byte_mess[6 + 4 * i] * 256 + byte_mess[7 + 4 * i]) /
                         1048575.0 * self.fullrange) - self.halfrange  # + self.pol_num[i] #need to shift by 4 bytes, 3 data bytes and 1 for the channel!
        return values

    # Communication with device
    def do_get_dac(self, channel):
        """
        Returns the value of the specified dac

        Input:
            channel (int) : 1 based index of the dac

        Output:
            voltage (float) : dacvalue in mV
        """
        logging.info('Reading dac%s', channel)
        mvoltages = self._get_dacs()
        logging.info(mvoltages)
        return mvoltages[channel - 1]

    def do_set_dac(self, mvoltage, channel):
        """
        Sets the specified dac to the specified voltage

        Input:
            mvoltage (float) : output voltage in mV
            channel (int)    : 1 based index of the dac

        Output:
            reply (string) : errormessage
        """
        logging.info('Setting dac%s to %.04f mV', channel, mvoltage)
        mvoltage = self._mvoltage_to_bytes(mvoltage)
        mvoltage_bytes = [0, 0, 0]
        mvoltage_bytes = [mvoltage >> i & 0xff for i in (16, 8, 0)]  # 0xff is 255
        channel = (int(channel) - 1) | 0b10000000  # 100 is a write operation
        message = [channel, mvoltage_bytes[0], mvoltage_bytes[1],
                   mvoltage_bytes[2]]  # generates the 4 byte message to send to the modem
        reply = self._send_and_read(message, self.communication_bytes)  # sends the message and reads the reply
        return reply

    def do_set_dac_fast(self, mvoltage, channel):  # added by Daniel, seems to work

        if channel > 4:
            print('Error: Only channels 1-4 have fast setting.')
        else:

            logging.info('Setting dac%s to %.04f mV', channel, mvoltage)
            mvoltage = self._mvoltage_to_bytes(mvoltage)
            mvoltage_bytes = [0, 0, 0]
            mvoltage_bytes = [mvoltage >> i & 0xff for i in (16, 8, 0)]
            channel = (int(channel) - 1) | 0b11000000  # 110 is a write fast operation
            message = [channel, mvoltage_bytes[0], mvoltage_bytes[1], mvoltage_bytes[2]]

            reply = self._send_and_read(message, 0)

            return reply

    def do_set_dacs_fast(self, mvoltages=[0, 0, 0, 0]):  # added by Daniel, 20.11.2019
        """
        Sets the first 4 dacs to the specified voltages
        mvoltages is an array or a list of voltages in mV, index 0 is for DAC1...index 3 is for DAC4
        The sent message consists of 1 byte to define the function and then 3 bytes per channel for a total of 13 bytes

        """

        if len(
                mvoltages) < 4:  # if less than 4 values are given the last DAC value on the missing channels should be set? or 0?
            print('Error: 4 entries have to be given, 1 for each DAC')

        else:

            channel = 1  # the channel for this function is fixed but we don't change the function too much in order to keep it readable
            channel = (int(channel) - 1) | 0b10100000  # 101 is a write fast operation to the first 4 DACS
            message = [channel]  # probably the channel doesnt even matter
            # logging.info('Setting dac 1-4 fast to %.04f mV', channel, mvoltage)
            for index in range(0, 4):
                mvoltage = self._mvoltage_to_bytes(mvoltages[index])
                mvoltage_bytes = [0, 0, 0]
                mvoltage_bytes = [mvoltage >> i & 0xff for i in (16, 8, 0)]
                message.append(mvoltage_bytes[0])
                message.append(mvoltage_bytes[1])
                message.append(mvoltage_bytes[2])

            reply = self._send_and_read(message, 0)

            return reply

    # not yet implemented
    # def do_ramp_dac(self, mvoltage, channel):  #added by Daniel, fucks it up completly right now...
    # 	if channel>2:
    # 		print('Error: Only channels 1-2 have ramping.')
    # 	else:

    # 		logging.info('Setting dac%s to %.04f mV', channel, mvoltage)
    # 		mvoltage = self._mvoltage_to_bytes(mvoltage)
    # 		mvoltage_bytes = [0,0]
    # 		mvoltage_bytes = [mvoltage >> i & 0xff for i in (8,0)]
    # 		channel = (int(channel)-1) | 0b10100000 #110 is a ramp operation
    # 		message = [channel,mvoltage_bytes[0], mvoltage_bytes[1]]

    # 		reply = self._send_and_read(message, self.communication_bytes)

    # 		return reply

    def do_set_trigger(self):
        """
        Sets the trigger; trigger is 1ms and around 4.2V

        Input:
            none
        Output:
            reply (string) : errormessage
        """
        logging.debug('Trigger out')
        message = "%c%c%c%c" % (4, 0, 2, 6)
        reply = self._send_and_read(message.encode(), 0)
        return reply

    def get_dacs(self):
        mvoltages = self._get_dacs()
        for i in range(self.numdacs):
            print('dac{}: '.format(i + 1) + str(mvoltages[i]))
        return mvoltages

    def _get_dacs(self):
        """
        Reads from device and returns all dacvoltages in a list

        Input:
            None

        Output:
            voltages (float[]) : list containing all dacvoltages (in mV)
        """
        logging.debug('Getting dac voltages from instrument')

        # first 3 bit are control, last 5 DAC number
        message = '\x40'  # 0b01000000 = 010 = read all dacs
        reply = self._send_and_read(message.encode(), self.numdacs * self.communication_bytes + 4)
        mvoltages = self._numbers_to_mvoltages(reply)
        return mvoltages

    def _send_and_read(self, message, bytestoread):
        """
        Send <message> to the device and read answer.
        Raises an error if one occurred
        Returns a list of bytes

        Input:
            message (string)    : string conform the IST_20 protocol

        Output:
            data_out_numbers (int[]) : return message
        """
        logging.info('Sending %r', message)

        # clear input buffer
        self.ser.flushInput()
        self.ser.write(message)  # NEW

        s = 0
        repetition = 0
        data1 = []
        while s < bytestoread:
            if repetition > 2:
                break
            char = self.ser.read()
            if char:  # empty string evaluates to False
                data1.append(ord(char))
                # logging.info(s)
                s = s + 1
                repetition = 0
            else:
                repetition += 1
        # data1 = [ord(s) for s in data1]
        # data2 = np.reshape(data1,(-1,4))
        # logging.info('finished reading')
        # data2 = np.uint32(data1) #from string to 32bit
        data2 = data1
        # logging.info('converted to uint32')
        # logging.info('sendAndRead: %s', data2)

        return data2

    def set_pol_dacrack(self, flag, channels, get_all=True):
        '''
        Changes the polarity of the specified set of dacs

        Input:
            flag (string) : 'BIP', 'POS' or 'NEG'
            channel (int) : 0 based index of the rack
            get_all (boolean): if True (default) perform a get_all

        Output:
            None
        '''
        flagmap = {'NEG': -self.fullrange, 'BIP': -self.halfrange, 'POS': 0}
        if flag.upper() not in flagmap:
            raise KeyError('Tried to set invalid dac polarity %s', flag)

        val = flagmap[flag.upper()]
        for ch in channels:
            self.pol_num[ch - 1] = val
        # self.set_parameter_bounds('dac%d' % (i+1), val, val +
        # self.Fullrange.0)

        if get_all:
            self.get_all()

    def get_numdacs(self):
        """
        Get the number of DACS.

        :return:
        """
        return self.numdacs

    def _gen_ch_set_func(self, fun, ch):
        """

        :param fun:
        :param ch:
        :return:
        """

        def set_func(val):
            return fun(val, ch)

        return set_func

    def _gen_ch_get_func(self, fun, ch):
        """

        :param fun:
        :param ch:
        :return:
        """

        def get_func():
            return fun(ch)

        return get_func

    def get_all(self):
        """

        :return:
        """
        return self.snapshot(update=True)
