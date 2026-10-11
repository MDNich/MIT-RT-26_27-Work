classdef IMU < handle
    %% --------------------------------------------------------------------
    % IMU
    % ---------------------------------------------------------------------
    % IMU class. Contains properties and functions that must be defined
    % when creating an IMU object.
    % ---------------------------------------------------------------------
    % Arguments
    %   None
    % ---------------------------------------------------------------------
    % Properties
    % - calc_vdot [func] returns sensed inertial velocity in body axes
    % - calc_omega [func] returns sensed angular velocity about body axes


    %% --------------------------------------------------------------------
    properties
        calc_vdot
        calc_omega
    end
end