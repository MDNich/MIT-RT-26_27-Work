classdef Controller < handle
    %% --------------------------------------------------------------------
    % Controller
    % ---------------------------------------------------------------------
    % Controller class. Contains properties and functions that must be 
    % defined when creating a Controller object.
    % ---------------------------------------------------------------------
    % Arguments
    %   None
    % ---------------------------------------------------------------------
    % Properties
    % - clog [struct] controller data log
    % - calc_deltastar [func] returns commanded actuator deflections
    % - initialize_log [func] initialize controller data log
    % - log_data [func] updates controller data log


    %% --------------------------------------------------------------------
    properties
        clog
        
        calc_deltastar
        initialize_log
        log_data
    end
end