function [slog] = simrocket(rocket, controller, options)
    %% --------------------------------------------------------------------
    % simrocket(rocket, controller, options)
    % ---------------------------------------------------------------------
    % Simulates rocket flight and returns history of all relevant 
    % quantities.
    % ---------------------------------------------------------------------
    % Arguments
    % - rocket: [struct] rocket object
    % - controller: [struct] controller object
    % - options.wind_v: [func] wind velocity function
    % - options.x0: [12 1] initial state. Default x0 = zeros(12, 1)
    % - options.xdot0: [12 1] initial state derivative. Default xdot0 =
    %      zeros(12, 1)
    % - options.delta0: [3 1] initial control state. Default delta0 =
    %      zeros(3, 1)
    % - options.dt: [1 1] time step in seconds. Default dt = 0.01 sec
    % - options.tmax: [1 1] final time in seconds. Default tmax = 10.0 sec.
    % - options.t0: [1 1] initial time in seconds; time vector begins at 
    %      t0. Default t0 = 0
    % ---------------------------------------------------------------------
    % Returns
    % - slog: [struct] simulation log. Fields:
    % --- .t: [1 N] time vector
    % --- .x: [12 N] state vector history
    % --- .delta: [3 N] control vector history
    % --- .xdot: [12 N] state derivative history
    % --- .m: [1 N] mass history
    % --- .I: [3 3 N] inertia history
    % --- .Vwind: [3 N] wind velocity history
    % --- .F_aero [3 N] aerodynamic force history
    % --- .M_aero [3 N] aerodynamic moment history
    % --- .F_prop [3 N] propulsive force history
    % --- .M_prop [3 N] propulsive moment history
    % --- .F_grav [3 N] gravitational force history
    %% ----------------------------------------------

    %% Arguments block
    arguments
        rocket
        controller
        options.wind_v = @(x, t) [0; 0; 0];
        options.x0 = zeros([12 1])
        options.xdot0 = zeros([12 1])
        options.delta0 = zeros([3 1])
        options.dt = .01
        options.tmax = 10
        options.t0 = 0
    end

    %% Extract options
    wind_v = options.wind_v;
    x0 = options.x0;
    xdot0 = options.xdot0;
    delta0 = options.delta0;
    dt = options.dt;
    tmax = options.tmax;
    t0 = options.t0;
    
    %% Get sensors
    imu = rocket.imu;
    servos = rocket.servos;

    %% Preallocate simulation log
    k = 1;
    N = round((tmax - t0)/dt);

    slog = struct();
    slog.k = zeros(1, N);
    slog.t = zeros(1, N);
    slog.x = zeros(12, N);
    slog.delta = zeros(3, N);
    slog.xdot = zeros(12, N);
    slog.m = zeros(1, N);
    slog.I = zeros(3, 3, N);
    slog.Vwind = zeros(3, N);
    slog.F_aero = zeros(3, N);
    slog.M_aero = zeros(3, N);
    slog.F_prop = zeros(3, N);
    slog.M_prop = zeros(3, N);
    slog.F_grav = zeros(3, N);
    slog.imu_omegahat = zeros(3, N);
    slog.imu_Vdothat = zeros(3, N);
    
    controller.initialize_log(controller, N);


    %% Initialize simulation
    t = t0;
    x = x0;
    xdot = xdot0;
    delta = delta0;
    
    %% Simulation loop
    while  xdot(1) >= 0 && k <= N
        %% Read sensors
        omegahat = imu.calc_omega(x, xdot);
        Vdothat = imu.calc_vdot(x, xdot);

        %% Control
        [deltastar] = controller.calc_deltastar(omegahat, Vdothat);

        delta = servos.calc_delta(delta, deltastar);

        %% Update external variables
        m = rocket.calc_mass(t);
        I = rocket.calc_inertia(t);

        Vwind = wind_v(x, t);
        
        [F_aero, M_aero] = aero_fm(x, t, delta, Vwind, rocket);
        [F_prop, M_prop] = prop_fm(x, t, rocket);
        [F_grav] = grav_fm(x, m, rocket);
        
        xdot = sixdof(x, m, I, F_aero, F_prop, F_grav, M_aero, M_prop);
        
    
        %% Log data from timestep k
        slog.t(k) = t;
        slog.x(:, k) = x;
        slog.delta(:, k) = delta;
        slog.xdot(:, k) = xdot;
        slog.m(k) = m;
        slog.I(:, :, k) = I;
        slog.Vwind(:, k) = Vwind;
        slog.F_aero(:, k) = F_aero;
        slog.M_aero(:, k) = M_aero;
        slog.F_prop(:, k) = F_prop;
        slog.M_prop(:, k) = M_prop;
        slog.F_grav(:, k) = F_grav;
        slog.imu_omegahat(:, k) = omegahat;
        slog.imu_Vdothat(:, k) = Vdothat;
        
        controller.log_data(controller, k)
        
        
        %% Update state
        x = x + xdot*dt;
        t = t + dt;
        k = k + 1;
    
    end

    slog.clog = controller.clog;

    slog.xE    = slog.x(1, :);
    slog.yE    = slog.x(2, :);
    slog.zE    = slog.x(3, :);
    slog.u     = slog.x(4, :);
    slog.v     = slog.x(5, :);
    slog.w     = slog.x(6, :);
    slog.phi   = slog.x(7, :);
    slog.theta = slog.x(8, :);
    slog.psi   = slog.x(9, :);
    slog.p     = slog.x(10, :);
    slog.q     = slog.x(11, :);
    slog.r     = slog.x(12, :);

    slog.uE       = slog.xdot(1, :);
    slog.vE       = slog.xdot(2, :);
    slog.wE       = slog.xdot(3, :);
    slog.ax       = slog.xdot(4, :);
    slog.ay       = slog.xdot(5, :);
    slog.az       = slog.xdot(6, :);
    slog.phidot   = slog.xdot(7, :);
    slog.thetadot = slog.xdot(8, :);
    slog.psidot   = slog.xdot(9, :);
    slog.pdot     = slog.xdot(10, :);
    slog.qdot     = slog.xdot(11, :);
    slog.rdot     = slog.xdot(12, :);

    %% Trim Data
    
    n = k - 1;                   
    fields = fieldnames(slog);

    for idx = 1:numel(fields)
        f = fields{idx};
        tmp = slog.(f);

        if isnumeric(tmp)
            switch ndims(tmp)
                case 2
                    if size(tmp,2) == N 
                        tmp(:,n+1:end) = [];
                    elseif size(tmp,1) == N 
                        tmp(n+1:end,:) = [];
                    end
                case 3
                    if size(tmp,3) == N   
                        tmp(:,:,n+1:end) = [];
                    end
            end
        elseif isstruct(tmp)
            tmp(n+1:end) = [];
        end
        slog.(f) = tmp;

    end

end