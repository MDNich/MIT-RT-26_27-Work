%% Simple Rocket Launch v1 %%
clear; close all;

%--------------------------------------------------------------------------
%%% Initialize objects %%%

rt = simple_rocket();
ctrl = simple_controller();

%%% End Initialize objects %%%
%--------------------------------------------------------------------------
%%% Wind %%%

wind_v = @(x, t) [0; 0; 0];

%%% End Wind %%%
%--------------------------------------------------------------------------
%%% Run Sim %%%

%%% TMP PATCHES %%%

kappa = 0;
atmos = @(x_E) [.002378, 1125];



%%% End TMP PATCHES %%%



    %% --------------------------------------------------------------------
    % simrocket(rocket, controller, wind_v, x0, xdot0, delta0, dt, ...
    % tmax, t0)
    % ---------------------------------------------------------------------
    % Simulates rocket flight and returns history of all relevant 
    % quantities.
    % ---------------------------------------------------------------------
    % Arguments
    % - rocket: [struct] rocket object
    % - controller: [struct] controller object
    % - wind_v: [func] wind velocity function
    % - x0: [12 1] initial state. Default x0 = zeros(12, 1)
    % - xdot0: [12 1] initial state derivative. Default xdot0 = zeros(12,
    %      1)
    % - delta0: [3 1] initial control state. Default delta0 = zeros(3, 1)
    % - dt: [1 1] time step in seconds. Default dt = 0.01 sec
    % - tmax: [1 1] final time in seconds. Default tmax = 10.0 sec.
    % - t0: [1 1] initial time in seconds; time vector begins at t0.
    %      Default t0 = 0
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
    % arguments
        rocket = rt;
        controller = ctrl;
    %     wind_v
        x0 = zeros([12 1]);
        xdot0 = zeros([12 1]);
        delta0 = zeros([3 1]);
        dt = .01;
        tmax = 15;
        t0 = 0;
    % end
    
    %% Get sensors
    imu = rocket.imu;
    servos = rocket.servos;

    %% Preallocate simulation log
    k = 1;
    N = round((tmax - t0)/dt);

    slog = struct();
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
    while x(1) >= -5 && k<=N 
        %% Read sensors
        omegahat = imu.calc_omega(x, xdot);
        Vdothat = imu.calc_vdot(x, xdot);

        %% Control
        [deltastar] = controller.calc_deltastar(omegahat, Vdothat);

        delta = servos.calc_delta(delta, deltastar, kappa);

        %% Update external variables
        m = rocket.calc_mass(t);
        I = rocket.calc_inertia(t);

        Vwind = wind_v(x, t);
        
        [F_aero, M_aero, alpha] = aero_fm(x, t, delta, Vwind, rocket);
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

    % Trim Data

    n = k - 1;                    % Last valid index
fields = fieldnames(slog);

for i = 1:numel(fields)
    f = fields{i};
    tmp = slog.(f);

    if isnumeric(tmp)
        switch ndims(tmp)
            case 2
                if size(tmp,2) == N      % Time is second dimension
                    tmp(:,n+1:end) = [];
                elseif size(tmp,1) == N  % Time is first dimension
                    tmp(n+1:end,:) = [];
                end

            case 3
                if size(tmp,3) == N      % Time is third dimension
                    tmp(:,:,n+1:end) = [];
                end
        end

    elseif isstruct(tmp)
        tmp(n+1:end) = [];
    end

    slog.(f) = tmp;
end

%%% End Run sim %%%
%--------------------------------------------------------------------------
%% 
%%% Analysis %%%

t = slog.t;

xE = slog.xE;
yE = slog.yE;
zE = slog.zE;
u = slog.u;
v = slog.v;
w = slog.w;
phi = slog.phi;
theta = slog.theta;
psi = slog.psi;
p = slog.p;
q = slog.q;
r = slog.r;

uE = slog.uE;
vE = slog.vE;
wE = slog.wE;
ax = slog.ax;
ay = slog.ay;
az = slog.az;
phidot = slog.phidot;
thetadot = slog.thetadot;
psidot = slog.psidot;
pdot = slog.pdot;
qdot = slog.qdot;
rdot = slog.rdot;


% r
figure
subplot(4, 1, 1)
plot(t, xE);
title('xE, u, uE, ax')
subplot(4, 1, 2)
plot(t, u);
subplot(4, 1, 3)
plot(t, uE)
subplot(4, 1, 4)
plot(t, ax)



figure
subplot(3, 1, 1)
plot(t, phi);
title('phi, theta, psi')
subplot(3, 1, 2)
plot(t, theta);
subplot(3, 1, 3)
plot(t, psi)

figure
subplot(3, 1, 1)
plot(t, p);
title('p, q, r')
subplot(3, 1, 2)
plot(t, q);
subplot(3, 1, 3)
plot(t, r)

figure
subplot(3, 1, 1)
plot(t, slog.F_grav(1, :));
title('FgravX, FgravY, FgravZ')
subplot(3, 1, 2)
plot(t, slog.F_grav(2, :));
subplot(3, 1, 3)
plot(t, slog.F_grav(3, :));

figure
subplot(3, 1, 1)
plot(t, slog.F_aero(1, :));
title('FaeroX, FaeroY, FaeroZ')
subplot(3, 1, 2)
plot(t, slog.F_aero(2, :));
subplot(3, 1, 3)
plot(t, slog.F_aero(3, :));

figure
subplot(3, 1, 1)
plot(t, slog.M_aero(1, :));
title('MaeroX, MaeroY, MaeroZ')
subplot(3, 1, 2)
plot(t, slog.M_aero(2, :));
subplot(3, 1, 3)
plot(t, slog.M_aero(3, :));