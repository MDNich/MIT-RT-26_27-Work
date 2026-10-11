classdef Servos < handle
    %% --------------------------------------------------------------------
    % Servos
    % ---------------------------------------------------------------------
    % Servos class. Contains properties and functions that must be defined
    % when creating a Servo object.
    % ---------------------------------------------------------------------
    % Arguments
    %   None
    % ---------------------------------------------------------------------
    % Properties
    % - calc_delta [func] returns actuator deflections

    %% --------------------------------------------------------------------
    properties
        calc_delta 
    end
end