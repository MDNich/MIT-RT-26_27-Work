function [F_aero, M_aero, alpha] = aero_fm(x, t, delta, Vwind, rocket)
    %% --------------------------------------------------------------------
    % aero_fm(x, t, delta, Vwind, rocket)
    % Returns net aerodynamic force and moment
    % in body axes.
    % Arguments:
    % - x: [12 1] [r; V; Theta; omega] state vector
    % --- r = [x_E; y_E; z_E] (inertial position, Earth axes)
    % --- V = [u; v; w] (inertial velocity, body axes)
    % --- Theta = [phi; theta; psi] (3-2-1 Euler angles)
    % --- omega_B = [p; q; r] (angular velocity of body frame 
    %        with respect to inertial frame about body axes)
    % - t: [1 1] time
    % - delta: [3 1] [del_a, del_e, del_r] control vector
    % - Vwind: [3 1] [uw_E; vw_E; ww_E] inertial wind velocity in body axes
    % - rocket: [struct] rocket object
    % Returns:
    % - F_aero: [3 1] [Fx; Fy; Fz] aerodynamic force, body axes
    % - M_aero: [3 1] [Mx; My; Mz] moment, body axes
    % - HIIIIIIi
    %% --------------------------------------------------------------------
  
    % Get reference quantities
    Sref = rocket.Sref;
    cref = rocket.cref;

    % Extract state variables and derive quantities
    x_E = x(1);

    u = x(4) + Vwind(1); 
    v = x(5) + Vwind(2); 
    w = x(6) + Vwind(3);
    p = x(10); q = x(11); r = x(12);
    del_a = delta(1); del_e = delta(2); del_r = delta(3);

    V = sqrt(u^2 + v^2 + w^2);

    [rho, a] = atmos(x_E);

    Q = 0.5 * rho * V^2;
    mach = V / a;
    
    if abs(V) > 1e-3
        alpha = atan2(w, u);
        beta = asin(v/V);
        
        pbar = p*cref/2/V;
        qbar = q*cref/2/V;
        rbar = r*cref/2/V;
        % Get aero coefficients
        [CX, CY, CZ, ClO, CmO, CnO] = rocket.calc_aero(alpha, beta, ...
            pbar, qbar, rbar, del_a, del_e, del_r, mach);
    else
        alpha = 0;
        beta = 0;
        CX = 0; CY = 0; CZ = 0; ClO = 0; CmO = 0; CnO = 0;
    end

    % Convert moments to be about CG
    x_CG = rocket.calc_cg(t);

    CM = [ClO; CmO; CnO] - cross(x_CG/cref, [CX; CY; CZ]);
    
    Cl = CM(1);
    Cm = CM(2);
    Cn = CM(3);

    % Compute forces and moments
    Fx = CX * Q * Sref;
    Fy = CY * Q * Sref;
    Fz = CZ * Q * Sref;

    Mx = Cl * Q * Sref * cref;
    My = Cm * Q * Sref * cref;
    Mz = Cn * Q * Sref * cref;

    F_aero = [Fx; Fy; Fz];
    M_aero = [Mx; My; Mz];
 
end