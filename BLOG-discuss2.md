Continuation from the Blog post above....

For better accuracy, you should do that for all directions and take the average. In our case, we got:

- front: 0.4628
- back: 0.4757
- left: 0.5426
- right: 0.5697
- average: 0.5127

Note that these are quite high values due to the ducts around the props.
For a normal copter with open propellers, it should be in the range of 0.1 to 0.2.

After it is set, do another flight and [check that the windspeed and direction are correctly estimated](https://ardupilot.org/copter/docs/airspeed-estimation.html#viewing-windspeed-and-direction-in-real-time).

# 12. [Baro Compensation flight(s)](https://ardupilot.org/copter/docs/airspeed-estimation.html#barometer-position-error-compensation)

Follow [ArduCopter's baro compensation Wiki](https://ardupilot.org/copter/docs/airspeed-estimation.html#barometer-position-error-compensation) and/or use the [Lua script provided by Yuri in the forum](https://discuss.ardupilot.org/t/scripting-copter-wind-estimation-baro-compensation-tuning/98470/).

Use *ArduPilot Methodic Configurator* to edit and upload the `39_barometer_compensation.param` file to the FC.

Now do the flight to collect the data and analyze the logs to see if the barometer is correctly compensated and insensitive to wind.

# 13. [System Identification Flights](https://ardupilot.org/copter/docs/systemid-mode-operation.html)

These steps are optional.
Their goal is to build a mathematical model of the vehicle that can later be used to further [optimize the control loops of the vehicle according to a set of constraints (requirements)](https://discuss.ardupilot.org/t/analitical-multicopter-flight-controller-pid-optimization/109759).

Documentation is available on [Fabian Bredemeier's Identification of a multicopter section at ArduCopter's_wiki](https://ardupilot.org/copter/docs/systemid-mode-operation.html#identification-of-a-multicopter).

## Roll rate mathematical model

Use *ArduPilot Methodic Configurator* to edit and upload the `40_system_id_roll.param` file to the FC.

Now do the flight to collect the data for the roll rate system identification.

## Pitch rate mathematical model

Use *ArduPilot Methodic Configurator* to edit and upload the `41_system_id_pitch.param` file to the FC.

Now do the flight to collect the data for the pitch rate system identification.

## Yaw rate mathematical model

Use *ArduPilot Methodic Configurator* to edit and upload the `42_system_id_yaw.param` file to the FC.

Now do the flight to collect the data for the yaw rate system identification.

## Thrust mathematical model

Use *ArduPilot Methodic Configurator* to edit and upload the `43_system_id_thrust.param` file to the FC.

Now do the flight to collect the data for the thrust system identification.

## [Analytical Multicopter Flight Controller PID Optimization](https://discuss.ardupilot.org/t/analytical-multicopter-flight-controller-pid-optimization/109759)

This describes how to use IAV's multi-objective optimization to achieve even better (according to a predefined set of constraints) PID tuning.

One other approach is described by Bill Geyer in his Blog post: [Predicting Closed Loop Response For Faster Autotune](https://discuss.ardupilot.org/t/predicting-closed-loop-response-for-faster-autotune/75096).

Use *ArduPilot Methodic Configurator* to edit and upload the `44_analytical_pid_optimization.param` file to the FC.

# 14. Productive configuration

Some changes should be made for everyday productive operation.

Use *ArduPilot Methodic Configurator* to edit and upload the `45_everyday_use.param` file to the FC.

# 15. Position controller

The most inner *angle rate* and *angle* control loops have been tuned. Now let's tune the position controller.

Use *ArduPilot Methodic Configurator* to edit and upload the `46_position_controller.param` file to the FC.

# 16. Precision land

These are **optional**, and only make sense if you have extra hardware on your vehicle to support it.

Use *ArduPilot Methodic Configurator* to edit and upload the `47_precision_land.param` file to the FC.

# 17. Guided operation without RC transmitter

These are **optional**, and only make sense if you do beyond visual line-of-sight (BVLOS) autonomous flights using a companion computer.

Use *ArduPilot Methodic Configurator* to edit and upload the `48_guided_operation.param` file to the FC.

# 18. Conclusion

We presented a sequence of small, methodic steps that result in a fully operational and safe drone. Beginning with informed hardware decisions, appropriate hardware configuration and concluding with a finely tuned vehicle equipped with robust, fast-acting control loops. Each step is documented in its own intermediate parameter file, ensuring reproducibility and traceability. Each file is numbered, ensuring that the sequence of steps is clear. The number of test flights was reduced to a minimum, and their order was optimized. This process was developed for our specific multicopter, but **it can be tailored to any other ArduPilot vehicle**.

Many thanks to the ArduPilot's developers and community.

This work has been sponsored by the company I work for [IAV GmbH](https://www.iav.com/). We provide engineering and consulting for robotic systems including multicopters. Feel free to contact us for help or development support.

Your vehicle is now properly tuned according to AduPilot's standard procedures and some of IAV GmbH's know-how.

Enjoy,
Jan Ole Noack
Amilcar do Carmo Lucas
