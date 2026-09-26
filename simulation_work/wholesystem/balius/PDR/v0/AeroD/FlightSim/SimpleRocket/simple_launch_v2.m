%% Simple Rocket Launch v1 %%
clear; close all;

%--------------------------------------------------------------------------
%%% Initialize objects %%%

rt = simple_rocket();
ctrl = simple_controller();

%%% End Initialize objects %%%
%--------------------------------------------------------------------------
%%% Wind %%%

wind_v = @(x, t) [0; 3*sin(t); 3*cos(t)];

%%% End Wind %%%
%--------------------------------------------------------------------------
%%% Run sim %%%

slog = simrocket(rt, ctrl, wind_v=wind_v);


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

V = sqrt(u.^2 + v.^2 + w.^2);
alpha = zeros(size(V));
beta = zeros(size(V));
alphaT = zeros(size(V));

for idx = 1:length(V)
    if abs(V(idx)) > 1e-3
        alpha(idx) = atan2(w(idx), u(idx));
        beta(idx) = asin(v(idx)/V(idx));
        alphaT(idx) = acos(u(idx)/V(idx));
    else
        alpha(idx) = 0;
        beta(idx) = 0;
    end
end

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
plot(t, u);
title('u, v, w')
subplot(3, 1, 2)
plot(t, v);
subplot(3, 1, 3)
plot(t, w)

figure
subplot(3, 1, 1)
plot(t, alpha);
title('\alpha, \beta, \alpha_T [deg]')
subplot(3, 1, 2)
plot(t, beta);
subplot(3, 1, 3)
plot(t, alphaT)

figure
subplot(3, 1, 1)
plot(t, phi*180/pi);
title('phi, theta, psi [deg]')
subplot(3, 1, 2)
plot(t, theta*180/pi);
subplot(3, 1, 3)
plot(t, psi*180/pi)

figure
subplot(3, 1, 1)
plot(t, p*180/pi);
title('p, q, r [deg/s]')
subplot(3, 1, 2)
plot(t, q*180/pi);
subplot(3, 1, 3)
plot(t, r*180/pi)

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
plot(t, slog.m(1, :));
title('m, Ixx, Irr')
subplot(3, 1, 2)
plot(t, squeeze(slog.I(1, 1, :)));
subplot(3, 1, 3)
plot(t, squeeze(slog.I(2, 2, :)));


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