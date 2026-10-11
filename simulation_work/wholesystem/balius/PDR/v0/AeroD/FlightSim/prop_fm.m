function [F_prop, M_prop] = prop_fm(x, t, rocket)
    %% --------------------------------------------------------------------
    % prop_fm(x, t, rocket)
    % Returns net propulsive force and moment
    % in body axes.
    % Arguments:
    % - x: [12 1] [r; V; Theta; omega] state vector
    % --- r = [x_E; y_E; z_E] (inertial position, Earth axes)
    % --- V = [u; v; w] (inertial velocity, body axes)
    % --- Theta = [phi; theta; psi] (3-2-1 Euler angles)
    % --- omega_B = [p; q; r] (angular velocity of body frame 
    %        with respect to inertial frame about body axes)
    % - t: [1 1] time
    % - rocket: [struct] rocket object
    % Returns:
    % - F_prop: [3 1] [Fx; Fy; Fz] propulsive force, body axes
    % - M_prop: [3 1] [Mx; My; Mz] propulsive moment about CG, body axes
    %% --------------------------------------------------------------------

    % Calculate thrust using rocket object's defined curve
    F_prop = zeros([3 1]);
    F_prop(1) = rocket.calc_thrust(x, t);
    M_prop = zeros([3 1]);

end