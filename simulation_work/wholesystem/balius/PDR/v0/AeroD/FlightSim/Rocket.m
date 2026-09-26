classdef Rocket < handle
    %% --------------------------------------------------------------------
    % Rocket
    % ---------------------------------------------------------------------
    % Rocket class. Contains properties and functions that must be defined
    % when creating a rocket object.
    % ---------------------------------------------------------------------
    % Arguments
    %   None
    % ---------------------------------------------------------------------
    % Properties
    % - Sref [1 1] reference area
    % - cref [1 1] reference length
    % - g0 [1 1] gravitational acceleration at launch altitude
    % - R0 [1 1] radius of Earth at launch altitude
    % - imu [IMU] imu object
    % - servos [Servos] servos object
    % - calc_mass(t) [func] returns mass of rocket as function of time
    % - calc_inertia(t) [func] returns inertia tensor of rocket as function
    %      of time
    % - calc_cg(t) [func] returns center of gravity of rocket as function
    %      of time
    % - calc_thrust(t) [func] returns thrust as function of time
    % - calc_aero(alpha, beta, p, q, r, del_a, del_e, del_r, mach) [func]
    %      returns coefficients of force and moment about origin

    %% --------------------------------------------------------------------

    properties
        Sref
        cref
        g0
        R0

        imu
        servos

        calc_mass
        calc_inertia
        calc_cg

        calc_thrust
        calc_aero

    end
end