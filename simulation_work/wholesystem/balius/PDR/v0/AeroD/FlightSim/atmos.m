function [rho, a] = atmos(x_E)
    %% --------------------------------------------------------------------
    % atmos(x_E)
    % Returns density and pressure at altitude x_E
    % Arguments:
    % - x_E: [1 1] inertial x position, Earth axes
    % Returns:
    % - rho: [1 1] air density
    % - a: [1 1] speed of sound
    %% --------------------------------------------------------------------
    
    rho = .002378;
    a = 1125;


end