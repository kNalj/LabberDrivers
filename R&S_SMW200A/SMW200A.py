#!/usr/bin/env python

from VISA_Driver import VISA_Driver
import numpy as np

__version__ = "0.0.1"

class Error(Exception):
    pass

class Driver(VISA_Driver):
    """ This class implements the Rohde&Schwarz Network Analyzer driver"""

    def performOpen(self, options={}):
        """
        Perform the operation of opening the instrument connection"
        
        :param options: 
        :return: NoneType
        """""
        # calling the generic VISA open to make sure we have a connection
        VISA_Driver.performOpen(self, options=options)

    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """
        Perform the Set Value instrument operation. This function should
        return the actual value set by the instrument

        :param quant: Quantity object (I believe Labber has some kind of object representing quantities)
        :type quant:
        :param value: Value to which the quantity is being set to
        :type value: int | float | str | bool
        :param sweepRate:
        :type sweepRate:
        :param options:
        :return: Value that has been passed to this method as the value we want to set the quantity to
        :rtype: None | int | float | str | bool
        """

        value = VISA_Driver.performSetValue(self, quant, value, sweepRate, options)
        return value

    def performGetValue(self, quant, options={}):
        """
        Perform the Get Value instrument operation

        :param quant: Quantity object (I believe Labber has some kind of class representing quantities)
        :type quant:
        :param options:
        :type options:
        :return:
        :rtype: None | int | float | str | bool
        """

        value = VISA_Driver.performGetValue(self, quant, options)
        return value
