import InstrumentDriver
import numpy as np
import os, sys, inspect, re, math
import zhinst.utils as zi

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
                ["OutAmp" + str(i+1) + "Enable" for i in range(4)] + \
                ["SigOut1Enable", "SigOut1Imp50", "SigOut1Autorange", "SigOut1Add", "SigOut1Diff"]:
            self.ziConnection.setInt(str(quant.get_cmd % self.device), 1 if value else 0)
        # ############# INT COMBOS ################
        elif quant.name in ["Demod" + str(i+1) + "Osc" for i in range(4)] + \
                ["Demod" + str(i+1) + "Signal" for i in range(4)] + \
                ["Demod" + str(i+1) + "Order" for i in range(4)] + \
                ["Demod" + str(i+1) + "TC" for i in range(4)] + \
                ["Demod" + str(i+1) + "Rate" for i in range(4)]:
            self.ziConnection.setInt(str(quant.get_cmd % self.device), int(quant.getCmdStringFromValue(value)))
        elif quant.name in ["SigOut1Range"]:
            self.ziConnection.setDouble(str(quant.get_cmd % self.device), float(quant.getCmdStringFromValue(value)))
        # ############# DOUBLES ################
        elif quant.name in ["SigIn1VoltageRange", "SigIn1VoltageScaling", "SigIn1CurrentRange", "SigIn1CurrentScaling"] + \
                ["Oscillator" + str(i+1) + "Frequency" for i in range(4)] + \
                ["Demod" + str(i+1) + "Harm" for i in range(4)] + \
                ["Demod" + str(i+1) + "Freq" for i in range(4)] + \
                ["Demod" + str(i+1) + "Phase" for i in range(4)] + \
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
                ["OutAmp" + str(i + 1) + "Enable" for i in range(4)] + \
                ["SigOut1Enable", "SigOut1Imp50", "SigOut1Autorange", "SigOut1Add", "SigOut1Diff"]:
            return self.ziConnection.getInt(str(quant.get_cmd % self.device)) > 0
        # ############# COMBOS ################
            # ### INT ###
        elif quant.name in ["Demod" + str(i+1) + "Osc" for i in range(4)] + \
                ["Demod" + str(i + 1) + "Signal" for i in range(4)] + \
                ["Demod" + str(i + 1) + "Order" for i in range(4)] + \
                ["Demod" + str(i + 1) + "TC" for i in range(4)] + \
                ["Demod" + str(i + 1) + "Rate" for i in range(4)]:
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
                ["OutAmp" + str(i+1) + "VpkValue" for i in range(4)] + \
                ["SigOut1Offset"]:
            return self.ziConnection.getDouble(str(quant.get_cmd % self.device))

        # ############# SPECIAL ################
        elif quant.name in ["Demod" + str(i+1) + "Mode" for i in range(4)]:
            enabled = self.ziConnection.getInt(quant.get_cmd % (self.device, "enabled"))
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
        # ############################################################################
        # ############################# ASYNC COMMANDS ###############################
        # ############################################################################

        # COMBO BOXES
        return quant.getValue()


if __name__ == "__main__":
    print("LSDKGH")