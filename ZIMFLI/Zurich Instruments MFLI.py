import InstrumentDriver
import numpy as np
import os, sys, inspect, re, math
import zhinst.utils as zi
import time

#Some stuff to import ziPython from a relative path independent from system wide installations
cmd_folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile(inspect.currentframe()))[0]))
if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)


class Driver(InstrumentDriver.InstrumentWorker):
    """ This class wraps the ziPython API"""

    def performOpen(self, options={}):
        """Perform the operation of opening the instrument connection"""

        try:
            self.ziConnection = zi.autoConnect(8004, 4)
        except:
            raise InstrumentDriver.CommunicationError(
                "Could not connect to Zurich Instruments Data Server. Is it running?")
            return

        if self.comCfg.address == "":
            self.device = zi.autoDetect(self.ziConnection)
            self.log(
                "Autodetected Zurich Instruments device \"" + self.device + "\". Use the address field to set a specific device.")
        else:
            self.device = self.comCfg.address

        try:
            devtype = self.ziConnection.getByte(str('/%s/features/devtype' % self.device))
        except:
            raise InstrumentDriver.CommunicationError("Device " + self.device + " not found.")
            return

        if re.match('MF', devtype):
            self.log("Zurich Instruments device \"" + self.device + "\" has been accepted by the driver.")
        else:
            self.log("Zurich Instruments device \"" + self.device + "\" has been rejected by the driver.", 50)
            raise InstrumentDriver.CommunicationError("Device " + self.device + " is not an MF lock-in")
            return

        # Check Options
        devoptions = self.ziConnection.getByte(str('/%s/features/options' % self.device))
        detectedOptions = []
        if re.search('MOD', devoptions):
            detectedOptions.append("MOD")
        self.instrCfg.setInstalledOptions(detectedOptions)

        self.scope_module = self.ziConnection.scopeModule()

    def performClose(self, bError=False, options={}):
        """Perform the close instrument connection operation"""
        pass

    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """Perform the Set Value instrument operation. This function should
        return the actual value set by the instrument"""
        # ############# BOOLEANS ################
        if quant.name in ["SigIn1VoltageAutorange", "SigIn1VoltageAC", "SigIn1VoltageImp", "SigIn1VoltageDiff",
                          "SigIn1VoltageFloat", "SigIn1CurrentAutorange", "SigIn1CurrentFloat"] + \
                ["Demod" + str(i+1) + "Enable" for i in range(4)] + \
                ["Demod" + str(i+1) + "PhaseAdjust" for i in range(4)] + \
                ["Demod" + str(i+1) + "SincFilter" for i in range(4)] + \
                ["Demod" + str(i + 1) + "On" for i in range(4)] + \
                ["OutAmp" + str(i+1) + "Enable" for i in range(4)] + \
                ["SigOut1Enable", "SigOut1Imp50", "SigOut1Autorange", "SigOut1Add", "SigOut1Diff"]:
            self.ziConnection.setInt(str(quant.get_cmd % self.device), 1 if value else 0)
        # ############# INT COMBOS ################
        elif quant.name in ["Demod" + str(i+1) + "Osc" for i in range(4)] + \
                ["Demod" + str(i+1) + "Signal" for i in range(4)] + \
                ["Demod" + str(i+1) + "Order" for i in range(4)]:
            self.ziConnection.setInt(str(quant.get_cmd % self.device), int(quant.getCmdStringFromValue(value)))
        elif quant.name in ["SigOut1Range"]:
            self.ziConnection.setDouble(str(quant.get_cmd % self.device), float(quant.getCmdStringFromValue(value)))
        # ############# DOUBLES ################
        elif quant.name in ["SigIn1VoltageRange", "SigIn1VoltageScaling", "SigIn1CurrentRange", "SigIn1CurrentScaling"] + \
                ["Oscillator" + str(i+1) + "Frequency" for i in range(4)] + \
                ["Demod" + str(i+1) + "Harm" for i in range(4)] + \
                ["Demod" + str(i+1) + "Phase" for i in range(4)] + \
                ["Demod" + str(i+1) + "TC" for i in range(4)] + \
                ["Demod" + str(i+1) + "Rate" for i in range(4)] + \
                ["OutAmp" + str(i+1) + "VpkValue" for i in range(4)] + \
                ["SigOut1Offset"]:
            self.ziConnection.setDouble(str(quant.get_cmd % self.device), float(value))

        # ############# SPECIAL ################
        elif quant.name in ["Demod" + str(i+1) + "Mode" for i in range(4)]:
            if int(quant.getCmdStringFromValue(value)) == 0:
                self.ziConnection.setInt(str(quant.get_cmd % (self.device, "enable")), 0)
            else:
                self.ziConnection.setInt(str(quant.get_cmd % (self.device, "automode")), int(quant.getCmdStringFromValue(value)))
                self.ziConnection.setInt(str(quant.get_cmd % (self.device, "enable")), 1)
        elif quant.name in ["LowPassFilter" + str(x+1) + "Bw3db" for x in range(8)]:
            order_cmd = "/{}/demods/{}/order".format(self.device, str(int(quant.name[13])-1))
            order = self.ziConnection.getDouble(str(order_cmd))
            value = zi.bw2tc(value, order)
            self.ziConnection.setDouble(str(quant.get_cmd % self.device), float(value))
        elif quant.name in ["LowPassFilter" + str(x+1) + "BwNep" for x in range(8)]:
            quotes = {1: 0.2500, 2: 0.1250, 3: 0.0938, 4: 0.0781, 5: 0.0684, 6: 0.0615, 7: 0.0564, 8: 0.0524}
            order_cmd = "/{}/demods/{}/order".format(self.device, str(int(quant.name[13])-1))
            order = self.ziConnection.getDouble(str(order_cmd))
            tc = quotes[order] / value
            self.ziConnection.setDouble(str(quant.get_cmd % self.device), float(tc))
        elif quant.name in ["OutAmp1VrmsValue"]:
            self.ziConnection.setDouble(str(quant.get_cmd % self.device), float(value) * math.sqrt(2))

        # ##################################################################
        # ###################### ASYNC COMMANDS ############################
        # ##################################################################
        return value

    def performGetValue(self, quant, options={}):
        if self.isFirstCall(options):
            self.resultBuffer = {}
            self.traceBuffer = {}
        """Perform the Get Value instrument operation"""
        # proceed depending on quantity
        # ############# BOOLEANS ################
        if quant.name in ["SigIn1VoltageAutorange", "SigIn1VoltageAC", "SigIn1VoltageImp", "SigIn1VoltageDiff",
                          "SigIn1VoltageFloat", "SigIn1CurrentAutorange", "SigIn1CurrentFloat"] + \
                ["Demod" + str(i + 1) + "Enable" for i in range(4)] + \
                ["Demod" + str(i + 1) + "PhaseAdjust" for i in range(4)] + \
                ["Demod" + str(i + 1) + "SincFilter" for i in range(4)] + \
                ["Demod" + str(i + 1) + "On" for i in range(4)] + \
                ["OutAmp" + str(i + 1) + "Enable" for i in range(4)] + \
                ["SigOut1Enable", "SigOut1Imp50", "SigOut1Autorange", "SigOut1Add", "SigOut1Diff"]:
            return self.ziConnection.getInt(str(quant.get_cmd % self.device)) > 0
        # ############# COMBOS ################
            # ### INT ###
        elif quant.name in ["Demod" + str(i+1) + "Osc" for i in range(4)] + \
                ["Demod" + str(i + 1) + "Signal" for i in range(4)] + \
                ["Demod" + str(i + 1) + "Order" for i in range(4)]:
            return quant.getValueFromCmdString(self.ziConnection.getInt(str(quant.get_cmd % self.device)))
            # ### DOUBLE ###
        elif quant.name in ["SigOut1Range"]:
            return quant.getValueFromCmdString(self.ziConnection.getDouble(str(quant.get_cmd % self.device)))
        # ############# DOUBLES ################
        elif quant.name in ["SigIn1VoltageRange", "SigIn1VoltageScaling", "SigIn1CurrentRange", "SigIn1CurrentScaling"] + \
                ["Oscillator" + str(i+1) + "Frequency" for i in range(4)] + \
                ["Demod" + str(i + 1) + "Harm" for i in range(4)] + \
                ["Demod" + str(i + 1) + "Freq" for i in range(4)] + \
                ["Demod" + str(i + 1) + "Phase" for i in range(4)] + \
                ["Demod" + str(i + 1) + "TC" for i in range(4)] + \
                ["Demod" + str(i + 1) + "Rate" for i in range(4)] + \
                ["Demod" + str(i + 1) + "SamplingRate" for i in range(4)] + \
                ["OutAmp" + str(i+1) + "VpkValue" for i in range(4)] + \
                ["SigOut1Offset"]:
            return self.ziConnection.getDouble(str(quant.get_cmd % self.device))

        # ############# SPECIAL ################
        elif quant.name in ["Demod" + str(i+1) + "Mode" for i in range(4)]:
            enabled = self.ziConnection.getInt(quant.get_cmd % (self.device, "enable"))
            automode = self.ziConnection.getInt(quant.get_cmd % (self.device, "automode"))

            if enabled == 0:
                return quant.getValueFromCmdString(enabled)
            else:
                return quant.getValueFromCmdString(automode)

        elif quant.name in ["LowPassFilter" + str(x + 1) + "Bw3db" for x in range(8)]:
            order_cmd = "/{}/demods/{}/order".format(self.device, str(int(quant.name[13]) - 1))
            order = self.ziConnection.getDouble(str(order_cmd))
            tc_cmd = "/{}/demods/{}/timeconstant".format(self.device, str(int(quant.name[13]) - 1))
            tc = self.ziConnection.getDouble(str(tc_cmd))
            value = zi.tc2bw(tc, order)
            return value
        elif quant.name in ["LowPassFilter" + str(x + 1) + "BwNep" for x in range(8)]:
            quotes = {1: 0.2500, 2: 0.1250, 3: 0.0938, 4: 0.0781, 5: 0.0684, 6: 0.0615, 7: 0.0564, 8: 0.0524}
            order_cmd = "/{}/demods/{}/order".format(self.device, str(int(quant.name[13]) - 1))
            order = self.ziConnection.getDouble(str(order_cmd))
            tc_cmd = "/{}/demods/{}/timeconstant".format(self.device, str(int(quant.name[13]) - 1))
            tc = self.ziConnection.getDouble(str(tc_cmd))
            value = 1 / tc * quotes[order]
            return value
        elif quant.name in ["OutAmp1VrmsValue"]:
            return self.ziConnection.getDouble(quant.get_cmd % self.device) / math.sqrt(2)

        # ############# Read-out channels of demods ################
        elif quant.name in ['Demod' + str(x + 1) + 'R' for x in range(4)] + \
                 ['Demod' + str(x + 1) + 'phi' for x in range(4)] + \
                 ['Demod' + str(x + 1) + 'X' for x in range(4)] + \
                 ['Demod' + str(x + 1) + 'Y' for x in range(4)]:
            method = self.getValue("DAQMethod")
            if method == "getSample()":
                return self.performGetSample(quant)
            elif method == "poll()":
                return self.performPoll(quant, options)

        # ############################################################################
        # ############################# ASYNC COMMANDS ###############################
        # ############################################################################

        # COMBO BOXES
        return quant.getValue()

    def performGetSample(self, quant):
        """


        :param quant: Quantity that we want to get
        :return: Last obtained value of the specified quantity
        """
        if quant.get_cmd in self.resultBuffer.keys():
            data = self.resultBuffer[quant.get_cmd]
        else:
            data = self.ziConnection.getSample(str(quant.get_cmd % self.device))
            self.resultBuffer[quant.get_cmd] = data
        channel = quant.name[6:]
        if channel == "X":
            return data["x"][0]
        elif channel == "Y":
            return data["y"][0]
        elif channel == "R":
            return math.sqrt(data["x"][0] ** 2 + data["y"][0] ** 2)
        elif channel == "phi":
            return math.degrees(math.atan2(data["y"][0], data["x"][0]))
        return float('nan')

    def performPoll(self, quant, options):
        """
        Method that subscribes to a certain node of ZIMFLI. Gets the data over time (and at a rate) specified in the
        user interface. Since the method subscribes to a whole node (example: demod 3) data for a specified quantity
        (such as X, Y, R, phi) needs to be extracted from the result, and averaged to get just one number as a return
        value.

        :param quant: Quantity being subscribed to and polled
        :return: Average of all the polled data
        """

        if quant.get_cmd % self.device in self.resultBuffer.keys():
            data = self.resultBuffer[quant.get_cmd % self.device]
        else:
            rate = self.getValue(quant.name[:6] + "SamplingRate")
            self.sendValueToOther(quant.name[:6] + "SamplingRate", rate)
            recording_time = self.getValue("PollRecordingTime")
            timeout = self.getValue("PollTimeout")
            self.ziConnection.subscribe(quant.get_cmd % self.device)
            self.ziConnection.sync()
            time.sleep(0.005)  # Make sleep depend on recording time
            data = self.ziConnection.poll(recording_time, int(timeout), 0, True)
            self.resultBuffer[quant.get_cmd % self.device] = data

        channel = quant.name[6:]
        if channel == "X":
            return np.average(data[quant.get_cmd % self.device]["x"])
        elif channel == "Y":
            return np.average(data[quant.get_cmd % self.device]["y"])
        elif channel == "R":
            return math.sqrt(
                np.average(data[quant.get_cmd % self.device]["x"]) ** 2 + np.average(data[quant.get_cmd % self.device]["y"]) ** 2
            )
        elif channel == "phi":
            return math.degrees(math.atan2(np.average(data[quant.get_cmd % self.device]["x"]),
                                           np.average(data[quant.get_cmd % self.device]["y"])))

        return 45.0


if __name__ == "__main__":
    print("LSDKGH")
