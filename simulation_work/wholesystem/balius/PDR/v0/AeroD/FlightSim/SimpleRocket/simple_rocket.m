%% SimpleRocket %%
% Create simple rocket object

function [rt] = simple_rocket()
    rt = Rocket();
    
    %----------------------------------------------------------------------
    %%% Reference quantities %%%
    
    % 4 in diameter
    rt.cref = 4/12; % [ft]
    rt.Sref = pi * rt.cref^2/4; % [ft^2]
    
    % Earth params
    rt.g0 = 32.174; % [ft/s^2]
    rt.R0 = 3950 * 5280; % [ft]
    
    %%% End reference quantities %%%
    %----------------------------------------------------------------------
    %%% External hardware %%%
    
    rt.servos = simple_servos();
    
    rt.imu = simple_imu();
    
    %%% End External hardware %%%
    %----------------------------------------------------------------------
    %%% Function assignments %%%
    
    rt.calc_mass = @calc_mass;
    rt.calc_inertia = @calc_inertia;
    rt.calc_cg = @calc_cg;
    rt.calc_thrust = @calc_thrust;
    rt.calc_aero = @calc_aero;
    
    %----------------------------------------------------------------------
    %%% calc_mass %%%
    
    function [m] = calc_mass(t)
        if t <= 1.35
            m = 16.333 - (16.333 - 14.25)*(t - 1.35);
        else
            m = 14.25;
        end
        m = m/32.174;
    end
    
    %%% End calc_mass %%%
    %----------------------------------------------------------------------
    %%% calc_inertia %%%
    
    function [I] = calc_inertia(t)
        I = [.33 0 0;  ...
             0  32.36 0;  ...
             0   0  32.36] / 32.174;
    end
    
    %%% End calc_mass %%%
    %----------------------------------------------------------------------
    %%% calc_cg %%%
    
    function [x_cg] = calc_cg(t)
        if t <= 1.35
            x = 43.68 - (43.68 - 42.71)*(1.35 - t);
        else
            x = 42.71;
        end
        x_cg = [x; 0; 0];
    end
    
    %%% End calc_cg %%%
    %----------------------------------------------------------------------
    %%% calc_thrust %%%
    
    function [thrust] = calc_thrust(x, t)
        if t <= 1.35
            thrust = 123;
        else
            thrust = 0;
        end
    end
    
    %%% end calc_thrust %%%
    %----------------------------------------------------------------------
    %%% calc_aero %%%
    
    function [CX, CY, CZ, Cl, Cm, Cn] = calc_aero(alpha, beta, ...
        p, q, r, del_a, del_e, del_r, mach)
    
        %     [CL0; CY0; CD0; Cl0; Cm0; Cn0]
        C0 =  [0; 0; 0.45; 0; 0; 0];
        %     [dCL; dCY; dCD; dCl; dCm; dCn]
        Ca  = [5.388451; 0; 0; 0; -50.090984; 0];
        Cb  = [0; -5.388451; 0; 0; 0; -50.090984];
        Cp  = [0; 0; 0; -9.58166; 0; 0];
        Cq  = [104.91683; 0; 0; 0; -1411.69988; 0];
        Cr  = [0; 104.91683; 0; 0; 0; -1411.69988];
        Cda = [0; 0; 0; 1.251757; 0; 0];
        Cde = [-0.888334; 0; 0; 0; 13.040395; 0];
        Cdr = [0; -0.888334; 0; 0; 0; 13.040395];
    
        Cwind = C0 + [Ca, Cb, Cp, Cq, Cr, Cda, Cde, Cdr] ...
            * [alpha; beta; p; q; r; del_a; del_e; del_r];
        CL = Cwind(1); CY = Cwind(2); CD = Cwind(3); 
        Cl = Cwind(4); Cm = Cwind(5); Cn = Cwind(6);
    
        CX = -CD*cos(alpha)*cos(beta) - CL*sin(alpha);
        CZ = -CL*cos(alpha) + CD*sin(alpha);
    
    end
    
    %%% End calc_aero %%%
end