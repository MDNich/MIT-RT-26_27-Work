function [xdot] = sixdof(x, m, I, F_aero, F_prop, F_grav, M_aero, M_prop)
    %% --------------------------------------------------------------------
    % sixdof(x, m, I, F_aero, F_prop, F_grav, M_aero, M_prop)
    % ---------------------------------------------------------------------
    % Returns the derivative of the state vector acted upon by aerodynamic,
    % propulsive, and gravitational forces and moments. Assumes a 
    % flat-Earth inertial frame.
    % ---------------------------------------------------------------------
    % Arguments
    % - x: [12 1] [r; V; Theta; omega] state vector
    % --- r = [xE; yE; zE] (inertial position, Earth axes)
    % --- V = [u; v; w] (inertial velocity, body axes)
    % --- Theta = [phi; theta; psi] (3-2-1 Euler angles)
    % --- omega_B = [p; q; r] (angular velocity of body frame with respect 
    %        to inertial frame about body axes)
    % - m: [1 1] mass
    % - I: [3 3] inertia tensor about CG, body axes
    % - F_aero: [3 1] [Fx; Fy; Fz] aerodynamic force, body axes
    % - F_prop: [3 1] [Fx; Fy; Fz] propulsive force, body axes
    % - F_grav: [3 1] [Fx; Fy; Fz] gravitational force, Earth axes
    % - M_aero: [3 1] [Mx; My; Mz] aerodynamic moment about CG, body axes
    % - M_prop: [3 1] [Mx; My; Mz] propulsive moment about CG, body axes
    % ---------------------------------------------------------------------
    % Returns
    % - xdot [12 1] derivative of state vector
    %% --------------------------------------------------------------------

    % Extract state variables
    V = x(4:6);
    Theta = x(7:9);
    phi = Theta(1); theta = Theta(2); psi = Theta(3);
    omega = x(10:12);
    
    % Rotation matrices
    R1_phi   = [1           0          0;
                0           cos(phi)   sin(phi);
                0           -sin(phi)  cos(phi)];

    R2_theta = [cos(theta)  0          -sin(theta);
                0           1          0;
                sin(theta)  0          cos(theta)];

    R3_psi   = [cos(psi)    sin(psi)   0;
                -sin(psi)   cos(psi)   0;
                0           0          1];

    H_Theta = [1  sin(phi)*tan(theta)  cos(phi)*tan(theta);
               0  cos(phi)             -sin(phi);
               0  sin(phi)/cos(theta)  cos(phi)/cos(theta)];
        
    C_BE = R1_phi * R2_theta * R3_psi; % Earth axes to body axes
    C_EB = C_BE';                      % Body axes to Earth axes

    % Sum forces and moments in body axes
    F = F_aero + F_prop + C_BE*F_grav;
    M = M_aero + M_prop;

    % Compute derivatives
    rdot = C_EB * V;
    
    Vdot = F / m + cross(V, omega);

    Thetadot = H_Theta*omega;
    
    omegadot = I \ (M + cross(I*omega, omega));
    
    xdot = [rdot; Vdot; Thetadot; omegadot];

end