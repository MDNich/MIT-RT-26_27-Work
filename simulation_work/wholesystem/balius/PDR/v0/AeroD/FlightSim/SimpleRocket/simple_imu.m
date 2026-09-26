%% SimpleIMU %%
% Create simple IMU object

function [imu] = simple_imu()
    imu = IMU();

    %----------------------------------------------------------------------
    %%% Function assignments %%%

    imu.calc_vdot = @calc_vdot;
    imu.calc_omega = @calc_omega;

    %----------------------------------------------------------------------
    %%% calc_vdot %%%
    
    function [Vdothat] = calc_vdot(x, xdot)
        Vdothat = xdot(4:6);
    end

    %%% End calc_vdot %%%
    %----------------------------------------------------------------------
    %%% calc_omega %%%

    function [omegahat] = calc_omega(x, xdot)
        omegahat = x(10:12);
    end

    %%% End calc_omega %%%

end