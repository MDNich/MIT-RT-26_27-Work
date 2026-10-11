function [F_grav] = grav_fm(x, m, rocket)
    %% --------------------------------------------------------------------
    % grav_fm(x, t, rocket)
    % Returns net gravitational force and moment
    % in Earth axes.
    % Arguments:
    % - x: [12 1] [r; V; Theta; omega] state vector
    % --- r = [x_E; y_E; z_E] (inertial position, Earth axes)
    % --- V = [u; v; w] (inertial velocity, body axes)
    % --- Theta = [phi; theta; psi] (3-2-1 Euler angles)
    % --- omega_B = [p; q; r] (angular velocity of body frame 
    %        with respect to inertial frame about body axes)
    % - m: [1 1] mass
    % - rocket: [Rocket] rocket object
    % Returns:
    % - : [3 1] [Fx; Fy; Fz] gravitational force, Earth axes
    %% --------------------------------------------------------------------
    
    % Extract parameters
    g0 = rocket.g0; % gravitational acceleration at launch altitude
    R0 = rocket.R0; % radius of Earth at launch altitude

    xE = x(1);

    % Compute gravitational force

    g = g0 * (R0 / (R0 + xE));

    F_grav = [-m*g; 0; 0];

end