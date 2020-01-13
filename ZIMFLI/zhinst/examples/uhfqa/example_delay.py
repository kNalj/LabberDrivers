# -*- coding: utf-8 -*-
""" Run a combined test of the monitor and result units.
"""

# Copyright 2018 Zurich Instruments AG

from __future__ import print_function
import sys
import time
import textwrap
import numpy as np

import zhinst.utils

from .common import initialize_device, acquisition_poll
from .common import ResultLoggingSource


def run_example(device_id, monitor_length=4000, num_averages=2**8, do_plot=True):
    """ Run a combined test of the monitor and result units.

    The example applies a simple square wave to the instrument using the AWG. The
    integration functions use the full length of the integrators, and each
    integration function is basically just a constant value through the entire
    integration window, with different values for the different channels. We
    then sweep the starting point of the integration in relation to the pulse
    generated by the AWG. Initially, the integrators will not see the pulse at
    all, so the result will be zero. Then, as we gradually get more and more
    overlap of the integration function and the pulse, we will see a ramp up
    until a point in time where the integration window is completely within the
    pulse. Then, for larger delays we have the reverse process.

    Requirements:

      - Connect signal output 1 to signal input 1.
      - Connect signal output 2 to signal input 2.

    Arguments:

      device_id (str): The ID of the device to run the example with. For
        example, `dev2006` or `uhf-dev2006`.

      monitor_length (int): Number of monitor samples to obtain.

      num_averages (int): Number of averages per measurement.

      do_plot (bool, optional): Specify whether to plot the polled data.

    Returns:

      data (dict): Measurement result.

    """
    apilevel_example = 6  # The API level supported by this example.
    # Call a zhinst utility function that returns:
    # - an API session `daq` in order to communicate with devices via the data server.
    # - the device ID string that specifies the device branch in the server's node hierarchy.
    # - the device's discovery properties.
    required_devtype = 'UHFQA'
    required_options = ['QA', 'AWG']
    daq, device, _ = zhinst.utils.create_api_session(device_id, apilevel_example,
                                                     required_devtype=required_devtype,
                                                     required_options=required_options)

    # Perform initialization for UHFQA examples
    initialize_device(daq, device)

    # Configure AWG
    awg_program = textwrap.dedent("""\
    const RATE = 0;
    const FS = 1.8e9*pow(2, -RATE);

    wave w = join(zeros(32), ones(64), -ones(64), zeros(32));

    var loop_cnt = getUserReg(0);
    var trig1;
    var trig0;
    if (getUserReg(1)) {
        trig1 = AWG_INTEGRATION_TRIGGER + AWG_INTEGRATION_ARM;
        trig0 = AWG_INTEGRATION_ARM;
    } else {
        trig1 = AWG_MONITOR_TRIGGER;
        trig0 = 0;
    }

    repeat(loop_cnt) {
        playWave(w, -w, RATE);
        wait(25);
        setTrigger(trig1);
        setTrigger(trig0);
        waitWave();
        wait(1000);
    }
    """)

    # Create an instance of the AWG module
    awgModule = daq.awgModule()
    awgModule.set('device', device)
    awgModule.set('index', 0)
    awgModule.execute()

    # Transfer the AWG sequence program. Compilation starts automatically.
    awgModule.set('compiler/sourcestring', awg_program)
    while awgModule.getInt('compiler/status') == -1:
        time.sleep(0.1)

    # Ensure that compilation was successful
    assert awgModule.getInt('compiler/status') != 1

    # Channels to test
    channels = [0, 1, 2, 3, 4, 5, 6, 7]

    # Configuration of weighted integration
    integration_length = 4
    for i in range(4):
        weights = np.zeros(integration_length)
        weights[i] = 1
        daq.setVector('/{:s}/qas/0/integration/weights/{}/real'.format(device, i), weights)
        daq.setVector('/{:s}/qas/0/integration/weights/{}/imag'.format(device, i), np.zeros(integration_length))
        daq.setVector('/{:s}/qas/0/integration/weights/{}/real'.format(device, i+4), np.zeros(integration_length))
        daq.setVector('/{:s}/qas/0/integration/weights/{}/imag'.format(device, i+4), weights)

    daq.setInt('/{:s}/qas/0/integration/length'.format(device), integration_length)
    daq.setInt('/{:s}/qas/0/integration/mode'.format(device), 0)
    daq.setInt('/{:s}/qas/0/delay'.format(device), 0)

    # Apply a rotation on half the channels to get the imaginary part instead
    for i in range(4):
        daq.setComplex('/{:s}/qas/0/rotations/{:d}'.format(device, i), 1)
        daq.setComplex('/{:s}/qas/0/rotations/{:d}'.format(device, i+4), -1j)

    #
    # First, perform a measurement with the monitor unit.
    #

    # Setup monitor
    daq.setInt('/{:s}/qas/0/monitor/averages'.format(device), num_averages)
    daq.setInt('/{:s}/qas/0/monitor/length'.format(device), monitor_length)

    # Now we're ready for readout. Enable monitor and start acquisition.
    daq.setInt('/{:s}/qas/0/monitor/reset'.format(device), 1)
    daq.setInt('/{:s}/qas/0/monitor/enable'.format(device), 1)
    daq.sync()

    # Set number of signal repetitions in AWG program
    daq.setDouble('/{:s}/awgs/0/userregs/0'.format(device), num_averages)

    # Trigger monitor from within the AWG program
    daq.setDouble('/{:s}/awgs/0/userregs/1'.format(device), 0)

    # Subscribe to monitor waves
    monitor_paths = []
    for channel in range(2):
        path = '/{:s}/qas/0/monitor/inputs/{:d}/wave'.format(device, channel)
        monitor_paths.append(path)
    daq.subscribe(monitor_paths)

    # Arm the device
    daq.asyncSetInt('/{:s}/awgs/0/single'.format(device), 1)
    daq.syncSetInt('/{:s}/awgs/0/enable'.format(device), 1)

    # Perform acquisition
    print('Acquiring monitor data...')
    monitor_data = acquisition_poll(daq, monitor_paths, monitor_length)
    print('Done.')

    # Stop monitor
    daq.unsubscribe(monitor_paths)
    daq.setInt('/{:s}/qas/0/monitor/enable'.format(device), 0)

    #
    # Next, perform the same measurement with the result unit.
    #

    # Trigger result unit from within the AWG program
    daq.setDouble('/{:s}/awgs/0/userregs/1'.format(device), 1)

    # Configure the result unit
    result_length = 1
    daq.setInt('/{:s}/qas/0/result/length'.format(device), result_length)
    daq.setInt('/{:s}/qas/0/result/averages'.format(device), num_averages)
    daq.setInt('/{:s}/qas/0/result/source'.format(device), ResultLoggingSource.TRANS)

    # Now we're ready for readout. Enable result unit and start acquisition.
    daq.setInt('/{:s}/qas/0/result/reset'.format(device), 1)
    daq.setInt('/{:s}/qas/0/result/enable'.format(device), 1)
    daq.sync()

    # Subscribe to result waves
    result_paths = []
    for ch in channels:
        path = '/{:s}/qas/0/result/data/{:d}/wave'.format(device, ch)
        result_paths.append(path)
    daq.subscribe(result_paths)

    print('Acquiring result data...')
    result_data = {k: [] for k in result_paths}
    for delay in range(50):
        print('.', end='')
        sys.stdout.flush()
        daq.setInt('/{:s}/qas/0/delay'.format(device), 4 * delay)

        # Arm the device
        daq.asyncSetInt('/{:s}/awgs/0/single'.format(device), 1)
        daq.syncSetInt('/{:s}/awgs/0/enable'.format(device), 1)

        data = acquisition_poll(daq, result_paths, result_length)
        for path in result_paths:
            result_data[path] = np.r_[result_data[path], data[path]]

    print('\nDone.')

    daq.unsubscribe(result_paths)
    daq.setInt('/{:s}/qas/0/result/enable'.format(device), 0)

    def combine_results(channels):
        """Combine result waveforms into I and Q result"""
        waves = [result_data['/{:s}/qas/0/result/data/{:d}/wave'.format(device, ch)] for ch in channels]
        return np.ravel(waves, order='F')

    result_i = combine_results([0, 1, 2, 3])
    result_q = combine_results([4, 5, 6, 7])
    residual_i = monitor_data[monitor_paths[0]][:200] - result_i
    residual_q = monitor_data[monitor_paths[1]][:200] - result_q

    if do_plot:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(nrows=2, ncols=2, figsize=(12, 6), sharex=True)
        ax[0, 0].set_title('Monitor and Result')
        ax[0, 0].set_ylabel('Amplitude (a.u.)')
        ax[0, 0].set_xlim(0, 200)
        ax[0, 0].plot(monitor_data[monitor_paths[0]], label='Monitor 0')
        ax[0, 0].plot(result_i, '--', label='Result')
        ax[0, 0].legend(loc='upper right')
        ax[1, 0].set_ylabel('Amplitude (a.u.)')
        ax[1, 0].set_xlabel('Sample (#)')
        ax[1, 0].plot(monitor_data[monitor_paths[1]], label='Monitor 1')
        ax[1, 0].plot(result_q, '--', label='Result')
        ax[1, 0].legend(loc='lower right')
        ax[0, 1].set_title('Residual Error')
        ax[0, 1].set_ylabel('Amplitude (a.u.)')
        ax[0, 1].plot(residual_i)
        ax[1, 1].set_ylabel('Amplitude (a.u.)')
        ax[1, 1].set_xlabel('Sample (#)')
        ax[1, 1].plot(residual_q)
        fig.set_tight_layout(True)
        plt.show()

    # Check residuals
    assert np.all(residual_i < 0.05)
    assert np.all(residual_q < 0.05)

    return monitor_data, (result_i, result_q)
