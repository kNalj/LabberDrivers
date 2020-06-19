#!/usr/bin/env python

import numpy as np
import os.path
import logging
import socket
import time
from BaseDriver import LabberDriver


class Driver(LabberDriver):
    """
    This class is an implementation of the AMI430 magnet with two AMI430 instruments for z and y axis. To be able to
    connect to this instrument read the IPs of each of the magnet axis manually on the instrument and palce them in
    appropriate variables (z_magnet_IP and y_magnet_IP).

    """

    z_magnet_IP = ""
    z_magnet_PORT = 7180
    y_magnet_IP = ""
    y_magnet_PORT = 7180

    BUFFSIZE = 1024
    CONNECTED_MAGNETS = {"z": False, "y": False}

    radius = 0
    phi = 0

    # Calculated from this instruments spec sheet
    combined_field_limit = 2.99 - 0.1  # 0.1 just to be sure
    # Restart treshold should be at 2.8 (for testing purposes it is changed to whatever number i find suitable)
    restart_all_threshold = 2.8  # When the field falls to ≈90% of max value, restart ramping
    # Stop treshold should be at 2.85 (for testing purposes it is changed to whatever number i find suitable)
    stop_threshold = 2.85  # When the field reaches close to 3 Tesla, stop magnets that are increasing it

    """
    # ####################################
    # ########## LABBER HOOKS ############
    # ####################################
    """
    def performOpen(self, options={}):
        """
        This method should attempt to connect to both instruments (Y and Z)

        :param options: Labber wants to have this.
        :type options:
        :return: all magnets which we successfully connected to
        :rtype: tuple
        """
        try:
            self.z_magnet_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.z_magnet_socket.settimeout(0.6)
            self.z_magnet_socket.connect((self.z_magnet_IP, self.z_magnet_PORT))
        except Exception as e:
            print(str(e))
        else:
            self.CONNECTED_MAGNETS["z"] = True
            self._receive(self.z_magnet_socket)
        try:
            self.y_magnet_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.y_magnet_socket.settimeout(0.6)
            self.y_magnet_socket.connect((self.y_magnet_IP, self.y_magnet_PORT))
        except Exception as e:
            print(str(e))
        else:
            self.CONNECTED_MAGNETS["y"] = True
            self._receive(self.y_magnet_socket)

        return self.CONNECTED_MAGNETS

    def performClose(self, options={}):
        """
        This method should attempt to close connection to all individual magnet sockets.

        :return: NoneType
        """
        self.z_magnet_socket.close()
        self.y_magnet_socket.close()

    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """
        TODO: Insert if statement that checks weather field is being set to a value over z_max (or y_max) and if it is,
        TODO: then it changes ramp rate to something else

        This method is called when any of the instruments quantities is being set to some value. Depending on the name
        of the quantity being set, different methods get called to handle the request.

        Since the instrument is actually combination of 2 individual magnets, first we find out which one is being
        modified and then send a command to the appropriate socket.

        All get and set methods accept an argument called magnet_socket which should be a reference to a socket that
        corresponds to the magnet being modified.

        :param quant: Name of the quantity that is being modified. Names of the quantities are specified in the
        .ini file located in the same folder as the driver.
        :type quant: str
        :param value: Value to which the quantity is being set to
        :type value:
        :param sweepRate: I have no idea what this is, it is required by labber
        :type sweepRate: float
        :param options: Same as sweepRate
        :type options:
        :return: value that is being sent to the instrument to set the quantity to
        :rtype: bool | int | float | None
        """
        if quant.name[0] == "z":
            socket = self.z_magnet_socket
            fieldrating = 8.99
        elif quant.name[0] == "y":
            fieldrating = 2.99
            socket = self.y_magnet_socket
        else:
            # This will happen when i try to perform a command involving more then 1 magnet
            if quant.name == "radius":
                return self.set_radius(value)
            elif quant.name == "phi":
                return self.set_phi(value)
            elif quant.name == "constant_phi":
                return self.set_constant_phi(value)
            else:
                pass

        if quant.name[2:] == "pSwitch":
            self.set_p_switch(socket, value)
        elif quant.name[2:] == "current":
            self.set_current(socket, value)
        elif quant.name[2:] == "field":
            self.set_field(socket, value)
        elif quant.name[2:] == "units":
            self.set_units(socket, value)
        elif quant.name[2:] == "setPoint":
            self.set_field(socket, value)
        elif quant.name[2:] == "rampRate":
            self.set_ramp_rate(socket, value, fieldrating)
        elif quant.name[2:] == "quench":
            self.reset_quench(socket)
        elif quant.name[2:] == "persistent":
            self.set_persistent(socket, value)
        elif quant.name[2:] == "ramp":
            if self.is_ready_to_ramp(socket):
                self.start_ramping(socket)
        elif quant.name[2:] == "pause":
            self.pause_ramp(socket)
        elif quant.name[2:] == "zero":
            self.ramp_to_zero(socket)
        else:
            return

        return value

    def performGetValue(self, quant, options={}):
        """
        This method is called when we are trying to get the value of any of the isntruments quantities. Depending on the
        name of the quantity, different methods get called to handle the request.

        Since the instrument is actually combination of 2 individual magnets, first we find out which one are we trying
         to get and then send a command to the appropriate socket.

        All get and set methods accept an argument called magnet_socket which should be a reference to a socket that
        corresponds to the magnet that we are communicating with.

        :param quant: Name of the quantity that we are getting. Names of the quantities are specified in the
        .ini file located in the same folder as the driver.
        :type quant: str
        :param options: parameter required by labber, i don't really know what it does
        :return: any: a response from the instrument after sending a command to read the specified parameter
        :rtype:
        """
        if quant.name[0] == "z":
            socket = self.z_magnet_socket
        elif quant.name[0] == "y":
            socket = self.y_magnet_socket
        else:
            # This means that it is one of the global parameters (radius, phi)
            if quant.name == "radius":
                return self.get_radius()
            elif quant.name == "phi":
                return self.get_phi()
            elif quant.name == "constant_phi":
                return self.get_constant_phi()
            else:
                pass

        if quant.name[2:] == "pSwitch":
            return self.get_p_switch(socket)
        elif quant.name[2:] == "current":
            return self.get_current(socket)
        elif quant.name[2:] == "field":
            return self.get_field(socket)
        elif quant.name[2:] == "units":
            return self.get_units(socket)
        elif quant.name[2:] == "setPoint":
            return self.get_set_point(socket)
        elif quant.name[2:] == "rampRate":
            return self.get_ramp_rate(socket)
        elif quant.name[2:] == "rampState":
            return self. get_ramp_state(socket)
        elif quant.name[2:] == "persistent":
            return self.get_persistent(socket)
        elif quant.name[2:] == "quench":
            return self.get_quench(socket)
        elif quant.name[2:] == "error":
            return self.get_error(socket)
        else:
            return False

    """
    # ####################################
    # ##### INSTRUMENT COMMUNICATION #####
    # ####################################
    """
    def _send(self, magnet_socket, command):  # ##TODO: check for timeout and throw exception
        """
        Send a command to a magnet specified by its socket. After sending a command sleep for 0.6 seconds to give magnet
        time to do the required action.

        :param magnet_socket: Socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                                    directions is controled by a unique instrument and they have to be specified by
                                    their socket.
        :param command: string: A command that we are sending to an instrument
        :return: NoneType
        """
        magnet_socket.sendall(bytes(command, "ASCII"))
        time.sleep(0.6)  # ##Temporary solution for too fast computers
        return

    def _receive(self, magnet_socket):
        """
        Read the data from the instruments standard event buffer. When a command is sent to an instrument the response
        is stored in the standard event buffer. In order to obtain  the result from the instrument we have to read this
        buffer.

        :param magnet_socket: Socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                                    directions is controled by a unique instrument and they have to be specified by
                                    their socket.
        :return: String: Content of the instruments standard event buffer after sending the command
        """
        return magnet_socket.recv(self.BUFFSIZE)

    def _ask(self, magnet_socket, command):
        """
        Send a command and instantly read a reply from the instrument. To be used when getting an instrument value.
        First we send a command to query some instrument value, instrument replies by setting that value in the
        standard event buffer. Then we read and return the value from the standard event buffer.

        :param magnet_socket: Socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                                    directions is controled by a unique instrument and they have to be specified by
                                    their socket.
        :param command: string: A command that we are sending to an instrument
        :return: String: Content of the instruments standard event buffer after sending the command
        """
        self._send(magnet_socket, command)
        return self._receive(magnet_socket)

    """
    # ####################################
    # ######### RAMPING MODES ############
    # ####################################
    """
    def is_ready_to_ramp(self, magnet_socket):
        """
        Ramp can have 9 states: Ramping, Holding, Paused, Manual up, Manual down, Ramping to zero, Quench detected,
        At zero, Heating switch and Cooling switch

        Magnet is NOT ready to ramp if MAGNET is in persistent mode or if RAMP is in one of the states: Ramping,
        Magnet quench, Manual up, Manual down, Ramping to zero, Heating switch or Cooling switch

        :param magnet_socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                              directions is controlled by a unique instrument and they have to be specified by
                              their socket.
        :type magnet_socket: socket.socket

        :return: True if ready, False if not ready
        :rtype: bool
        """
        if self.get_quench(magnet_socket):
            logging.error(__name__ + ': Magnet quench')
            return False
        elif self.get_persistent(magnet_socket):
            logging.error(__name__ + ': Magnet set to persistent mode')
            return False
        else:
            ramp_state = self.get_ramp_state(magnet_socket)
            if ramp_state == 3 or ramp_state == 4:
                logging.error(__name__ + ': Magnet set to manual ramp')
                return False
            elif ramp_state == 5:
                logging.error(__name__ + ': Magnet is ramping to zero')
                return False
            elif ramp_state == 8 or ramp_state == 9:
                logging.error(__name__ + ': Persistent switch being heated or cooled')
                return False
            elif ramp_state == 6:
                logging.error(__name__ + ': Magnet quench')
                return False
            elif ramp_state == 0:
                if self.get_p_switch(magnet_socket):
                    return True
                else:
                    logging.error(__name__ + ': Already ramping with switch heater off (persistent mode?)')
                    return False
            elif ramp_state == 1 or ramp_state == 2 or ramp_state == 7:
                return True
            else:
                logging.error(__name__ + ': Invalid status received')
                return False

    def start_ramping(self, magnet_socket):
        """
        Issue a RAMP state. Magnet will start ramping

        :param magnet_socket: Socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                                    directions is controled by a unique instrument and they have to be specified by
                                    their socket.
        :return: NoneType
        """
        self._send(magnet_socket, "RAMP\n")
        return

    def pause_ramp(self, magnet_socket):
        """
        Issue a PAUSE state. Magnet will stop ramping immediately.

        :param magnet_socket: Socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                                    directions is controled by a unique instrument and they have to be specified by
                                    their socket.
        :return: NoneType
        """
        self._send(magnet_socket, "PAUSE\n")
        return

    def ramp_to_zero(self, magnet_socket):
        """
        Issue ZERO state. Magnet will ramp to zero (regardless of earlier pause)

        :param magnet_socket: Socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                                    directions is controled by a unique instrument and they have to be specified by
                                    their socket.
        :return: NoneType
        """
        self._send(magnet_socket, "ZERO\n")
        return

    """
    # ####################################
    # ######## GETERS AND SETERS #########
    # ####################################
    """

    def get_ramp_state(self, magnet_socket):
        """
        Get the current state of the ramp.

        :param magnet_socket: Socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                                    directions is controled by a unique instrument and they have to be specified by
                                    their socket.
        :return: Integer:
        """
        return int(self._ask(magnet_socket, "STATE?\n")) - 1

    def get_p_switch(self, magnet_socket):
        """


        :param magnet_socket: Socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                                    directions is controled by a unique instrument and they have to be specified by
                                    their socket.
        :return: Boolean: True if pSwitch is ON, False is pSwitch is OFF.
        """
        return int(self._ask(magnet_socket, 'PS?\n')) == 1

    def set_p_switch(self, magnet_socket, value):
        """
        Set the value of pSwitch of a magnet specified by magnet_socket to a value specified by parameter value.

        :param magnet_socket: Socket: Reference to one of 3 sockets (x, y or z)
        :param value: Boolean (1 or 0): Value to set the pSwitch to, 1 for ON, 0 for OFF
        :return: NoneType
        """
        if value:
            self._send(magnet_socket, "PS 1\n")
            time.sleep(0.5)
            while self.get_ramp_state(magnet_socket) == 8:
                time.sleep(0.3)
            return
        else:
            self._send(magnet_socket, "PS 0\n")
            time.sleep(0.5)
            while self.get_ramp_state(magnet_socket) == 9:
                time.sleep(0.3)
            return

    def get_ramp_rate(self, magnet_socket):
        """


        :param magnet_socket: Socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                                    directions is controled by a unique instrument and they have to be specified by
                                    their socket.
        :return: Float: Current value of the ramp rate. Represents how fast is the value of field changing
        """
        return float(str(self._ask(magnet_socket, "RAMP:RATE:FIELD:1?\n")).split(",", 1)[0][2:])

    def set_ramp_rate(self, magnet_socket, value, magnet_fieldrating):
        """


        :param magnet_socket: Socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                                    directions is controled by a unique instrument and they have to be specified by
                                    their socket.
        :param value: Value to which we want to set the ramp rate to. Ramp rate determines the speed at which the field
                        is changing
        :param magnet_fieldrating: Maximum allowed ramp rate for a magnet specified by its socket. Calculated and taken
                                    care of in the .ini file.
        :return: NoneType
        """
        self._send(magnet_socket, "CONF:RAMP:RATE:FIELD 1, {}, {}\n".format(str(value), str(magnet_fieldrating)))
        return

    def get_field(self, magnet_socket):
        """
        Get the current value of the field

        :param magnet_socket: Socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                                    directions is controled by a unique instrument and they have to be specified by
                                    their socket.
        :return: Float: Current value of the magnetic field.
        """
        self.get_ramp_state(magnet_socket)
        return float(self._ask(magnet_socket, "FIELD:MAG?\n"))

    def set_field(self, magnet_socket, value):
        """
        This method does not set the field to a certain value but rather configures a setPoint to that value and starts
        ramping the magnet to the selected value.

        :param magnet_socket: Socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                                    directions is controled by a unique instrument and they have to be specified by
                                    their socket.
        :param value: Desired value for the field
        :param magnet:
        :return: NoneType
        """
        self.pause_ramp(magnet_socket)
        self._send(magnet_socket, "CONF:FIELD:TARG {} ;".format(float(value)))
        self.start_ramping(magnet_socket)
        while not self.is_ready_to_ramp(magnet_socket):
            time.sleep(1)
        return True

    def set_set_point(self, magnet_socket, value):
        """
        Set point is the value to which the magnet will ramp the field.

        :param magnet_socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                              directions is controlled by a unique instrument and they have to be specified by
                              their socket.
        :type magnet_socket: socket.socket
        :param value: Desired value for the set point
        :type value: float
        :return: NoneType
        """
        self.pause_ramp(magnet_socket)
        self._send(magnet_socket, "CONF:FIELD:TARG {} ;".format(float(value)))

    def get_set_point(self, magnet_socket):
        """
        Get the current set point of the field. The is the value to which we are trying to ramp the field to.

        :param magnet_socket: Socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                                    directions is controlled by a unique instrument and they have to be specified by
                                    their socket.
        :return: Float: Current set point to which we are trying to ramp the field to.
        """
        self.get_ramp_state(magnet_socket)
        return float(self._ask(magnet_socket, "FIELD:TARG?\n"))

    def get_current(self, magnet_socket):
        """
        Method that gets the value of the current.

        :param magnet_socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                              directions is controled by a unique instrument and they have to be specified by
                              their socket.
        :type magnet_socket: socket.socket
        :return: Value of the current on the instrument.
        :rtype: float
        """
        return float(self._ask(magnet_socket, "CURR:MAG?\n"))

    def set_current(self, magnet_socket, value):
        """
        Method that pauses ramping of the magnet, changes the value of the current and then resumes the ramping of the
        field.

        :param magnet_socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                              directions is controlled by a unique instrument and they have to be specified by
                              their socket.
        :type magnet_socket: socket.socket
        :param value: Value that we want our current to be.
        :type value: float
        :return: NoneType
        """
        self.pause_ramp(magnet_socket)
        self._send(magnet_socket, "CONF:CURR:TARG {} ;".format(float(value)))
        self.start_ramping(magnet_socket)
        return

    def get_units(self, magnet_socket):
        """
        Method that gets the currently used units in the instrument.

        :param magnet_socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                              directions is controlled by a unique instrument and they have to be specified by
                              their socket.
        :type magnet_socket: socket.socket
        :return: Currently used units
        :rtype: int
        """
        return int(self._ask(magnet_socket, "FIELD:UNITS?\n"))

    def set_units(self, magnet_socket, value):
        """
        Method that is used to set the units that the instrument uses.

        :param magnet_socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                              directions is controlled by a unique instrument and they have to be specified by
                              their socket.
        :type magnet_socket: socket.socket
        :param value: Desired units
        :type value: int
        :return: NoneType
        """
        self._send(magnet_socket, "CONF:FIELD:UNITS {}".format(value))
        return

    def get_quench(self, magnet_socket):
        """
        Method tat is used to check if the magnet quenched.

        :param magnet_socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                              directions is controlled by a unique instrument and they have to be specified by
                              their socket.
        :type magnet_socket: socket.socket
        :return: True if quenching, False if not
        :rtype: bool
        """
        return int(self._ask(magnet_socket, "QU?\n")) == 1

    def reset_quench(self, magnet_socket):
        """
        Method that resets the quench flag on the instrument.

        :param magnet_socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                              directions is controlled by a unique instrument and they have to be specified by
                              their socket.
        :type magnet_socket: socket.socket
        :return: NoneType
        """
        return self._send(magnet_socket, "QU 0\n")

    def get_persistent(self, magnet_socket):
        """
        Method that checks if the instrument is in persistent mode

        :param magnet_socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                              directions is controlled by a unique instrument and they have to be specified by
                              their socket.
        :type magnet_socket: socket.socket
        :return: True if in persistent mode, False otherwise
        :rtype: bool
        """
        return int(self._ask(magnet_socket, "PERS?\n")) == 1

    def set_persistent(self, magnet_socket, value):
        """
        Method that puts the instrument in or out of persistent mode.

        :param magnet_socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                              directions is controlled by a unique instrument and they have to be specified by
                              their socket.
        :type magnet_socket: socket.socket
        :param value: True if we want the instrument in persistent mode, otherwise False
        :type value: bool
        :return: True if instrument is in persistent mode at the end of this method, otherwise False
        :rtype: bool
        """
        if value == 1:
            if self.get_persistent(magnet_socket):
                return True
            else:
                temp = self.get_ramp_state(magnet_socket)
                if not (temp == 1 or temp == 2):
                    logging.error(__name__ + ': setting persistent mode failed, because of magnet status' + str(temp))
                    return False
                else:
                    self.set_p_switch(magnet_socket, False)
                    self.ramp_to_zero(magnet_socket)
                    time.sleep(0.5)
                    while self.get_ramp_state(magnet_socket) == 5:
                        time.sleep(0.3)
                    time.sleep(2.0)
                    if self.get_persistent(magnet_socket) and (self.get_ramp_state(magnet_socket) == 7):
                        return True
                    else:
                        logging.error(__name__ + ': Setting persistent mode failed, magnet status is ' +
                                      str(self.get_ramp_state(magnet_socket)))
                        return False
        else:
            if not self.get_persistent(magnet_socket):
                return True
            else:
                temp = self.get_ramp_state(magnet_socket)
                if not (temp == 1 or temp == 2 or temp == 7):
                    logging.error(__name__ + ': setting driven mode failed, because of magnet status ' + str(temp))
                    return False
                else:
                    if self.set_field(magnet_socket, self.get_field(magnet_socket)):
                        self.set_p_switch(magnet_socket, True)
                        return True
                    else:
                        logging.error(__name__ + ': setting driven mode failed, magnet cannot ramp to specified value')
                        return False

    def get_error(self, magnet_socket):
        """


        :param magnet_socket: Specifies magnets socket. Magnet can have more then 1 direction. Each of those
                              directions is controlled by a unique instrument and they have to be specified by
                              their socket.
        :type magnet_socket: socket.socket
        :return: Value stored in the error buffer of the instrument
        :rtype: str
        """
        return self._ask(magnet_socket, "SYST:ERR?\n").rstrip()

    """
    # ####################################
    # ###### MULTIPLE MAGNETS MODE #######
    # ####################################
    """

    def polar_to_cartesian(self, r, phi):
        """
        Method that takes Spherical coordinates that represent the current field, and returns cartesian coordinates
        representing the same field.

        :param r: Radius of the spherical coordinate system (value of the combined field)
                            x-y plane
        :type r: float
        :return: Float, Float, Float: Cartesian coordinates (value of field in each direction [x, y and z])
        :rtype: tuple
        """
        z = r * np.cos(phi)
        y = r * np.sin(phi)
        return z, y

    def cartesian_to_polar(self, z, y):
        """
        Get polar coordinates from a set of cartesian coordinates.

        :param z: Current value of Z coordinate
        :type z: float
        :param y: Current value of y coordinate
        :type y: float
        :return: float, float: polar coordinates of the same point
        :rtype: tuple
        """
        r = np.sqrt(z * z + y * y)
        phi = np.rad2deg(np.arctan2(y, z))
        return r, phi

    def get_phi(self):
        """
        Calculate the value of angle between x axis and the projection of radius on to the x-y plane. Since it only
        needs values of x and y fields, it gets those from the instruments and then calculates the angle. Formula used
        for calculation is: phi = np.rad2deg(np.arctan2(y, x))

        :return: Value of phi
        :rtype: float
        """
        z = self.get_field(self.z_magnet_socket)
        y = self.get_field(self.y_magnet_socket)

        phi = np.rad2deg(np.arctan2(y, z))

        return phi

    def set_phi(self, value):
        """
        Set the values of x, y and z field in such a way that radius remains the same, theta remains the same, but phi
        gets changed to a value specified by user.

        :param value: value to which to set the phi to
        :type value: float
        :return: Value passed to this method (the one we want to set phi to)
        :rtype: float
        """
        z = self.get_field(self.z_magnet_socket)
        y = self.get_field(self.y_magnet_socket)
        target_angle = value

        r, phi = self.cartesian_to_polar(z, y)

        target_z = r * np.cos(np.deg2rad(target_angle))
        target_y = r * np.sin(np.deg2rad(target_angle))

        self.start_ramping_algorithm(target_z, target_y)

        self.set_constant_phi(value)
        return value

    def get_constant_phi(self):
        """
        Get the value of the helper variable constant phi. This variable is used to calculate the fields when setting
        radius.

        :return: Value of helper variable constant phi
        :rtype: float
        """
        return self.phi

    def set_constant_phi(self, value):
        """
        Set the value of the helper variable constant phi to a value specified by user. This helper variable is later
        used in method the set the radius.

        :param value: value to which to set the constant phi to
        :type value: float
        :return: value passed to this method (one we want to set the phi to)
        :rtype: float
        """
        self.phi = value
        return value

    def get_radius(self):
        """
        Calculate and return the value of radius. Value of the radius is calculated by formula: sqrt(y^2 + z^2)

        :return: Current REAL value of the radius
        :rtype: float
        """
        z = self.get_field(self.z_magnet_socket)
        y = self.get_field(self.y_magnet_socket)
        return np.sqrt(z * z + y * y)

    def set_radius(self, value):
        """
        Set the values of y and z field in such a way that phi remains the same, but radius
        gets changed to a value specified by user.

        :param value: value to which to set the radius to
        :type value: float
        :return: Value passed to this method (the one we want to set radius to)
        :rtype: float
        """
        target_radius = value

        target_z = target_radius * np.cos(np.deg2rad(self.phi))
        target_y = target_radius * np.sin(np.deg2rad(self.phi))

        self.start_ramping_algorithm(target_z, target_y)

        return value

    def get_polar_coords(self):
        """
        Get the current field represented by polar coordinates.

        :return: polar coordinates of the field
        :rtype: tuple
        """
        z = self.get_field(self.z_magnet_socket)
        y = self.get_field(self.y_magnet_socket)

        radius = np.sqrt(z * z + y * y)
        phi = np.rad2deg(np.arctan2(y, z))

        return radius, phi

    def start_ramping_algorithm(self, target_z, target_y):
        """
        This method is used to change the result field of both magnets in any way. Since it is required to have some
        safety not all magnets will ramp at the same time. There are 2 important numbers in this method: first one is
        restart all threshold. This number specifies the value of the field when all magnets are allowed to ramp freely.
        If current value of the field is equal or lower then the restart all threshold, we will start the ramping of all
        magnets. Other import number is stop threshold. This number specifies the highest value of the field until which
        both magnets can ramp at the same time. If the field ever passes this value, we will stop ramping all magnets
        that are increasing the total value of the field. If there is no magnets that are decreasing the field, then we
        will start one by one magnet until we reach the desired value of the field.
        TODO: Change limits (Radius, stop and restart threshold)

        :param target_y: Y magnet will ramp to this value
        :type target_y: float
        :param target_z: Z magnet will ramp to this value
        :type target_z: float
        :return: True if successful, else False
        :rtype: bool
        """

        radius = np.sqrt(target_z * target_z + target_y * target_y)
        self.pause_ramp(self.z_magnet_socket)
        self.pause_ramp(self.y_magnet_socket)

        # Radius should never be more then 1T ( can be adjusted to anz other value for testing purposes)
        if radius > self.combined_field_limit:
            self.getValueFromUserDialog(value="Don't put anything here",
                                        text="Field will exceed the maximum allowed value (sweep canceled)",
                                        title="Burn after reading")
            return False
        else:
            self.set_set_point(self.y_magnet_socket, target_y)
            self.set_set_point(self.z_magnet_socket, target_z)

        z = self.get_field(self.z_magnet_socket)
        y = self.get_field(self.y_magnet_socket)
        radius, phi = self.cartesian_to_polar(z, y)

        if radius < self.restart_all_threshold:
            # If the field is in "safe zone (less then 0.9)" start ramping all magnets
            self.start_ramping(self.y_magnet_socket)
            self.start_ramping(self.z_magnet_socket)
        else:
            # If the field is not in "safe zone" only start ramping those magnets which will decrease the total value
            # of the field
            # If the current value and target value are on the same side of the axis (both greater or both less then
            # zero), check if the current value is greater then target value, if it is, ramping will decrease the
            # value of the field
            if target_z * z >= 0:
                if np.abs(target_z) < np.abs(z):  # This is decreasing the field
                    self.start_ramping(self.z_magnet_socket)
            if target_y * y >= 0:
                if np.abs(target_y) < np.abs(y):
                    self.start_ramping(self.y_magnet_socket)

        z_ramp_state = self.get_ramp_state(self.z_magnet_socket)
        y_ramp_state = self.get_ramp_state(self.y_magnet_socket)

        # loop that keeps checking if we left the the safe zone, and stop some magnets if we did
        # additionally it keeps checking if we went back to the safe zone and restarts the magnets
        while True:

            if self.isStopped():
                self.pause_ramp(self.y_magnet_socket)
                self.pause_ramp(self.z_magnet_socket)
                return False

            z = self.get_field(self.z_magnet_socket)
            y = self.get_field(self.y_magnet_socket)
            radius, phi = self.cartesian_to_polar(z, y)
            self.reportStatus("Y: {}, Z: {}".format(y, z))

            # Radius should never be more then 3T ( can be adjusted to any other value for testing purposes)
            if radius > 2.9:
                self.pause_ramp(self.z_magnet_socket)
                self.pause_ramp(self.y_magnet_socket)
                return False

            # Count how many magnets are currently ramping
            number_of_magnets_currently_ramping = 0

            if z_ramp_state == 0:
                number_of_magnets_currently_ramping += 1
            if y_ramp_state == 0:
                number_of_magnets_currently_ramping += 1

            # Handling the part when field is in "DANGER ZONE"
            if radius >= self.stop_threshold:
                # THIS SHOULD ONLY HAPPEN IF MORE THEN 1 MAGNET IS CURRENTLY RAMPING
                if number_of_magnets_currently_ramping > 1:
                    if target_z * z >= 0:
                        if np.abs(target_z) > np.abs(z):  # This is increasing the field
                            if z_ramp_state == 0:
                                self.pause_ramp(self.z_magnet_socket)
                    if target_y * y >= 0:
                        if np.abs(target_y) > np.abs(y):  # This is increasing the field
                            if y_ramp_state == 0:
                                self.pause_ramp(self.y_magnet_socket)
                elif number_of_magnets_currently_ramping < 1:
                    # start one magnet that still needs to ramp to get to target value
                    finished = True
                    if z_ramp_state == 2:
                        self.start_ramping(self.z_magnet_socket)
                        finished = False
                        continue

                    if y_ramp_state == 2:
                        self.start_ramping(self.y_magnet_socket)
                        finished = False
                        continue

                    if finished:
                        return True
                else:
                    pass

            # Handling the part where the field is in "SAFE ZONE"
            elif radius < self.restart_all_threshold:
                if z_ramp_state == 2:  # Paused
                    self.start_ramping(self.z_magnet_socket)
                if y_ramp_state == 2:  # Paused
                    self.start_ramping(self.y_magnet_socket)

            # Handling then grey zone
            else:  # Area between 0.9 and 0.95
                if number_of_magnets_currently_ramping < 1:
                    # start one magnet that still needs to ramp to get to target value
                    finished = True
                    if z_ramp_state == 2:
                        self.start_ramping(self.z_magnet_socket)
                        finished = False
                        continue

                    if y_ramp_state == 2:
                        self.start_ramping(self.y_magnet_socket)
                        finished = False
                        continue

                    if finished:
                        return True

            z_ramp_state = self.get_ramp_state(self.z_magnet_socket)
            y_ramp_state = self.get_ramp_state(self.y_magnet_socket)

            # Make sure the result field is close to zero when the measurement is done
            if z_ramp_state == 1 and y_ramp_state == 1:
                time.sleep(1)
                self.pause_ramp(self.y_magnet_socket)
                self.pause_ramp(self.z_magnet_socket)
                return True
